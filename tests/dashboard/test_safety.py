import ast
import builtins
import io
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from fastapi.testclient import TestClient
from astraljet.dashboard.config import Config, HOST, PORT, ROOT, load_accounts
from astraljet.dashboard.api.app import create_app
from astraljet.dashboard.collectors.mt5 import read_sdk, collect
from astraljet.dashboard.models import datum, utcnow, age_tree
from astraljet.dashboard.security import redact, data_path
from astraljet.dashboard.service import DashboardService

# Jawnie fikcyjne numery rachunków; prawdziwe są tylko w lokalnym .runtime/dashboard/accounts.toml.
DEMO_LOGIN = 90000001
LIVE_LOGIN = 90000002


def cfg(**kwargs):
    return Config(demo_login=DEMO_LOGIN, forbidden_logins=(LIVE_LOGIN,), **kwargs)


class FakeSDK:
    ACCOUNT_TRADE_MODE_DEMO = 0
    def __init__(self, login=DEMO_LOGIN, mode=0, server='VantageMarkets-Demo'):
        self.account = NS(login=login, trade_mode=mode, server=server, currency='USD', balance=20000, equity=19990, margin=50, margin_free=19940, profit=-10)
        self.closed = False
        self.reads = []
        self.accounts = 0
        self.change_after = None
        self.positions = []
        self.deals = []
    def initialize(self, path, **kwargs):
        assert set(kwargs) == {'timeout'}
        return True
    def account_info(self):
        self.accounts += 1
        if self.change_after and self.accounts >= self.change_after:
            self.account.login = LIVE_LOGIN
        return self.account
    def terminal_info(self): return NS(connected=True, trade_allowed=False)
    def positions_get(self): self.reads.append('positions'); return self.positions
    def history_deals_get(self, start, end): self.reads.append('history'); assert start.tzinfo and end.tzinfo; return self.deals
    def shutdown(self): self.closed = True


@pytest.mark.parametrize('login,mode,server', [(LIVE_LOGIN,2,'VantageMarkets-Live'),(LIVE_LOGIN,0,'VantageMarkets-Demo'),(1,0,'VantageMarkets-Demo'),(DEMO_LOGIN,2,'VantageMarkets-Demo'),(DEMO_LOGIN,0,'VantageMarkets-Live')])
def test_account_gate(login, mode, server):
    sdk = FakeSDK(login, mode, server)
    result = read_sdk(sdk, cfg())
    assert all(v['state'] == 'MISSING' for v in result.values())
    assert sdk.closed and not sdk.reads
    assert '20000' not in json.dumps(result)


def test_demo_and_empty_positions_are_confirmed():
    sdk = FakeSDK()
    result = read_sdk(sdk, cfg())
    assert result['positions']['value'] == []
    assert result['positions']['state'] == 'CONFIRMED'
    assert result['terminal']['value']['algo_trading'] is False
    assert result['account']['value']['login'] == DEMO_LOGIN
    assert sdk.closed


def test_missing_local_account_config_blocks_every_read():
    sdk = FakeSDK()  # poprawny rachunek DEMO, ale bez lokalnej konfiguracji numerów
    result = read_sdk(sdk, Config())
    assert all(v['state'] == 'MISSING' for v in result.values())
    assert sdk.closed and not sdk.reads and sdk.accounts == 0


def test_local_accounts_file(tmp_path):
    assert load_accounts(tmp_path / 'brak.toml') == {}
    p = tmp_path / 'accounts.toml'
    p.write_text(f'demo_login = {DEMO_LOGIN}\nforbidden_logins = [{LIVE_LOGIN}]\n', encoding='utf-8')
    loaded = load_accounts(p)
    assert loaded == {'demo_login': DEMO_LOGIN, 'forbidden_logins': (LIVE_LOGIN,)}
    assert Config(**loaded).demo_login == DEMO_LOGIN


@pytest.mark.parametrize('demo,forbidden', [(DEMO_LOGIN, (DEMO_LOGIN,)), ('123', ()), (-1, ()), (DEMO_LOGIN, ('x',)), (True, ())])
def test_invalid_account_config_rejected(demo, forbidden):
    with pytest.raises(ValueError):
        Config(demo_login=demo, forbidden_logins=forbidden)


def test_account_switch_invalidates_whole_snapshot():
    sdk = FakeSDK(); sdk.change_after = 4
    result = read_sdk(sdk, cfg())
    assert all(v['value'] is None for v in result.values())
    assert sdk.closed


