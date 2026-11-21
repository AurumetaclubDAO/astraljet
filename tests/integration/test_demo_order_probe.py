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
        report = probe.run_probe(mt5, RULE, self.dir / "db")
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
        probe.write_report(report, out, None)
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
            probe.run_probe(mt5, RULE, self.dir / "db", report=report)
        self.assertEqual(1, len(mt5.sends))
        self.assertIn("2. otwarcie", "\n".join(report.lines))

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
