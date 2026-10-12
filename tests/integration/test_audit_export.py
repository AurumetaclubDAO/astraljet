from __future__ import annotations

import json
import tempfile
import unittest

from astraljet.application.mandates import MandateRequest, create_incubation, create_mandate
from astraljet.application.status import export_audit
from astraljet.domain.enums import (
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
from astraljet.domain.records import (
    CandidateRecord,
    DataRecord,
    ExperimentRecord,
    ReviewRecord,
    RiskDecisionRecord,
    RunRecord,
    SourceRecord,
    StrategyRecord,
)
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.repositories import RecordRepository


NOW = "2025-06-01T12:00:00Z"
HASH = "A" * 64


def common(record_id: str, *, version: int = 1, supersedes: str | None = None) -> dict[str, object]:
    return {
        "record_id": record_id,
        "version": version,
        "owner": "tester",
        "created_at": NOW,
        "technical_status": TechnicalStatus.COMPLETED,
        "content_hash": HASH,
        "limitations": ("fixture test_only",),
        "supersedes": supersedes,
    }


class AuditExportIntegrationTest(unittest.TestCase):
    def test_exports_full_chain_redacts_locators_and_keeps_append_only_correction(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            repository = RecordRepository(database)
            source = SourceRecord(
                **common("SRC-12345678"),
                locator=r"C:\private\strategie.md",
                sha256=HASH,
                size_bytes=123,
                observed_at=NOW,
                author="unknown",
                media_type="text/markdown",
                trust_status=TrustStatus.UNVERIFIED,
            )
            candidate = CandidateRecord(
                **common("CAND-12345678"), title="BTC/ETH", source_ids=(source.record_id,),
                thesis="trend", asset_class="crypto", market_scope="spot",
                missing_decisions=(), candidate_status=CandidateStatus.QUALIFIED,
            )
            strategy = StrategyRecord(
                **common("STRAT-12345678"), candidate_id=candidate.record_id,
                instruments=("BTCUSD", "ETHUSD"), venue="TEST", timeframe="1d",
                signal_timing="close", execution_timing="next open", entry_rule="rule",
                exit_rule="rule", sizing_rule="rule", cost_model="10 bps",
                constraints=("no leverage",), missing_data_policy="block", benchmark="static",
                allowed_parameters={"window": 3}, source_adaptation="fixture",
                strategy_status=StrategyStatus.FROZEN,
            )
            data = DataRecord(
                **common("DATA-12345678"), provider="fixture", venue="TEST",
                instruments=("BTCUSD", "ETHUSD"), timeframe="1d", timezone="UTC",
                start="2025-01-01T00:00:00Z", end="2025-01-10T00:00:00Z",
                available_at_rule="close", locator=r"C:\private\market.csv", sha256=HASH,
                schema_version="1", transformations=("none",), cost_model="10 bps",
                quality_findings=(), row_count=20, data_status=DataStatus.READY,
            )
            experiment = ExperimentRecord(
                **common("EXP-12345678"), strategy_id=strategy.record_id, strategy_version=1,
                data_id=data.record_id, data_version=1, code_hash=HASH, hypothesis="fixture",
                in_sample=("2025-01-01T00:00:00Z", "2025-01-05T00:00:00Z"),
                out_of_sample=("2025-01-06T00:00:00Z", "2025-01-10T00:00:00Z"),
                allowed_variants=({},), criteria={"test": True}, budget="0", seed=1,
                metrics=("return",), tolerance={"return": "0"}, stop_rules=("gap",),
                cost_model="10 bps", frozen_at=NOW, plan_hash=HASH,
            )
            run = RunRecord(
                **common("RUN-12345678"), experiment_id=experiment.record_id,
                experiment_version=1, evidence_type=EvidenceType.BACKTEST,
                started_at=NOW, completed_at=NOW, engine_version="test", trades=(),
                rejected_signals=(), total_cost="0", exposure=(), equity_curve=(), errors=(),
                metrics={"evidence_strength": "test_only"}, reproduction={"test_only": True},
                run_outcome=RunOutcome.INCONCLUSIVE, input_hash=HASH,
            )
            review = ReviewRecord(
                **common("REVIEW-12345678"), run_ids=(run.record_id,), reviewer="AJ-08",
                evidence=("fixture",), findings=("test_only",), missing_evidence=(),
                verdict=ReviewVerdict.VERIFIED, conditions=("PAPER only",),
                comparability_status="PORÓWNYWALNE", reproduction_verified=True,
            )
            risk = RiskDecisionRecord(
                **common("RISK_DECISION-12345678"), review_id=review.record_id,
                scope="PAPER fixture", valid_from="2025-01-01T00:00:00Z",
                valid_until="2025-12-31T00:00:00Z",
                limits={"max_notional": "1000", "max_position_quantity": "10"},
                decision=RiskDecisionStatus.ALLOWED, rationale="fixture",
                permitted_next_step="PAPER", blockers=(),
            )
            mandate = create_mandate(
                risk_decision=risk,
                request=MandateRequest(
                    authorized_by="Karol", strategy_id=strategy.record_id, strategy_version=1,
                    code_hash=HASH, environment=ExecutionEnvironment.PAPER_CONTINUOUS,
                    environment_id="audit-paper", account_id=None, instruments=("BTCUSD",),
                    limits={"max_notional": "1000", "max_position_quantity": "10"},
                    starts_at="2025-01-02T00:00:00Z", expires_at="2025-12-30T00:00:00Z",
                    stop_conditions=("kill switch",), max_data_age_seconds=60,
                ),
                owner="Karol",
            )
            incubation = create_incubation(
                mandate=mandate, lease_id="LEASE-12345678", worker_id="worker-audit",
                last_heartbeat_at=NOW, status=IncubationStatus.ACTIVE,
                owner="Wykonawca AstralJet",
            )
            records = (source, candidate, strategy, data, experiment, run, review, risk, mandate, incubation)
            for index, record in enumerate(records):
                repository.save(
                    record,
                    event_type="audit.fixture",
                    reason="Budowa pełnego łańcucha odbiorowego.",
                    outcome="recorded",
                    actor="tester",
                    idempotency_key=f"audit-chain-{index:02d}",
                )

            corrected = SourceRecord(
                **common(source.record_id, version=2, supersedes=f"{source.record_id}:1"),
                locator=source.locator, sha256="B" * 64, size_bytes=124, observed_at=NOW,
                author="unknown", media_type="text/markdown", trust_status=TrustStatus.UNVERIFIED,
            )
            repository.save(
                corrected,
                event_type="source.corrected",
                reason="Korekta metadanych bez nadpisania historii.",
                outcome="corrected",
                actor="tester",
                idempotency_key="audit-source-correction",
            )
            exported = export_audit(database)

        text = json.dumps(exported, ensure_ascii=False)
        self.assertNotIn(r"C:\private", text)
        self.assertEqual(
            {"SRC", "CAND", "STRAT", "DATA", "EXP", "RUN", "REVIEW", "RISK_DECISION", "MANDATE", "INCU"},
            set(exported["chain"]),
        )
        source_versions = [
            item for item in exported["records"] if item["record_id"] == source.record_id
        ]
        self.assertEqual([1, 2], [item["version"] for item in source_versions])
        self.assertEqual(2, len([event for event in exported["events"] if event["record_id"] == source.record_id]))
        self.assertEqual("[REDACTED_LOCAL_LOCATOR]", source_versions[0]["payload"]["locator"])


if __name__ == "__main__":
    unittest.main()
