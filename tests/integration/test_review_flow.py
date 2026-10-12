from __future__ import annotations

import tempfile
import copy
import unittest
from dataclasses import replace

from astraljet.application.mandates import RiskDecisionRequest, create_risk_decision
from astraljet.application.reviews import ReviewRequest, create_review
from astraljet.application.status import build_status
from astraljet.domain.enums import RiskDecisionStatus, ReviewVerdict
from astraljet.domain.records import record_content_hash
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.repositories import RecordRepository
from astraljet.lab.reproduction import ReproductionReport

from tests.contract.test_review import experiment, run_record, independent_check


class ReviewFlowIntegrationTest(unittest.TestCase):
    def test_inconsistent_nested_evidence_cannot_authorize_new_risk(self):
        runs = (run_record(record_id='RUN-11111111',owner='AJ-07'),
                run_record(record_id='RUN-22222222',owner='reproducer'))
        review = create_review(runs=runs,experiments=(experiment(),experiment()),
            request=ReviewRequest('AJ-08',('test only',),(),(),(),()),
            reproduction=ReproductionReport(True,()),owner='AJ-08',
            independent_checks=(independent_check(runs),))
        mutations = (
            lambda d:d['comparisons'][0].update(verified=False),
            lambda d:d['independent_checks'][0].update(verified=False),
            lambda d:d['independent_checks'][0]['artifact'].update(report_hash='0'*64),
            lambda d:d.update(comparisons='not a list'),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                details = copy.deepcopy(review.verification_details)
                mutate(details)
                modified = replace(review, verification_details=details)
                modified = replace(modified, content_hash=record_content_hash(modified.payload()))
                decision = create_risk_decision(review=modified,request=RiskDecisionRequest(
                    RiskDecisionStatus.ALLOWED,'test','2025-01-03T00:00:00Z','2025-01-10T00:00:00Z',
                    {'max_notional':'0'},'test','test'),owner='AJ-09')
                self.assertIs(decision.decision,RiskDecisionStatus.BLOCKED)
                self.assertIn('review_evidence_not_verified',decision.blockers)

    def test_legacy_verified_label_without_evidence_does_not_allow_new_risk(self):
        review = create_review(runs=(run_record(record_id='RUN-11111111',owner='AJ-07'),),
            experiments=(experiment(),), request=ReviewRequest('AJ-08',('test',),(),(),(),()),
            reproduction=None,owner='AJ-08')
        legacy = replace(review,verdict=ReviewVerdict.VERIFIED,reproduction_verified=True,
                         missing_evidence=(),verification_details={})
        decision = create_risk_decision(review=legacy,request=RiskDecisionRequest(
            RiskDecisionStatus.ALLOWED,'test','2025-01-03T00:00:00Z','2025-01-10T00:00:00Z',
            {'max_notional':'0'},'test','test'),owner='AJ-09')
        self.assertIs(decision.decision,RiskDecisionStatus.BLOCKED)
        self.assertIn('review_evidence_not_verified',decision.blockers)

        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            RecordRepository(database).save(legacy,event_type='review.completed',reason='legacy fixture',
                outcome='verified',actor='AJ-08',idempotency_key='legacy-review')
            status = build_status(database)
            self.assertEqual('review_evidence_not_verified',status['blocker'])

    def test_verified_review_can_create_bounded_risk_decision(self) -> None:
        runs = (
            run_record(record_id="RUN-11111111", owner="AJ-07"),
            run_record(record_id="RUN-22222222", owner="independent-reproducer"),
        )
        review = create_review(
            runs=runs,
            experiments=(experiment(), experiment()),
            request=ReviewRequest(
                reviewer="AJ-08",
                evidence=("dwa zgodne RUN",),
                findings=("fixture test_only",),
                missing_evidence=(),
                conditions=("wyłącznie dalsza ocena",),
                rejection_reasons=(),
            ),
            reproduction=ReproductionReport(True, ()),
            owner="AJ-08",
            independent_checks=(independent_check(runs),),
        )
        self.assertIs(review.verdict, ReviewVerdict.VERIFIED)
        decision = create_risk_decision(
            review=review,
            request=RiskDecisionRequest(
                requested_decision=RiskDecisionStatus.ALLOWED,
                scope="rozważenie testowego PAPER dla fixture",
                valid_from="2025-01-03T00:00:00Z",
                valid_until="2025-01-10T00:00:00Z",
                limits={"max_notional": "0", "environment": "test_only"},
                rationale="Zgodność mechaniki; bez twierdzenia o przewadze.",
                permitted_next_step="przygotować projekt mandatu testowego",
            ),
            owner="AJ-09",
        )
        self.assertIs(decision.decision, RiskDecisionStatus.ALLOWED)

        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            repository = RecordRepository(database)
            saved_review, _, _ = repository.save(
                review,
                event_type="review.completed",
                reason="Niezależny przegląd fixture.",
                outcome=review.verdict.value,
                actor="AJ-08",
                idempotency_key="review-flow-review",
            )
            saved_decision, _, _ = repository.save(
                decision,
                event_type="risk.decided",
                reason="Ograniczona decyzja następnego kroku.",
                outcome=decision.decision.value,
                actor="AJ-09",
                idempotency_key="review-flow-risk",
            )
            self.assertEqual(saved_review.record_id, decision.review_id)
            self.assertEqual(1, repository.count_by_type("REVIEW"))
            self.assertEqual(1, repository.count_by_type("RISK_DECISION"))
            self.assertEqual(saved_decision.decision, RiskDecisionStatus.ALLOWED)

    def test_unverified_review_forces_blocked_decision(self) -> None:
        review = create_review(
            runs=(run_record(record_id="RUN-11111111", owner="AJ-07"),),
            experiments=(experiment(),),
            request=ReviewRequest(
                reviewer="AJ-08",
                evidence=("jeden RUN",),
                findings=(),
                missing_evidence=(),
                conditions=(),
                rejection_reasons=(),
            ),
            reproduction=None,
            owner="AJ-08",
        )
        decision = create_risk_decision(
            review=review,
            request=RiskDecisionRequest(
                requested_decision=RiskDecisionStatus.ALLOWED,
                scope="inkubacja",
                valid_from="2025-01-03T00:00:00Z",
                valid_until="2025-01-10T00:00:00Z",
                limits={"max_notional": "100"},
                rationale="prośba o awans",
                permitted_next_step="brak",
            ),
            owner="AJ-09",
        )
        self.assertIs(decision.decision, RiskDecisionStatus.BLOCKED)
        self.assertIn("review_not_verified", decision.blockers)


if __name__ == "__main__":
    unittest.main()
