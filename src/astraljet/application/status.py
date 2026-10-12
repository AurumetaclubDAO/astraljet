from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from astraljet.application.reviews import review_evidence_verified
from astraljet.domain.enums import IncubationStatus, TechnicalStatus
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.records import BudgetStatusRecord, record_content_hash
from astraljet.domain.validation import canonical_json, new_record_id, sha256_text, utc_now
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.repositories import RecordRepository


CHAIN = (
    "SRC",
    "CAND",
    "STRAT",
    "DATA",
    "EXP",
    "RUN",
    "REVIEW",
    "RISK_DECISION",
    "MANDATE",
    "INCU",
)


@dataclass(frozen=True, slots=True)
class BudgetStatusRequest:
    currency: str
    limit: str
    settled_cost: str
    active_reservation: str
    unresolved_cost: str
    scope: str


def _decimal(value: str, name: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"{name} musi być liczbą dziesiętną.") from exc
    if not result.is_finite() or result < 0:
        raise ValidationError(f"{name} musi być skończoną wartością nieujemną.")
    return result


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def create_budget_status(request: BudgetStatusRequest, *, owner: str) -> BudgetStatusRecord:
    limit = _decimal(request.limit, "limit")
    settled = _decimal(request.settled_cost, "settled_cost")
    reserved = _decimal(request.active_reservation, "active_reservation")
    unresolved = _decimal(request.unresolved_cost, "unresolved_cost")
    available = limit - settled - reserved - unresolved
    if not request.currency.strip() or not request.scope.strip():
        raise ValidationError("BUDGET-STATUS wymaga waluty i zakresu.")
    if available < 0:
        raise DomainBlockedError(
            "Koszty i rezerwacje przekraczają limit budżetu.",
            blocker="budget_exceeded",
            owner=owner,
            allowed_next_action="Rozlicz koszty albo jawnie zwiększ limit.",
        )
    payload = {
        "currency": request.currency,
        "limit_amount": _decimal_text(limit),
        "settled_cost": _decimal_text(settled),
        "active_reservation": _decimal_text(reserved),
        "unresolved_cost": _decimal_text(unresolved),
        "available_amount": _decimal_text(available),
        "scope": request.scope,
    }
    return BudgetStatusRecord(
        record_id=new_record_id("BUDGET_STATUS"),
        version=1,
        owner=owner,
        created_at=utc_now(),
        technical_status=TechnicalStatus.COMPLETED,
        content_hash=record_content_hash(payload),
        limitations=(
            "Koszt nierozstrzygnięty zmniejsza dostępny budżet do czasu rozliczenia.",
        ),
        **payload,
    )


def authorize_cost(budget: BudgetStatusRecord, amount: str) -> None:
    requested = _decimal(amount, "amount")
    available = _decimal(budget.available_amount, "available_amount")
    if requested > available:
        raise DomainBlockedError(
            "Operacja przekracza dostępny budżet.",
            blocker="budget_limit_exhausted",
            owner=budget.owner,
            allowed_next_action="Zmniejsz koszt, rozlicz rezerwację lub zatwierdź nowy limit.",
        )


