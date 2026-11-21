"""Adapter zleceń MT5 tylko dla DEMO: testy na atrapie terminala (bez połączenia z brokerem)."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

from astraljet.domain.enums import ExecutionEnvironment, ExecutionResultState
from astraljet.executor.mt5_demo import DemoAccountRule, MT5DemoAdapter, OrderSDK, PROBE_MAGIC

from tests.integration.test_tq_lessons import NOW, ExecutorCase, order

RULE = DemoAccountRule(label="DEMO-PROJEKT", login=81234567, server="Broker-Demo")


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_REAL = 0, 2
    TRADE_ACTION_DEAL, ORDER_TIME_GTC = 1, 0
    ORDER_TYPE_BUY, ORDER_TYPE_SELL, POSITION_TYPE_BUY = 0, 1, 0
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2

    def __init__(self) -> None:
        self.account = NS(login=81234567, trade_mode=0, server="Broker-Demo")
        self.terminal = NS(connected=True, trade_allowed=True)
        self.positions, self.deals, self.sends, self.checks = {}, [], [], []
        self.next_ticket = 1000
        self.send_returns_none = False
        self.switch_to_real_after_send = False

    def account_info(self): return self.account
    def terminal_info(self): return self.terminal
    def symbol_info(self, symbol):
        return NS(visible=True, trade_contract_size=1.0, volume_step=0.01, volume_min=0.01, volume_max=100.0,
                  filling_mode=2)
    def symbol_info_tick(self, symbol): return NS(bid=3000.0, ask=3001.0)
    def order_check(self, request): self.checks.append(request); return NS(retcode=0)

    def order_send(self, request):
        self.sends.append(request)
        if self.switch_to_real_after_send:
            self.account = NS(login=999, trade_mode=2, server="Broker-Live")
        if self.send_returns_none:
            return None
        self.next_ticket += 1
        ticket = self.next_ticket
        if "position" in request:
            self.positions.pop(request["position"])
        else:
            self.positions[ticket] = NS(ticket=ticket, symbol=request["symbol"], type=request["type"],
                                        volume=request["volume"], magic=request["magic"], price_current=3000.5)
        self.deals.append(NS(magic=request["magic"], comment=request["comment"], ticket=ticket, order=ticket))
        return NS(retcode=10009, order=ticket, deal=ticket, price=request["price"] + 0.5, volume=request["volume"])

    def positions_get(self, ticket=None, symbol=None):
        if ticket is not None:
            return tuple(p for t, p in self.positions.items() if t == ticket)
        return tuple(self.positions.values())

    def history_deals_get(self, start, end): return tuple(self.deals)
    def shutdown(self): self.closed = True


class MT5DemoCase(ExecutorCase):
    environment = ExecutionEnvironment.BROKER_DEMO
    environment_id = "demo-test"
    account_id = "DEMO-PROJEKT"

    def setUp(self) -> None:
        super().setUp()
        self.mt5 = FakeMT5()
        self.adapter = MT5DemoAdapter(self.database, self.guard, self.mt5, RULE, symbols=("ETHUSD",))
        self.n = 0

    def submit(self, intent, **kwargs):
        self.n += 1
        key = kwargs.pop("key", f"mt5-demo-{self.n:04d}")
        return self.adapter.submit_intent(self.ctx(mandate_record=kwargs.pop("mandate_record", None)), intent,
                                          idempotency_key=key, now=NOW, **kwargs)

    def eth(self, intent_id, side="buy", quantity="0.01"):
        return order(intent_id, instrument="ETHUSD", side=side, quantity=quantity, price="3000")

    def kill_active(self) -> bool:
        with self.database.connect() as connection:
            row = connection.execute("SELECT active FROM kill_switches WHERE environment_id = ?",
                                     (self.environment_id,)).fetchone()
        return bool(row and row["active"])


class FullRoundTrip(MT5DemoCase):
    def test_open_read_close_reconcile(self) -> None:
        opened = self.submit(self.eth("OPEN-1"))
        self.assertIs(opened.state, ExecutionResultState.ACCEPTED)
        self.assertEqual({"ETHUSD": "0.01"}, self.adapter.positions(self.environment_id).quantities)
        ticket = next(iter(self.mt5.positions))
        self.assertEqual(PROBE_MAGIC, self.mt5.sends[0]["magic"])
        closed = self.submit(self.eth("CLOSE-1", side="sell"), position_ticket=ticket)
        self.assertIs(closed.state, ExecutionResultState.ACCEPTED)
        self.assertEqual({}, self.adapter.positions(self.environment_id).quantities)
        self.assertEqual(2, len(self.mt5.sends))
        self.assertEqual(ticket, self.mt5.sends[1]["position"])
        response = self.adapter.response("mt5-demo-0001")
        self.assertEqual(3001.0, response["requested_price"])
        self.assertEqual(3001.5, response["fill_price"])
        self.assertEqual([("CLOSE-1", "accepted"), ("OPEN-1", "accepted")], self.intents())

    def test_close_must_be_opposite_full_volume_of_own_position(self) -> None:
        self.submit(self.eth("OPEN-1"))
        ticket = next(iter(self.mt5.positions))
        self.assertEqual("close_mismatch", self.blocker(lambda: self.submit(self.eth("CLOSE-X"), position_ticket=ticket)))
        self.assertEqual("position_not_owned", self.blocker(
            lambda: self.submit(self.eth("CLOSE-Y", side="sell"), position_ticket=424242)))
        self.assertEqual(1, len(self.mt5.sends))


class DemoOnlyGate(MT5DemoCase):
    def test_real_account_is_refused_and_trips_kill_switch(self) -> None:
        self.mt5.account = NS(login=999, trade_mode=2, server="Broker-Live")
        self.assertEqual("not_demo_account", self.blocker(lambda: self.submit(self.eth("OPEN-1"))))
        self.assertTrue(self.kill_active())
        self.assertEqual([], self.mt5.sends)
        self.mt5.account = NS(login=81234567, trade_mode=0, server="Broker-Demo")
        self.assertEqual("kill_switch_active", self.blocker(lambda: self.submit(self.eth("OPEN-2"))))
        self.assertEqual([], self.mt5.sends)

    def test_wrong_server_or_login_is_refused(self) -> None:
        for account in (NS(login=81234567, trade_mode=0, server="Other-Demo"), NS(login=222, trade_mode=0, server="Broker-Demo")):
            with self.subTest(account=account):
                self.mt5.account = account
                self.assertEqual("demo_account_mismatch", self.blocker(lambda: self.submit(self.eth(f"O-{account.login}-{account.server}"))))
        self.assertEqual([], self.mt5.sends)
        self.assertFalse(self.kill_active())

    def test_algo_trading_off_is_refused(self) -> None:
        self.mt5.terminal = NS(connected=True, trade_allowed=False)
        self.assertEqual("algo_trading_disabled", self.blocker(lambda: self.submit(self.eth("OPEN-1"))))
        self.assertEqual([], self.mt5.sends)

    def test_account_switch_to_real_during_send_is_recorded_and_stops(self) -> None:
        self.mt5.switch_to_real_after_send = True
        self.assertEqual("not_demo_account", self.blocker(lambda: self.submit(self.eth("OPEN-1"))))
        self.assertEqual([("OPEN-1", "accepted")], self.intents())  # wynik zapisany mimo odmowy po wysłaniu
        self.assertTrue(self.kill_active())

    def test_mandate_for_other_account_or_paper_is_refused(self) -> None:
        other = dataclasses.replace(self.mandate, account_id="INNE-DEMO")
        self.assertEqual("wrong_adapter", self.blocker(lambda: self.submit(self.eth("OPEN-1"), mandate_record=other)))
        self.assertEqual([], self.mt5.sends)


class TqLessonsOnMt5(MT5DemoCase):
    def test_kill_switch_stops_order(self) -> None:
        self.kill()
        self.assertEqual("kill_switch_active", self.blocker(lambda: self.submit(self.eth("OPEN-1"))))
        self.assertEqual([], self.mt5.sends)

    def test_retry_after_denial_goes_through_gate_again(self) -> None:
        self.mt5.terminal = NS(connected=True, trade_allowed=False)
        self.assertEqual("algo_trading_disabled", self.blocker(lambda: self.submit(self.eth("OPEN-1"))))
        self.assertEqual("algo_trading_disabled", self.blocker(lambda: self.submit(self.eth("OPEN-1"))))
        self.mt5.terminal = NS(connected=True, trade_allowed=True)
        self.assertIs(self.submit(self.eth("OPEN-1")).state, ExecutionResultState.ACCEPTED)
        self.assertEqual(1, len(self.mt5.sends))

    def test_same_intent_twice_is_refused(self) -> None:
        self.submit(self.eth("OPEN-1"), key="mt5-demo-key-1")
        self.assertIs(self.submit(self.eth("OPEN-1"), key="mt5-demo-key-1").state, ExecutionResultState.DUPLICATE)
        self.assertEqual("duplicate_intent", self.blocker(
            lambda: self.submit(order("OPEN-1", instrument="ETHUSD", quantity="0.01", price="3000", signal_id="S-NEW"))))
        self.assertEqual(1, len(self.mt5.sends))

    def test_interrupted_reconciliation_does_not_send_second_order(self) -> None:
        self.mt5.send_returns_none = True
        self.assertIs(self.submit(self.eth("OPEN-1")).state, ExecutionResultState.UNCERTAIN)
        self.mt5.send_returns_none = False
        self.assertEqual("unresolved_execution", self.blocker(lambda: self.submit(self.eth("OPEN-2"))))
        self.assertEqual(1, len(self.mt5.sends))
        receipt = self.adapter.reconcile("MT5D-OPEN-1", idempotency_key="reconcile-0001", now=NOW,
                                         since=NOW - timedelta(hours=1))
        self.assertIs(receipt.state, ExecutionResultState.REJECTED)  # atrapa nie zapisała deala
        self.assertIs(self.submit(self.eth("OPEN-2")).state, ExecutionResultState.ACCEPTED)

    def test_reconcile_finds_deal_by_comment(self) -> None:
        self.mt5.send_returns_none = True
        self.submit(self.eth("OPEN-1"))
        self.mt5.deals.append(NS(magic=PROBE_MAGIC, comment=self.mt5.sends[0]["comment"], ticket=1))
        receipt = self.adapter.reconcile("MT5D-OPEN-1", idempotency_key="reconcile-0002", now=NOW,
                                         since=NOW - timedelta(hours=1))
        self.assertIs(receipt.state, ExecutionResultState.ACCEPTED)


class LimitsAndCalls(MT5DemoCase):
    def test_volume_must_fit_symbol_step(self) -> None:
        self.assertEqual("volume_not_allowed", self.blocker(lambda: self.submit(self.eth("OPEN-1", quantity="0.015"))))
        self.assertEqual([], self.mt5.sends)

    def test_gross_exposure_uses_terminal_positions(self) -> None:
        limited = dataclasses.replace(self.mandate, limits={**self.mandate.limits, "max_gross_exposure": "50"})
        self.assertIs(self.submit(self.eth("OPEN-1"), mandate_record=limited).state, ExecutionResultState.ACCEPTED)
        self.assertEqual("gross_exposure_exceeded", self.blocker(
            lambda: self.submit(self.eth("OPEN-2"), mandate_record=limited)))
        self.assertEqual(1, len(self.mt5.sends))

    def test_order_sdk_blocks_everything_outside_the_list(self) -> None:
        sdk = OrderSDK(self.mt5)
        for name in ("order_calc_margin", "login", "symbol_select", "history_orders_get", "orders_get", "copy_rates_range"):
            with self.subTest(name=name), self.assertRaises(PermissionError):
                getattr(sdk, name)
        self.assertEqual(0, sdk.ACCOUNT_TRADE_MODE_DEMO)

    def test_no_account_number_or_server_in_events(self) -> None:
        self.submit(self.eth("OPEN-1"))
        from astraljet.infrastructure.event_store import EventStore
        text = repr([e.payload for e in EventStore(self.database).list_for_record("SYSTEM-EXECUTOR")])
        self.assertNotIn("81234567", text)
        self.assertNotIn("Broker-Demo", text)


class SdkBoundary(MT5DemoCase):
    """Granica SDK: sam słownik zlecenia, niezależnie od bramki wykonawcy."""

    def request(self, **changes):
        base = {"action": FakeMT5.TRADE_ACTION_DEAL, "symbol": "ETHUSD", "volume": 0.01, "type": FakeMT5.ORDER_TYPE_BUY,
                "price": 3001.0, "deviation": 50, "magic": PROBE_MAGIC, "comment": "AJ-x", "type_time": 0,
                "type_filling": 2}
        base.update(changes)
        return {k: v for k, v in base.items() if v is not None or k == "position"}

    def test_only_minimal_market_buy_or_closing_sell_passes(self) -> None:
        sdk = OrderSDK(self.mt5, symbols=("ETHUSD",))
        sdk.order_check(self.request())
        sdk.order_check(self.request(type=FakeMT5.ORDER_TYPE_SELL, position=1001))
        bad = {
            "zlecenie oczekujące": self.request(action=5),
            "modyfikacja SL/TP": self.request(action=6),
            "inny symbol": self.request(symbol="BTCUSD"),
            "większy wolumen": self.request(volume=0.02),
            "inny magic": self.request(magic=1),
            "sprzedaż bez ticketu": self.request(type=FakeMT5.ORDER_TYPE_SELL),
            "kupno z ticketem": self.request(position=1001),
            "typ zlecenia limit": self.request(type=2),
            "dodatkowe pole": {**self.request(), "sl": 2900.0},
        }
        for name, request in bad.items():
            for call in ("order_check", "order_send"):
                with self.subTest(case=name, call=call), self.assertRaises(PermissionError):
                    getattr(sdk, call)(request)
        self.assertEqual(2, len(self.mt5.checks))
        self.assertEqual([], self.mt5.sends)

    def test_sell_without_ticket_is_refused_by_adapter(self) -> None:
        self.assertEqual("sell_without_position", self.blocker(lambda: self.submit(self.eth("SELL-1", side="sell"))))
        self.assertEqual([], self.mt5.sends)

    def test_symbol_outside_adapter_list_is_refused_before_write_ahead(self) -> None:
        self.assertEqual("request_not_allowed", self.blocker(lambda: self.submit(order("BTC-1", quantity="0.01", price="3000"))))
        self.assertEqual([], self.intents())


class UncertainResults(MT5DemoCase):
    def test_non_done_retcode_is_uncertain_and_blocks(self) -> None:
        original = self.mt5.order_send
        self.mt5.order_send = lambda request: (self.mt5.sends.append(request), NS(retcode=10004, order=0, deal=0))[1]
        self.assertIs(self.submit(self.eth("OPEN-1")).state, ExecutionResultState.UNCERTAIN)
        self.mt5.order_send = original
        self.assertEqual("unresolved_execution", self.blocker(lambda: self.submit(self.eth("OPEN-2"))))
        self.assertEqual(1, len(self.mt5.sends))

    def test_connection_error_is_uncertain_without_retry(self) -> None:
        def broken(request):
            self.mt5.sends.append(request)
            raise ConnectionError("sieć")
        self.mt5.order_send = broken
        self.assertIs(self.submit(self.eth("OPEN-1")).state, ExecutionResultState.UNCERTAIN)
        self.assertEqual(1, len(self.mt5.sends))
        self.assertEqual([("OPEN-1", "uncertain")], self.intents())

    def test_reconcile_uses_order_ticket_first(self) -> None:
        self.submit(self.eth("OPEN-1"))
        ticket = self.adapter.response("mt5-demo-0001")["order"]
        self.mt5.deals = [NS(magic=PROBE_MAGIC, comment="nadpisany przez brokera", ticket=ticket, order=ticket)]
        receipt = self.adapter.reconcile("MT5D-OPEN-1", idempotency_key="reconcile-0003", now=NOW,
                                         since=NOW - timedelta(hours=1))
        self.assertIs(receipt.state, ExecutionResultState.ACCEPTED)


class NoPathToLive(MT5DemoCase):
    def test_constructor_refuses_non_demo(self) -> None:
        with self.assertRaises(Exception):
            MT5DemoAdapter(self.database, self.guard, self.mt5, RULE, symbols=("ETHUSD",),
                           environment=ExecutionEnvironment.PAPER_CONTINUOUS)
        with self.assertRaises(Exception):
            MT5DemoAdapter(self.database, self.guard, self.mt5,
                           DemoAccountRule(label="X", login=1, server="Broker-Live"), symbols=("ETHUSD",))
        with self.assertRaises(Exception):
            MT5DemoAdapter(self.database, self.guard, self.mt5, RULE, symbols=())

    def test_real_account_closes_connection(self) -> None:
        self.mt5.closed = False
        self.mt5.account = NS(login=999, trade_mode=2, server="Broker-Live")
        self.blocker(lambda: self.submit(self.eth("OPEN-1")))
        self.assertTrue(self.mt5.closed)

    def test_adapter_is_imported_only_by_probe_script(self) -> None:
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        users = sorted(str(p.relative_to(root)).replace("\\", "/") for folder in ("src", "scripts")
                       for p in (root / folder).rglob("*.py")
                       if "mt5_demo" in p.read_text(encoding="utf-8", errors="ignore")
                       and p.name != "mt5_demo.py")
        self.assertEqual(["scripts/demo_order_probe.py"], users)


class ReadsNeedDemoAccount(MT5DemoCase):
    def test_reconcile_on_real_account_does_not_read_history(self) -> None:
        self.mt5.send_returns_none = True
        self.submit(self.eth("OPEN-1"))
        reads = []
        self.mt5.history_deals_get = lambda a, b: reads.append(1) or ()
        self.mt5.account = NS(login=999, trade_mode=2, server="Broker-Live")
        self.assertEqual("not_demo_account", self.blocker(lambda: self.adapter.reconcile(
            "MT5D-OPEN-1", idempotency_key="reconcile-live-01", now=NOW, since=NOW - timedelta(hours=1))))
        self.assertEqual([], reads)
        self.assertEqual([("OPEN-1", "uncertain")], self.intents())

    def test_positions_on_real_account_is_refused(self) -> None:
        self.mt5.account = NS(login=999, trade_mode=2, server="Broker-Live")
        self.assertEqual("not_demo_account", self.blocker(lambda: self.adapter.positions(self.environment_id)))

    def test_unassigned_magic_deal_keeps_uncertain(self) -> None:
        self.mt5.send_returns_none = True
        self.submit(self.eth("OPEN-1"))
        self.mt5.deals.append(NS(magic=PROBE_MAGIC, comment="zmieniony", ticket=77, order=77))
        receipt = self.adapter.reconcile("MT5D-OPEN-1", idempotency_key="reconcile-0004", now=NOW,
                                         since=NOW - timedelta(hours=1))
        self.assertIs(receipt.state, ExecutionResultState.UNCERTAIN)
        self.assertEqual([("OPEN-1", "uncertain")], self.intents())
