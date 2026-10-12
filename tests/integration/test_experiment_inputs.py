from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from astraljet.application.experiment_inputs import InputWindow, inspect_experiment_inputs
from astraljet.cli import main
from astraljet.domain.errors import ValidationError
from astraljet.domain.validation import sha256_file
from astraljet.infrastructure.database import Database


class ExperimentInputInspectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.strategies = Database.from_state_dir(self.root / 'strategies')
        self.data = Database.from_state_dir(self.root / 'data')
        for db in (self.strategies, self.data):
            db.initialize()
        self.csv = self.root / 'bars.csv'
        self.metadata = self.root / 'bars.csv.metadata.json'
        self.window = InputWindow('2021-01-01', '2021-12-31', '2022-01-01', '2022-02-04', 200, 20, 6)

    def save(self, db, kind, payload, version=1, content_hash='A' * 64):
        with db.transaction() as connection:
            connection.execute(
                "INSERT INTO records VALUES (?, ?, ?, 'tester', '2022-02-06T00:00:00Z', "
                "'blocked', ?, '[]', NULL, ?)",
                (kind, kind + '-fixture', version, content_hash, json.dumps(payload)),
            )

    def rows(self):
        return [[(date(2021, 1, 1) + timedelta(days=i)).isoformat() + 'T00:00:00Z',
                 symbol, '100', '102', '98', '101', '2', '1', '100']
                for i in range(400) for symbol in ('BTCUSD', 'ETHUSD')]

    def seed(self, *, rows=None, metadata_overrides=None, ready=False):
        rows = self.rows() if rows is None else rows
        with self.csv.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['timestamp', 'instrument', 'open', 'high', 'low', 'close', 'volume', 'trade_count', 'vwap'])
            writer.writerows(rows)
        digest = sha256_file(self.csv)
        metadata = {
            'csv_sha256': digest, 'provider': 'fixture', 'venue': 'fixture',
            'observed_start': '2021-01-01T00:00:00Z', 'observed_end': '2022-02-04T00:00:00Z',
            'row_count': len(rows), 'retrieved_at': '2022-02-06T00:00:00Z',
            'request': {'normalized_instruments': ['BTCUSD', 'ETHUSD'], 'timeframe': '1Day'},
            'credentials': 'DO-NOT-EXPORT',
        }
        metadata.update(metadata_overrides or {})
        self.metadata.write_text(json.dumps(metadata), encoding='utf-8')
        shared = {'instruments': ['BTCUSD', 'ETHUSD'], 'venue': 'fixture', 'timeframe': '1d',
                  'cost_model': 'fee_fixture' if ready else 'unknown'}
        self.save(self.strategies, 'STRAT', {**shared, 'strategy_status': 'ready' if ready else 'needs_input',
                                          'secret': 'DO-NOT-EXPORT'})
        self.save(self.data, 'DATA', {**shared, 'data_status': 'ready' if ready else 'gaps',
            'sha256': digest, 'provider': 'fixture', 'timezone': 'UTC', 'row_count': len(rows),
            'start': metadata['observed_start'], 'end': metadata['observed_end'],
            'locator': 'C:/DO-NOT-EXPORT/device.json'}, content_hash=digest)

    def inspect(self, **overrides):
        args = dict(strategy_id='STRAT-fixture', strategy_version=1, data_id='DATA-fixture', data_version=1,
                    csv_path=self.csv, metadata_path=self.metadata, window=self.window)
        args.update(overrides)
        return inspect_experiment_inputs(self.strategies, self.data, **args)

    def test_exact_versions_and_220_day_history_without_writes_or_network(self):
        self.seed()
        self.save(self.strategies, 'STRAT', {'strategy_status': 'ready'}, version=2)
        paths = [self.strategies.config.database_path, self.data.config.database_path, self.csv, self.metadata]
        before = [p.read_bytes() for p in paths]
        with patch.object(Database, 'initialize', side_effect=AssertionError('migration')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('network')):
            report = self.inspect()
        self.assertEqual(before, [p.read_bytes() for p in paths])
        self.assertEqual(1, report['strategy_reference']['version'])
        self.assertFalse(report['same_registry'])
        self.assertEqual('checked_local_structure', report['snapshot']['structural_status'])
        schedule = report['proposed_schedule']
        self.assertEqual(220, schedule['required_observations_including_signal_bar'])
        self.assertEqual('2021-08-08', schedule['first_weekly_signal_bar'])
        self.assertEqual('2021-08-09T00:00:00Z', schedule['first_model_execution_boundary_utc'])
        self.assertEqual((365, 35, 219), (schedule['aligned_days_in_sample'], schedule['aligned_days_out_of_sample'], schedule['warmup_bars_before_oos']))
        self.assertFalse(schedule['out_of_sample_untouched_verified'])
        self.assertNotIn('DO-NOT-EXPORT', json.dumps(report))

    def test_ready_records_do_not_authorize_freeze_or_execution(self):
        self.seed(ready=True)
        report = self.inspect()
        self.assertEqual('DRAFT_BLOCKED', report['status'])
        self.assertFalse(report['can_freeze'])
        self.assertFalse(report['execution_authorized'])
        self.assertEqual(0, report['records_written'])
        self.assertIsNone(report['experiment_id'])
        self.assertIn('human_rule_and_cost_decisions_missing', report['blockers'])

    def test_missing_explicit_version_does_not_use_latest(self):
        self.seed()
        for field in ('strategy_version', 'data_version'):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.inspect(**{field: 9})
        with self.assertRaises(ValidationError):
            self.inspect(strategy_version=True)

    def test_missing_database_does_not_create_it(self):
        absent = Database.from_state_dir(self.root / 'absent')
        with self.assertRaises(ValidationError):
            inspect_experiment_inputs(absent, self.data, strategy_id='STRAT-fixture', strategy_version=1,
                data_id='DATA-fixture', data_version=1, csv_path=self.csv, metadata_path=self.metadata, window=self.window)
        self.assertFalse(absent.config.state_dir.exists())

    def test_missing_day_in_both_instruments_is_not_compressed(self):
        rows = [r for r in self.rows() if r[0] != '2021-04-10T00:00:00Z']
        self.seed(rows=rows)
        report = self.inspect()
        codes = {r['code'] for r in report['snapshot']['findings']}
        self.assertTrue({'requested_calendar_gap', 'snapshot_calendar_gap'} <= codes)
        self.assertIsNone(report['proposed_schedule']['first_weekly_signal_bar'])

    def test_duplicate_nan_and_optional_missing_are_distinct(self):
        rows = self.rows()
        rows[0][5] = 'NaN'
        rows[1][6:] = ['', '', '']
        rows[2][6] = '0'
        duplicate = rows[3].copy()
        duplicate[0] = duplicate[0].replace('Z', '+00:00')
        rows.append(duplicate)
        self.seed(rows=rows)
        report = self.inspect()
        codes = {r['code'] for r in report['snapshot']['findings']}
        self.assertTrue({'duplicate_bar', 'invalid_ohlc'} <= codes)
        self.assertEqual({'volume': 1, 'trade_count': 1, 'vwap': 1}, report['snapshot']['optional_missing'])
        self.assertEqual(1, report['snapshot']['zero_volume_rows'])

    def test_changed_csv_and_sidecar_are_detected(self):
        self.seed(metadata_overrides={'csv_sha256': None, 'row_count': True})
        self.csv.write_bytes(self.csv.read_bytes().replace(b'102', b'103', 1))
        report = self.inspect()
        codes = {r['code'] for r in report['snapshot']['findings']}
        self.assertTrue({'registered_csv_hash_mismatch', 'sidecar_csv_hash_mismatch',
                         'data_content_hash_mismatch', 'sidecar_row_count_mismatch'} <= codes)

    def test_non_midnight_non_utc_and_unclosed_daily_bars_are_findings(self):
        rows = self.rows()
        rows[0][0] = '2021-01-01T01:00:00Z'
        rows[1][0] = '2021-01-01T00:00:00+01:00'
        self.seed(rows=rows, metadata_overrides={'retrieved_at': '2022-02-04T12:00:00Z'})
        codes = {r['code'] for r in self.inspect()['snapshot']['findings']}
        self.assertTrue({'invalid_daily_timestamp', 'bar_not_closed_at_retrieval'} <= codes)

    def test_invalid_or_short_windows_never_produce_valid_calendar(self):
        self.seed()
        for window in (
            InputWindow('2021-01-01', '2022-01-01', '2022-01-01', '2022-02-04', 200, 20, 6),
            InputWindow('2021-01-01', '2021-12-31', '2022-01-02', '2022-02-04', 200, 20, 6),
            InputWindow('20210101', '2021-12-31', '2022-01-01', '2022-02-04', 200, 20, 6),
            InputWindow('2021-01-01', '2021-12-31', '2022-01-01', '2022-02-04', 200, True, 6),
        ):
            with self.subTest(window=window), self.assertRaises(ValidationError):
                self.inspect(window=window)
        short = InputWindow('2021-01-01', '2021-02-01', '2021-02-02', '2021-02-03', 200, 20, 6)
        report = self.inspect(window=short)
        self.assertIsNone(report['proposed_schedule']['first_indicator_bar'])
        self.assertIn('insufficient_history_for_signal_and_next_open', {r['code'] for r in report['snapshot']['findings']})

    def test_cli_never_migrates_and_publishes_only_to_new_file(self):
        self.seed()
        for db in (self.strategies, self.data):
            with db.transaction() as connection:
                connection.execute('DELETE FROM schema_migrations WHERE version>=5')
        args = ['--state-dir', str(self.strategies.config.state_dir), 'experiment', 'inspect-inputs',
            '--strategy-id', 'STRAT-fixture', '--strategy-version', '1',
            '--data-state-dir', str(self.data.config.state_dir), '--data-id', 'DATA-fixture', '--data-version', '1',
            '--csv', str(self.csv), '--metadata', str(self.metadata), '--start', '2021-01-01',
            '--is-end', '2021-12-31', '--oos-start', '2022-01-01', '--end', '2022-02-04',
            '--ma-window', '200', '--slope-lookback', '20', '--signal-weekday', '6',
            '--output', str(self.root / 'report.json')]
        before = [db.config.database_path.read_bytes() for db in (self.strategies, self.data)]
        with patch.object(Database, 'initialize', side_effect=AssertionError('migration')), redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(args))
        written = (self.root / 'report.json').read_bytes()
        report = json.loads(written)
        self.assertEqual(4, report['data_reference']['storage_schema_version'])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(2, main(args))
        self.assertEqual(written, (self.root / 'report.json').read_bytes())
        self.assertEqual(before, [db.config.database_path.read_bytes() for db in (self.strategies, self.data)])

    def test_input_bytes_are_read_once_for_hash_and_inspection(self):
        self.seed()
        original_open = Path.open
        reads = []
        def watched_open(path, *args, **kwargs):
            if path == self.csv:
                reads.append(path)
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', watched_open):
            self.inspect()
        self.assertEqual([self.csv], reads)


if __name__ == '__main__':
    unittest.main()
