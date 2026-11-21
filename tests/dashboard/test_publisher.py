import importlib.util
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import pytest

DEMO_LOGIN = 90000001  # fikcyjny numer testowy

spec = importlib.util.spec_from_file_location('dashboard_site_publish', Path(__file__).resolve().parents[2] / 'scripts/dashboard_site_publish.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)

def sample():
    return {'generated_at': datetime.now(timezone.utc).isoformat(), 'account': {'value': {'login': DEMO_LOGIN, 'server': 'VantageMarkets-Demo', 'mode': 'DEMO'}}, 'positions': {'value': []}}

def test_destination_and_demo_guard():
    with pytest.raises(ValueError):
        publisher.publish({'site': 'https://wrong.example'})
    for key, value in [('login', 1), ('mode', 'LIVE'), ('server', 'Other')]:
        s = sample(); s['account']['value'][key] = value
        with pytest.raises(ValueError):
            publisher.prepare(s, DEMO_LOGIN)

def test_credentials_paths_and_staleness():
    s = sample(); s['source'] = r'C:\Users\tester\Desktop\TQ-HORMUZ\runner.log'
    assert json.loads(publisher.prepare(s, DEMO_LOGIN))['source'] == 'TQ-HORMUZ/runner.log'
    s['generated_at'] = (datetime.now(timezone.utc)-timedelta(minutes=6)).isoformat()
    with pytest.raises(ValueError): publisher.prepare(s, DEMO_LOGIN)
    s = sample(); s['nested'] = {'api_key': 'do-not-upload'}
    with pytest.raises(ValueError): publisher.prepare(s, DEMO_LOGIN)

def test_missing_account_cannot_ship_positions():
    s = sample(); s['account']['value'] = None
    with pytest.raises(ValueError): publisher.prepare(s, DEMO_LOGIN)
    s['positions']['value'] = None
    assert json.loads(publisher.prepare(s, DEMO_LOGIN))['positions']['value'] is None

def test_publisher_requires_local_demo_login(tmp_path):
    with pytest.raises(ValueError):
        publisher.demo_login(tmp_path / 'brak.toml')
    p = tmp_path / 'accounts.toml'
    p.write_text(f'demo_login = {DEMO_LOGIN}\n', encoding='utf-8')
    assert publisher.demo_login(p) == DEMO_LOGIN
    s = sample()
    publisher.ACCOUNTS, original = tmp_path / 'brak.toml', publisher.ACCOUNTS
    try:
        with pytest.raises(ValueError):
            publisher.prepare(s)  # bez lokalnej konfiguracji nic nie jest publikowane
    finally:
        publisher.ACCOUNTS = original

def test_dpapi_roundtrip():
    encrypted = publisher.protect(b'test-not-a-real-secret')
    assert b'test-not-a-real-secret' not in encrypted
    assert publisher.protect(encrypted, decrypt=True) == b'test-not-a-real-secret'
