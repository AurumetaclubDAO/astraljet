from dataclasses import replace
import unittest

from astraljet.application.reviews import create_review
from astraljet.domain.enums import ReviewVerdict, TechnicalStatus
from astraljet.lab.reproduction import ReproductionReport, compare_runs
from tests.contract.test_review import experiment, request, run_record


class ReviewIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.first = run_record(record_id='RUN-11111111', owner='AJ-07')
        self.second = run_record(record_id='RUN-22222222', owner='reproducer')

    def review(self, runs, experiments=None, req=None):
        return create_review(runs=runs, experiments=experiments or tuple(experiment() for _ in runs),
                             request=req or request(), reproduction=ReproductionReport(True, ()), owner='AJ-08')

    def test_duplicate_run_is_not_independent_reproduction(self):
        review = self.review((self.first, self.first))
        self.assertIs(review.verdict, ReviewVerdict.UNVERIFIED)
        self.assertIn('duplicate_run', review.missing_evidence)

    def test_same_engine_replay_is_not_an_independent_method(self):
        review = self.review((self.first, self.second))
        self.assertIs(review.verdict, ReviewVerdict.UNVERIFIED)
        self.assertIn('missing_independent_check', review.missing_evidence)

    def test_experiment_binding_checked_for_every_run(self):
        review = self.review((self.first, self.second), (experiment(), replace(experiment(), version=2)))
        self.assertIn('run_experiment_binding_mismatch', review.missing_evidence)

    def test_forged_positive_comparison_does_not_hide_changed_metric(self):
        second = replace(self.second, metrics={'final_equity':'999'})
        review = self.review((self.first, second))
        self.assertFalse(review.reproduction_verified)
        self.assertTrue(any('metric_outside_tolerance' in code for code in review.missing_evidence))

    def test_third_run_is_not_ignored(self):
        third = replace(self.second, record_id='RUN-33333333', metrics={'final_equity':'999'})
        review = self.review((self.first, self.second, third))
        self.assertFalse(review.reproduction_verified)

    def test_technical_failure_is_not_verified(self):
        second = replace(self.second, technical_status=TechnicalStatus.BLOCKED, errors=('failed',))
        review = self.review((self.first, second))
        self.assertIs(review.verdict, ReviewVerdict.UNVERIFIED)
        self.assertIn('run_not_completed', review.missing_evidence)

    def test_empty_metric_contract_is_not_verified(self):
        report = compare_runs(self.first, self.second, {})
        self.assertFalse(report.verified)

    def test_missing_output_hash_is_not_evidence_of_equality(self):
        first = replace(self.first, reproduction={})
        second = replace(self.second, reproduction={})
        self.assertFalse(compare_runs(first, second, {'final_equity':'0.01'}).verified)

    def test_non_finite_numbers_never_pass_or_crash(self):
        for bad in ('NaN','sNaN','Infinity','-Infinity','1e999999999999999999999'):
            for where in ('metric','tolerance'):
                with self.subTest(bad=bad, where=where):
                    first = replace(self.first, metrics={'final_equity':bad}) if where == 'metric' else self.first
                    tolerance = {'final_equity':bad if where == 'tolerance' else '0.01'}
                    report = compare_runs(first, self.second, tolerance)
                    self.assertFalse(report.verified)

    def test_negative_tolerance_and_invalid_cost_are_not_verified(self):
        self.assertFalse(compare_runs(self.first, self.second, {'final_equity':'-1'}).verified)
        for cost in ('NaN','-1',''):
            with self.subTest(cost=cost):
                report = compare_runs(self.first, replace(self.second,total_cost=cost), {'final_equity':'0.01'})
                self.assertFalse(report.verified)

    def test_precise_difference_does_not_round_down_to_tolerance(self):
        from astraljet.lab.reproduction import compare_metrics
        issues = compare_metrics({'value':'1.00000000000000000000000000001'}, {'value':'0'}, {'value':'1'})
        self.assertIn('metric_outside_tolerance_value',issues)

    def test_normalized_reviewer_cannot_rename_self_for_independence(self):
        from astraljet.domain.errors import DomainBlockedError
        with self.assertRaises(DomainBlockedError):
            self.review((self.first,self.second),req=request(reviewer='  aj-07 '))


if __name__ == '__main__':
    unittest.main()
