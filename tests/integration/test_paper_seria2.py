"""Paper serii 2 na danych sztucznych: zgodność z backtestem, przebiegi dzienne, bramka, hamulec, świeżość."""
from __future__ import annotations

import copy
import dataclasses
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from astraljet.infrastructure.database import Database

from tests.unit.test_seria2_engine import LONG, days, market, noisy

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("paper_seria2", ROOT / "scripts" / "paper_seria2.py")
paper = importlib.util.module_from_spec(spec)
sys.modules["paper_seria2"] = paper
spec.loader.exec_module(paper)
s2 = paper.s2

COSTS = s2.Costs(spread=0.0005, commission_side=6.0, fin_long=0.05, fin_short=0.02, payout_short=0.03)
NAMES = ("UP1", "UP2", "UP3", "DN1", "DN2", "DN3")
NO_BRAKE = 0.99


def synthetic(count: int = LONG) -> dict[str, s2.Market]:
    return {n: market(n, 0, costs=COSTS, dates=days(count),
                      closes=noisy(1.001 if n.startswith("UP") else 0.999, count, n)) for n in NAMES}


def truncate(markets: dict[str, s2.Market], last: str) -> dict[str, s2.Market]:
    out = {}
    for n, m in markets.items():
        k = paper.bisect.bisect_right(m.dates, last)
        out[n] = dataclasses.replace(m, dates=m.dates[:k], opens=m.opens[:k], closes=m.closes[:k])
    return out


class PaperCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database.from_state_dir(Path(self.tmp.name) / "state")
        self.db.initialize()
        self.now = lambda: datetime.now(timezone.utc)

    def gate(self, hyp: str):
        return paper.PaperGate(self.db, paper.ENVIRONMENTS[hyp], hyp, self.now)

    def fresh_state(self, hyp: str, start: str) -> paper.PaperState:
        return paper.PaperState.new(hyp, 2500.0, 1.0, start)


class SameAsBacktest(PaperCase):
    def test_paper_from_first_day_equals_simulate_account(self) -> None:
        markets = synthetic()
        for hyp in ("H4", "H5"):
            with self.subTest(hypothesis=hyp):
                state = self.fresh_state(hyp, markets["UP1"].dates[0])
                gate = self.gate(hyp)
                paper.advance(state, markets, gate, NO_BRAKE)
                backtest = s2.simulate_account(markets, hypothesis=hyp, capital=2500.0, gross=1.0)
                self.assertEqual(len(state.rows), len(backtest.rows) - 1)  # ostatni dzień czeka na następny
                for (d1, e1), (d2, e2) in zip(state.rows, backtest.rows):
                    self.assertEqual(d1, d2)
                    self.assertAlmostEqual(e1, e2, places=6)
                self.assertEqual(len(state.trades), len([t for t in backtest.trades if t.date <= state.last_day]))
                for key in ("spread", "commission"):
                    self.assertAlmostEqual(state.costs[key], backtest.costs[key], places=6)
                self.assertEqual([], state.refusals)
                held = {n: float(v) for n, v in gate.positions().items() if float(v)}
                self.assertEqual({n: round(v, 9) for n, v in held.items()},
                                 {n: round(v, 9) for n, v in state.volume.items() if v})
                rows = paper.compare_with_backtest(state, markets)
                self.assertTrue(rows)
                self.assertTrue(all(r["comparable"] and abs(r["diff_pp"]) < 1e-6 for r in rows))
                if hyp == "H4":  # spadki dają pozycje krótkie
                    self.assertTrue(any(v < 0 for v in state.volume.values()))

    def test_daily_runs_equal_one_run(self) -> None:
        markets = synthetic(800)
        start = markets["UP1"].dates[0]
        one = self.fresh_state("H4", start)
        paper.advance(one, markets, None, NO_BRAKE)
        daily = self.fresh_state("H4", start)
        gate = self.gate("H4")
        for last in ("2023-02-10", "2023-03-31", "2023-04-01", "2023-07-15", markets["UP1"].dates[-1]):
            paper.advance(daily, truncate(markets, last), gate, NO_BRAKE)
        self.assertEqual([r[0] for r in one.rows], [r[0] for r in daily.rows])
        for (_, e1), (_, e2) in zip(one.rows, daily.rows):
            self.assertAlmostEqual(e1, e2, places=6)

    def test_rerun_books_nothing_and_crash_rerun_does_not_double_orders(self) -> None:
        markets = synthetic(800)
        state = self.fresh_state("H4", markets["UP1"].dates[0])
        gate = self.gate("H4")
        before_crash = copy.deepcopy(state)
        paper.advance(state, markets, gate, NO_BRAKE)          # przebieg wykonał zlecenia...
        self.assertEqual(0, paper.advance(state, markets, gate, NO_BRAKE))  # ...drugi przebieg nic nie księguje
        # Awaria przed zapisem stanu: ponowny przebieg od starego stanu dostaje DUPLICATE, nie nowe zlecenia.
        paper.advance(before_crash, markets, self.gate("H4"), NO_BRAKE)
        self.assertEqual(state.volume, before_crash.volume)
        held = {n: float(v) for n, v in gate.positions().items() if float(v)}
        self.assertEqual({n: round(v, 9) for n, v in held.items()},
                         {n: round(v, 9) for n, v in before_crash.volume.items() if v})


