from __future__ import annotations

from datetime import datetime

from astraljet.domain.enums import ExecutionEnvironment, ExecutionResultState
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.validation import canonical_json
from astraljet.infrastructure.database import Database

from .guard import ExecutorGuard, _iso
from .paper import _receipt_from_row
from .ports import ExecutionReceipt, FrozenContext, Health, OrderIntent, PositionSnapshot


class DemoAdapter:
    """Bezpieczny adapter testowy. Nie zawiera klienta brokera ani sekretów."""

    def __init__(
        self,
        database: Database,
        guard: ExecutorGuard,
        *,
        confirmed_demo_account: str | None,
        simulate_next_uncertain: bool = False,
    ) -> None:
        self.database = database
        self.guard = guard
        self.confirmed_demo_account = confirmed_demo_account
        self.simulate_next_uncertain = simulate_next_uncertain
        self._reconciliation_results: dict[str, ExecutionResultState] = {}

    def health(self, mandate: object) -> Health:
        if mandate.environment is not ExecutionEnvironment.BROKER_DEMO:
            return Health(ExecutionResultState.REJECTED, "Mandat nie dotyczy BROKER_DEMO.")
        if not self.confirmed_demo_account or self.confirmed_demo_account != mandate.account_id:
            return Health(ExecutionResultState.REJECTED, "Demo account nie został jawnie potwierdzony.")
        return Health(ExecutionResultState.ACCEPTED, "BROKER_DEMO potwierdzony; adapter testowy gotowy.")

    def submit_intent(
        self,
        context: FrozenContext,
        intent: OrderIntent,
        *,
        idempotency_key: str,
        now: datetime,
    ) -> ExecutionReceipt:
        if len(idempotency_key) < 8:
            raise ValidationError("Klucz idempotencji intencji jest za krótki.")
        with self.database.connect() as connection:
            duplicate = connection.execute(
                "SELECT * FROM execution_intents WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        if duplicate:
            return _receipt_from_row(duplicate)
        health = self.health(context.mandate)
        if health.state is not ExecutionResultState.ACCEPTED:
            return ExecutionReceipt(health.state, intent.intent_id, None, health.message)
        self.guard.authorize(context=context, intent=intent, now=now)
        state = ExecutionResultState.UNCERTAIN if self.simulate_next_uncertain else ExecutionResultState.ACCEPTED
        self.simulate_next_uncertain = False
        external_reference = f"DEMO-{intent.intent_id}"
        created_at = _iso(now)
        denial: tuple[str, str, str] | None = None
        with self.database.transaction() as connection:
            duplicate = connection.execute(
                "SELECT * FROM execution_intents WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if duplicate:
                return _receipt_from_row(duplicate)
            claimed = connection.execute(
                "SELECT intent_id FROM execution_signal_claims WHERE environment_id = ? AND signal_id = ?",
                (context.environment_id, intent.signal_id),
            ).fetchone()
            if claimed:
                denial = (
                    "Ten sygnał został już wykorzystany w tym środowisku.",
                    "duplicate_signal",
                    "Nie wykonuj sygnału ponownie; utwórz nowy sygnał z nową przyczyną.",
                )
            else:
                connection.execute(
                    """
                    INSERT INTO execution_signal_claims(
                        environment_id, signal_id, intent_id, idempotency_key, claimed_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        context.environment_id,
                        intent.signal_id,
                        intent.intent_id,
                        idempotency_key,
                        created_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO execution_intents(
                        idempotency_key, intent_id, environment_id, mandate_id, state,
                        external_reference, payload_json, response_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        idempotency_key, intent.intent_id, context.environment_id,
                        context.mandate.record_id, state.value, external_reference,
                        canonical_json(intent), canonical_json({"adapter": "test_only"}),
                        created_at, created_at,
                    ),
                )
                self.guard.audit_event(
                    event_type=(
                        "executor.demo_uncertain"
                        if state is ExecutionResultState.UNCERTAIN
                        else "executor.demo_accepted"
                    ),
                    outcome=state.value,
                    actor=context.worker_id,
                    reason="Zapisano wynik testowego adaptera BROKER_DEMO.",
                    payload={
                        "environment_id": context.environment_id,
                        "mandate_id": context.mandate.record_id,
                        "intent_id": intent.intent_id,
                        "signal_id": intent.signal_id,
                        "external_reference": external_reference,
                    },
                    idempotency_key=f"executor-event:{idempotency_key}",
                    connection=connection,
                )
        if denial:
            raise self.guard.deny_execution(
                denial[0],
                denial[1],
                denial[2],
                environment_id=context.environment_id,
                actor=context.worker_id,
            )
        message = "Wynik adaptera DEMO wymaga reconciliation." if state is ExecutionResultState.UNCERTAIN else "Adapter DEMO potwierdził przyjęcie."
        return ExecutionReceipt(state, intent.intent_id, external_reference, message)

    def set_reconciliation_result(self, external_reference: str | None, state: ExecutionResultState) -> None:
        if not external_reference or state not in {ExecutionResultState.ACCEPTED, ExecutionResultState.REJECTED}:
            raise ValidationError("Reconciliation wymaga referencji i rozstrzygniętego stanu.")
        self._reconciliation_results[external_reference] = state

    def reconcile(
        self,
        external_reference: str | None,
        *,
        idempotency_key: str,
        now: datetime,
    ) -> ExecutionReceipt:
        if not external_reference or len(idempotency_key) < 8:
            raise ValidationError("Reconciliation wymaga referencji i klucza idempotencji.")
        with self.database.transaction() as connection:
            duplicate = connection.execute(
                "SELECT * FROM execution_reconciliations WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            row = connection.execute(
                "SELECT * FROM execution_intents WHERE external_reference = ?",
                (external_reference,),
            ).fetchone()
            if not row:
                raise ValidationError("Nie znaleziono zewnętrznej referencji DEMO.")
            if duplicate:
                return ExecutionReceipt(
                    ExecutionResultState.DUPLICATE, row["intent_id"], external_reference,
                    "Duplikat reconciliation.", ExecutionResultState(duplicate["result_state"]),
                )
            result = self._reconciliation_results.get(external_reference)
            if result not in {ExecutionResultState.ACCEPTED, ExecutionResultState.REJECTED}:
                raise DomainBlockedError(
                    "Stan realizacji pozostaje nieznany.",
                    blocker="reconciliation_unresolved",
                    owner="Wykonawca AstralJet",
                    allowed_next_action="Sprawdź stan w rachunku DEMO i ponów reconciliation.",
                )
            stamp = _iso(now)
            connection.execute(
                "UPDATE execution_intents SET state = ?, updated_at = ? WHERE external_reference = ?",
                (result.value, stamp, external_reference),
            )
            connection.execute(
                "INSERT INTO execution_reconciliations(idempotency_key, external_reference, result_state, reconciled_at) VALUES (?, ?, ?, ?)",
                (idempotency_key, external_reference, result.value, stamp),
            )
            self.guard.audit_event(
                event_type="executor.demo_reconciled",
                outcome=result.value,
                actor="reconciler",
                reason="Rozstrzygnięto wcześniejszy stan uncertain.",
                payload={"external_reference": external_reference, "intent_id": row["intent_id"]},
                idempotency_key=f"executor-event:{idempotency_key}",
                connection=connection,
            )
        return ExecutionReceipt(result, row["intent_id"], external_reference, "Reconciliation rozstrzygnięte.")

    def positions(self, environment_id: str) -> PositionSnapshot:
        return PositionSnapshot(environment_id, {})
