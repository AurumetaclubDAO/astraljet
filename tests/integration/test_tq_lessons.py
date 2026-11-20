"""Lekcje z Areny TQ zapisane jako testy toru zleceń AstralJet.

Audyt Areny TQ z 25/26.10.2026 wskazał cztery luki w torze zleceń:
1. ponowienie zlecenia omijało bramkę ryzyka,
2. nie było ochrony przed podwójnym zleceniem,
3. bramka przepuszczała błędne wartości,
4. limit nie liczył ryzyka nowej pozycji.

Te testy pilnują, żeby wykonawca AstralJet ich nie powtórzył. Działają na PAPER i na testowym
adapterze DEMO, bez połączenia z brokerem. Lekcję 2 pokrywają też testy w `test_incubation.py`
(ten sam klucz po restarcie, ten sam sygnał pod nowym kluczem); tutaj jest tylko brakujący przypadek.

Znana luka poza tymi testami: limit `max_notional` działa na pozycję w jednym instrumencie.
Bramka nie ma limitu łącznej ekspozycji na wszystkich instrumentach naraz.
"""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from astraljet.domain.enums import ExecutionEnvironment, ExecutionResultState
from astraljet.domain.errors import DomainBlockedError
from astraljet.executor.demo import DemoAdapter
from astraljet.executor.guard import ExecutorGuard
from astraljet.executor.paper import PaperExecutor
from astraljet.executor.ports import FrozenContext, OrderIntent
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.event_store import EventStore

from tests.executor_support import mandate
from tests.unit.test_executor_guard import context


NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
STALE = "2025-06-01T11:00:00Z"


def order(intent_id: str, *, instrument: str = "BTCUSD", side: str = "buy", quantity: str = "1",
          price: str = "100", signal_id: str | None = None) -> OrderIntent:
    return OrderIntent(
        intent_id=intent_id,
        instrument=instrument,
        side=side,
        quantity=Decimal(quantity),
        reference_price=Decimal(price),
        signal_id=f"SIGNAL-{intent_id}" if signal_id is None else signal_id,
    )


class ExecutorCase(unittest.TestCase):
    environment = ExecutionEnvironment.PAPER_CONTINUOUS
    environment_id = "paper-test"
    account_id: str | None = None

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.database = Database.from_state_dir(self.temp_dir.name)
        self.database.initialize()
        self.guard = ExecutorGuard(self.database)
        self.risk, self.mandate = mandate(
            environment=self.environment,
            environment_id=self.environment_id,
            account_id=self.account_id,
        )
        self.lease = self.guard.acquire_lease(self.environment_id, "worker-1", ttl_seconds=120, now=NOW)

    def ctx(self, *, observed_at: str = "2025-06-01T11:59:30Z", mandate_record: object | None = None) -> FrozenContext:
        return context(
            mandate_record=mandate_record or self.mandate,
            risk=self.risk,
            lease_id=self.lease.lease_id,
            observed_at=observed_at,
        )

    def blocker(self, call) -> str:
        with self.assertRaises(DomainBlockedError) as caught:
            call()
        return caught.exception.blocker

    def intents(self) -> list[tuple[str, str]]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT intent_id, state FROM execution_intents ORDER BY intent_id").fetchall()
        return [(row["intent_id"], row["state"]) for row in rows]

    def blocked_events(self) -> list[str]:
        events = EventStore(self.database).list_for_record("SYSTEM-EXECUTOR")
        return [event.payload["blocker"] for event in events if event.event_type == "executor.blocked"]

    def kill(self) -> None:
        self.guard.activate_kill_switch(self.environment_id, reason="test lekcji TQ",
                                        idempotency_key="tq-kill-switch-v1", now=NOW)


class RetryGoesThroughTheGate(ExecutorCase):
    """Lekcja 1: ponowienie zlecenia nie omija bramki ryzyka."""

    def test_paper_retry_after_refusal_is_judged_again(self) -> None:
        executor = PaperExecutor(self.database, self.guard)
        for _ in range(2):
            self.assertEqual("stale_data", self.blocker(lambda: executor.submit_intent(
                self.ctx(observed_at=STALE), order("INTENT-RETRY"), idempotency_key="tq-paper-retry-v1", now=NOW)))
        self.assertEqual([], self.intents())
        self.assertEqual({}, executor.positions(self.environment_id).quantities)
        self.assertEqual(2, self.blocked_events().count("stale_data"))

        receipt = executor.submit_intent(
            self.ctx(), order("INTENT-RETRY"), idempotency_key="tq-paper-retry-v1", now=NOW)
        self.assertIs(receipt.state, ExecutionResultState.ACCEPTED)
        self.assertEqual({"BTCUSD": "1"}, executor.positions(self.environment_id).quantities)

    def test_paper_retry_is_stopped_by_kill_switch_set_in_between(self) -> None:
        executor = PaperExecutor(self.database, self.guard)
        self.assertEqual("stale_data", self.blocker(lambda: executor.submit_intent(
            self.ctx(observed_at=STALE), order("INTENT-RETRY"), idempotency_key="tq-paper-retry-v2", now=NOW)))
        self.kill()
        self.assertEqual("kill_switch_active", self.blocker(lambda: executor.submit_intent(
            self.ctx(), order("INTENT-RETRY"), idempotency_key="tq-paper-retry-v2", now=NOW)))
        self.assertEqual([], self.intents())
        self.assertEqual({}, executor.positions(self.environment_id).quantities)

    def test_paper_retry_after_lease_expired_is_refused(self) -> None:
        executor = PaperExecutor(self.database, self.guard)
        self.assertEqual("stale_data", self.blocker(lambda: executor.submit_intent(
            self.ctx(observed_at=STALE), order("INTENT-RETRY"), idempotency_key="tq-paper-retry-v3", now=NOW)))
        later = datetime(2025, 6, 1, 12, 10, 0, tzinfo=timezone.utc)
        self.assertEqual("lease_inactive", self.blocker(lambda: executor.submit_intent(
            self.ctx(observed_at="2025-06-01T12:09:45Z"), order("INTENT-RETRY"),
            idempotency_key="tq-paper-retry-v3", now=later)))
        self.assertEqual([], self.intents())