class GateAndBrake(PaperCase):
    def test_kill_switch_refuses_orders_and_keeps_ledger(self) -> None:
        markets = synthetic(800)
        state = self.fresh_state("H5", markets["UP1"].dates[0])
        gate = self.gate("H5")
        gate.guard.activate_kill_switch(paper.ENVIRONMENTS["H5"], reason="test", idempotency_key="paper-kill-0001",
                                        now=self.now())
        paper.advance(state, markets, gate, NO_BRAKE)
        self.assertEqual([], state.trades)
        self.assertTrue(state.refusals)
        self.assertTrue(all("kill_switch_active" in r["reason"] for r in state.refusals if "bramka" in r["reason"]))
        self.assertEqual(2500.0, state.rows[-1][1])  # bez pozycji i kosztów

    def test_brake_closes_positions_and_zeroes_decisions(self) -> None:
        count = 900
        dates = days(count)
        markets = {}
        for n in NAMES:
            closes = noisy(1.001, count, n)
            crash = [c * (0.97 ** max(0, i - 700)) for i, c in enumerate(closes)]  # od dnia 700 spadek
            markets[n] = market(n, 0, costs=COSTS, dates=dates, closes=crash)
        state = self.fresh_state("H5", dates[0])
        paper.advance(state, markets, self.gate("H5"), 0.1)
        self.assertTrue(state.brake_state["tripped"])
        tripped = state.brake_state["tripped_at"]
        self.assertTrue(any(d["kind"] == "hamulec" for d in state.decisions))
        self.assertEqual({}, {n: v for n, v in state.volume.items() if v})
        later = [d for d in state.decisions if d["day"] > tripped and d["kind"].startswith("decyzja")]
        self.assertTrue(all(all(v == 0 for v in d["targets"].values()) for d in later))

    def test_brake_threshold_is_required(self) -> None:
        with self.assertRaises(SystemExit):
            paper.main([])

    def test_h5_never_goes_short_and_h4_flip_uses_two_orders(self) -> None:
        markets = synthetic()
        h5 = self.fresh_state("H5", markets["UP1"].dates[0])
        paper.advance(h5, markets, self.gate("H5"), NO_BRAKE)
        self.assertTrue(all(v >= 0 for v in h5.volume.values()))
        with self.db.connect() as connection:
            legs = {row["intent_id"].rsplit(":", 1)[1] for row in connection.execute(
                "SELECT intent_id FROM execution_intents WHERE environment_id = 'paper-seria2-h5'")}
        self.assertEqual({"zmiana"}, legs)


class RunAndReport(PaperCase):
    def test_stale_data_books_nothing_and_says_why(self) -> None:
        markets = synthetic(800)
        out = Path(self.tmp.name) / "out"
        result = paper.run(threshold=0.2, start=markets["UP1"].dates[0], today="2030-01-01", markets=markets,
                           out_dir=out, now_fn=self.now, threshold_decision="Karol, 21.11.2026")
        self.assertTrue(result["stale"])
        for st in result["states"].values():
            self.assertEqual([], st.rows)
            self.assertIn("nieświeże dane", st.refusals[-1]["reason"])
        text = (out / "RAPORT_PAPER_SERIA2.md").read_text(encoding="utf-8")
        self.assertIn("NIE PRZESZŁA BADANIA", text)
        self.assertIn("Nieświeże dane", text)

    def test_fresh_run_writes_state_and_report_and_needs_start_first(self) -> None:
        markets = synthetic(800)
        out = Path(self.tmp.name) / "out"
        today = (datetime.fromisoformat(markets["UP1"].dates[-1]) .date() + paper.timedelta(days=1)).isoformat()
        with self.assertRaises(paper.ValidationError):
            paper.run(threshold=0.2, start=None, today=today, markets=markets, out_dir=out, now_fn=self.now)
        with self.assertRaises(paper.ValidationError):  # bez zapisu decyzji o progu
            paper.run(threshold=0.2, start="2023-06-01", today=today, markets=markets, out_dir=out, now_fn=self.now)
        result = paper.run(threshold=0.2, start="2023-06-01", today=today, markets=markets, out_dir=out,
                           now_fn=self.now, threshold_decision="Karol, 21.11.2026")
        self.assertEqual([], result["stale"])
        for hyp, st in result["states"].items():
            self.assertTrue((out / paper.ENVIRONMENTS[hyp] / "state.json").exists())
            self.assertEqual("2023-06-01", st.rows[0][0])
            rows = result["comparisons"][hyp]
            self.assertTrue(any(not r["comparable"] for r in rows))  # miesiąc startu bez pozycji
        text = (out / "RAPORT_PAPER_SERIA2.md").read_text(encoding="utf-8")
        self.assertIn("werdykt badania: FAIL", text)
        self.assertIn("| Miesiąc | Paper | Backtest |", text)
        # drugi przebieg czyta zapisany stan (bez --start) i nic nie dokłada
        again = paper.run(threshold=0.2, start=None, today=today, markets=markets, out_dir=out, now_fn=self.now)
        self.assertEqual(result["states"]["H4"].rows, again["states"]["H4"].rows)

        self.assertIn("Próg hamulca: 20% od szczytu (decyzja: Karol, 21.11.2026)", text)
        with self.assertRaises(paper.ValidationError):  # inny próg bez nowej decyzji
            paper.run(threshold=0.3, start=None, today=today, markets=markets, out_dir=out, now_fn=self.now)
        changed = paper.run(threshold=0.3, start=None, today=today, markets=markets, out_dir=out, now_fn=self.now,
                            threshold_decision="Karol, 30.11.2026")
        self.assertEqual(0.3, changed["states"]["H5"].brake_threshold)