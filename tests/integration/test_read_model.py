from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

from astraljet.application.read_model import inspect_system, strategy_lineage, list_strategies
from astraljet.cli import main
from astraljet.domain.errors import ValidationError
from astraljet.infrastructure.database import Database


class ReadModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Database.from_state_dir(self.temp.name)
        self.database.initialize()

    def save(self, record_id: str, payload: dict, version: int = 1) -> None:
        record_type = record_id.split('-')[0]
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO records VALUES (?, ?, ?, 'tester', '2026-09-19T00:00:00Z', "
                "'completed', ?, '[]', NULL, ?)",
                (record_type, record_id, version, 'a' * 64, json.dumps(payload)),
            )

    def seed(self) -> None:
        self.save('SRC-a', {'locator': 'C:/private/secret.md', 'token': 'DO-NOT-EXPORT'})
        self.save('CAND-a', {'source_ids': ['SRC-a']})
        self.save('CAND-b', {'source_ids': ['SRC-a']})
        self.save('STRAT-a', {'candidate_id': 'CAND-a', 'strategy_status': 'needs_input'})
        self.save('STRAT-b', {'candidate_id': 'CAND-b', 'strategy_status': 'ready'})
        self.save('DATA-a', {'locator': 'C:/private/data.csv', 'data_status': 'ready'})
        for suffix in ('a', 'b'):
            self.save(f'EXP-{suffix}', {
                'strategy_id': f'STRAT-{suffix}', 'strategy_version': 1,
                'data_id': 'DATA-a', 'data_version': 1,
            })
            self.save(f'RUN-{suffix}', {
                'experiment_id': f'EXP-{suffix}', 'experiment_version': 1,
                'evidence_type': 'BACKTEST', 'run_outcome': 'passed',
                'metrics': {'token': 'DO-NOT-EXPORT'},
            })

    def test_missing_database_does_not_create_directory(self) -> None:
        database = Database.from_state_dir(Path(self.temp.name) / 'not-created')
        with self.assertRaises(ValidationError) as caught:
            inspect_system(database)
        self.assertEqual('database_missing', caught.exception.blocker)
        self.assertFalse(database.config.state_dir.exists())

    def test_read_connection_rejects_writes(self) -> None:
        with self.database.read_only() as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("INSERT INTO schema_migrations VALUES (99, 'test')")

    def test_read_only_commands_do_not_migrate_old_schema(self) -> None:
        with self.database.connect() as connection:
            connection.execute('DELETE FROM schema_migrations WHERE version >= 5')
            for name in ('records_no_update', 'records_no_delete', 'records_no_replace', 'events_no_replace'):
                connection.execute(f'DROP TRIGGER IF EXISTS {name}')
            connection.commit()
        before = self.database.config.database_path.read_bytes()
        for args in (['system', 'inspect'], ['strategy', 'list'], ['status'], ['audit', 'export']):
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(['--state-dir', self.temp.name, *args])
            self.assertEqual(0, code, output.getvalue())
        result = inspect_system(self.database)
        self.assertEqual(4, result['storage_schema_version'])
        self.assertIn('history_guards_missing', [d['code'] for d in result['diagnostics']])
        self.assertEqual(before, self.database.config.database_path.read_bytes())

    def test_schema_mismatch_is_reported_without_creation(self) -> None:
        other = Database.from_state_dir(Path(self.temp.name) / 'foreign')
        other.config.state_dir.mkdir()
        with closing(sqlite3.connect(other.config.database_path)) as connection:
            connection.execute('CREATE TABLE orders (id TEXT)')
            connection.commit()
        with self.assertRaises(ValidationError) as caught:
            inspect_system(other)
        self.assertEqual('schema_unsupported', caught.exception.blocker)

    def test_lineage_keeps_exact_versions_and_excludes_unrelated_siblings(self) -> None:
        self.seed()
        self.save('STRAT-a', {'candidate_id': 'CAND-a', 'strategy_status': 'ready'}, version=2)
        first = strategy_lineage(self.database, 'STRAT-a', version=1)
        ids = {node['record_id'] for node in first['nodes']}
        self.assertEqual({'SRC-a', 'CAND-a', 'STRAT-a', 'DATA-a', 'EXP-a', 'RUN-a'}, ids)
        self.assertNotIn('RUN-b', ids)
        strategy = next(n for n in first['nodes'] if n['record_id'] == 'STRAT-a')
        self.assertEqual(1, strategy['version'])
        latest = strategy_lineage(self.database, 'STRAT-a')
        self.assertEqual(2, latest['root']['version'])
        self.assertNotIn('EXP-a', {n['record_id'] for n in latest['nodes']})
        self.assertFalse(first['execution_authorized'])
        self.assertEqual({'BACKTEST': 1}, first['evidence_counts'])

    def test_unversioned_multi_version_reference_is_not_guessed(self) -> None:
        self.seed()
        self.save('SRC-a', {'locator': 'different'}, version=2)
        result = strategy_lineage(self.database, 'STRAT-a')
        edge = next(e for e in result['edges'] if e['relation'] == 'source_ids')
        self.assertEqual('ambiguous', edge['resolution'])
        self.assertIsNone(edge['parent']['version'])
        self.assertEqual([1, 2], edge['available_versions'])
        self.assertFalse(any(n['record_id'] == 'SRC-a' for n in result['nodes']))
        self.assertEqual('incomplete', result['provenance_status'])

    def test_missing_exact_version_does_not_fall_back_to_latest(self) -> None:
        self.seed()
        self.save('EXP-missing', {'strategy_id': 'STRAT-a', 'strategy_version': 1,
                                  'data_id': 'DATA-a', 'data_version': 99})
        result = strategy_lineage(self.database, 'STRAT-a')
        edge = next(e for e in result['edges'] if e['child']['record_id'] == 'EXP-missing' and e['relation'] == 'data_id')
        self.assertEqual('missing', edge['resolution'])
        self.assertEqual(99, edge['parent']['version'])
        self.assertEqual('incomplete', result['provenance_status'])

    def test_invalid_reference_types_fail_closed(self) -> None:
        self.save('STRAT-invalid', {'candidate_id': 123})
        self.save('CAND-invalid', {'source_ids': 'SRC-string-not-list'})
        result = inspect_system(self.database)
        self.assertIn('invalid_reference', [d['code'] for d in result['diagnostics']])
        self.save('STRAT-bool', {'candidate_id': 'CAND-invalid'})
        self.save('EXP-bool', {'strategy_id': 'STRAT-bool', 'strategy_version': True,
                               'data_id': 'DATA-missing', 'data_version': 1})
        self.assertIn('invalid_reference', [d['code'] for d in inspect_system(self.database)['diagnostics']])

    def test_snapshots_export_only_safe_metadata_not_payloads(self) -> None:
        self.seed()
        output = json.dumps({'inspect': inspect_system(self.database),
                             'strategies': list_strategies(self.database),
                             'lineage': strategy_lineage(self.database, 'STRAT-a')})
        self.assertNotIn('DO-NOT-EXPORT', output)
        self.assertNotIn('C:/private', output)
        self.assertNotIn('metrics', output)
        self.assertEqual(2, len(list_strategies(self.database)['strategies']))

    def test_lineage_cli_and_unknown_strategy(self) -> None:
        self.seed()
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(['--state-dir', self.temp.name, 'strategy', 'lineage',
                         '--strategy-id', 'STRAT-a', '--version', '1'])
        self.assertEqual(0, code, output.getvalue())
        self.assertEqual({'record_id': 'STRAT-a', 'version': 1}, json.loads(output.getvalue())['root'])
        with self.assertRaises(ValidationError):
            strategy_lineage(self.database, 'STRAT-absent')

    def test_backtest_forward_and_demo_evidence_remain_separate(self) -> None:
        self.seed()
        for kind in ('LATER_DATA_REPLAY', 'PAPER_CONTINUOUS', 'BROKER_DEMO'):
            self.save(f'RUN-{kind}', {'experiment_id': 'EXP-a', 'experiment_version': 1,
                                      'evidence_type': kind, 'run_outcome': 'inconclusive'})
        self.assertEqual({'BACKTEST': 1, 'LATER_DATA_REPLAY': 1, 'PAPER_CONTINUOUS': 1, 'BROKER_DEMO': 1},
                         strategy_lineage(self.database, 'STRAT-a')['evidence_counts'])
