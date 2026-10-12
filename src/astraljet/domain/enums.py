from __future__ import annotations

from enum import StrEnum


class RecordType(StrEnum):
    SRC = "SRC"
    CAND = "CAND"
    STRAT = "STRAT"
    DATA = "DATA"
    EXP = "EXP"
    RUN = "RUN"
    REVIEW = "REVIEW"
    RISK_DECISION = "RISK_DECISION"
    MANDATE = "MANDATE"
    INCU = "INCU"
    BUDGET_STATUS = "BUDGET_STATUS"


class TechnicalStatus(StrEnum):
    QUEUED = "queued"
    BLOCKED = "blocked"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CandidateStatus(StrEnum):
    UNASSESSED = "unassessed"
    NEEDS_INPUT = "needs_input"
    QUALIFIED = "qualified"
    REJECTED = "rejected"


class TrustStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED_ORIGIN = "verified_origin"


class StrategyStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_INPUT = "needs_input"
    READY = "ready"
    FROZEN = "frozen"
    RETIRED = "retired"


class DataStatus(StrEnum):
    READY = "ready"
    GAPS = "gaps"
    UNSUITABLE = "unsuitable"


class RunOutcome(StrEnum):
    PASSED = "passed"
    FAILED_CRITERIA = "failed_criteria"
    INCONCLUSIVE = "inconclusive"
    TECHNICAL_FAILURE = "technical_failure"


class ReviewVerdict(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    REJECTED = "rejected"


class RiskDecisionStatus(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"


class ExecutionEnvironment(StrEnum):
    PAPER_CONTINUOUS = "PAPER_CONTINUOUS"
    BROKER_DEMO = "BROKER_DEMO"


class ExecutionResultState(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"
    DUPLICATE = "duplicate"


class IncubationStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    STOPPED = "stopped"
    COMPLETED = "completed"
    UNCERTAIN = "uncertain"


class EvidenceType(StrEnum):
    BACKTEST = "BACKTEST"
    LATER_DATA_REPLAY = "LATER_DATA_REPLAY"
    PAPER_CONTINUOUS = "PAPER_CONTINUOUS"
    BROKER_DEMO = "BROKER_DEMO"
