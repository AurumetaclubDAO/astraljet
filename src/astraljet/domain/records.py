from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .enums import (
    CandidateStatus,
    DataStatus,
    EvidenceType,
    ExecutionEnvironment,
    IncubationStatus,
    ReviewVerdict,
    RiskDecisionStatus,
    RunOutcome,
    StrategyStatus,
    TechnicalStatus,
    TrustStatus,
)
from .errors import ValidationError
from .validation import canonical_json, sha256_text, validate_sha256, validate_utc


@dataclass(frozen=True, slots=True)
class BaseRecord:
    record_id: str
    version: int
    owner: str
    created_at: str
    technical_status: TechnicalStatus
    content_hash: str
    limitations: tuple[str, ...]
    supersedes: str | None = None

    record_type: str = field(init=False, default="BASE")

    def __post_init__(self) -> None:
        if not self.record_id.startswith(f"{self.record_type}-"):
            raise ValidationError(f"Identyfikator musi zaczynać się od {self.record_type}-.")
        if self.version < 1:
            raise ValidationError("Wersja rekordu musi być >=1.")
        if not self.owner.strip():
            raise ValidationError("Właściciel rekordu nie może być pusty.")
        validate_utc(self.created_at)
        validate_sha256(self.content_hash)
        if not isinstance(self.limitations, tuple):
            raise ValidationError("Ograniczenia muszą być jawną, niezmienną listą.")

    def payload(self) -> dict[str, Any]:
        data = asdict(self)
        for key in (
            "record_id",
            "version",
            "owner",
            "created_at",
            "technical_status",
            "content_hash",
            "limitations",
            "supersedes",
            "record_type",
        ):
            data.pop(key, None)
        return data


@dataclass(frozen=True, slots=True)
class SourceRecord(BaseRecord):
    locator: str = ""
    sha256: str = ""
    size_bytes: int = 0
    observed_at: str = ""
    author: str = "unknown"
    media_type: str = "application/octet-stream"
    trust_status: TrustStatus = TrustStatus.UNVERIFIED

    record_type: str = field(init=False, default="SRC")

    def __post_init__(self) -> None:
        super(SourceRecord, self).__post_init__()
        if not self.locator:
            raise ValidationError("Lokalizator źródła nie może być pusty.")
        validate_sha256(self.sha256)
        validate_utc(self.observed_at)
        if self.size_bytes < 0:
            raise ValidationError("Rozmiar źródła nie może być ujemny.")


@dataclass(frozen=True, slots=True)
class CandidateRecord(BaseRecord):
    title: str = ""
    source_ids: tuple[str, ...] = ()
    thesis: str = ""
    asset_class: str = ""
    market_scope: str = ""
    missing_decisions: tuple[str, ...] = ()
    candidate_status: CandidateStatus = CandidateStatus.UNASSESSED

    record_type: str = field(init=False, default="CAND")

    def __post_init__(self) -> None:
        super(CandidateRecord, self).__post_init__()
        if not self.title.strip() or not self.source_ids:
            raise ValidationError("CAND wymaga tytułu i co najmniej jednego SRC.")


@dataclass(frozen=True, slots=True)
class StrategyRecord(BaseRecord):
    candidate_id: str = ""
    instruments: tuple[str, ...] = ()
    venue: str = ""
    timeframe: str = ""
    signal_timing: str = ""
    execution_timing: str = ""
    entry_rule: str = ""
    exit_rule: str = ""
    sizing_rule: str = ""
    cost_model: str = ""
    constraints: tuple[str, ...] = ()
    missing_data_policy: str = ""
    benchmark: str = ""
    allowed_parameters: dict[str, int | float | str] = field(default_factory=dict)
    source_adaptation: str = ""
    strategy_status: StrategyStatus = StrategyStatus.DRAFT

    record_type: str = field(init=False, default="STRAT")

    def __post_init__(self) -> None:
        super(StrategyRecord, self).__post_init__()
        if not self.candidate_id.startswith("CAND-"):
            raise ValidationError("STRAT wymaga powiązanego CAND.")


