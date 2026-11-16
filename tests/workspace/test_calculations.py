"""Obliczenia planu, jednostki instrumentu, geometria wykresu, widgety."""

from __future__ import annotations

import unittest
from datetime import timedelta
from decimal import Decimal

from astraljet.workspace.instruments import (
    FxRate, FxTable, Side, eurusd_example, index_example, usdjpy_example, xauusd_example,
)
from astraljet.workspace.market import CandleSeries, DataMode, Freshness, Timeframe, assess_quote, synthetic_series
from astraljet.workspace.model import Position
from astraljet.workspace.plan import CostModel, OrderType, TradePlan, evaluate_plan
from astraljet.workspace.protection import TrailingRule
from astraljet.workspace.session import chart_range, price_to_y
from astraljet.workspace.widgets import candle_timer, indicators, macd, margin_usage, risk_to_sl, rsi

from .helpers import T0, quote

D = Decimal
USD = FxTable()


def plan(side=Side.BUY, entry="1.15438", sl="1.13949", tp="1.16505", volume="0.01", order_type=OrderType.LIMIT,
         symbol="EURUSD"):
    return TradePlan("SIM", symbol, side, D(volume), order_type, None if entry is None else D(entry),
                     None if sl is None else D(sl), None if tp is None else D(tp))


class AcceptanceNumbers(unittest.TestCase):
    """Konkretne testy odbioru ze zlecenia BB-36."""

    def test_hero_eurusd_points_money_and_rr(self):
        ev = evaluate_plan(plan(), eurusd_example(), "USD", USD)
        self.assertEqual(ev.tp_points, D(1067))
        self.assertEqual(ev.sl_points, D(1489))
        self.assertEqual(ev.reward_account, D("10.67"))
        self.assertEqual(ev.risk_account, D("14.89"))
        self.assertEqual(ev.reward_risk.quantize(D("0.0001")), D("0.7166"))
        self.assertEqual(ev.breakeven_win_rate.quantize(D("0.00001")), D("0.58255"))
        self.assertEqual(ev.tp_pips, D("106.7"))
        self.assertEqual(ev.sl_pips, D("148.9"))

    def test_widget_reward_risk_2_5109(self):
        ev = evaluate_plan(plan(entry="1.15350", sl="1.14890", tp="1.16505"), eurusd_example(), "USD", USD)
        self.assertEqual(ev.reward_risk.quantize(D("0.0001")), D("2.5109"))

    def test_trailing_candidate_plus_474_points(self):
        spec = eurusd_example()
        pos = Position("P1", "SIM", "EURUSD", Side.BUY, D("0.01"), D("1.15000"), T0)
        close = D("1.15000") + spec.from_points(724)
        cand = TrailingRule(D(500), D(250)).candidate(pos, spec, close)
        self.assertEqual(spec.to_points(cand - pos.open_price), D(474))
        # przed progiem aktywacji nie ma kandydata
        self.assertIsNone(TrailingRule(D(800), D(250)).candidate(pos, spec, close))

    def test_margin_usage_is_not_loss(self):
        out = margin_usage(D("2459.34"), D("10247.25"))
        self.assertEqual(D(out["ratio"]), D("0.24"))
        self.assertEqual(D(out["free_margin"]), D("7787.91"))
        self.assertIn("nie jest strata", out["label"])