class DemoRetryGoesThroughTheGate(ExecutorCase):
    """Lekcja 1 na adapterze DEMO: po niepewnym i odrzuconym wyniku nic nie idzie bokiem."""

    environment = ExecutionEnvironment.BROKER_DEMO
    environment_id = "demo-test"
    account_id = "DEMO-001"

    def test_after_rejected_reconciliation_every_new_attempt_is_judged_again(self) -> None:
        adapter = DemoAdapter(self.database, self.guard, confirmed_demo_account="DEMO-001",
                              simulate_next_uncertain=True)
        first = order("INTENT-DEMO-1")
        uncertain = adapter.submit_intent(self.ctx(), first, idempotency_key="tq-demo-v1", now=NOW)
        self.assertIs(uncertain.state, ExecutionResultState.UNCERTAIN)

        # Dopóki wynik jest nieznany, nowe ryzyko jest zablokowane.
        self.assertEqual("unresolved_execution", self.blocker(lambda: adapter.submit_intent(
            self.ctx(), order("INTENT-DEMO-2"), idempotency_key="tq-demo-v2", now=NOW)))

        adapter.set_reconciliation_result(uncertain.external_reference, ExecutionResultState.REJECTED)
        reconciled = adapter.reconcile(uncertain.external_reference, idempotency_key="tq-demo-reconcile-v1", now=NOW)
        self.assertIs(reconciled.state, ExecutionResultState.REJECTED)

        # Ten sam klucz: nic nie jest wysyłane drugi raz.
        again = adapter.submit_intent(self.ctx(), first, idempotency_key="tq-demo-v1", now=NOW)
        self.assertEqual((ExecutionResultState.DUPLICATE, ExecutionResultState.REJECTED),
                         (again.state, again.previous_state))

        # Ten sam sygnał pod nowym kluczem: odmowa, potrzebny jest nowy sygnał.
        self.assertEqual("duplicate_signal", self.blocker(lambda: adapter.submit_intent(
            self.ctx(), order("INTENT-DEMO-3", signal_id=first.signal_id), idempotency_key="tq-demo-v3", now=NOW)))

        # Nowy sygnał przechodzi przez bramkę od początku: nieświeże dane, potem kill switch.
        fresh = order("INTENT-DEMO-4")
        self.assertEqual("stale_data", self.blocker(lambda: adapter.submit_intent(
            self.ctx(observed_at=STALE), fresh, idempotency_key="tq-demo-v4", now=NOW)))
        self.kill()
        self.assertEqual("kill_switch_active", self.blocker(lambda: adapter.submit_intent(
            self.ctx(), fresh, idempotency_key="tq-demo-v4", now=NOW)))
        self.assertEqual([("INTENT-DEMO-1", "rejected")], self.intents())


class NoDoubleOrder(ExecutorCase):
    """Lekcja 2: to samo zlecenie nie wykona się dwa razy."""

    def test_same_intent_under_new_key_and_new_signal_is_not_executed_again(self) -> None:
        executor = PaperExecutor(self.database, self.guard)
        executor.submit_intent(self.ctx(), order("INTENT-TWICE", signal_id="SIGNAL-ONE"),
                               idempotency_key="tq-twice-v1", now=NOW)
        # Czysta odmowa bramki z wpisem executor.blocked (wcześniej surowy sqlite3.IntegrityError).
        self.assertEqual("duplicate_intent", self.blocker(lambda: executor.submit_intent(
            self.ctx(), order("INTENT-TWICE", signal_id="SIGNAL-TWO"), idempotency_key="tq-twice-v2", now=NOW)))
        self.assertEqual({"BTCUSD": "1"}, executor.positions(self.environment_id).quantities)
        self.assertEqual([("INTENT-TWICE", "accepted")], self.intents())
        self.assertEqual(["duplicate_intent"], self.blocked_events())