@dataclass(frozen=True, slots=True)
class DataRecord(BaseRecord):
    provider: str = ""
    venue: str = ""
    instruments: tuple[str, ...] = ()
    timeframe: str = ""
    timezone: str = "UTC"
    start: str = ""
    end: str = ""
    available_at_rule: str = ""
    locator: str = ""
    sha256: str = ""
    schema_version: str = ""
    transformations: tuple[str, ...] = ()
    cost_model: str = ""
    quality_findings: tuple[str, ...] = ()
    row_count: int = 0
    data_status: DataStatus = DataStatus.UNSUITABLE

    record_type: str = field(init=False, default="DATA")

    def __post_init__(self) -> None:
        super(DataRecord, self).__post_init__()
        validate_sha256(self.sha256)
        if self.timezone != "UTC":
            raise ValidationError("MVP dopuszcza wyłącznie dane zapisane w UTC.")
        if self.row_count < 0:
            raise ValidationError("Liczba wierszy DATA nie może być ujemna.")


@dataclass(frozen=True, slots=True)
class ExperimentRecord(BaseRecord):
    strategy_id: str = ""
    strategy_version: int = 1
    data_id: str = ""
    data_version: int = 1
    code_hash: str = ""
    hypothesis: str = ""
    in_sample: tuple[str, str] = ("", "")
    out_of_sample: tuple[str, str] = ("", "")
    allowed_variants: tuple[dict[str, object], ...] = ()
    criteria: dict[str, object] = field(default_factory=dict)
    budget: str = "0"
    seed: int = 0
    metrics: tuple[str, ...] = ()
    tolerance: dict[str, str] = field(default_factory=dict)
    stop_rules: tuple[str, ...] = ()
    cost_model: str = ""
    frozen_at: str = ""
    plan_hash: str = ""

    record_type: str = field(init=False, default="EXP")

    def __post_init__(self) -> None:
        super(ExperimentRecord, self).__post_init__()
        validate_sha256(self.code_hash)
        validate_sha256(self.plan_hash)
        validate_utc(self.frozen_at)
        if not self.strategy_id.startswith("STRAT-") or not self.data_id.startswith("DATA-"):
            raise ValidationError("EXP wymaga wersji STRAT i DATA.")


@dataclass(frozen=True, slots=True)
class RunRecord(BaseRecord):
    experiment_id: str = ""
    experiment_version: int = 1
    evidence_type: EvidenceType = EvidenceType.BACKTEST
    started_at: str = ""
    completed_at: str = ""
    engine_version: str = ""
    trades: tuple[dict[str, object], ...] = ()
    rejected_signals: tuple[dict[str, object], ...] = ()
    total_cost: str = "0"
    exposure: tuple[dict[str, object], ...] = ()
    equity_curve: tuple[dict[str, object], ...] = ()
    errors: tuple[str, ...] = ()
    metrics: dict[str, object] = field(default_factory=dict)
    reproduction: dict[str, object] = field(default_factory=dict)
    run_outcome: RunOutcome = RunOutcome.INCONCLUSIVE
    input_hash: str = ""

    record_type: str = field(init=False, default="RUN")

    def __post_init__(self) -> None:
        super(RunRecord, self).__post_init__()
        validate_utc(self.started_at)
        validate_utc(self.completed_at)
        validate_sha256(self.input_hash)
        if not self.experiment_id.startswith("EXP-"):
            raise ValidationError("RUN wymaga powiązanego EXP.")


@dataclass(frozen=True, slots=True)
class ReviewRecord(BaseRecord):
    run_ids: tuple[str, ...] = ()
    reviewer: str = ""
    evidence: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    verdict: ReviewVerdict = ReviewVerdict.UNVERIFIED
    conditions: tuple[str, ...] = ()
    comparability_status: str = "NIEPORÓWNYWALNE"
    reproduction_verified: bool = False
    verification_details: dict[str, object] = field(default_factory=dict)

    record_type: str = field(init=False, default="REVIEW")

    def __post_init__(self) -> None:
        super(ReviewRecord, self).__post_init__()
        if not self.run_ids or not self.reviewer.strip():
            raise ValidationError("REVIEW wymaga RUN i recenzenta.")


