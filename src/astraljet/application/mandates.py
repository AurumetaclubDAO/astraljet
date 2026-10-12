from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from astraljet.application.reviews import review_evidence_verified
from astraljet.domain.enums import (
    ExecutionEnvironment,
    IncubationStatus,
    ReviewVerdict,
    RiskDecisionStatus,
    TechnicalStatus,
)
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.records import (
    IncubationRecord,
    MandateRecord,
    ReviewRecord,
    RiskDecisionRecord,
    record_content_hash,
)
from astraljet.domain.validation import new_record_id, utc_now, validate_sha256, validate_utc


@dataclass(frozen=True, slots=True)
class RiskDecisionRequest:
    requested_decision: RiskDecisionStatus
    scope: str
    valid_from: str
    valid_until: str
    limits: dict[str, object]
    rationale: str
    permitted_next_step: str


@dataclass(frozen=True, slots=True)
class MandateRequest:
    authorized_by: str
    strategy_id: str
    strategy_version: int
    code_hash: str
    environment: ExecutionEnvironment
    environment_id: str
    account_id: str | None
    instruments: tuple[str, ...]
    limits: dict[str, object]
    starts_at: str
    expires_at: str
    stop_conditions: tuple[str, ...]
    max_data_age_seconds: int


def _as_datetime(value: str) -> datetime:
    validate_utc(value)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _limits_within(asked: dict[str, object], allowed: dict[str, object]) -> bool:
    """Brak lub nieporównywalna granica oznacza blokadę, nigdy domysł."""
    try:
        for name, value in asked.items():
            if name not in allowed or Decimal(str(value)) > Decimal(str(allowed[name])):
                return False
    except (InvalidOperation, ValueError, TypeError):
        return False
    return bool(asked)


def create_risk_decision(
    *,
    review: ReviewRecord,
    request: RiskDecisionRequest,
    owner: str,
) -> RiskDecisionRecord:
    validate_utc(request.valid_from)
    validate_utc(request.valid_until)
    if request.valid_from >= request.valid_until:
        raise ValidationError("RISK-DECISION wymaga valid_until po valid_from.")
    if not request.scope.strip() or not request.rationale.strip() or not request.permitted_next_step.strip():
        raise ValidationError("RISK-DECISION wymaga zakresu, uzasadnienia i następnego kroku.")

    blockers: list[str] = []
    if review.verdict is not ReviewVerdict.VERIFIED:
        blockers.append("review_not_verified")
    if not review_evidence_verified(review):
        blockers.append('review_evidence_not_verified')
    if not request.limits:
        blockers.append("missing_limits")
    decision = (
        RiskDecisionStatus.ALLOWED
        if request.requested_decision is RiskDecisionStatus.ALLOWED and not blockers
        else RiskDecisionStatus.BLOCKED
    )
    now = utc_now()
    payload = {
        "review_id": review.record_id,
        **asdict(request),
        "decision": decision.value,
        "blockers": tuple(blockers),
    }
    return RiskDecisionRecord(
        record_id=new_record_id("RISK_DECISION"),
        version=1,
        owner=owner,
        created_at=now,
        technical_status=TechnicalStatus.COMPLETED,
        content_hash=record_content_hash(payload),
        limitations=(
            "Decyzja ryzyka dotyczy wyłącznie zapisanego zakresu i czasu.",
            "RISK-DECISION nie jest mandatem ani uprawnieniem do REAL.",
        ),
        review_id=review.record_id,
        scope=request.scope,
        valid_from=request.valid_from,
        valid_until=request.valid_until,
        limits=request.limits,
        decision=decision,
        rationale=request.rationale,
        permitted_next_step=request.permitted_next_step,
        blockers=tuple(blockers),
    )


