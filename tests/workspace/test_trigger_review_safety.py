"""Trend Trigger, Review Center, ustawienia UI, granice modułu, sesja i serwer."""

from __future__ import annotations

import ast
import http.client
import json
import threading
import unittest
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from astraljet.workspace.analytics import ReviewFilter, review
from astraljet.workspace.execution import OrderService
from astraljet.workspace.instruments import Side, eurusd_example
from astraljet.workspace.model import Deal, DealEntry, DealType, MarginMode, OrderRequest, RequestKind
from astraljet.workspace.server import serve
from astraljet.workspace.session import WorkspaceSession, SimClock
from astraljet.workspace.settings import UISettings, apply_ui_settings
from astraljet.workspace.trigger import Cross, Line, PriceSource, TrendTrigger, TriggerState

from .helpers import T0, broker, quote

D = Decimal
SPEC = eurusd_example()


def trg(cross=Cross.UP, side=Side.BUY, sl="150", line="1.15500", **kw):
    return TrendTrigger("t1", "EURUSD", Line(D(line)), cross, side, D("0.01"), PriceSource.BID,
                        None if sl is None else D(sl), D("300"), **kw)


def obs(t, bid, minutes, fresh=True):
    b = D(bid)
    return t.observe(b, b + D("0.00008"), T0 + timedelta(minutes=minutes), fresh)


class Trigger(unittest.TestCase):
    def test_incomplete_cannot_arm_and_summary_names_missing(self):
        t = TrendTrigger("t0", "EURUSD", None, None, None, None)
        t.arm(D("1.15"), T0)
        self.assertIs(t.state, TriggerState.DRAFT)
        self.assertIn("brakuje", t.summary(SPEC))

    def test_cross_up_fires_once(self):
        t = trg()
        t.arm(D("1.15400"), T0)
        self.assertIs(t.state, TriggerState.ARMED)
        self.assertIsNone(obs(t, "1.15450", 1))
        fire = obs(t, "1.15500", 2)               # dotknięcie linii od dołu = przecięcie
        self.assertIsNotNone(fire)
        self.assertEqual(fire.request_id, "trg-t1-r0")
        self.assertIs(t.state, TriggerState.FIRED)
        self.assertIsNone(obs(t, "1.15400", 3))
        self.assertIsNone(obs(t, "1.15600", 4))   # jednorazowość

    def test_already_beyond_waits_for_reset(self):
        t = trg()
        t.arm(D("1.15600"), T0)
        self.assertIs(t.state, TriggerState.WAITING_RESET)
        self.assertIsNone(obs(t, "1.15700", 1))
        self.assertIsNone(obs(t, "1.15400", 2))   # powrót pod linię
        self.assertIs(t.state, TriggerState.ARMED)
        self.assertIsNotNone(obs(t, "1.15510", 3))

    def test_cross_down_and_contrarian_warning(self):
        t = trg(cross=Cross.DOWN, side=Side.BUY)
        self.assertTrue(any("kontrariańska" in w for w in t.warnings()))
        t.arm(D("1.15600"), T0)
        self.assertIsNotNone(obs(t, "1.15490", 1))

    def test_missing_sl_warning_and_summary(self):
        t = trg(sl=None)
        self.assertTrue(any("brak SL" in w for w in t.warnings()))
        s = t.summary(SPEC)
        self.assertIn("SL BRAK", s)
        self.assertIn("BID", s)
        self.assertIn("jednorazowo BUY 0.01", s)

    def test_move_line_resets_side_and_delete_cancels(self):
        t = trg()
        t.arm(D("1.15400"), T0)
        t.move_line(Line(D("1.15300")), T0)
        self.assertEqual(t.revision, 1)
        self.assertIsNone(obs(t, "1.15400", 1))   # pierwsza obserwacja po przesunięciu tylko ustala stronę
        self.assertIs(t.state, TriggerState.WAITING_RESET)
        self.assertIsNone(obs(t, "1.15200", 2))
        fire = obs(t, "1.15350", 3)
        self.assertEqual(fire.request_id, "trg-t1-r1")
        with self.assertRaises(ValueError):
            t.move_line(Line(D("1.2")), T0)
        t2 = trg()
        t2.arm(D("1.15400"), T0)
        t2.delete_line(T0)
        self.assertIs(t2.state, TriggerState.CANCELLED)
        self.assertIsNone(t2.line)

    def test_expiry_stale_and_restart(self):
        t = trg(expires_at=T0 + timedelta(minutes=5))
        t.arm(D("1.15400"), T0)
        self.assertIsNone(obs(t, "1.15600", 1, fresh=False))   # nieświeże: brak oceny
        self.assertIs(t.state, TriggerState.ARMED)
        restored = TrendTrigger.from_dict(json.loads(json.dumps(t.to_dict())))
        restored.restore_after_restart(T0)
        self.assertIsNone(obs(restored, "1.15600", 2))         # po restarcie bez wyzwolenia
        self.assertIs(restored.state, TriggerState.WAITING_RESET)
        self.assertIsNone(obs(restored, "1.15400", 6))
        self.assertIs(restored.state, TriggerState.EXPIRED)

    def test_trend_line_price(self):
        line = Line(D("1.15000"), T0, D("1.16000"), T0 + timedelta(hours=10), extend_right=False)
        self.assertEqual(line.price_at(T0 + timedelta(hours=5)), D("1.15500"))
        self.assertIsNone(line.price_at(T0 + timedelta(hours=11)))
        self.assertIsNone(line.price_at(T0 - timedelta(hours=1)))
        t = TrendTrigger("t2", "EURUSD", line, Cross.UP, Side.BUY, D("0.01"), PriceSource.ASK, D(100), None)
        t.arm(D("1.15000"), T0 + timedelta(hours=1))
        fire = t.observe(D("1.15200"), D("1.15210"), T0 + timedelta(hours=2), True)
        self.assertIsNotNone(fire)
        self.assertEqual(fire.line_price, D("1.15200"))

    def test_fired_request_is_deduplicated_by_order_service(self):
        b, clock = broker()
        svc = OrderService(b, clock)
        t = trg()
        t.arm(D("1.15400"), T0)
        fire = obs(t, "1.15520", 1)
        req = OrderRequest(fire.request_id, "SIM-T", RequestKind.OPEN, "EURUSD", fire.side, fire.volume)
        svc.submit(req)
        svc.submit(req)
        self.assertEqual(len(b.positions()), 1)


