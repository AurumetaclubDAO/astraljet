from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from astraljet.domain.enums import ExecutionEnvironment, ExecutionResultState
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.validation import canonical_json
from astraljet.infrastructure.database import Database

from .guard import ExecutorGuard, _iso
from .ports import ExecutionReceipt, FrozenContext, Health, OrderIntent, PositionSnapshot


def _receipt_from_row(row: object) -> ExecutionReceipt:
    return ExecutionReceipt(
        state=ExecutionResultState.DUPLICATE,
        intent_id=row["intent_id"],
        external_reference=row["external_reference"],
        message="Duplikat klucza idempotencji; nie wykonano ponownie.",
        previous_state=ExecutionResultState(row["state"]),
    )


class PaperExecutor:
    def __init__(self, database: Database, guard: ExecutorGuard) -> None:
        self.database = database
        self.guard = guard

    def health(self, mandate: object) -> Health:
        if mandate.environment is not ExecutionEnvironment.PAPER_CONTINUOUS:
            return Health(ExecutionResultState.REJECTED, "Mandat nie dotyczy PAPER_CONTINUOUS.")
        return Health(ExecutionResultState.ACCEPTED, "PAPER_CONTINUOUS gotowy.")

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
        if context.environment is not ExecutionEnvironment.PAPER_CONTINUOUS:
            raise DomainBlockedError("PaperExecutor przyjmuje wyłącznie PAPER_CONTINUOUS.", blocker="wrong_adapter")
        self.guard.authorize(context=context, intent=intent, now=now)
        external_reference = f"PAPER-{intent.intent_id}"
        signed_quantity = intent.quantity if intent.side == "buy" else -intent.quantity
        created_at = _iso(now)
        response = {"fill_price": str(intent.reference_price), "fill_quantity": str(intent.quantity)}
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
                current = connection.execute(
                    "SELECT quantity_text FROM paper_positions WHERE environment_id = ? AND instrument = ?",
                    (context.environment_id, intent.instrument),
                ).fetchone()
                quantity = Decimal(current["quantity_text"]) if current else Decimal("0")
                next_quantity = quantity + signed_quantity
                max_notional = Decimal(str(context.mandate.limits["max_notional"]))
                max_quantity = Decimal(
                    str(context.mandate.limits.get("max_position_quantity", max_notional))
                )
                allow_short = context.mandate.limits.get("allow_short") is True
                if next_quantity < 0 and not allow_short:
                    denial = (
                        "Zlecenie utworzyłoby krótką pozycję bez zgody mandatu.",
                        "short_position_not_allowed",
                        "Zmniejsz sprzedaż do posiadanej ilości albo uzyskaj nowy mandat.",
                    )
                elif (
                    abs(next_quantity) > max_quantity
                    or abs(next_quantity) * intent.reference_price > max_notional
                ):
                    denial = (
                        "Po zleceniu pozycja przekroczyłaby limity mandatu.",
                        "position_limit_exceeded",
                        "Zmniejsz zlecenie lub ekspozycję; nie zwiększaj limitu bez decyzji Karola.",
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
                        ) VALUES (?, ?, ?, ?, 'accepted', ?, ?, ?, ?, ?)
                        """,
                        (
                            idempotency_key, intent.intent_id, context.environment_id,
                            context.mandate.record_id, external_reference, canonical_json(intent),
                            canonical_json(response), created_at, created_at,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO paper_positions(environment_id, instrument, quantity_text, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(environment_id, instrument) DO UPDATE SET
                            quantity_text = excluded.quantity_text,
                            updated_at = excluded.updated_at
                        """,
                        (context.environment_id, intent.instrument, str(next_quantity), created_at),
                    )
                    self.guard.audit_event(
                        event_type="executor.paper_accepted",
                        outcome="accepted",
                        actor=context.worker_id,
                        reason="Trwale zapisano symulowaną realizację PAPER.",
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
        return ExecutionReceipt(
            ExecutionResultState.ACCEPTED,
            intent.intent_id,
            external_reference,
            "Symulowana realizacja PAPER została zapisana trwale.",
        )

    def positions(self, environment_id: str) -> PositionSnapshot:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT instrument, quantity_text FROM paper_positions WHERE environment_id = ? ORDER BY instrument",
                (environment_id,),
            ).fetchall()
        return PositionSnapshot(environment_id, {row["instrument"]: row["quantity_text"] for row in rows})