def create_mandate(
    *,
    risk_decision: RiskDecisionRecord,
    request: MandateRequest,
    owner: str,
) -> MandateRecord:
    if risk_decision.decision is not RiskDecisionStatus.ALLOWED or risk_decision.blockers:
        raise DomainBlockedError(
            "Mandat wymaga jednoznacznie dozwolonej RISK-DECISION.",
            blocker="risk_decision_not_allowed",
            owner="AJ-09",
            allowed_next_action="Uzyskaj zweryfikowaną, datowaną decyzję ryzyka.",
        )
    if request.authorized_by.strip().casefold() != "karol":
        raise DomainBlockedError(
            "MANDATE musi być autoryzowany przez Karola.",
            blocker="missing_owner_authorization",
            owner="Karol",
            allowed_next_action="Uzyskaj jawną zgodę Karola na konkretny mandat.",
        )
    if not isinstance(request.environment, ExecutionEnvironment):
        raise ValidationError("Nieznane środowisko wykonawcze.")
    if request.environment is ExecutionEnvironment.BROKER_DEMO and not request.account_id:
        raise DomainBlockedError(
            "BROKER_DEMO wymaga jawnego identyfikatora demo account.",
            blocker="demo_account_missing",
            owner="Karol",
            allowed_next_action="Wskaż i potwierdź rachunek demonstracyjny.",
        )
    if request.environment is ExecutionEnvironment.PAPER_CONTINUOUS and request.account_id:
        raise ValidationError("PAPER_CONTINUOUS nie przyjmuje identyfikatora rachunku brokera.")
    starts_at = _as_datetime(request.starts_at)
    expires_at = _as_datetime(request.expires_at)
    risk_from = _as_datetime(risk_decision.valid_from)
    risk_until = _as_datetime(risk_decision.valid_until)
    if starts_at >= expires_at:
        raise ValidationError("MANDATE wymaga expires_at po starts_at.")
    if starts_at < risk_from or expires_at > risk_until:
        raise DomainBlockedError(
            "Okres MANDATE wykracza poza ważność RISK-DECISION.",
            blocker="mandate_outside_risk_window",
            owner="AJ-09",
            allowed_next_action="Ogranicz daty mandatu do okresu decyzji ryzyka.",
        )
    validate_sha256(request.code_hash)
    if not request.strategy_id.startswith("STRAT-") or request.strategy_version < 1:
        raise ValidationError("MANDATE wymaga konkretnej wersji STRAT.")
    if not request.environment_id.strip() or not request.instruments:
        raise ValidationError("MANDATE wymaga środowiska i co najmniej jednego instrumentu.")
    if not request.stop_conditions or request.max_data_age_seconds <= 0:
        raise ValidationError("MANDATE wymaga warunków zatrzymania i limitu wieku danych.")
    if not _limits_within(request.limits, risk_decision.limits):
        raise DomainBlockedError(
            "Limity MANDATE nie mieszczą się w RISK-DECISION.",
            blocker="mandate_limits_exceed_risk",
            owner="AJ-09",
            allowed_next_action="Zmniejsz limity lub uzyskaj nową decyzję ryzyka.",
        )

    payload = {
        "risk_decision_id": risk_decision.record_id,
        **asdict(request),
    }
    return MandateRecord(
        record_id=new_record_id("MANDATE"),
        version=1,
        owner=owner,
        created_at=utc_now(),
        technical_status=TechnicalStatus.COMPLETED,
        content_hash=record_content_hash(payload),
        limitations=(
            "Mandat obejmuje wyłącznie PAPER_CONTINUOUS albo BROKER_DEMO.",
            "Mandat nie daje możliwości wykonania zleceń REAL.",
        ),
        risk_decision_id=risk_decision.record_id,
        authorized_by=request.authorized_by,
        strategy_id=request.strategy_id,
        strategy_version=request.strategy_version,
        code_hash=request.code_hash,
        environment=request.environment,
        environment_id=request.environment_id,
        account_id=request.account_id,
        instruments=request.instruments,
        limits=request.limits,
        starts_at=request.starts_at,
        expires_at=request.expires_at,
        stop_conditions=request.stop_conditions,
        max_data_age_seconds=request.max_data_age_seconds,
    )


def create_incubation(
    *,
    mandate: MandateRecord,
    lease_id: str,
    worker_id: str,
    last_heartbeat_at: str,
    status: IncubationStatus,
    owner: str,
    alerts: tuple[str, ...] = (),
) -> IncubationRecord:
    validate_utc(last_heartbeat_at)
    payload = {
        "mandate_id": mandate.record_id,
        "environment": mandate.environment,
        "environment_id": mandate.environment_id,
        "lease_id": lease_id,
        "worker_id": worker_id,
        "incubation_status": status,
        "last_heartbeat_at": last_heartbeat_at,
        "open_intents": 1 if status is IncubationStatus.UNCERTAIN else 0,
        "position_count": 0,
        "alerts": alerts,
    }
    return IncubationRecord(
        record_id=new_record_id("INCU"),
        version=1,
        owner=owner,
        created_at=utc_now(),
        technical_status=(
            TechnicalStatus.BLOCKED if status is IncubationStatus.UNCERTAIN else TechnicalStatus.RUNNING
        ),
        content_hash=record_content_hash(payload),
        limitations=(
            "INCU opisuje lokalny stan wykonawcy, nie rachunek REAL.",
            "BROKER_DEMO jest adapterem testowym bez sekretów i sieci.",
        ),
        **payload,
    )