@dataclass(frozen=True, slots=True)
class RiskDecisionRecord(BaseRecord):
    review_id: str = ""
    scope: str = ""
    valid_from: str = ""
    valid_until: str = ""
    limits: dict[str, object] = field(default_factory=dict)
    decision: RiskDecisionStatus = RiskDecisionStatus.BLOCKED
    rationale: str = ""
    permitted_next_step: str = ""
    blockers: tuple[str, ...] = ()

    record_type: str = field(init=False, default="RISK_DECISION")

    def __post_init__(self) -> None:
        super(RiskDecisionRecord, self).__post_init__()
        validate_utc(self.valid_from)
        validate_utc(self.valid_until)
        if not self.review_id.startswith("REVIEW-"):
            raise ValidationError("RISK-DECISION wymaga REVIEW.")


@dataclass(frozen=True, slots=True)
class MandateRecord(BaseRecord):
    risk_decision_id: str = ""
    authorized_by: str = ""
    strategy_id: str = ""
    strategy_version: int = 1
    code_hash: str = ""
    environment: ExecutionEnvironment = ExecutionEnvironment.PAPER_CONTINUOUS
    environment_id: str = ""
    account_id: str | None = None
    instruments: tuple[str, ...] = ()
    limits: dict[str, object] = field(default_factory=dict)
    starts_at: str = ""
    expires_at: str = ""
    stop_conditions: tuple[str, ...] = ()
    max_data_age_seconds: int = 0

    record_type: str = field(init=False, default="MANDATE")

    def __post_init__(self) -> None:
        super(MandateRecord, self).__post_init__()
        if not self.risk_decision_id.startswith("RISK_DECISION-"):
            raise ValidationError("MANDATE wymaga RISK-DECISION.")
        if not self.strategy_id.startswith("STRAT-") or self.strategy_version < 1:
            raise ValidationError("MANDATE wymaga konkretnej wersji STRAT.")
        validate_sha256(self.code_hash)
        validate_utc(self.starts_at)
        validate_utc(self.expires_at)
        if not self.environment_id.strip() or not self.instruments:
            raise ValidationError("MANDATE wymaga środowiska i instrumentów.")
        if self.max_data_age_seconds <= 0:
            raise ValidationError("MANDATE wymaga dodatniego limitu wieku danych.")


@dataclass(frozen=True, slots=True)
class IncubationRecord(BaseRecord):
    mandate_id: str = ""
    environment: ExecutionEnvironment = ExecutionEnvironment.PAPER_CONTINUOUS
    environment_id: str = ""
    lease_id: str = ""
    worker_id: str = ""
    incubation_status: IncubationStatus = IncubationStatus.PLANNED
    last_heartbeat_at: str = ""
    open_intents: int = 0
    position_count: int = 0
    alerts: tuple[str, ...] = ()

    record_type: str = field(init=False, default="INCU")

    def __post_init__(self) -> None:
        super(IncubationRecord, self).__post_init__()
        if not self.mandate_id.startswith("MANDATE-"):
            raise ValidationError("INCU wymaga MANDATE.")
        if not self.environment_id.strip() or not self.lease_id.strip() or not self.worker_id.strip():
            raise ValidationError("INCU wymaga środowiska, lease i wykonawcy.")
        validate_utc(self.last_heartbeat_at)
        if self.open_intents < 0 or self.position_count < 0:
            raise ValidationError("Liczniki INCU nie mogą być ujemne.")


@dataclass(frozen=True, slots=True)
class BudgetStatusRecord(BaseRecord):
    currency: str = ""
    limit_amount: str = "0"
    settled_cost: str = "0"
    active_reservation: str = "0"
    unresolved_cost: str = "0"
    available_amount: str = "0"
    scope: str = ""

    record_type: str = field(init=False, default="BUDGET_STATUS")

    def __post_init__(self) -> None:
        super(BudgetStatusRecord, self).__post_init__()
        if not self.currency.strip() or not self.scope.strip():
            raise ValidationError("BUDGET-STATUS wymaga waluty i zakresu.")


def candidate_content_hash(
    *,
    title: str,
    source_ids: tuple[str, ...],
    thesis: str,
    asset_class: str,
    market_scope: str,
    missing_decisions: tuple[str, ...],
) -> str:
    return sha256_text(
        canonical_json(
            {
                "title": title,
                "source_ids": source_ids,
                "thesis": thesis,
                "asset_class": asset_class,
                "market_scope": market_scope,
                "missing_decisions": missing_decisions,
            }
        )
    )


def record_content_hash(payload: dict[str, Any]) -> str:
    return sha256_text(canonical_json(payload))
