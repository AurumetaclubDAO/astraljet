import copy
import json
from pathlib import Path
import tempfile
import unittest

from astraljet.application.reviews import create_review
from astraljet.domain.enums import ReviewVerdict
from astraljet.domain.errors import ValidationError
from astraljet.domain.records import record_content_hash
from astraljet.lab.reproduction import ReproductionReport
from tests.contract.test_review import experiment, request, run_record, independent_check


class IndependentCheckTest(unittest.TestCase):
    def setUp(self):
        self.runs = (run_record(record_id='RUN-11111111',owner='AJ-07'),
                     run_record(record_id='RUN-22222222',owner='reproducer'))

    def review(self, check):
        return create_review(runs=self.runs, experiments=(experiment(),experiment()), request=request(),
            reproduction=ReproductionReport(True,()), owner='AJ-08', independent_checks=(check,))

    def test_bound_observations_allow_completed_review(self):
        review = self.review(independent_check(self.runs))
        self.assertIs(review.verdict, ReviewVerdict.VERIFIED)
        self.assertTrue(review.verification_details['independent_check_verified'])
        self.assertEqual(1, len(review.verification_details['independent_checks']))

    def test_claimed_boolean_is_not_a_supported_report(self):
        review = self.review({'verified':True})
        self.assertIs(review.verdict, ReviewVerdict.UNVERIFIED)

    def test_saved_assessment_does_not_share_mutable_input(self):
        check = independent_check(self.runs)
        review = self.review(check)
        check['observations'][0]['metrics']['final_equity'] = '999'
        stored = review.verification_details['independent_checks'][0]['artifact']
        self.assertEqual('101', stored['observations'][0]['metrics']['final_equity'])
        self.assertEqual(review.content_hash, record_content_hash(review.payload()))

    def test_hex_case_does_not_change_the_binding(self):
        check = independent_check(self.runs)
        check['plan_hash'] = check['plan_hash'].lower()
        check['report_hash'] = record_content_hash({k:v for k,v in check.items() if k != 'report_hash'})
        self.assertIs(self.review(check).verdict, ReviewVerdict.VERIFIED)

    def test_changed_observations_bindings_hashes_or_identity_fail(self):
        mutations = (
            lambda c:c.update(report_hash='0'*64),
            lambda c:c.update(implementation_hash=experiment().code_hash),
            lambda c:c.update(verifier='  aj-07 '),
            lambda c:c.update(experiment_version=2),
            lambda c:c.update(plan_hash='0'*64),
            lambda c:c['observations'].pop(),
            lambda c:c['observations'][0].update(record_hash='0'*64),
            lambda c:c['observations'][0].update(trace_hash='0'*64),
            lambda c:c['observations'][0].update(input_hash='0'*64),
            lambda c:c['observations'][0].update(total_cost='NaN'),
            lambda c:c['observations'][0].update(metrics={'final_equity':'999'}),
            lambda c:c['observations'][0].update(metrics={}),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                check=copy.deepcopy(independent_check(self.runs));mutate(check)
                if index:
                    check['report_hash']=record_content_hash({k:v for k,v in check.items() if k!='report_hash'})
                review=self.review(check)
                self.assertIs(review.verdict,ReviewVerdict.UNVERIFIED)
                self.assertFalse(review.verification_details['independent_check_verified'])

    def test_private_file_loader_is_bounded_strict_and_does_not_echo_content(self):
        from astraljet.application.independent_check import load_independent_check
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'check.json'
            path.write_text(json.dumps(independent_check(self.runs)),encoding='utf-8')
            self.assertEqual(independent_check(self.runs),load_independent_check(str(path)))
            for raw in ('{"SECRET":1,"SECRET":2}', 'SECRET'*(1024*1024), '{"n":NaN}'):
                path.write_text(raw,encoding='utf-8')
                with self.assertRaises(ValidationError) as context:
                    load_independent_check(str(path))
                self.assertNotIn('SECRET',str(context.exception))
