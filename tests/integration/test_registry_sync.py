from __future__ import annotations

import hashlib
import hmac
import io
import json
import tempfile
import unittest
import urllib.error
import uuid
from unittest.mock import patch

from astraljet.application import registry_sync as sync
from astraljet.domain.errors import TechnicalError, ValidationError
from astraljet.infrastructure.database import Database


class RegistrySyncTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Database.from_state_dir(self.temp.name)
        self.db.initialize()
        no_network = patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected real network'))
        no_network.start()
        self.addCleanup(no_network.stop)
        self.args = dict(endpoint='https://tradebot-astra-pro.solyg.chatgpt.site/api/astra/registry-sync',
                         device_token='a' * 64, key_id='local-v1', signing_secret='s' * 64)
        self.save('SRC-test', {'locator': 'C:/SECRET/source.txt', 'token': 'SECRET'})
        self.save('CAND-test', {'source_ids': ['SRC-test']})
        self.save('STRAT-test', {'candidate_id': 'CAND-test', 'strategy_status': 'needs_input'})

    def save(self, record_id, payload, version=1):
        with self.db.transaction() as c:
            c.execute("INSERT INTO records VALUES (?,?,?,'tester','2026-09-23T00:00:00Z','completed',?,'[]',NULL,?)",
                      (record_id.split('-')[0], record_id, version, 'b' * 64, json.dumps(payload)))

    def row(self, batch_id):
        with self.db.read_only() as c:
            return dict(c.execute('SELECT * FROM registry_sync_batches WHERE batch_id=?', (batch_id,)).fetchone())

    def ack(self, request, **_):
        p = json.loads(request.data)
        return io.BytesIO(json.dumps(dict(format='astraljet-registry-ack-v1', request_id=str(uuid.uuid4()),
            server_time='2026-09-24T00:00:00Z', batch_id=p['batch_id'], registry_id=p['registry_id'],
            installation_id=p['installation_id'], body_hash=hashlib.sha256(request.data).hexdigest(),
            accepted=len(p['records']), cursor=p['cursor'], execution_authorized=False)).encode())

    def test_signing_uses_real_newlines_and_binds_key(self):
        headers = sync.sign_headers(b'{}', key_id='local-v1', signing_secret='s' * 64,
                                    timestamp=1790204120, nonce='12345678-1234-4234-8234-123456789abc')
        text = '\n'.join(['AJ-SYNC-V1', 'POST', '/api/astra/registry-sync', 'local-v1',
                          '1790204120', headers['X-AJ-Nonce'], hashlib.sha256(b'{}').hexdigest()])
        self.assertEqual(hmac.new(b's' * 64, text.encode(), hashlib.sha256).hexdigest(), headers['X-AJ-Signature'])

    def test_metadata_only_and_edges_exclude_unsynced_roles(self):
        self.save('REVIEW-test', {'run_ids': ['RUN-missing']})
        p, body = sync.build_batch(self.db, 'test')
        self.assertNotIn(b'SECRET', body)
        self.assertNotIn(b'REVIEW', body)
        self.assertEqual(3, len(p['records']))
        self.assertEqual(2, len(p['edges']))
        self.assertFalse(p['execution_authorized'])
        self.assertEqual({'event_id': None}, p['cursor'])

    def test_retry_reuses_frozen_body_after_source_changes(self):
        sent = []
        def timeout(request, **_):
            sent.append(request)
            raise urllib.error.URLError('SECRET remote detail')
        with patch.object(sync, '_open', timeout), self.assertRaises(TechnicalError):
            sync.push(self.db, 'test', **self.args)
        batch = json.loads(sent[0].data)['batch_id']
        self.save('SRC-after', {})
        def accept(request, **kwargs):
            sent.append(request)
            return self.ack(request, **kwargs)
        with patch.object(sync, '_open', accept):
            result = sync.push(self.db, 'test', batch_id=batch, **self.args)
        self.assertEqual(sent[0].data, sent[1].data)
        self.assertNotEqual(sent[0].get_header('X-aj-nonce'), sent[1].get_header('X-aj-nonce'))
        self.assertEqual('acknowledged', self.row(batch)['status'])
        self.assertEqual(3, result['receipt']['accepted'])
        with patch.object(sync, '_open', side_effect=AssertionError('ACK must not resend')):
            self.assertEqual(result, sync.push(self.db, 'test', batch_id=batch, **self.args))

    def test_invalid_ack_does_not_advance_cursor_or_persist_remote_text(self):
        for change in [{'accepted': 0}, {'execution_authorized': True}, {'body_hash': '0' * 64},
                       {'batch_id': str(uuid.uuid4())}, {'cursor': {'event_id': 'EVT-wrong'}},
                       {'secret': 'SECRET'}, {'server_time': 'bad'}]:
            sent = []
            def bad(request, **kwargs):
                sent.append(request)
                data = json.loads(self.ack(request).read()); data.update(change)
                return io.BytesIO(json.dumps(data).encode())
            with patch.object(sync, '_open', bad), self.assertRaises(TechnicalError):
                sync.push(self.db, 'test', **self.args)
            row = self.row(json.loads(sent[0].data)['batch_id'])
            self.assertEqual('retryable_failure', row['status'])
            self.assertIsNone(row['server_receipt_json'])
            self.assertNotIn('SECRET', str(row))
        with self.db.read_only() as c:
            self.assertEqual(0, c.execute('SELECT COUNT(*) FROM registry_sync_cursors').fetchone()[0])

    def test_http_errors_are_classified_and_not_echoed(self):
        for code, state in [(409, 'conflict'), (401, 'rejected'), (422, 'rejected'), (429, 'retryable_failure'), (503, 'retryable_failure')]:
            sent = []
            def fail(request, **_):
                sent.append(request)
                raise urllib.error.HTTPError(request.full_url, code, 'SECRET', {}, io.BytesIO(b'SECRET'))
            with patch.object(sync, '_open', fail), self.assertRaises((TechnicalError, ValidationError)) as err:
                sync.push(self.db, 'test', **self.args)
            self.assertNotIn('SECRET', str(err.exception))
            row = self.row(json.loads(sent[0].data)['batch_id'])
            self.assertEqual(state, row['status'])
            if state in {'conflict', 'rejected'}:
                with patch.object(sync, '_open', side_effect=AssertionError('terminal retry')), self.assertRaises(ValidationError):
                    sync.push(self.db, 'test', batch_id=row['batch_id'], **self.args)

    def test_redirect_handler_never_forwards_credentials(self):
        handler = sync.NoRedirect()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            handler.redirect_request(None, None, 307, 'redirect', {}, 'https://elsewhere.invalid/')
        caught.exception.close()

    def test_bad_endpoint_or_credentials_create_no_outbox(self):
        for endpoint in ['http://localhost/api/astra/registry-sync', 'https://user:secret@example.com/api/astra/registry-sync',
                         'https://example.com/other', 'https://example.com/api/astra/registry-sync?q=secret',
                         'https://example.com/api/astra/registry-sync#fragment']:
            with self.assertRaises(ValidationError):
                sync.push(self.db, 'test', **{**self.args, 'endpoint': endpoint})
        with self.db.read_only() as c:
            self.assertEqual(0, c.execute('SELECT COUNT(*) FROM registry_sync_batches').fetchone()[0])

    def test_batch_cannot_move_between_registries_or_origins(self):
        with patch.object(sync, '_open', self.ack):
            result = sync.push(self.db, 'test', **self.args)
        for registry, endpoint in [('other', self.args['endpoint']), ('test', 'https://example.com/api/astra/registry-sync')]:
            with self.assertRaises(ValidationError):
                sync.push(self.db, registry, batch_id=result['batch_id'], **{**self.args, 'endpoint': endpoint})

    def test_cursor_updates_only_after_verified_ack(self):
        with self.db.transaction() as c:
            c.execute("INSERT INTO events VALUES ('EVT-test','2026-09-23T00:00:00Z','2026-09-23T00:00:00Z',"
                      "'tester','created','SRC','SRC-test',1,'test','ok','{}','correlation',NULL,'idempotent')")
        with patch.object(sync, '_open', self.ack):
            result = sync.push(self.db, 'test', **self.args)
        self.assertEqual({'event_id': 'EVT-test'}, result['receipt']['cursor'])
        with self.db.read_only() as c:
            self.assertEqual('EVT-test', c.execute('SELECT event_id FROM registry_sync_cursors').fetchone()[0])

    def test_legacy_bodyless_batch_cannot_be_rebuilt_from_new_source(self):
        batch = str(uuid.uuid4())
        with self.db.transaction() as c:
            c.execute("INSERT INTO registry_sync_batches(batch_id,body_hash,status,created_at,updated_at) VALUES (?,?,'pending','old','old')", (batch, 'a' * 64))
        with self.assertRaises(ValidationError):
            sync.push(self.db, 'test', batch_id=batch, **self.args)

    def test_cli_credentials_are_not_command_line_arguments(self):
        from astraljet.cli import build_parser
        helptext = build_parser().format_help()
        self.assertIn('registry', helptext)
        source = __import__('inspect').getsource(__import__('astraljet.cli', fromlist=['main']))
        self.assertFalse('add_argument("--signing-secret"' in source)
        self.assertFalse('add_argument("--device-token"' in source)

    def test_private_connection_file_strict_validation_and_redacted_errors(self):
        from pathlib import Path
        path = Path(self.temp.name) / 'registry-connection.json'
        config = {**self.args, 'format': 'astraljet-registry-connection-v1', 'dispatch_token': 'private-token'}
        path.write_text(json.dumps(config), encoding='utf-8')
        self.assertEqual({k: v for k, v in config.items() if k != 'format'}, sync.load_connection(str(path)))
        for raw in ['{"SECRET":true}', json.dumps({**config, 'endpoint': 'https://evil.test/SECRET'}),
                    json.dumps(config)[:-1] + ',"key_id":"duplicate"}', 'SECRET' * 4000]:
            path.write_text(raw, encoding='utf-8')
            with self.assertRaises(ValidationError) as caught:
                sync.load_connection(str(path))
            self.assertNotIn('SECRET', str(caught.exception))

    def test_in_flight_batch_is_not_sent_twice(self):
        with patch.object(sync, '_open', side_effect=urllib.error.URLError('timeout')):
            with self.assertRaises(TechnicalError):
                sync.push(self.db, 'test', **self.args)
        with self.db.transaction() as c:
            row = c.execute('SELECT batch_id FROM registry_sync_batches').fetchone()
            c.execute("UPDATE registry_sync_batches SET status='sending',lease_until=?",
                      (__import__('time').time() + 90,))
        with patch.object(sync, '_open', side_effect=AssertionError('second sender')), self.assertRaises(ValidationError):
            sync.push(self.db, 'test', batch_id=row[0], **self.args)

    def test_cli_bad_connection_cannot_create_or_migrate_registry(self):
        from astraljet.cli import main
        from contextlib import redirect_stdout, redirect_stderr
        from pathlib import Path
        for directory in [Path(self.temp.name) / 'missing', Path(self.temp.name)]:
            with patch.object(Database, 'initialize', side_effect=AssertionError('Unexpected migration')):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertNotEqual(0, main(['--state-dir', str(directory), 'registry', 'sync-push',
                                                '--registry-id', 'test', '--connection-file', 'missing-file.json']))
        self.assertFalse((Path(self.temp.name) / 'missing').exists())

    def test_late_old_ack_does_not_move_cursor_back(self):
        with patch.object(sync, '_open', side_effect=urllib.error.URLError('timeout')), self.assertRaises(TechnicalError):
            sync.push(self.db, 'test', **self.args)
        with self.db.read_only() as c:
            old = c.execute('SELECT batch_id FROM registry_sync_batches').fetchone()[0]
        with patch.object(sync, '_open', self.ack):
            new = sync.push(self.db, 'test', **self.args)
            sync.push(self.db, 'test', batch_id=old, **self.args)
        with self.db.read_only() as c:
            self.assertEqual(new['batch_id'], c.execute('SELECT batch_id FROM registry_sync_cursors').fetchone()[0])

    def test_body_is_immutable_and_status_read_does_not_migrate(self):
        import sqlite3
        with patch.object(sync, '_open', self.ack):
            sync.push(self.db, 'test', **self.args)
        with self.db.transaction() as c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("UPDATE registry_sync_batches SET body_json='{}'")
        from astraljet.cli import main
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(['--state-dir', self.temp.name, 'registry', 'sync-status']))
        self.db.initialize()  # Repeat additive migration without duplicate columns.
