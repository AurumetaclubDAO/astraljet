from __future__ import annotations

import io
import json
import sqlite3
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from tests.integration import test_weekly_experiment as fixture
from astraljet.application.weekly_recorded import record_weekly_experiment
from astraljet.application.registry_sync import build_batch
from astraljet.application.reviews import create_review, ReviewRequest
from astraljet.cli import main
from astraljet.domain.enums import RunOutcome, ReviewVerdict, TechnicalStatus
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.event_store import EventStore
from astraljet.infrastructure.repositories import RecordRepository
from astraljet.lab.reproduction import compare_runs, run_integrity_issues


class WeeklyRecordedTest(unittest.TestCase):
    setUp = fixture.WeeklyExperimentTest.setUp
    seed = fixture.WeeklyExperimentTest.seed

    def execute(self, **changes):
        args = dict(experiment_id=self.experiment.record_id, version=1,
                    csv_path=self.csv, owner='AJ-07 fixture', idempotency_key='weekly-fixture-batch-1')
        args.update(changes)
        return record_weekly_experiment(self.database, **args)

    def counts(self):
        with self.database.read_only() as connection:
            return tuple(connection.execute('SELECT count(*) FROM ' + table).fetchone()[0]
                         for table in ('records', 'events'))

    def test_all_variants_persist_without_qualification_and_restart_replays(self):
        self.seed()
        before = self.counts()
        with patch.object(Database, 'initialize', side_effect=AssertionError('migration')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('network')):
            result = self.execute()
        self.assertTrue(result['created'])
        self.assertEqual(2, len(result['runs']))
        self.assertEqual((before[0] + 2, before[1] + 3), self.counts())
        repo = RecordRepository(self.database)
        for index, item in enumerate(result['runs']):
            run = repo.get(item['record_id'], item['version'])
            self.assertEqual(RunOutcome.INCONCLUSIVE, run.run_outcome)
            self.assertEqual(TechnicalStatus.COMPLETED, run.technical_status)
            self.assertEqual(index, run.reproduction['weekly_input']['scenario_index'])
            self.assertEqual((), run_integrity_issues(run))
            detail = run.reproduction['weekly_result']
            self.assertEqual(detail['metrics']['strategy']['full']['total_cost'], run.total_cost)
            self.assertEqual(detail['metrics']['strategy']['out_of_sample']['net_return'], run.metrics['net_return'])
            self.assertIn('benchmark', detail['daily'])
            self.assertFalse(detail['execution_authorized'])
        self.database = Database.from_state_dir(self.database.config.state_dir)
        with patch('astraljet.application.weekly_recorded.run_weekly_experiment', side_effect=AssertionError('recompute')):
            duplicate = self.execute()
        self.assertFalse(duplicate['created'])
        self.assertEqual(result['runs'], duplicate['runs'])
        self.assertEqual((before[0] + 2, before[1] + 3), self.counts())

    def test_key_conflict_different_owner_or_record_type_never_returns_wrong_result(self):
        self.seed()
        self.execute()
        before = self.counts()
        with self.assertRaises(ValidationError):
            self.execute(owner='someone else')
        with self.assertRaises(ValidationError):
            self.execute(idempotency_key=self.strategy.record_id + str(self.strategy.version))
        self.assertEqual(before, self.counts())

    def test_event_failure_rolls_back_whole_series(self):
        self.seed()
        before = self.counts()
        original = EventStore.insert
        count = 0
        def failing(connection, event):
            nonlocal count
            count += 1
            if count == 2:
                raise sqlite3.OperationalError('injected storage failure')
            return original(connection, event)
        with patch.object(EventStore, 'insert', side_effect=failing), self.assertRaises(sqlite3.OperationalError):
            self.execute()
        self.assertEqual(before, self.counts())
        self.assertTrue(self.execute()['created'])

    def test_input_change_during_computation_prevents_write(self):
        self.seed()
        before = self.counts()
        from astraljet.application.weekly_experiment import run_weekly_experiment
        def changed(*args, **kwargs):
            report = run_weekly_experiment(*args, **kwargs)
            self.csv.write_bytes(self.csv.read_bytes().replace(b'101', b'102', 1))
            return report
        with patch('astraljet.application.weekly_recorded.run_weekly_experiment', side_effect=changed), \
                self.assertRaises(DomainBlockedError):
            self.execute()
        self.assertEqual(before, self.counts())

    def test_missing_registry_and_old_schema_never_created_or_migrated(self):
        original = self.database
        self.database = Database.from_state_dir(self.root / 'absent')
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertFalse(self.database.config.state_dir.exists())
        self.database = original
        with self.database.transaction() as connection:
            connection.execute('DELETE FROM schema_migrations WHERE version = 7')
        before = self.database.config.database_path.read_bytes()
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertEqual(before, self.database.config.database_path.read_bytes())

    def test_reproduction_is_per_variant_and_does_not_create_verified_review(self):
        self.seed()
        first = self.execute()
        second = self.execute(idempotency_key='weekly-fixture-batch-2')
        repo = RecordRepository(self.database)
        def records(result):
            return [repo.get(r['record_id'], r['version']) for r in result['runs']]
        a, b = records(first), records(second)
        self.assertTrue(compare_runs(a[0], b[0], self.experiment.tolerance).verified)
        self.assertFalse(compare_runs(a[0], b[1], self.experiment.tolerance).verified)
        review = create_review(runs=(a[0], b[0]), experiments=(self.experiment, self.experiment),
                               request=ReviewRequest('independent reviewer', (), (), (), (), ()),
                               reproduction=None, owner='AJ-08')
        self.assertEqual(ReviewVerdict.UNVERIFIED, review.verdict)

    def test_tampered_benchmark_and_projection_are_detected(self):
        self.seed()
        result = self.execute()
        run = RecordRepository(self.database).get(result['runs'][0]['record_id'], 1)
        clone = json.loads(json.dumps(run.reproduction))
        clone['weekly_result']['metrics']['benchmark']['out_of_sample']['net_return'] = '999'
        self.assertIn('weekly_artifact_integrity_mismatch', run_integrity_issues(replace(run, reproduction=clone)))
        self.assertTrue(run_integrity_issues(replace(run, total_cost='0')))
        self.assertTrue(run_integrity_issues(replace(run, run_outcome=RunOutcome.PASSED)))
        self.assertTrue(run_integrity_issues(replace(run, reproduction={})))

    def test_metadata_batch_includes_runs_without_prices_or_full_results(self):
        self.seed()
        result = self.execute()
        batch, body = build_batch(self.database, 'test-weekly')
        text = body.decode('utf-8')
        for run in result['runs']:
            self.assertIn(run['record_id'], text)
        self.assertNotIn('weekly_result', text)
        self.assertNotIn('equity_close', text)
        self.assertNotIn(str(self.csv), text)

    def test_cli_writes_only_explicit_recorded_path_and_returns_small_receipt(self):
        self.seed()
        args = ['--state-dir', str(self.database.config.state_dir), 'run', 'weekly-recorded',
                '--experiment-id', self.experiment.record_id, '--version', '1', '--csv', str(self.csv),
                '--idempotency-key', 'cli-weekly-test']
        output = io.StringIO()
        with redirect_stdout(output), patch.object(Database, 'initialize', side_effect=AssertionError('migration')):
            code = main(args)
        self.assertEqual(0, code)
        receipt = json.loads(output.getvalue())
        self.assertTrue(receipt['created'])
        self.assertFalse(receipt['execution_authorized'])
        self.assertEqual(2, len(receipt['runs']))
        self.assertLess(len(output.getvalue()), 6000)

    def test_two_callers_commit_one_batch(self):
        self.seed()
        before = self.counts()
        from astraljet.application.weekly_experiment import run_weekly_experiment
        barrier = Barrier(2)
        def synchronized(*args, **kwargs):
            report = run_weekly_experiment(*args, **kwargs)
            barrier.wait(timeout=15)
            return report
        with patch('astraljet.application.weekly_recorded.run_weekly_experiment', side_effect=synchronized):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.execute) for _ in range(2)]
                results = [future.result(timeout=30) for future in futures]
        self.assertEqual([False, True], sorted(result['created'] for result in results))
        self.assertEqual(results[0]['runs'], results[1]['runs'])
        self.assertEqual((before[0] + 2, before[1] + 3), self.counts())

    def test_missing_version_invalid_arguments_and_missing_guards_do_not_write(self):
        self.seed()
        before = self.counts()
        for args in ({'version': 2}, {'version': True}, {'owner': ' '}, {'idempotency_key': 'bad'}):
            with self.subTest(args=args), self.assertRaises(ValidationError):
                self.execute(**args)
        with self.database.transaction() as connection:
            connection.execute('DROP TRIGGER records_no_update')
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertEqual(before, self.counts())

    def test_partial_or_reordered_report_and_size_overflow_never_write(self):
        self.seed()
        before = self.counts()
        from astraljet.application.weekly_experiment import run_weekly_experiment
        for operation in ('missing', 'reversed'):
            def broken(*args, **kwargs):
                report = run_weekly_experiment(*args, **kwargs)
                report['results'] = report['results'][:1] if operation == 'missing' else report['results'][::-1]
                return report
            with patch('astraljet.application.weekly_recorded.run_weekly_experiment', side_effect=broken), \
                    self.assertRaises(ValidationError):
                self.execute()
            self.assertEqual(before, self.counts())
        with patch('astraljet.application.weekly_recorded.MAX_BATCH_BYTES', 1), self.assertRaises(ValidationError):
            self.execute()
        self.assertEqual(before, self.counts())

    def test_saved_report_can_be_exported_read_only_without_recomputing_or_csv(self):
        self.seed()
        receipt = self.execute()
        self.csv.unlink()  # this is a disposable synthetic fixture, not market data
        output_file = self.root / 'stored-report.json'
        args = ['--state-dir', str(self.database.config.state_dir), 'run', 'weekly-export',
                '--idempotency-key', 'weekly-fixture-batch-1', '--output', str(output_file)]
        before = self.counts()
        with redirect_stdout(io.StringIO()), \
                patch.object(Database, 'initialize', side_effect=AssertionError('migration')), \
                patch('astraljet.application.weekly_recorded.run_weekly_experiment', side_effect=AssertionError('recompute')):
            self.assertEqual(0, main(args))
            self.assertEqual(2, main(args))  # no overwrite
        report = json.loads(output_file.read_text(encoding='utf-8'))
        self.assertEqual(receipt['report_hash'], report['report_hash'])
        self.assertEqual(2, len(report['results']))
        self.assertEqual('OFFLINE_UNQUALIFIED', report['status'])
        self.assertEqual(before, self.counts())


if __name__ == '__main__':
    unittest.main()
