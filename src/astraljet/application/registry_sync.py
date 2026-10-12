"""Durable, one-way metadata outbox. No broker access or execution authority."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from datetime import datetime
from typing import Any

from astraljet.application.read_model import registry_snapshot
from astraljet.domain.errors import TechnicalError, ValidationError
from astraljet.domain.validation import utc_now
from astraljet.infrastructure.database import Database

PATH = '/api/astra/registry-sync'
MAX_BODY = 4 * 1024 * 1024
MAX_ACK = 4096
KINDS = {'SRC', 'CAND', 'STRAT', 'DATA', 'EXP', 'RUN'}
KEY_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')


def load_connection(path: str) -> dict[str, str]:
    try:
        with Path(path).open('rb') as handle:
            raw = handle.read(16385)
        if len(raw) > 16384:
            raise ValueError('size')
        def unique(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError('duplicate connection field')
                result[key] = item
            return result
        value = json.loads(raw, object_pairs_hook=unique)
        expected = {'format', 'endpoint', 'key_id', 'device_token', 'signing_secret', 'dispatch_token'}
        if (not isinstance(value, dict) or set(value) != expected
                or value['format'] != 'astraljet-registry-connection-v1'
                or not all(isinstance(v, str) for v in value.values())):
            raise ValueError('format')
        credentials = {k: v for k, v in value.items() if k != 'format'}
        validate_connection(**credentials)
        return credentials
    except (OSError, ValueError, TypeError):
        raise ValidationError('Nie można odczytać poprawnej konfiguracji połączenia. Nie wklejaj jej zawartości do czatu.') from None


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _uuid(value: object) -> bool:
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _installation_id(database: Database) -> str:
    with database.transaction() as connection:
        row = connection.execute('SELECT installation_id FROM registry_sync_installation LIMIT 1').fetchone()
        if row:
            return str(row[0])
        installation_id = str(uuid.uuid4())
        connection.execute('INSERT INTO registry_sync_installation VALUES (?,?)', (installation_id, utc_now()))
        return installation_id


def _from_snapshot(snapshot, installation_id, batch_id=None, sequence=1):
    records = [{**{k: n[k] for k in ('id', 'version', 'kind', 'status', 'technical_status', 'created_at', 'evidence_type')},
                'content_hash': n['hash'].lower()} for n in snapshot['nodes'] if n['kind'] in KINDS]
    selected = {(n['id'], n['version']) for n in records}
    p = dict(format='astraljet-registry-sync-v1', installation_id=installation_id,
             registry_id=snapshot['registry_id'], batch_id=batch_id or str(uuid.uuid4()), generated_at=snapshot['generated_at'],
             sequence=sequence, cursor=snapshot['cursor'], execution_authorized=False, records=records,
             edges=[e for e in snapshot['edges'] if (e['child']['id'], e['child']['version']) in selected],
             warnings=snapshot['warnings'])
    if not _uuid(p['batch_id']):
        raise ValidationError('Nieprawidłowy identyfikator przekazu.')
    body = _canonical(p)
    if len(body) > MAX_BODY:
        raise ValidationError('Metadane przekraczają limit przekazu.', blocker='sync_too_large')
    return p, body


def build_batch(database: Database, registry_id: str, *, batch_id: str | None = None) -> tuple[dict[str, Any], bytes]:
    installation_id = _installation_id(database)
    with database.read_only() as c:
        sequence = c.execute('SELECT COALESCE(MAX(rowid),0)+1 FROM registry_sync_batches').fetchone()[0]
    return _from_snapshot(registry_snapshot(database, registry_id, include_cursor=True), installation_id, batch_id, sequence)


def sign_headers(body: bytes, *, key_id: str, signing_secret: str, timestamp: int | None = None,
                 nonce: str | None = None) -> dict[str, str]:
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    nonce = nonce or str(uuid.uuid4())
    digest = hashlib.sha256(body).hexdigest()
    message = '\n'.join(['AJ-SYNC-V1', 'POST', PATH, key_id, stamp, nonce, digest]).encode('utf-8')
    return {'X-AJ-Key-Id': key_id, 'X-AJ-Timestamp': stamp, 'X-AJ-Nonce': nonce,
            'X-AJ-Content-SHA256': digest,
            'X-AJ-Signature': hmac.new(signing_secret.encode('utf-8'), message, hashlib.sha256).hexdigest()}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError('', code, 'Redirect refused', headers, fp)


def _open(request: urllib.request.Request, *, timeout: int):
    return urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout)


def validate_connection(endpoint: str, device_token: str, key_id: str, signing_secret: str, dispatch_token: str | None = None):
    try:
        url = urllib.parse.urlsplit(endpoint)
        valid = (url.scheme == 'https' and url.hostname and url.port in (None, 443) and not url.username
                 and not url.password and url.path == PATH and not url.query and not url.fragment
                 and not any(c.isspace() for c in endpoint) and '\\' not in endpoint)
    except ValueError:
        valid = False
    if not valid:
        raise ValidationError('Wymagany jest dokładny adres HTTPS endpointu synchronizacji, bez loginu i parametrów.')
    if (not re.fullmatch('[a-f0-9]{64}', device_token) or not KEY_ID.fullmatch(key_id)
            or not 32 <= len(signing_secret) <= 4096 or any(c in signing_secret for c in '\r\n')
            or dispatch_token is not None and (not dispatch_token or any(c in dispatch_token for c in '\r\n'))):
        raise ValidationError('Niepoprawna konfiguracja poświadczeń synchronizacji.')


def _claim(database: Database, registry_id: str, endpoint: str, batch_id: str | None):
    if not re.fullmatch('[a-z0-9][a-z0-9-]{0,47}', registry_id):
        raise ValidationError('Niepoprawna etykieta rejestru.')
    _installation_id(database)
    with database.transaction() as c:
        row = c.execute('SELECT rowid AS seq,* FROM registry_sync_batches WHERE batch_id=?', (batch_id,)).fetchone() if batch_id else None
        if batch_id and row is None:
            raise ValidationError('Nie znaleziono zapisanego przekazu do ponowienia.')
        if row:
            if not row['body_json'] or row['registry_id'] != 'local:' + registry_id or row['endpoint'] != endpoint:
                raise ValidationError('Przekaz nie ma zamrożonej treści lub należy do innego rejestru/adresu.')
            body = row['body_json'].encode('utf-8')
            if hashlib.sha256(body).hexdigest() != row['body_hash']:
                raise ValidationError('Niezgodność integralności zapisanego przekazu.')
            payload = json.loads(body)
            if row['status'] == 'acknowledged':
                receipt = _receipt(row['server_receipt_json'].encode('utf-8'), payload, row['body_hash'])
                return payload, body, row['seq'], None, receipt
            if row['status'] in ('conflict', 'rejected'):
                raise ValidationError('Przekaz wymaga decyzji operatora; automatyczne ponowienie jest zablokowane.')
            if row['status'] == 'sending' and row['lease_until'] and row['lease_until'] > time.time():
                raise ValidationError('Trwa już wysyłanie tego przekazu.', blocker='sync_in_flight')
        else:
            # The write lock prevents source changes while the separate read-only
            # snapshot captures metadata and its event cursor in one transaction.
            snapshot = registry_snapshot(database, registry_id, include_cursor=True)
            installation = c.execute('SELECT installation_id FROM registry_sync_installation LIMIT 1').fetchone()[0]
            sequence = c.execute('SELECT COALESCE(MAX(rowid),0)+1 FROM registry_sync_batches').fetchone()[0]
            payload, body = _from_snapshot(snapshot, installation, sequence=sequence)
            stamp = utc_now()
            c.execute("INSERT INTO registry_sync_batches(batch_id,body_hash,cursor_event_id,status,created_at,updated_at,body_json,registry_id,endpoint) VALUES (?,?,?,'pending',?,?,?,?,?)",
                      (payload['batch_id'], hashlib.sha256(body).hexdigest(), payload['cursor']['event_id'], stamp, stamp,
                       body.decode('utf-8'), payload['registry_id'], endpoint))
            row = c.execute('SELECT rowid AS seq,* FROM registry_sync_batches WHERE batch_id=?', (payload['batch_id'],)).fetchone()
        attempt = row['attempts'] + 1
        c.execute("UPDATE registry_sync_batches SET status='sending',attempts=?,lease_until=?,updated_at=?,last_error=NULL WHERE batch_id=?",
                  (attempt, time.time() + 120, utc_now(), payload['batch_id']))
        return payload, body, row['seq'], attempt, None


def _receipt(raw: bytes, payload: dict, digest: str) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate ACK field')
            result[key] = value
        return result
    if len(raw) > MAX_ACK:
        raise ValueError('ACK size')
    value = json.loads(raw, object_pairs_hook=unique)
    expected = {'format', 'request_id', 'server_time', 'batch_id', 'registry_id', 'installation_id',
                'body_hash', 'accepted', 'cursor', 'execution_authorized'}
    if (not isinstance(value, dict) or set(value) != expected or value['format'] != 'astraljet-registry-ack-v1'
            or not _uuid(value['request_id']) or value['execution_authorized'] is not False
            or type(value['accepted']) is not int or value['accepted'] != len(payload['records'])
            or value['body_hash'] != digest or value['cursor'] != payload['cursor']
            or any(value[k] != payload[k] for k in ('batch_id', 'registry_id', 'installation_id'))
            or not isinstance(value['server_time'], str) or not value['server_time'].endswith('Z')):
        raise ValueError('ACK mismatch')
    datetime.fromisoformat(value['server_time'].replace('Z', '+00:00'))
    return value


def _failed(database, batch_id, attempt, status, code):
    with database.transaction() as c:
        c.execute("UPDATE registry_sync_batches SET status=?,last_error=?,updated_at=?,lease_until=NULL WHERE batch_id=? AND attempts=? AND status='sending'",
                  (status, code, utc_now(), batch_id, attempt))


def push(database: Database, registry_id: str, *, endpoint: str, device_token: str, key_id: str,
         signing_secret: str, batch_id: str | None = None, dispatch_token: str | None = None) -> dict[str, Any]:
    validate_connection(endpoint, device_token, key_id, signing_secret, dispatch_token)
    payload, body, sequence, attempt, receipt = _claim(database, registry_id, endpoint, batch_id)
    digest = hashlib.sha256(body).hexdigest()
    if receipt is not None:
        return dict(batch_id=payload['batch_id'], body_hash=digest, receipt=receipt, execution_authorized=False)
    headers = {**sign_headers(body, key_id=key_id, signing_secret=signing_secret),
               'Content-Type': 'application/json', 'Authorization': 'Bearer ' + device_token}
    if dispatch_token:
        headers['OAI-Sites-Authorization'] = 'Bearer ' + dispatch_token
    request = urllib.request.Request(endpoint, data=body, method='POST', headers=headers)
    try:
        with _open(request, timeout=20) as response:
            receipt = _receipt(response.read(MAX_ACK + 1), payload, digest)
    except urllib.error.HTTPError as exc:
        state = 'conflict' if exc.code == 409 else 'retryable_failure' if exc.code >= 500 or exc.code in (408, 429) else 'rejected'
        _failed(database, payload['batch_id'], attempt, state, 'http_' + str(exc.code))
        exc.close()
        error = TechnicalError if state == 'retryable_failure' else ValidationError
        raise error('Przekaz nie został potwierdzony; stan zapisano w lokalnej kolejce.', blocker='sync_' + state) from None
    except (OSError, ValueError, TypeError, KeyError, urllib.error.URLError):
        _failed(database, payload['batch_id'], attempt, 'retryable_failure', 'transport_or_ack_invalid')
        raise TechnicalError('Brak poprawnego potwierdzenia. Ponów ten sam zapisany batch.', blocker='sync_retryable_failure') from None
    with database.transaction() as c:
        changed = c.execute("UPDATE registry_sync_batches SET status='acknowledged',updated_at=?,server_receipt_json=?,lease_until=NULL,last_error=NULL WHERE batch_id=? AND attempts=? AND status='sending'",
                            (utc_now(), _canonical(receipt).decode('utf-8'), payload['batch_id'], attempt)).rowcount
        if changed != 1:
            raise TechnicalError('Próbę przejęło inne wysłanie; sprawdź zapisany status.', blocker='sync_attempt_superseded')
        c.execute('INSERT INTO registry_sync_cursors VALUES (?,?,?,?,?) ON CONFLICT(registry_id) DO UPDATE SET batch_id=excluded.batch_id,batch_seq=excluded.batch_seq,event_id=excluded.event_id,acknowledged_at=excluded.acknowledged_at WHERE excluded.batch_seq>registry_sync_cursors.batch_seq',
                  (payload['registry_id'], payload['batch_id'], sequence, payload['cursor']['event_id'], utc_now()))
    return dict(batch_id=payload['batch_id'], body_hash=digest, receipt=receipt, execution_authorized=False)


def sync_status(database: Database) -> dict:
    with database.read_only() as c:
        rows = c.execute('SELECT batch_id,registry_id,status,attempts,created_at,updated_at,last_error FROM registry_sync_batches ORDER BY rowid DESC LIMIT 50').fetchall()
    return dict(execution_authorized=False, batches=[dict(row) for row in rows])
