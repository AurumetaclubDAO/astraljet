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