def deal(i, minutes, type_=DealType.TRADE, **kw):
    return Deal(f"d{i}", "A", T0 + timedelta(minutes=minutes), type_, **kw)


class Review(unittest.TestCase):
    def setUp(self):
        self.deals = [
            deal(0, 0, DealType.DEPOSIT, amount=D("1000")),
            deal(1, 10, symbol="EURUSD", side=Side.BUY, entry=DealEntry.IN, volume=D("0.10"), position_id="P1", commission=D("-0.35")),
            deal(2, 20, symbol="EURUSD", side=Side.SELL, entry=DealEntry.OUT, volume=D("0.04"), position_id="P1", profit=D("4"), commission=D("-0.14")),
            deal(3, 30, symbol="EURUSD", side=Side.SELL, entry=DealEntry.OUT, volume=D("0.06"), position_id="P1", profit=D("-3"), commission=D("-0.21"), swap=D("-0.10")),
            deal(4, 40, symbol="EURUSD", side=Side.SELL, entry=DealEntry.IN, volume=D("0.05"), position_id="P2"),
            deal(5, 50, symbol="EURUSD", side=Side.BUY, entry=DealEntry.OUT, volume=D("0.02"), position_id="P2", profit=D("2")),
            deal(6, 55, DealType.WITHDRAWAL, amount=D("-100")),
            deal(7, 56, DealType.FEE, amount=D("-1.5")),
        ]

    def test_definitions_partials_cash_flows_and_curve_consistency(self):
        r = review(self.deals, "A", "USD", ReviewFilter(), D("3.21"), "test", "test")
        self.assertEqual(r["stats"]["trades"], 1)                        # P1 w pełni zamknięta; P2 częściowo
        self.assertEqual(D(r["trades"][0]["net"]), D("0.20"))            # 4 − 3 − 0.35 − 0.14 − 0.21 − 0.10
        self.assertEqual(r["trades"][0]["exits"], 2)
        self.assertEqual(D(r["realized_breakdown"]["from_partial_closes_of_open_positions"]), D("2"))
        self.assertEqual(D(r["realized_period"]), D("2.20"))
        b = r["realized_breakdown"]
        parts = (D(b["from_closed_trades_in_period"]) + D(b["from_partial_closes_of_open_positions"])
                 + D(b["entry_costs_of_open_positions"]))
        self.assertEqual(parts, D(r["realized_period"]))
        # okres od 25. minuty: wejście P1 sprzed okresu nie wchodzi do realized, ale wynik transakcji jest pełny
        r2 = review(self.deals, "A", "USD", ReviewFilter(start=T0 + timedelta(minutes=25)), None, "", "test")
        b2 = r2["realized_breakdown"]
        self.assertEqual(D(b2["from_closed_trades_in_period"]) + D(b2["from_partial_closes_of_open_positions"])
                         + D(b2["entry_costs_of_open_positions"]), D(r2["realized_period"]))
        self.assertEqual(D(b2["closed_trades_full_net"]), D("0.20"))
        self.assertEqual(D(b2["from_closed_trades_in_period"]), D("-3.31"))
        self.assertEqual(D(r["cash_flows"]["deposits"]), D("1000"))
        self.assertEqual(D(r["cash_flows"]["withdrawals"]), D("-100"))
        self.assertEqual(r["floating_now"], "3.21")
        start, end = D(r["curve"][0]["balance"]), D(r["curve"][-1]["balance"])
        cf = r["cash_flows"]
        self.assertEqual(end - start, D(r["realized_period"]) + D(cf["deposits"]) + D(cf["withdrawals"]) + D(cf["account_fees"]))
        self.assertEqual(r["balance"]["end"], r["curve"][-1]["balance"])
        self.assertEqual(r["by_side"]["BUY"]["net"], r["trades"][0]["net"])   # wykres kierunków = tabela

    def test_period_filter_and_start_balance(self):
        r = review(self.deals, "A", "USD", ReviewFilter(start=T0 + timedelta(minutes=25)), None, "", "test")
        self.assertEqual(D(r["balance"]["start"]), D("1003.51"))
        self.assertEqual(r["stats"]["trades"], 1)
        self.assertIsNone(r["floating_now"])

    def test_side_filter_excludes_cash_flows_from_curve(self):
        r = review(self.deals, "A", "USD", ReviewFilter(side=Side.SELL), None, "", "test")
        self.assertEqual(r["stats"]["trades"], 0)
        self.assertEqual(D(r["curve"][-1]["balance"]), D("2"))
        self.assertIsNone(r["balance"]["start"])

    def test_profit_factor_none_without_losses(self):
        r = review(self.deals[:3], "A", "USD", ReviewFilter(), None, "", "test")
        self.assertEqual(r["stats"]["trades"], 0)
        self.assertIsNone(r["stats"]["profit_factor"])
        self.assertIsNone(r["stats"]["win_rate"])