class GateRefusesBadValues(ExecutorCase):
    """Lekcja 3: bramka nie przepuszcza błędnych wartości."""

    def authorize(self, intent: OrderIntent, mandate_record: object | None = None) -> str:
        return self.blocker(lambda: self.guard.authorize(
            context=self.ctx(mandate_record=mandate_record), intent=intent, now=NOW))

    def test_bad_quantity_and_price_are_refused(self) -> None:
        for value in ("0", "-1", "NaN", "Infinity", "-Infinity"):
            with self.subTest(quantity=value):
                self.assertEqual("invalid_order_values", self.authorize(order("INTENT-BAD", quantity=value)))
        for value in ("0", "-5", "NaN", "Infinity"):
            with self.subTest(price=value):
                self.assertEqual("invalid_order_values", self.authorize(order("INTENT-BAD", price=value)))

    def test_unknown_side_instrument_and_missing_identity_are_refused(self) -> None:
        for side in ("BUY", "hold", ""):
            with self.subTest(side=side):
                self.assertEqual("intent_not_allowed", self.authorize(order("INTENT-BAD", side=side)))
        self.assertEqual("intent_not_allowed", self.authorize(order("INTENT-BAD", instrument="XAUUSD")))
        self.assertEqual("intent_identity_missing", self.authorize(order(" ")))
        self.assertEqual("intent_identity_missing", self.authorize(order("INTENT-BAD", signal_id="")))

    def test_broken_mandate_limits_are_refused(self) -> None:
        broken_limits = (
            {"max_notional": "NaN", "max_position_quantity": "10"},
            {"max_notional": "-1", "max_position_quantity": "10"},
            {"max_notional": "0", "max_position_quantity": "10"},
            {"max_notional": "abc", "max_position_quantity": "10"},
            {"max_notional": None, "max_position_quantity": "10"},
            {"max_notional": "10000", "max_position_quantity": "Infinity"},
            {"max_notional": "10000", "max_position_quantity": "0"},
            {"max_position_quantity": "10"},
        )
        for limits in broken_limits:
            with self.subTest(limits=limits):
                broken = dataclasses.replace(self.mandate, limits=limits)
                self.assertEqual("invalid_limits", self.authorize(order("INTENT-OK"), broken))

    def test_paper_keeps_no_trace_of_refused_values(self) -> None:
        executor = PaperExecutor(self.database, self.guard)
        for number, bad in enumerate((order("INTENT-BAD-1", quantity="NaN"), order("INTENT-BAD-2", price="-5"),
                                      order("INTENT-BAD-3", quantity="1000"))):
            with self.assertRaises(DomainBlockedError):
                executor.submit_intent(self.ctx(), bad, idempotency_key=f"tq-bad-value-{number}", now=NOW)
        self.assertEqual([], self.intents())
        self.assertEqual({}, executor.positions(self.environment_id).quantities)
        self.assertEqual(["invalid_order_values", "invalid_order_values", "limit_exceeded"], self.blocked_events())


class LimitCountsNewRisk(ExecutorCase):
    """Lekcja 4: limit liczy pozycję po zleceniu, a nie samo zlecenie."""

    def setUp(self) -> None:
        super().setUp()
        self.executor = PaperExecutor(self.database, self.guard)

    def submit(self, intent: OrderIntent) -> ExecutionResultState:
        return self.executor.submit_intent(
            self.ctx(), intent, idempotency_key=f"tq-limit-{intent.intent_id}", now=NOW).state

    def position(self) -> dict[str, str]:
        return self.executor.positions(self.environment_id).quantities

    def test_whole_resulting_position_is_valued_at_the_new_price(self) -> None:
        self.assertIs(self.submit(order("INTENT-L1", quantity="5", price="900")), ExecutionResultState.ACCEPTED)
        # Samo zlecenie mieści się w limitach (6000 <= 10000, łączna ilość 10 <= 10),
        # ale cała pozycja po nowej cenie już nie: 10 * 1200 = 12000.
        self.assertEqual("position_limit_exceeded",
                         self.blocker(lambda: self.submit(order("INTENT-L2", quantity="5", price="1200"))))
        self.assertEqual({"BTCUSD": "5"}, self.position())

    def test_order_that_reduces_position_is_accepted_at_the_limit(self) -> None:
        self.assertIs(self.submit(order("INTENT-FULL", quantity="10", price="1000")), ExecutionResultState.ACCEPTED)
        self.assertEqual("position_limit_exceeded",
                         self.blocker(lambda: self.submit(order("INTENT-MORE", quantity="1", price="1000"))))
        self.assertIs(self.submit(order("INTENT-LESS", side="sell", quantity="4", price="1000")),
                      ExecutionResultState.ACCEPTED)
        self.assertEqual({"BTCUSD": "6"}, self.position())

    def test_sell_beyond_position_needs_short_permission_in_mandate(self) -> None:
        self.assertIs(self.submit(order("INTENT-LONG", quantity="2")), ExecutionResultState.ACCEPTED)
        self.assertEqual("short_position_not_allowed",
                         self.blocker(lambda: self.submit(order("INTENT-SHORT", side="sell", quantity="3"))))
        self.assertEqual({"BTCUSD": "2"}, self.position())


if __name__ == "__main__":
    unittest.main()
