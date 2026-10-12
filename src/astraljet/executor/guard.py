from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from astraljet.domain.enums import RiskDecisionStatus
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.validation import new_record_id
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.event_store import Event, EventStore

from .ports import FrozenContext, Heartbeat, KillSwitchReceipt, Lease, OrderIntent


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValidationError("Czas wykonawcy musi mieć jawną strefę UTC.")
    return value.astimezone(timezone.utc)


def _parse(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("Niepoprawny czas ISO-8601 w kontekście wykonawcy.") from exc
    return _utc(result)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _blocked(message: str, code: str, action: str) -> DomainBlockedError:
    return DomainBlockedError(
        message,
        blocker=code,
        owner="Wykonawca AstralJet",
        allowed_next_action=action,
    )


class ExecutorGuard:
    def __init__(self, database: Database) -> None:
        self.database = database

    def audit_event(
        self,
        *,
        event_type: str,
        outcome: str,
        actor: str,
        reason: str,
        payload: dict[str, object],
        idempotency_key: str | None = None,
        connection: object | None = None,
    ) -> None:
        event = Event.create(
            actor=actor,
            event_type=event_type,
            record_type="SYSTEM",
            record_id="SYSTEM-EXECUTOR",
            record_version=1,
            reason=reason,
            outcome=outcome,
            payload=payload,
            correlation_id=new_record_id("CORR"),
            idempotency_key=idempotency_key or new_record_id("IDEM"),
        )
        if connection is not None:
            EventStore.insert(connection, event)
            return
        with self.database.transaction() as owned_connection:
            EventStore.insert(owned_connection, event)

    def _denial(
        self,
        message: str,
        code: str,
        action: str,
        *,
        environment_id: str,
        actor: str,
    ) -> DomainBlockedError:
        error = _blocked(message, code, action)
        self.audit_event(
            event_type="executor.blocked",
            outcome="blocked",
            actor=actor or "unknown-worker",
            reason=message,
            payload={
                "environment_id": environment_id,
                "blocker": error.blocker,
                "owner": error.owner,
                "allowed_next_action": error.allowed_next_action,
            },
        )
        return error

    def deny_execution(
        self,
        message: str,
        code: str,
        action: str,
        *,
        environment_id: str,
        actor: str,
    ) -> DomainBlockedError:
        """Zapisz odmowę wykonawcy i zwróć błąd do podniesienia przez adapter."""
        return self._denial(
            message,
            code,
            action,
            environment_id=environment_id,
            actor=actor,
        )

    def acquire_lease(
        self,
        environment_id: str,
        worker_id: str,
        *,
        ttl_seconds: int,
        now: datetime,
    ) -> Lease:
        moment = _utc(now)
        if not environment_id.strip() or not worker_id.strip() or ttl_seconds <= 0:
            raise ValidationError("Lease wymaga środowiska, wykonawcy i dodatniego TTL.")
        conflict = False
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM executor_leases WHERE environment_id = ?",
                (environment_id,),
            ).fetchone()
            if row and _parse(row["expires_at"]) > moment and row["worker_id"] != worker_id:
                conflict = True
            else:
                lease_id = row["lease_id"] if row and row["worker_id"] == worker_id else new_record_id("LEASE")
                expires_at = _iso(moment + timedelta(seconds=ttl_seconds))
                heartbeat_at = _iso(moment)
                connection.execute(
                    """
                    INSERT INTO executor_leases(environment_id, lease_id, worker_id, expires_at, heartbeat_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(environment_id) DO UPDATE SET
                        lease_id = excluded.lease_id,
                        worker_id = excluded.worker_id,
                        expires_at = excluded.expires_at,
                        heartbeat_at = excluded.heartbeat_at
                    """,
                    (environment_id, lease_id, worker_id, expires_at, heartbeat_at),
                )
        if conflict:
            raise self._denial(
                "Środowisko ma już aktywny lease innego wykonawcy.",
                "exclusive_lease_conflict",
                "Poczekaj na wygaśnięcie lease albo zatrzymaj poprzedniego wykonawcę.",
                environment_id=environment_id,
                actor=worker_id,
            )
        self.audit_event(
            event_type="executor.lease_acquired",
            outcome="active",
            actor=worker_id,
            reason="Uzyskano wyłączny lease wykonawcy.",
            payload={"environment_id": environment_id, "lease_id": lease_id, "expires_at": expires_at},
        )
        return Lease(environment_id, lease_id, worker_id, expires_at, heartbeat_at)

    def heartbeat(self, lease_id: str, worker_id: str, *, now: datetime) -> Heartbeat:
        moment = _utc(now)
        invalid = False
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM executor_leases WHERE lease_id = ?",
                (lease_id,),
            ).fetchone()
            if not row or row["worker_id"] != worker_id or _parse(row["expires_at"]) <= moment:
                invalid = True
            else:
                previous_heartbeat = _parse(row["heartbeat_at"])
                ttl = max(_parse(row["expires_at"]) - previous_heartbeat, timedelta(seconds=1))
                expires_at = _iso(moment + ttl)
                heartbeat_at = _iso(moment)
                connection.execute(
                    "UPDATE executor_leases SET expires_at = ?, heartbeat_at = ? WHERE lease_id = ?",
                    (expires_at, heartbeat_at, lease_id),
                )
        if invalid:
            raise self._denial(
                "Heartbeat nie pasuje do aktywnego lease.",
                "heartbeat_without_active_lease",
                "Uzyskaj nowy wyłączny lease.",
                environment_id="unknown",
                actor=worker_id,
            )
        self.audit_event(
            event_type="executor.heartbeat",
            outcome="active",
            actor=worker_id,
            reason="Odświeżono heartbeat aktywnego lease.",
            payload={"environment_id": row["environment_id"], "lease_id": lease_id, "expires_at": expires_at},
        )
        return Heartbeat(row["environment_id"], lease_id, worker_id, expires_at, heartbeat_at)

    def activate_kill_switch(
        self,
        environment_id: str,
        *,
        reason: str,
        idempotency_key: str,
        now: datetime,
    ) -> KillSwitchReceipt:
        if not reason.strip() or len(idempotency_key) < 8:
            raise ValidationError("Kill switch wymaga przyczyny i klucza idempotencji.")
        activated_at = _iso(_utc(now))
        with self.database.transaction() as connection:
            duplicate = connection.execute(
                "SELECT * FROM kill_switches WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if duplicate:
                return KillSwitchReceipt(
                    duplicate["environment_id"], bool(duplicate["active"]), duplicate["reason"],
                    duplicate["activated_at"], True,
                )
            connection.execute(
                """
                INSERT INTO kill_switches(environment_id, active, reason, activated_at, idempotency_key)
                VALUES (?, 1, ?, ?, ?)
                ON CONFLICT(environment_id) DO UPDATE SET
                    active = 1,
                    reason = excluded.reason,
                    activated_at = excluded.activated_at,
                    idempotency_key = excluded.idempotency_key
                """,
                (environment_id, reason, activated_at, idempotency_key),
            )
        self.audit_event(
            event_type="executor.kill_switch_activated",
            outcome="blocked",
            actor="operator",
            reason=reason,
            payload={"environment_id": environment_id, "active": True},
            idempotency_key=f"executor-event:{idempotency_key}",
        )
        return KillSwitchReceipt(environment_id, True, reason, activated_at)

    def authorize(self, *, context: FrozenContext, intent: OrderIntent, now: datetime) -> None:
        moment = _utc(now)
        mandate = context.mandate
        risk = context.risk_decision
        def deny(message: str, code: str, action: str) -> DomainBlockedError:
            return self._denial(
                message,
                code,
                action,
                environment_id=context.environment_id,
                actor=context.worker_id,
            )

        if risk.record_id != mandate.risk_decision_id or risk.decision is not RiskDecisionStatus.ALLOWED:
            raise deny("RISK-DECISION nie zezwala na wykonanie.", "risk_not_allowed", "Zatrzymaj wykonawcę.")
        if moment < _parse(risk.valid_from) or moment >= _parse(risk.valid_until):
            raise deny("RISK-DECISION nie jest aktualnie ważna.", "risk_expired", "Uzyskaj nową decyzję ryzyka.")
        if moment < _parse(mandate.starts_at) or moment >= _parse(mandate.expires_at):
            raise deny("MANDATE nie jest aktualnie ważny.", "mandate_expired", "Uzyskaj nowy mandat.")
        if mandate.authorized_by.strip().casefold() != "karol":
            raise deny("Brak autoryzacji Karola.", "authorization_missing", "Uzyskaj zgodę Karola.")
        if (
            context.strategy_id != mandate.strategy_id
            or context.strategy_version != mandate.strategy_version
            or context.code_hash != mandate.code_hash
        ):
            raise deny("Zamrożona strategia lub kod nie zgadza się z mandatem.", "frozen_context_mismatch", "Odtwórz kontekst z mandatu.")
        if context.environment is not mandate.environment or context.environment_id != mandate.environment_id:
            raise deny("Środowisko nie zgadza się z mandatem.", "environment_mismatch", "Użyj środowiska z mandatu.")
        if intent.instrument not in mandate.instruments or intent.side not in {"buy", "sell"}:
            raise deny("Instrument lub strona zlecenia nie są dozwolone.", "intent_not_allowed", "Odrzuć intencję.")
        if not intent.intent_id.strip() or not intent.signal_id.strip():
            raise deny("ORDER-INTENT wymaga identyfikatora intencji i sygnału.", "intent_identity_missing", "Odrzuć intencję.")
        if (
            not intent.quantity.is_finite()
            or not intent.reference_price.is_finite()
            or intent.quantity <= 0
            or intent.reference_price <= 0
        ):
            raise deny("Ilość i cena referencyjna muszą być dodatnie.", "invalid_order_values", "Popraw ORDER-INTENT.")
        age = moment - _parse(context.data_observed_at)
        if age < timedelta(0) or age > timedelta(seconds=mandate.max_data_age_seconds):
            raise deny("Dane są nieświeże albo pochodzą z przyszłości.", "stale_data", "Odśwież dane i sygnał.")
        try:
            max_notional = Decimal(str(mandate.limits["max_notional"]))
            max_quantity = Decimal(str(mandate.limits.get("max_position_quantity", max_notional)))
        except (KeyError, InvalidOperation, TypeError) as exc:
            raise deny("Limity mandatu są niepełne.", "invalid_limits", "Uzupełnij mandat.") from exc
        if (
            not max_notional.is_finite()
            or not max_quantity.is_finite()
            or max_notional <= 0
            or max_quantity <= 0
        ):
            raise deny("Limity mandatu są niepoprawne.", "invalid_limits", "Uzupełnij mandat.")
        if intent.quantity * intent.reference_price > max_notional or intent.quantity > max_quantity:
            raise deny("ORDER-INTENT przekracza limity mandatu.", "limit_exceeded", "Zmniejsz intencję.")

        with self.database.connect() as connection:
            lease = connection.execute(
                "SELECT * FROM executor_leases WHERE environment_id = ?",
                (context.environment_id,),
            ).fetchone()
            kill = connection.execute(
                "SELECT active FROM kill_switches WHERE environment_id = ?",
                (context.environment_id,),
            ).fetchone()
            uncertain = connection.execute(
                "SELECT 1 FROM execution_intents WHERE environment_id = ? AND state = 'uncertain' LIMIT 1",
                (context.environment_id,),
            ).fetchone()
        if (
            not lease
            or lease["lease_id"] != context.lease_id
            or lease["worker_id"] != context.worker_id
            or _parse(lease["expires_at"]) <= moment
        ):
            raise deny("Brak aktywnego lease i świeżego heartbeat.", "lease_inactive", "Uzyskaj lub odśwież lease.")
        if kill and bool(kill["active"]):
            raise deny("Kill switch jest aktywny.", "kill_switch_active", "Nie twórz nowego ryzyka.")
        if uncertain:
            raise deny("Istnieje nierozstrzygnięta realizacja.", "unresolved_execution", "Wykonaj reconciliation.")
