"""Skrypt próby zleceń DEMO na atrapie terminala: pełny przebieg i zatrzymania."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from tests.integration.test_mt5_demo_adapter import RULE, FakeMT5

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("demo_order_probe", ROOT / "scripts" / "demo_order_probe.py")
probe = importlib.util.module_from_spec(spec)
import sys  # noqa: E402

sys.modules["demo_order_probe"] = probe
spec.loader.exec_module(probe)


class ProbeOnFake(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_full_probe_sends_exactly_two_orders(self) -> None:
        mt5 = FakeMT5()
        report = probe.run_probe(mt5, RULE, self.dir / "db", send=True)
        self.assertEqual(2, len(mt5.sends))
        self.assertEqual("buy", "buy" if mt5.sends[0]["type"] == mt5.ORDER_TYPE_BUY else "sell")
        self.assertIn("position", mt5.sends[1])
        self.assertEqual({}, mt5.positions)
        self.assertIsNone(report.open_ticket)
        text = "\n".join(report.lines)
        for step in ("1. wyłącznik awaryjny", "1. zlecenie ponad limit, próba 2", "3. ta sama intencja, nowy klucz",
                     "6. uzgodnienie", "7. uzgodnienie przerwanej intencji", "KONIEC"):
            self.assertIn(step, text)
        self.assertNotIn("81234567", text)
        out = self.dir / "r.md"
        probe.write_report(report, out, None, True)
        body = out.read_text(encoding="utf-8")
        self.assertNotIn("81234567", body)
        self.assertNotIn("Broker-Demo", body)

    def test_real_account_stops_before_any_order(self) -> None:
        mt5 = FakeMT5()
        mt5.account = NS(login=999, trade_mode=2, server="Broker-Live")
        with self.assertRaises(probe.ProbeStop):
            probe.run_probe(mt5, RULE, self.dir / "db")
        self.assertEqual([], mt5.sends)

    def test_algo_off_stops_before_any_order(self) -> None:
        mt5 = FakeMT5()
        mt5.terminal = NS(connected=True, trade_allowed=False)
        with self.assertRaises(probe.ProbeStop):
            probe.run_probe(mt5, RULE, self.dir / "db")
        self.assertEqual([], mt5.sends)

    def test_unexpected_open_result_stops_without_second_order(self) -> None:
        mt5 = FakeMT5()
        mt5.send_returns_none = True
        report = probe.Report()
        with self.assertRaises(probe.ProbeStop):
            probe.run_probe(mt5, RULE, self.dir / "db", send=True, report=report)
        self.assertEqual(1, len(mt5.sends))
        self.assertIn("2. kupno", "\n".join(report.lines))

    def test_rule_needs_local_demo_login_and_server(self) -> None:
        p = self.dir / "accounts.toml"
        p.write_text("demo_login = 81234567\n", encoding="utf-8")
        with self.assertRaises(probe.ProbeStop):
            probe.load_rule(p)
        p.write_text("demo_login = 81234567\ndemo_server = 'Broker-Demo'\n", encoding="utf-8")
        self.assertEqual(81234567, probe.load_rule(p).login)

    def test_unknown_terminal_path_is_refused(self) -> None:
        with self.assertRaises(probe.ProbeStop):
            probe.check_terminal(r"C:\inny\terminal64.exe")
        with self.assertRaises(probe.ProbeStop):
            probe.check_terminal(None)


class ProbeStartAndWindow(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "state"

    def test_without_flag_nothing_is_sent(self) -> None:
        mt5 = FakeMT5()
        report = probe.run_probe(mt5, RULE, self.db)
        self.assertEqual([], mt5.sends)
        self.assertIn("KONIEC (bez brokera)", "\n".join(report.lines))

    def test_kill_switch_from_previous_run_blocks_start(self) -> None:
        mt5 = FakeMT5()
        mt5.account = NS(login=999, trade_mode=2, server="Broker-Live")
        with self.assertRaises(probe.ProbeStop):
            probe.run_probe(mt5, RULE, self.db, send=True)
        self.assertTrue(mt5.closed)  # rozłączenie po wykryciu LIVE
        again = FakeMT5()  # poprawny rachunek DEMO, ale wyłącznik z poprzedniego uruchomienia trwa
        with self.assertRaises(probe.ProbeStop):
            probe.run_probe(again, RULE, self.db, send=True)
        self.assertEqual([], again.sends)

    def test_leftover_probe_position_blocks_start(self) -> None:
        mt5 = FakeMT5()
        mt5.positions[5] = NS(ticket=5, symbol="ETHUSD", type=0, volume=0.01, magic=probe.PROBE_MAGIC, price_current=3000.0)
        with self.assertRaises(probe.ProbeStop):
            probe.run_probe(mt5, RULE, self.db, send=True)
        self.assertEqual([], mt5.sends)

    def test_symbol_not_in_market_watch_blocks_start(self) -> None:
        mt5 = FakeMT5()
        mt5.symbol_info = lambda symbol: NS(visible=False, trade_contract_size=1.0, volume_step=0.01, volume_min=0.01,
                                            volume_max=100.0, filling_mode=2)
        with self.assertRaises(probe.ProbeStop):
            probe.run_probe(mt5, RULE, self.db, send=True)
        self.assertEqual([], mt5.sends)

    def test_collector_window(self) -> None:
        from datetime import datetime
        now = datetime(2026, 11, 21, 8, 50)
        self.assertTrue(probe.collector_problem(now, datetime(2026, 11, 21, 9, 0), "Ready"))
        self.assertTrue(probe.collector_problem(now, None, "Running"))
        self.assertIsNone(probe.collector_problem(now, datetime(2026, 11, 21, 9, 6), "Ready"))
        self.assertIsNone(probe.collector_problem(datetime(2026, 11, 21, 2, 30), datetime(2026, 11, 21, 9, 0), "Ready"))

class ProbeMarkerAndOutput(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_real_account_writes_persistent_marker(self) -> None:
        marker = self.dir / "STOP.txt"
        mt5 = FakeMT5()
        mt5.account = NS(login=999, trade_mode=2, server="Broker-Live")
        with self.assertRaises(probe.ProbeStop):
            probe.run_probe(mt5, RULE, self.dir / "state", send=True, live_marker=marker)
        self.assertTrue(marker.exists())
        self.assertNotIn("999", marker.read_text(encoding="utf-8"))

    def test_print_failure_does_not_stop_probe(self) -> None:
        import io
        import sys

        class Broken(io.StringIO):
            def write(self, s):
                raise UnicodeEncodeError("cp852", s, 0, 1, "test")

        saved, sys.stdout = sys.stdout, Broken()
        try:
            mt5 = FakeMT5()
            report = probe.run_probe(mt5, RULE, self.dir / "state", send=True)
        finally:
            sys.stdout = saved
        self.assertEqual(2, len(mt5.sends))
        self.assertIn("KONIEC", "\n".join(report.lines))

    def test_ticket_mismatch_stops_at_step_4(self) -> None:
        mt5 = FakeMT5()
        original = mt5.order_send

        def shifted(request):
            result = original(request)
            return NS(retcode=result.retcode, order=result.order + 500, deal=result.deal, price=result.price,
                      volume=result.volume)
        mt5.order_send = shifted
        report = probe.Report()
        with self.assertRaises(probe.ProbeStop):
            probe.run_probe(mt5, RULE, self.dir / "state", send=True, report=report)
        self.assertEqual(1, len(mt5.sends))
        self.assertIn("4. pozycja w terminalu", report.lines[-1])
        self.assertIsNotNone(report.open_ticket)

    def test_messages_have_no_characters_outside_cp852(self) -> None:
        text = (ROOT / "scripts" / "demo_order_probe.py").read_text(encoding="utf-8")
        code = text.split('"""', 2)[2]  # bez nagłówka
        for ch in set(code):
            ch.encode("cp852")