class Settings(unittest.TestCase):
    def test_ui_settings_cannot_touch_automation(self):
        s = apply_ui_settings(UISettings(), {"theme": "light", "density": "compact"})
        self.assertEqual(s.theme, "light")
        for bad in ({"trailing": True}, {"auto_trading": True}, {"theme": "neon"}, {"panel_order": ["chart"]}):
            with self.assertRaises(ValueError):
                apply_ui_settings(s, bad)

    def test_theme_change_in_session_keeps_rules_and_triggers(self):
        s = WorkspaceSession()
        s.act("trigger_create", {"line_price": "1.2", "cross": "UP", "side": "BUY", "volume": "0.01"})
        before = json.dumps(s.snapshot()["triggers"], sort_keys=True)
        s.act("ui_settings", {"theme": "light"})
        self.assertEqual(json.dumps(s.snapshot()["triggers"], sort_keys=True), before)


class ModuleBoundaries(unittest.TestCase):
    FORBIDDEN = ("MetaTrader5", "socket", "urllib", "requests", "httpx", "astraljet.dashboard", "astraljet.executor",
                 "astraljet.alpaca_challenge", "subprocess")

    def test_workspace_has_no_broker_or_network_imports(self):
        root = Path(__file__).resolve().parents[2] / "src" / "astraljet" / "workspace"
        violations = []
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module or ""]
                for n in names:
                    if any(n == f or n.startswith(f + ".") for f in self.FORBIDDEN):
                        violations.append(f"{path.name}:{n}")
        self.assertEqual([], violations)

    def test_observatory_still_read_only(self):
        app = Path(__file__).resolve().parents[2] / "src" / "astraljet" / "dashboard" / "api" / "app.py"
        text = app.read_text(encoding="utf-8")
        self.assertIn("if request.method != 'GET'", text)
        self.assertNotIn("workspace", text)


