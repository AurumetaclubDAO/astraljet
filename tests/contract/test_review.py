from __future__ import annotations

import unittest

from astraljet.application.reviews import ReviewRequest, comparability_issues, create_review
from astraljet.domain.enums import EvidenceType, ReviewVerdict, RunOutcome, TechnicalStatus
from astraljet.domain.errors import DomainBlockedError
from astraljet.domain.records import ExperimentRecord, RunRecord, record_content_hash
from astraljet.lab.reproduction import ReproductionReport


def experiment(*, record_id: str = "EXP-12345678", data_id: str = "DATA-12345678", cost_model: str = "10 bps") -> ExperimentRecord:
    return ExperimentRecord(
        record_id=record_id,
        version=1,
        owner="tester",
        created_at="2025-01-01T00:00:00Z",
        technical_status=TechnicalStatus.COMPLETED,
        content_hash="A" * 64,
        limitations=(),
        strategy_id="STRAT-12345678",
        strategy_version=1,
        data_id=data_id,
        data_version=1,
        code_hash="B" * 64,
        hypothesis="test",
        in_sample=("2024-01-01T00:00:00Z", "2024-06-30T00:00:00Z"),
        out_of_sample=("2024-07-01T00:00:00Z", "2024-12-31T00:00:00Z"),
        allowed_variants=({"window": 3},),
        criteria={"max_drawdown_lte": "0.5"},
        budget="0",
        seed=42,
        metrics=("final_equity",),
        tolerance={"final_equity": "0.01"},
        stop_rules=("stop on gap",),
        cost_model=cost_model,
        frozen_at="2025-01-01T00:00:00Z",
        plan_hash="C" * 64,
    )


def run_record(*, record_id: str, owner: str, experiment_id: str = "EXP-12345678", input_hash: str = "D" * 64) -> RunRecord:
    output_hash = record_content_hash({'trades':(), 'rejected_signals':(), 'exposure':(),
        'equity_curve':(), 'metrics':{'final_equity':'101'}, 'outcome':'passed'})
    return RunRecord(
        record_id=record_id,
        version=1,
        owner=owner,
        created_at="2025-01-02T00:00:00Z",
        technical_status=TechnicalStatus.COMPLETED,
        content_hash=record_content_hash({'input_hash':input_hash, 'output_hash':output_hash, 'outcome':'passed'}),
        limitations=(),
        experiment_id=experiment_id,
        experiment_version=1,
        evidence_type=EvidenceType.BACKTEST,
        started_at="2025-01-02T00:00:00Z",
        completed_at="2025-01-02T00:01:00Z",
        engine_version="test",
        trades=(),
        rejected_signals=(),
        total_cost="1",
        exposure=(),
        equity_curve=(),
        errors=(),
        metrics={"final_equity": "101"},
        reproduction={"input_hash": input_hash, "output_hash": output_hash},
        run_outcome=RunOutcome.PASSED,
        input_hash=input_hash,
    )


def independent_check(runs, exp=None):
    """Explicit synthetic independent-observation artifact, not financial evidence."""
    from dataclasses import asdict
    exp = exp or experiment()
    body = {'schema':'astraljet-independent-check-v1', 'method':'control_calculation',
        'verifier':'external-fixture-checker', 'implementation_hash':'1'*64,
        'experiment_id':exp.record_id, 'experiment_version':exp.version, 'plan_hash':exp.plan_hash,
        'observations':[{'run_id':run.record_id, 'run_version':run.version,
          'record_hash':record_content_hash(asdict(run)), 'input_hash':run.input_hash,
          'trace_hash':record_content_hash({k:getattr(run,k) for k in ('trades','rejected_signals','exposure','equity_curve')}),
          'metrics':{k:run.metrics[k] for k in exp.metrics}, 'total_cost':run.total_cost} for run in runs]}
    return {**body, 'report_hash':record_content_hash(body)}


def request(*, reviewer: str = "AJ-08", rejection_reasons: tuple[str, ...] = ()) -> ReviewRequest:
    return ReviewRequest(
        reviewer=reviewer,
        evidence=("pełny pakiet",),
        findings=("wynik fixture",),
        missing_evidence=(),
        conditions=("brak awansu bez decyzji ryzyka",),
        rejection_reasons=rejection_reasons,
    )


class ReviewContractTest(unittest.TestCase):
    def test_run_author_cannot_verify_own_result(self) -> None:
        runs = (
            run_record(record_id="RUN-11111111", owner="AJ-07"),
            run_record(record_id="RUN-22222222", owner="reproducer"),
        )
        with self.assertRaises(DomainBlockedError):
            create_review(
                runs=runs,
                experiments=(experiment(), experiment()),
                request=request(reviewer="AJ-07"),
                reproduction=ReproductionReport(True, ()),
                owner="AJ-08",
            )

    def test_matching_independent_reproduction_can_be_verified(self) -> None:
        runs = (
            run_record(record_id="RUN-11111111", owner="AJ-07"),
            run_record(record_id="RUN-22222222", owner="reproducer"),
        )
        review = create_review(
            runs=runs,
            experiments=(experiment(), experiment()),
            request=request(),
            reproduction=ReproductionReport(True, ()),
            owner="AJ-08",
            independent_checks=(independent_check(runs),),
        )
        self.assertIs(review.verdict, ReviewVerdict.VERIFIED)
        self.assertEqual("comparable", review.comparability_status)

    def test_missing_second_run_is_unverified(self) -> None:
        review = create_review(
            runs=(run_record(record_id="RUN-11111111", owner="AJ-07"),),
            experiments=(experiment(),),
            request=request(),
            reproduction=None,
            owner="AJ-08",
        )
        self.assertIs(review.verdict, ReviewVerdict.UNVERIFIED)
        self.assertIn("missing_independent_reproduction", review.missing_evidence)

    def test_incompatible_data_is_not_comparable_and_not_ranked(self) -> None:
        first = experiment(record_id="EXP-11111111", data_id="DATA-11111111")
        second = experiment(record_id="EXP-22222222", data_id="DATA-22222222")
        runs = (
            run_record(record_id="RUN-11111111", owner="AJ-07", experiment_id=first.record_id),
            run_record(record_id="RUN-22222222", owner="reproducer", experiment_id=second.record_id),
        )
        issues = comparability_issues(runs, (first, second))
        review = create_review(
            runs=runs,
            experiments=(first, second),
            request=request(),
            reproduction=ReproductionReport(True, ()),
            owner="AJ-08",
        )
        self.assertIn("data_version_mismatch", issues)
        self.assertEqual("NIEPORÓWNYWALNE", review.comparability_status)
        self.assertIs(review.verdict, ReviewVerdict.UNVERIFIED)

    def test_explicit_methodological_failure_is_rejected(self) -> None:
        runs = (
            run_record(record_id="RUN-11111111", owner="AJ-07"),
            run_record(record_id="RUN-22222222", owner="reproducer"),
        )
        review = create_review(
            runs=runs,
            experiments=(experiment(), experiment()),
            request=request(rejection_reasons=("future_information_leak",)),
            reproduction=ReproductionReport(True, ()),
            owner="AJ-08",
        )
        self.assertIs(review.verdict, ReviewVerdict.REJECTED)


if __name__ == "__main__":
    unittest.main()