class FailureAfterSendIsReported(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def run_failing(self, mt5):
        report = probe.Report()
        with self.assertRaises(Exception):
            probe.run_probe(mt5, RULE, self.dir / "state", send=True, report=report)
        out = self.dir / "r.md"
        probe.write_report(report, out, "test", True)
        return report, out.read_text(encoding="utf-8")

    def test_algo_off_right_after_buy_send(self) -> None:
        mt5 = FakeMT5()
        original = mt5.order_send

        def send_then_algo_off(request):
            result = original(request)
            mt5.terminal = NS(connected=True, trade_allowed=False)
            return result
        mt5.order_send = send_then_algo_off
        report, body = self.run_failing(mt5)
        self.assertEqual(1, len(mt5.sends))
        self.assertEqual(1, len(mt5.positions))
        self.assertEqual(1, report.sent)
        self.assertIn("Wysłane zlecenia: 1.", body)
        ticket = next(iter(mt5.positions))
        self.assertEqual(ticket, report.open_ticket)
        self.assertIn(f"Numer zlecenia kupna: {ticket}", body)
        self.assertIn("może być otwarta pozycja", body)

    def test_no_result_for_buy(self) -> None:
        mt5 = FakeMT5()
        mt5.send_returns_none = True
        report, body = self.run_failing(mt5)
        self.assertEqual(1, report.sent)
        self.assertIn("Wysłane zlecenia: 1.", body)
        self.assertIn("brak w bazie próby", body)
        self.assertIn("może być otwarta pozycja", body)

    def test_partial_fill_is_named(self) -> None:
        mt5 = FakeMT5()
        original = mt5.order_send

        def partial(request):
            result = original(request)
            return NS(retcode=10010, order=result.order, deal=result.deal, price=result.price, volume=result.volume)
        mt5.order_send = partial
        report, body = self.run_failing(mt5)
        self.assertTrue(report.partial)
        self.assertIn("wykonane częściowo", body)

    def test_successful_run_has_no_warning(self) -> None:
        mt5 = FakeMT5()
        report = probe.run_probe(mt5, RULE, self.dir / "state", send=True)
        self.assertIsNone(report.warning)
        self.assertEqual(2, report.sent)
        self.assertTrue(report.closed)


class SingleInstanceAndHeader(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        saved = {k: getattr(probe, k) for k in ("PROBE_DIR", "STATE_DIR", "LIVE_MARKER", "RUN_LOCK")}
        self.addCleanup(lambda: [setattr(probe, k, v) for k, v in saved.items()])
        probe.PROBE_DIR = self.dir
        probe.STATE_DIR = self.dir / "state"
        probe.LIVE_MARKER = self.dir / "STOP.txt"
        probe.RUN_LOCK = self.dir / "PROBA_TRWA.lock"

    def reports(self):
        return [p.read_text(encoding="utf-8") for p in self.dir.glob("*/RAPORT_PROBY.md")]

    def test_second_lock_is_refused_until_release(self) -> None:
        probe.acquire_run_lock(probe.RUN_LOCK)
        with self.assertRaises(probe.ProbeStop):
            probe.acquire_run_lock(probe.RUN_LOCK)
        probe.release_run_lock(probe.RUN_LOCK)
        probe.acquire_run_lock(probe.RUN_LOCK)
        probe.release_run_lock(probe.RUN_LOCK)

    def test_main_refuses_while_other_run_holds_lock(self) -> None:
        probe.acquire_run_lock(probe.RUN_LOCK)  # „pierwszy przebieg” trwa
        self.assertEqual(1, probe.main(["--wyslij-na-demo"]))
        self.assertTrue(probe.RUN_LOCK.exists())  # cudzej blokady nie zdejmuje
        self.assertFalse(probe.STATE_DIR.exists())  # baza próby nie została otwarta
        (text,) = self.reports()
        self.assertIn("Trwa inny przebieg", text)
        self.assertIn("Wysłane zlecenia: 0.", text)
        self.assertIn("Rachunek: nie sprawdzono", text)

    def test_lock_is_released_after_early_stop(self) -> None:
        probe.LIVE_MARKER.write_text("x", encoding="utf-8")
        self.assertEqual(1, probe.main([]))
        self.assertFalse(probe.RUN_LOCK.exists())
        self.assertIn("rachunek inny niż DEMO", self.reports()[0])

    def test_header_mentions_account_only_after_step_0(self) -> None:
        report = probe.run_probe(FakeMT5(), RULE, self.dir / "state2")
        self.assertTrue(report.account_verified)
        out = self.dir / "ok.md"
        probe.write_report(report, out, None, False)
        self.assertIn("Rachunek: DEMO (numer i serwer sprawdzone", out.read_text(encoding="utf-8"))
