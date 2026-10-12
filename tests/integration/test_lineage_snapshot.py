from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from astraljet.application.read_model import registry_snapshot
from astraljet.cli import main
from astraljet.domain.errors import TechnicalError, ValidationError
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.snapshot_file import publish_snapshot, MAX_SNAPSHOT_BYTES


class LineageSnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = Database.from_state_dir(self.root / 'state')
        self.database.initialize()
        with self.database.transaction() as connection:
            for kind, payload in [('SRC', {'locator': 'C:/private/secret.md', 'token': 'DO-NOT-EXPORT'}),
                                  ('CAND', {'source_ids': ['SRC-a']}),
                                  ('STRAT', {'candidate_id': 'CAND-a', 'strategy_status': 'needs_input'})]:
                connection.execute(
                    "INSERT INTO records VALUES (?, ?, 1, 'tester', '2026-09-19T00:00:00Z', "
                    "'completed', ?, '[]', NULL, ?)",
                    (kind, kind + '-a', 'a' * 64, json.dumps(payload)),
                )

    def test_metadata_contract_legacy_database_unchanged(self) -> None:
        with self.database.transaction() as connection:
            connection.execute('DELETE FROM schema_migrations WHERE version=5')
            connection.execute('DROP TRIGGER records_no_replace')
        before = self.database.config.database_path.read_bytes()
        result = registry_snapshot(self.database, 'quickstart')
        self.assertEqual('local:quickstart', result['registry_id'])
        self.assertEqual('astraljet-lineage-v1', result['format'])
        self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['truncated'])
        self.assertEqual({'SRC', 'CAND', 'STRAT'}, {n['kind'] for n in result['nodes']})
        self.assertEqual({'unversioned_single'}, {e['resolution'] for e in result['edges']})
        self.assertIn('history_guards_missing', result['warnings'])
        self.assertIn('audit_event_missing', result['warnings'])
        encoded = json.dumps(result)
        for private in ('DO-NOT-EXPORT', 'C:/private', 'locator', 'payload', 'SYSTEM-EXECUTOR'):
            self.assertNotIn(private, encoded)
        self.assertEqual(before, self.database.config.database_path.read_bytes())

    def test_cli_publishes_complete_snapshot_and_never_overwrites(self) -> None:
        output = self.root / 'exports' / 'view.json'
        args = ['--state-dir', str(self.database.config.state_dir), 'system', 'snapshot',
                '--registry-id', 'test-registry', '--output', str(output)]
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(0, main(args))
        content = output.read_bytes()
        self.assertEqual(hashlib.sha256(content).hexdigest(), json.loads(stdout.getvalue())['sha256'])
        self.assertEqual(3, len(json.loads(content)['nodes']))
        with redirect_stdout(io.StringIO()):
            self.assertNotEqual(0, main(args))
        self.assertEqual(content, output.read_bytes())

    def test_missing_database_creates_neither_database_nor_output(self) -> None:
        output = self.root / 'not-created' / 'view.json'
        with redirect_stdout(io.StringIO()):
            result = main(['--state-dir', str(self.root / 'missing'), 'system', 'snapshot',
                           '--registry-id', 'test', '--output', str(output)])
        self.assertNotEqual(0, result)
        self.assertFalse(output.parent.exists())
        self.assertFalse((self.root / 'missing').exists())

    def test_concurrent_file_is_preserved(self) -> None:
        output = self.root / 'race.json'
        original_link = os.link

        def competitor(source: str, destination: Path) -> None:
            destination.write_bytes(b'other writer')
            original_link(source, destination)

        with patch('astraljet.infrastructure.snapshot_file.os.link', side_effect=competitor):
            with self.assertRaises(ValidationError):
                publish_snapshot(registry_snapshot(self.database, 'test'), output)
        self.assertEqual(b'other writer', output.read_bytes())
        self.assertEqual([], list(self.root.glob('.lineage-*.tmp')))

    def test_failed_publication_has_no_fallback_or_partial_file(self) -> None:
        output = self.root / 'unsupported.json'
        with patch('astraljet.infrastructure.snapshot_file.os.link', side_effect=OSError('unsupported')):
            with self.assertRaises(TechnicalError):
                publish_snapshot(registry_snapshot(self.database, 'test'), output)
        self.assertFalse(output.exists())
        self.assertEqual([], list(self.root.glob('.lineage-*.tmp')))

    def test_size_limit_and_bad_label_fail_before_writes(self) -> None:
        output = self.root / 'not-created' / 'too-big.json'
        with self.assertRaises(ValidationError):
            publish_snapshot({'too_big': 'x' * MAX_SNAPSHOT_BYTES}, output)
        self.assertFalse(output.parent.exists())
        for label in ('../secret', 'Test Label', 'a' * 49, ''):
            with self.assertRaises(ValidationError):
                registry_snapshot(self.database, label)

    def test_invalid_reference_does_not_export_free_text(self) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO records VALUES ('STRAT', 'STRAT-invalid', 1, 'tester', "
                "'2026-09-19T00:00:00Z', 'completed', ?, '[]', NULL, ?)",
                ('a' * 64, json.dumps({'candidate_id': 'C:/private/DO-NOT-EXPORT'})),
            )
        result = registry_snapshot(self.database, 'test')
        edge = next(e for e in result['edges'] if e['child']['id'] == 'STRAT-invalid')
        self.assertIsNone(edge['parent']['id'])
        self.assertEqual('invalid', edge['resolution'])
        self.assertNotIn('DO-NOT-EXPORT', json.dumps(result))