class SessionEndToEnd(unittest.TestCase):
    def test_single_snapshot_consistency_and_protection_flow(self):
        s = WorkspaceSession(seed=3)
        snap = s.snapshot()
        self.assertEqual(snap["mode"], "SIMULATED")
        ev = snap["plan"]["evaluation"]
        lo, hi = D(snap["chart"]["lo"]), D(snap["chart"]["hi"])
        for level in (ev["entry"], snap["plan"]["sl"], snap["plan"]["tp"]):
            self.assertTrue(lo <= D(level) <= hi)
        s.act("send_plan", {"client_request_id": "click-0001"})
        s.act("send_plan", {"client_request_id": "click-0001"})       # podwójne kliknięcie
        snap = s.snapshot()
        self.assertEqual(len(snap["positions"]), 1)
        pid = snap["positions"][0]["position_id"]
        self.assertEqual(snap["positions"][0]["protection"]["status"], "PROTECTED")
        s.act("set_be", {"position_id": pid, "trigger_points": 100, "offset_points": 10})
        s.act("set_trailing", {"position_id": pid, "activation_points": 500, "distance_points": 250, "step_points": 10})
        s.act("step", {"n": 12, "drift_points": 60})
        snap = s.snapshot()
        pos = snap["positions"][0]
        self.assertGreater(D(pos["sl"]), D(pos["open_price"]))        # SL przesunięty ponad wejście
        self.assertIn(pos["rules"]["trailing_status"]["state"], {"CONFIRMED", "SATISFIED", "WAITING"})
        self.assertEqual(snap["widgets"]["risk_to_sl"]["state"], "COMPLETE")
        # wersja snapshotu rośnie z każdą akcją
        self.assertGreaterEqual(snap["version"], 5)

    def test_disconnect_shows_missing_not_zero(self):
        s = WorkspaceSession()
        s.act("set_connected", {"connected": False})
        s.act("step", {"n": 3})
        snap = s.snapshot()
        self.assertIsNone(snap["account"])
        self.assertIsNone(snap["review"])
        self.assertEqual(snap["quote_status"]["state"], "UNCONFIRMED")
        self.assertEqual(snap["widgets"]["margin"]["state"], "MISSING")
        self.assertEqual(snap["positions"], [])
        self.assertEqual(snap["connection"]["state"], "DISCONNECTED")

    def test_trigger_through_session(self):
        s = WorkspaceSession(seed=5)
        bid = D(s.snapshot()["quote"]["bid"])
        line = bid + D("0.00030")
        tid = s.act("trigger_create", {"line_price": str(line), "cross": "UP", "side": "BUY", "volume": "0.01",
                                       "sl_points": "150"})["trigger_id"]
        s.act("trigger_arm", {"trigger_id": tid})
        s.act("step", {"n": 3, "drift_points": 20})
        snap = s.snapshot()
        t = [x for x in snap["triggers"] if x["trigger_id"] == tid][0]
        self.assertEqual(t["state"], "FIRED")
        req = [r for r in snap["requests"] if r["request"]["request_id"] == t["fired_request_id"]]
        self.assertEqual(len(req), 1)
        self.assertEqual(req[0]["request"]["origin"], f"trigger:{tid}")
        self.assertIsNotNone(req[0]["request"]["sl"])


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = serve(port=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"127.0.0.1:{self.port}"}
        h.update(headers or {})
        conn.request(method, path, body=body, headers=h)
        r = conn.getresponse()
        data = r.read()
        conn.close()
        return r.status, data

    def test_state_and_static(self):
        status, data = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["mode"], "SIMULATED")
        self.assertEqual(self.request("GET", "/")[0], 200)

    def test_post_requires_header_and_json(self):
        body = json.dumps({"action": "step", "params": {"n": 1}})
        self.assertEqual(self.request("POST", "/api/action", body, {"Content-Type": "application/json"})[0], 403)
        self.assertEqual(self.request("POST", "/api/action", body, {"X-Astra-Workspace": "SIMULATED", "Content-Type": "text/plain"})[0], 415)
        status, _ = self.request("POST", "/api/action", body, {"X-Astra-Workspace": "SIMULATED", "Content-Type": "application/json"})
        self.assertEqual(status, 200)
        status, data = self.request("POST", "/api/action", json.dumps({"action": "nope"}),
                                    {"X-Astra-Workspace": "SIMULATED", "Content-Type": "application/json"})
        self.assertEqual(status, 400)

    def test_foreign_host_and_methods(self):
        self.assertEqual(self.request("GET", "/api/state", headers={"Host": "evil.example"})[0], 421)
        self.assertEqual(self.request("PUT", "/api/action", "{}")[0], 405)

    def test_refuses_non_local_bind(self):
        with self.assertRaises(SystemExit):
            serve(host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()