def build_status(database: Database) -> dict[str, Any]:
    repository = RecordRepository(database)
    latest_by_type: dict[str, list[object]] = {
        record_type: repository.list_by_type(record_type)
        for record_type in (*CHAIN, "BUDGET_STATUS")
    }
    artifacts = [
        record.record_id
        for record_type in (*CHAIN, "BUDGET_STATUS")
        for record in latest_by_type[record_type]
    ]
    latest_type = next((name for name in reversed(CHAIN) if latest_by_type[name]), None)
    if latest_type is None:
        object_id = "unknown"
        stage = "unknown"
        result = "unknown"
        blocker = "source_missing"
        owner = "Karol"
        next_action = "Zarejestruj jawnie wskazane źródło poleceniem source add."
        blocking_details: list[str] = []
    else:
        record = latest_by_type[latest_type][-1]
        object_id = record.record_id
        stage = latest_type
        result = record.technical_status.value
        for status_field in (
            "incubation_status",
            "decision",
            "verdict",
            "run_outcome",
            "data_status",
            "strategy_status",
            "candidate_status",
            "trust_status",
        ):
            domain_status = getattr(record, status_field, None)
            if domain_status is not None:
                result = domain_status.value
                break
        blocker = "none"
        owner = record.owner
        blocking_details = [
            limitation
            for limitation in record.limitations
            if limitation.startswith("Brak/blokada:")
        ]
        next_map = {
            "SRC": "Zarejestruj kandydatów CAND.",
            "CAND": "Sformalizuj jednoznaczną STRAT.",
            "STRAT": "Zatwierdź DATA i zamroź EXP.",
            "DATA": "Zamroź EXP przed wynikiem.",
            "EXP": "Wykonaj i odtwórz RUN.",
            "RUN": "Przekaż komplet RUN do niezależnego REVIEW.",
            "REVIEW": "Uzyskaj datowaną RISK-DECISION.",
            "RISK_DECISION": "Uzyskaj jawny MANDATE Karola.",
            "MANDATE": "Uruchom wyłącznie PAPER_CONTINUOUS albo BROKER_DEMO.",
            "INCU": "Monitoruj heartbeat, limity, pozycje i reconciliation.",
        }
        next_action = next_map[latest_type]
        if latest_type == 'REVIEW' and record.verdict.value != 'verified':
            blocker = 'review_not_verified'
            blocking_details = list(record.missing_evidence) + list(record.findings if record.verdict.value == 'rejected' else ())
            next_action = 'Uzupełnij dowody REVIEW albo rozstrzygnij odrzucenie; nie przechodź do mandatu.'
        elif latest_type == 'REVIEW' and not review_evidence_verified(record):
            blocker = 'review_evidence_not_verified'
            blocking_details = ['Brak kompletnego, spójnego pakietu weryfikacji REVIEW.']
            next_action = 'Zachowaj historię i utwórz nową ocenę z dowodami; nie przechodź do mandatu.'
        elif latest_type == 'RISK_DECISION' and record.decision.value != 'allowed':
            blocker = 'risk_not_allowed'
            blocking_details = list(record.blockers)
            next_action = 'Rozstrzygnij zapisane blokady RISK-DECISION; nie twórz mandatu.'
        elif latest_type == "INCU" and record.incubation_status is IncubationStatus.UNCERTAIN:
            result = "uncertain"
            blocker = "reconciliation_required"
            owner = "Wykonawca AstralJet"
            next_action = "Wykonaj reconciliation; do tego czasu nie twórz nowego ryzyka."
        elif record.technical_status is TechnicalStatus.BLOCKED:
            blocked_projection = {
                "CAND": (
                    "candidate_needs_input",
                    "Rozstrzygnij brakujące decyzje CAND i dopiero wtedy formalizuj STRAT.",
                ),
                "STRAT": (
                    "strategy_needs_input",
                    "Uzupełnij blokery STRAT; nie przechodź do ocenianego DATA/EXP.",
                ),
                "DATA": (
                    "data_not_ready",
                    "Napraw jakość lub kompletność DATA przed zamrożeniem EXP.",
                ),
                "EXP": (
                    "experiment_blocked",
                    "Uzupełnij plan i zamroź nową wersję EXP przed uruchomieniem RUN.",
                ),
                "RUN": (
                    "run_blocked",
                    "Usuń błąd techniczny albo utwórz nowy RUN bez zmiany zamrożonego planu.",
                ),
                "REVIEW": (
                    "review_not_verified",
                    "Uzupełnij dowody wymagane przez niezależny REVIEW.",
                ),
                "RISK_DECISION": (
                    "risk_not_allowed",
                    "Nie twórz mandatu; spełnij blokery RISK-DECISION.",
                ),
                "MANDATE": (
                    "mandate_blocked",
                    "Nie uruchamiaj Wykonawcy; uzyskaj poprawny, datowany mandat.",
                ),
                "INCU": (
                    "incubation_blocked",
                    "Nie twórz nowego ryzyka; rozstrzygnij alarm inkubacji.",
                ),
            }
            blocker, next_action = blocked_projection.get(
                latest_type,
                ("record_blocked", "Rozstrzygnij blokadę bieżącego rekordu."),
            )

    budgets = latest_by_type["BUDGET_STATUS"]
    if budgets:
        budget_record = budgets[-1]
        budget: dict[str, Any] = {
            "currency": budget_record.currency,
            "limit": budget_record.limit_amount,
            "settled_cost": budget_record.settled_cost,
            "active_reservation": budget_record.active_reservation,
            "unresolved_cost": budget_record.unresolved_cost,
            "available": budget_record.available_amount,
            "scope": budget_record.scope,
        }
    else:
        budget = {
            "currency": "unknown",
            "limit": "unknown",
            "settled_cost": "unknown",
            "active_reservation": "unknown",
            "unresolved_cost": "unknown",
            "available": "unknown",
            "scope": "unknown",
        }
    return {
        "schema_version": 1,
        "object": object_id,
        "stage": stage,
        "result": result,
        "blocker": blocker,
        "owner": owner,
        "artifacts": artifacts,
        "blocking_details": blocking_details,
        "budget": budget,
        "allowed_next_action": next_action,
    }