def test_failed_positions_not_empty_success():
    sdk = FakeSDK(); sdk.positions = None
    assert read_sdk(sdk, cfg())['positions']['state'] == 'MISSING'


def test_timeout_returns_missing():
    import subprocess
    def run(*args, **kwargs): raise subprocess.TimeoutExpired('worker',15)
    assert collect(cfg(), run)['account']['state'] == 'MISSING'


@pytest.mark.parametrize('age,state', [(0,'CONFIRMED'),(90,'CONFIRMED'),(91,'UNCONFIRMED'),(-6,'UNCONFIRMED')])
def test_data_state_age(age,state):
    now=utcnow()
    assert datum(0,'test',now-timedelta(seconds=age),now=now)['state']==state


def test_cached_data_expires():
    now=utcnow();ds=datum(1,'test',now,now=now)
    assert age_tree({'data':ds},now+timedelta(seconds=91))['data']['state']=='UNCONFIRMED'


@pytest.mark.parametrize('value', ['sk-'+'x'*30,'PK'+'a'*20,'AK'+'b'*20,'password=secret123','hasło: tajemnica','Bearer '+ 'z'*20,'a'*64,'QmFzZTY0'*10,'https://user:pass@example.test'])
def test_redaction(value):
    assert '[UKRYTO]' in redact(value)
    assert redact(value)!=value


def test_recursive_redaction_preserves_numbers():
    assert redact({'api_key':'hidden','value':[{'profit':12.5}]}) == {'api_key':'[UKRYTO]','value':[{'profit':12.5}]}


def test_no_secret_files_opened(tmp_path,monkeypatch):
    original_builtin,original_io=builtins.open,io.open
    def protect(original):
        def guard(file,*args,**kwargs):
            if not isinstance(file,int):
                name=Path(file).name.lower()
                assert not name.startswith('.env') and name!='klucze.txt'
            return original(file,*args,**kwargs)
        return guard
    monkeypatch.setattr(builtins,'open',protect(original_builtin))
    monkeypatch.setattr(io,'open',protect(original_io))
    config=Config(desktop=tmp_path,mt5_enabled=False,schedule_enabled=False)
    service=DashboardService(config)
    import asyncio
    asyncio.run(service.refresh())
    assert service.view()['account']['state']=='MISSING'
    with pytest.raises(ValueError): data_path(tmp_path/'.env')
    with pytest.raises(ValueError): data_path(tmp_path/'KLUCZE.txt')


def client(tmp_path):
    cfg=Config(desktop=tmp_path,mt5_enabled=False,schedule_enabled=False)
    return TestClient(create_app(config=cfg,start_polling=False),base_url='http://127.0.0.1')


@pytest.mark.parametrize('route',['health','summary','bots','positions','risk','arena','funding','schedule','alpaca'])
def test_api_missing_sources_200(tmp_path,route):
    with client(tmp_path) as c:
        r=c.get('/api/'+route)
        assert r.status_code==200
        assert r.headers['cache-control']=='no-store'
        assert 'access-control-allow-origin' not in r.headers


@pytest.mark.parametrize('method',['POST','PUT','DELETE','PATCH','HEAD','OPTIONS'])
def test_mutations_rejected(tmp_path,method):
    with client(tmp_path) as c: assert c.request(method,'/api/summary').status_code==405


def test_host_guard(tmp_path):
    with client(tmp_path) as c: assert c.get('/api/summary',headers={'host':'attacker.example'}).status_code==400


def test_routes_bind_and_static_boundary(tmp_path):
    app=create_app(Config(desktop=tmp_path),start_polling=False)
    assert HOST=='127.0.0.1' and PORT==8877
    assert all(r.methods=={'GET'} for r in app.routes)
    forbidden_calls={'order_send','order_check','submit_order','login','symbol_select','post','put','delete','patch'}
    for p in (ROOT/'src/astraljet/dashboard').rglob('*.py'):
        tree=ast.parse(p.read_text(encoding='utf-8'))
        for n in ast.walk(tree):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute): assert n.func.attr not in forbidden_calls,(p,n.lineno)
            if isinstance(n,(ast.Import,ast.ImportFrom)):
                text=ast.unparse(n)
                assert all(x not in text for x in ('alpaca_challenge','executor','gated_order','tq_core','dotenv'))
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name): assert n.func.id not in {'eval','exec','__import__'}
        assert 'shell=True' not in p.read_text(encoding='utf-8')


def test_client_rendering_has_no_html_injection():
    js=(ROOT/'src/astraljet/dashboard/web/app.js').read_text(encoding='utf-8')
    assert 'innerHTML' not in js and 'textContent' in js