class PlanSidesAndLevels(unittest.TestCase):
    def test_sell_mirror(self):
        ev = evaluate_plan(plan(Side.SELL, "1.15438", "1.16927", "1.14371"), eurusd_example(), "USD", USD)
        self.assertEqual(ev.sl_points, D(1489))
        self.assertEqual(ev.tp_points, D(1067))
        self.assertEqual(ev.risk_account, D("14.89"))
        self.assertFalse(ev.errors)

    def test_wrong_side_sl_and_tp_block(self):
        ev = evaluate_plan(plan(Side.BUY, "1.15438", "1.16000", "1.15000"), eurusd_example(), "USD", USD)
        self.assertFalse(ev.can_send)
        self.assertTrue(any("SL" in e and "złej stronie" in e for e in ev.errors))
        self.assertTrue(any("TP" in e and "złej stronie" in e for e in ev.errors))

    def test_stops_level(self):
        spec = eurusd_example(stops_level_points=50)
        ev = evaluate_plan(plan(sl="1.15400", tp="1.16505"), spec, "USD", USD)
        self.assertTrue(any("stops level" in e for e in ev.errors))

    def test_market_entry_from_quote_and_stale_warning(self):
        q = quote("EURUSD", "1.15430", "1.15438")
        st = assess_quote(q, T0 + timedelta(seconds=120), 30)
        ev = evaluate_plan(plan(entry=None, order_type=OrderType.MARKET), eurusd_example(), "USD", USD, quote=q, quote_status=st)
        self.assertEqual(ev.entry, D("1.15438"))
        self.assertEqual(ev.entry_basis, "Ask")
        self.assertTrue(any("UNCONFIRMED" in w for w in ev.warnings))
        ev_sell = evaluate_plan(plan(Side.SELL, entry=None, sl="1.16927", tp="1.14371", order_type=OrderType.MARKET),
                                eurusd_example(), "USD", USD, quote=q)
        self.assertEqual(ev_sell.entry, D("1.15430"))

    def test_market_without_quote_blocks(self):
        ev = evaluate_plan(plan(entry=None, order_type=OrderType.MARKET), eurusd_example(), "USD", USD)
        self.assertFalse(ev.can_send)

    def test_missing_sl_is_not_zero_risk(self):
        ev = evaluate_plan(plan(sl=None), eurusd_example(), "USD", USD)
        self.assertIsNone(ev.risk_account)
        self.assertIsNone(ev.reward_risk)
        self.assertTrue(any("NIE jest 0%" in w for w in ev.warnings))

    def test_costs_unknown_vs_known(self):
        ev = evaluate_plan(plan(), eurusd_example(), "USD", USD)
        self.assertIsNone(ev.costs_account)
        self.assertIsNone(ev.net_risk_account)
        ev2 = evaluate_plan(plan(), eurusd_example(), "USD", USD, CostModel(D("3.5"), "test"))
        self.assertEqual(ev2.costs_account, D("0.07"))
        self.assertEqual(ev2.net_risk_account, D("14.96"))
        self.assertEqual(ev2.net_reward_account, D("10.60"))

    def test_pending_order_side_checks(self):
        q = quote("EURUSD", "1.15430", "1.15438")
        ev = evaluate_plan(plan(entry="1.15500", sl="1.14000", tp="1.17000", order_type=OrderType.LIMIT),
                           eurusd_example(), "USD", USD, quote=q)
        self.assertTrue(any("LIMIT" in e for e in ev.errors))


class InstrumentUnits(unittest.TestCase):
    def test_volume_rules_never_round_up(self):
        spec = eurusd_example()
        self.assertFalse(spec.check_volume(D("0.001")).ok)
        self.assertFalse(spec.check_volume(D("0.015")).ok)
        self.assertFalse(spec.check_volume(D("101")).ok)
        self.assertTrue(spec.check_volume(D("0.02")).ok)
        self.assertEqual(spec.floor_volume(D("0.019")), D("0.01"))
        self.assertIsNone(spec.floor_volume(D("0.005")))
        ev = evaluate_plan(plan(volume="0.005"), spec, "USD", USD)
        self.assertTrue(any("poniżej minimum" in e for e in ev.errors))

    def test_tick_size_differs_from_point(self):
        spec = index_example()
        self.assertEqual(spec.point, D("0.01"))
        self.assertEqual(spec.tick, D("0.25"))
        self.assertEqual(spec.normalize_price(D("5900.13")), D("5900.25"))
        ev = evaluate_plan(plan(entry="5900.10", sl="5890.00", tp="5920.00", volume="1", symbol="US500"), spec, "USD", USD)
        self.assertTrue(any("siatce ticka" in e for e in ev.errors))
        ev2 = evaluate_plan(plan(entry="5900.25", sl="5890.00", tp="5920.00", volume="1", symbol="US500"), spec, "USD", USD)
        self.assertEqual(ev2.risk_account, D("10.25"))

    def test_jpy_profit_needs_explicit_rate(self):
        spec = usdjpy_example()
        p = plan(entry="154.320", sl="153.320", tp="155.820", symbol="USDJPY")
        ev = evaluate_plan(p, spec, "USD", FxTable())
        self.assertEqual(ev.risk_profit_ccy, D("1000"))   # 1000 JPY
        self.assertIsNone(ev.risk_account)                # brak kursu != 0
        fx = FxTable()
        fx.add(FxRate("USD", "JPY", D("154.320"), "test"))
        ev2 = evaluate_plan(p, spec, "USD", fx)
        self.assertEqual(ev2.risk_account.quantize(D("0.0001")), D("6.4800"))
        self.assertEqual(ev2.sl_pips, D(100))  # 3 cyfry: pip = 0,01

    def test_gold_pip_explicit(self):
        spec = xauusd_example()
        ev = evaluate_plan(plan(entry="2650.00", sl="2640.00", tp="2670.00", volume="0.10", symbol="XAUUSD"), spec, "USD", USD)
        self.assertEqual(ev.sl_points, D(1000))
        self.assertEqual(ev.sl_pips, D(100))
        self.assertEqual(ev.risk_account, D("100"))

    def test_account_currency_eur(self):
        fx = FxTable()
        fx.add(FxRate("EUR", "USD", D("1.25"), "test"))
        ev = evaluate_plan(plan(), eurusd_example(), "EUR", fx)
        self.assertEqual(ev.risk_account, D("11.912"))


