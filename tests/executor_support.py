from __future__ import annotations

from astraljet.application.mandates import MandateRequest, create_mandate
from astraljet.domain.enums import (
    ExecutionEnvironment,
    ReviewVerdict,
    RiskDecisionStatus,
    TechnicalStatus,
)
from astraljet.domain.records import ReviewRecord, RiskDecisionRecord


def allowed_risk(*, environment: str = "PAPER_CONTINUOUS") -> RiskDecisionRecord:
    return RiskDecisionRecord(
        record_id="RISK_DECISION-12345678",
        version=1,
        owner="AJ-09",
        created_at="2025-01-01T00:00:00Z",
        technical_status=TechnicalStatus.COMPLETED,
        content_hash="A" * 64,
        limitations=(),
        review_id="REVIEW-12345678",
        scope=f"test {environment}",
        valid_from="2025-01-01T00:00:00Z",
        valid_until="2025-12-31T00:00:00Z",
        limits={"max_notional": "10000", "max_position_quantity": "10"},
        decision=RiskDecisionStatus.ALLOWED,
        rationale="test",
        permitted_next_step="mandat testowy",
        blockers=(),
    )


def mandate(
    *,
    environment: ExecutionEnvironment = ExecutionEnvironment.PAPER_CONTINUOUS,
    environment_id: str = "paper-test",
    account_id: str | None = None,
):
    risk = allowed_risk(environment=environment.value)
    record = create_mandate(
        risk_decision=risk,
        request=MandateRequest(
            authorized_by="Karol",
            strategy_id="STRAT-12345678",
            strategy_version=1,
            code_hash="B" * 64,
            environment=environment,
            environment_id=environment_id,
            account_id=account_id,
            instruments=("BTCUSD", "ETHUSD"),
            limits={"max_notional": "10000", "max_position_quantity": "10"},
            starts_at="2025-01-02T00:00:00Z",
            expires_at="2025-12-30T00:00:00Z",
            stop_conditions=("kill switch", "stale data", "uncertain execution"),
            max_data_age_seconds=60,
        ),
        owner="Karol",
    )
    return risk, record