_REDACT_KEYS = {"locator", "secret", "token", "password", "api_key", "private_source_content"}


def _redact(value: Any, *, key: str | None = None) -> Any:
    if key and (key.casefold() in _REDACT_KEYS or any(part in key.casefold() for part in ("secret", "password", "token", "api_key"))):
        return "[REDACTED_LOCAL_LOCATOR]" if key.casefold() == "locator" else "[REDACTED]"
    if isinstance(value, dict):
        return {name: _redact(item, key=name) for name, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def export_audit(database: Database) -> dict[str, Any]:
    with database.connect() as connection:
        record_rows = connection.execute(
            "SELECT * FROM records ORDER BY created_at, record_id, version"
        ).fetchall()
        event_rows = connection.execute(
            "SELECT * FROM events ORDER BY recorded_at, event_id"
        ).fetchall()
    records: list[dict[str, Any]] = []
    for row in record_rows:
        records.append(
            {
                "record_type": row["record_type"],
                "record_id": row["record_id"],
                "version": row["version"],
                "owner": row["owner"],
                "created_at": row["created_at"],
                "technical_status": row["technical_status"],
                "content_hash": row["content_hash"],
                "limitations": json.loads(row["limitations_json"]),
                "supersedes": row["supersedes"],
                "payload": _redact(json.loads(row["payload_json"])),
            }
        )
    events: list[dict[str, Any]] = []
    for row in event_rows:
        events.append(
            {
                "event_id": row["event_id"],
                "occurred_at": row["occurred_at"],
                "recorded_at": row["recorded_at"],
                "actor": row["actor"],
                "event_type": row["event_type"],
                "record_type": row["record_type"],
                "record_id": row["record_id"],
                "record_version": row["record_version"],
                "reason": row["reason"],
                "outcome": row["outcome"],
                "payload": _redact(json.loads(row["payload_json"])),
                "correlation_id": row["correlation_id"],
                "causation_id": row["causation_id"],
                "idempotency_key": row["idempotency_key"],
            }
        )
    chain = {
        record_type: [
            record["record_id"]
            for record in records
            if record["record_type"] == record_type
            and record["version"] == max(
                candidate["version"]
                for candidate in records
                if candidate["record_id"] == record["record_id"]
            )
        ]
        for record_type in CHAIN
        if any(record["record_type"] == record_type for record in records)
    }
    core = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "chain": chain,
        "records": records,
        "events": events,
        "redactions": ["lokalne locatory", "pola sekretów i tokenów"],
    }
    return {**core, "export_hash": sha256_text(canonical_json(core))}