class ChartGeometry(unittest.TestCase):
    def test_range_contains_all_levels_and_mapping_is_exact(self):
        prices = [D("1.1500"), D("1.1560")]
        levels = [D("1.15438"), D("1.13949"), D("1.16505")]
        lo, hi = chart_range(prices + levels)
        for p in levels:
            self.assertTrue(lo <= p <= hi)
        h = D(400)
        y_entry, y_sl, y_tp = (price_to_y(p, lo, hi, h) for p in levels)
        self.assertLess(y_tp, y_entry)
        self.assertLess(y_entry, y_sl)
        # Proporcje odległości na osi = proporcje cen (1067 : 1489).
        self.assertLess(abs(((y_sl - y_entry) / (y_entry - y_tp)) - D(1489) / D(1067)), D("1e-20"))


class Freshness_(unittest.TestCase):
    def test_states(self):
        q = quote("EURUSD", "1.1", "1.1")
        self.assertIs(assess_quote(None, T0, 30).state, Freshness.MISSING)
        self.assertIs(assess_quote(q, T0 + timedelta(seconds=10), 30).state, Freshness.CONFIRMED)
        self.assertIs(assess_quote(q, T0 + timedelta(seconds=31), 30).state, Freshness.UNCONFIRMED)
        self.assertIs(assess_quote(q, T0, 30, connected=False).state, Freshness.UNCONFIRMED)


class Widgets(unittest.TestCase):
    def test_risk_to_sl_incomplete_without_sl(self):
        spec = eurusd_example()
        with_sl = Position("A", "SIM", "EURUSD", Side.BUY, D("0.01"), D("1.15000"), T0, sl=D("1.14500"))
        no_sl = Position("B", "SIM", "EURUSD", Side.SELL, D("0.01"), D("1.15000"), T0)
        q = {"EURUSD": quote("EURUSD", "1.15100", "1.15108")}
        out = risk_to_sl([with_sl, no_sl], {"EURUSD": spec}, q, USD, "USD", D("10000"))
        self.assertEqual(out["state"], "INCOMPLETE")
        self.assertIsNone(out["loss_to_sl_from_now"])
        self.assertIsNone(out["loss_to_sl_pct_equity"])
        self.assertEqual(out["positions_without_sl"], 1)
        complete = risk_to_sl([with_sl], {"EURUSD": spec}, q, USD, "USD", D("10000"))
        self.assertEqual(D(complete["loss_to_sl_from_now"]), D("-6.00"))

    def test_rsi_and_macd(self):
        rising = [D(i) for i in range(1, 40)]
        self.assertEqual(rsi(rising), D(100))
        self.assertIsNone(rsi(rising[:10]))
        self.assertIsNone(macd(rising[:20]))
        m = macd(rising)
        self.assertEqual(m["histogram"], m["macd"] - m["signal"])
        flat_then = [D(10)] * 20 + [D(9)] * 20
        self.assertLess(rsi(flat_then), D(50))

    def test_indicators_only_closed_bars(self):
        spec = eurusd_example()
        series = synthetic_series(spec, Timeframe.M15, T0, 60, D("1.15"), seed=1)
        out = indicators(series, T0)
        self.assertEqual(out["rsi14"]["closed_bars"], 59)   # ostatnia świeca jeszcze trwa
        self.assertEqual(out["rsi14"]["mode"], DataMode.SIMULATED.value)
        self.assertEqual(out["rsi14"]["timeframe"], "M15")

    def test_candle_timer(self):
        out = candle_timer(Timeframe.M15, T0 + timedelta(minutes=5), None)
        self.assertEqual(out["remaining_s"], 600)
        self.assertIn("Brak ticka", out["note"])


if __name__ == "__main__":
    unittest.main()
