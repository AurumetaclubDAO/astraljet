"""Publish only the read-only dashboard DTO to the existing private AstralJet Site."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import sys
import time
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.runtime/dashboard'
CONFIG = STATE / 'site-connection.dpapi'
ACCOUNTS = STATE / 'accounts.toml'  # numer rachunku DEMO tylko lokalnie, poza Git
SITE = 'https://tradebot-astra-pro.solyg.chatgpt.site'
SOURCE = 'http://127.0.0.1:8877/api/summary'
MAX_BYTES = 200_000


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def protect(value, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('Windows DPAPI required')
    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise RuntimeError('DPAPI operation failed')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'Redirect refused', headers, fp)


def request_json(url, headers=None, data=None):
    request = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Response too large')
        return json.loads(raw)


def sanitize(value):
    if isinstance(value, str):
        return re.sub(r'[A-Za-z]:[\\/][^\n]*', lambda m: '/'.join(re.split(r'[\\/]', m.group())[-2:]), value)
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, dict):
        if any(re.search(r'password|passwd|secret|token|authorization|api.?key|credential', k, re.I) for k in value):
            raise ValueError('Unexpected sensitive field')
        return {k: sanitize(v) for k, v in value.items()}
    return value


# Strict site schema: bots array must have exactly these 6 cards until site redeploy.
SITE_BOT_IDS = ('tq-hormuz', 'tq-tech-vol', 'tq-xasset-lag', 'tq-alt-spec', 'tq-long-hold', 'tq-vb')


def demo_login(path=None):
    path = Path(path or ACCOUNTS)
    try:
        with path.open('rb') as stream:
            value = tomllib.load(stream).get('demo_login')
    except OSError:
        value = None
    if type(value) is not int or value <= 0:
        raise ValueError('Missing local DEMO account configuration')
    return value


def prepare(snapshot, expected_login=None):
    stamp = datetime.fromisoformat(snapshot['generated_at'])
    if stamp.tzinfo is None or not -5 <= (datetime.now(timezone.utc) - stamp).total_seconds() <= 300:
        raise ValueError('Stale source')
    account = snapshot['account']['value']
    if account is not None and (account.get('login'), account.get('server'), account.get('mode')) != (
            expected_login if expected_login is not None else demo_login(), 'VantageMarkets-Demo', 'DEMO'):
        raise ValueError('Unexpected account')
    if account is None and snapshot['positions']['value'] is not None:
        raise ValueError('Unverified account positions')
    if isinstance(snapshot.get('bots'), list):
        snapshot = dict(snapshot, bots=[b for b in snapshot['bots'] if b.get('id') in SITE_BOT_IDS])
    payload = json.dumps(sanitize(snapshot), ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(payload) > MAX_BYTES:
        raise ValueError('Snapshot too large')
    return payload


def publish(connection):
    if connection['site'] != SITE:
        raise ValueError('Destination not allowed')
    snapshot = request_json(SOURCE)
    payload = prepare(snapshot)
    result = request_json(SITE + '/api/observatory/ingest', {
        'Content-Type': 'application/json',
        'OAI-Sites-Authorization': 'Bearer ' + connection['dispatch_token'],
        'X-Astraljet-Publisher': connection['publisher_secret'],
    }, payload)
    if result.get('ok') is not True or result.get('snapshot_id') != snapshot['snapshot_id']:
        raise ValueError('Missing acknowledgement')
    return {'ok': True, 'snapshot_id': snapshot['snapshot_id'], 'generated_at': snapshot['generated_at'], 'acknowledged_at': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--configure', action='store_true')
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    STATE.mkdir(exist_ok=True, parents=True)
    if args.configure:
        import getpass
        connection = json.loads(getpass.getpass('Connection JSON (hidden): '))
        if connection.get('site') != SITE or any(not isinstance(connection.get(k), str) or len(connection[k]) < 32 for k in ('dispatch_token', 'publisher_secret')):
            raise ValueError('Invalid connection')
        CONFIG.write_bytes(protect(json.dumps(connection).encode()))
        print('Connection saved with Windows user encryption')
        return
    connection = json.loads(protect(CONFIG.read_bytes(), decrypt=True))
    import msvcrt
    with (STATE / 'publisher.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            print('Publisher already running')
            return
        while True:
            started = time.monotonic()
            try:
                state = publish(connection)
            except Exception as error:
                state = {'ok': False, 'checked_at': datetime.now(timezone.utc).isoformat(), 'error': ('HTTP ' + str(error.code)) if isinstance(error, urllib.error.HTTPError) else type(error).__name__}
            temporary = STATE / 'publisher-status.tmp'
            temporary.write_text(json.dumps(state), encoding='utf-8')
            temporary.replace(STATE / 'publisher-status.json')
            if args.once:
                print(json.dumps(state))
                raise SystemExit(0 if state['ok'] else 1)
            time.sleep(max(1, 45 - (time.monotonic() - started)))


if __name__ == '__main__':
    main()
