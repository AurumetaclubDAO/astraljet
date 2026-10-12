import asyncio
from datetime import timedelta
import httpx
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from astraljet.alpaca_challenge.config import Settings
from astraljet.alpaca_challenge.models import Signal, Quote, now
from astraljet.alpaca_challenge.broker import Broker, BrokerError, UnknownOrder
from astraljet.alpaca_challenge.service import Service, protection_trigger
from astraljet.alpaca_challenge.risk import assess, challenge, payload
from astraljet.alpaca_challenge.main import create_app
from astraljet.alpaca_challenge.strategies import evaluate


@pytest.mark.parametrize('change',[{'paper_only':False},{'alpaca_trading_base_url':'https://api.alpaca.markets'},
    {'alpaca_trading_base_url':'https://paper-api.alpaca.markets/'},{'alpaca_trading_base_url':'https://paper-api.alpaca.markets.evil'}])
def test_paper_guards(change):
    with pytest.raises(ValidationError):
        Settings(_env_file=None,executor_bearer_token='x'*32,**change)


@pytest.mark.asyncio
async def test_transport_dry_guard(settings):
    calls=[]
    b=Broker(settings,httpx.MockTransport(lambda r: calls.append(r)))
    with pytest.raises(BrokerError): await b.request('POST','/v2/orders',body={})
    assert not calls
    await b.close()


def test_invalid_signal(signal):
    with pytest.raises(ValidationError): Signal.model_validate({**signal.model_dump(),'max_loss_usd':-1})


def test_crypto_short(signal):
    with pytest.raises(ValidationError): Signal.model_validate({**signal.model_dump(),'direction':'SHORT'})


def test_naked_option_sell(signal):
    with pytest.raises(ValidationError): Signal.model_validate({**signal.model_dump(),'position_intent':'sell_to_open'})


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation,reason',[
    ('risk','max risk'),('daily','daily loss'),('drawdown','drawdown'),('positions','max positions'),
    ('buying','buying power'),('kill','kill switch'),('stale','stale'),('extended','extended-hours')])
async def test_risk_limits(settings,signal,broker,mutation,reason):
    j=Service(settings,broker).journal
    a=await broker.account(); pos=[]; asset=await broker.asset('',''); q=await broker.quote('','')
    state=challenge(j,a,pos,settings); kill=False; market='crypto'
    if mutation=='risk': signal=signal.model_copy(update={'max_loss_usd':151})
    if mutation=='daily': state['daily_loss']=250
    if mutation=='drawdown': state['drawdown']=450
    if mutation=='positions': pos=[{'symbol':s,'market_value':'1'} for s in ['A','B','C']]
    if mutation=='buying': a['buying_power']='0'
    if mutation=='kill': kill=True
    if mutation=='stale': signal=signal.model_copy(update={'timestamp':now()-timedelta(minutes=5)})
    if mutation=='extended':
        signal=signal.model_copy(update={'asset_type':'equity','symbol':'NVDA','entry_type':'market','extended_hours':True,'time_in_force':'day'})
        market='extended'
    with pytest.raises(ValueError,match=reason): assess(signal,a,pos,[],asset,q,market,state,settings,kill)


@pytest.mark.asyncio
async def test_dry_run_duplicate_restart(settings,signal,broker):
    svc=Service(settings,broker); await svc.reconcile()
    result=await svc.submit(signal,verify_setup=False)
    assert result['status']=='DRY_RUN',result
    assert not broker.writes
    second=Service(settings,broker)
    assert (await second.submit(signal,verify_setup=False))['status']=='DUPLICATE'
    assert len(second.journal.rows('signals'))==1


@pytest.mark.asyncio
async def test_concurrent_idempotency(settings,signal,broker):
    svc=Service(settings,broker); await svc.reconcile()
    results=await asyncio.gather(*(svc.submit(signal,verify_setup=False) for _ in range(8)))
    assert sum(r['status']=='DRY_RUN' for r in results)==1


@pytest.mark.asyncio
async def test_option_buy_to_open(settings,signal,broker):
    s=signal.model_copy(update={'asset_type':'option','symbol':'SPY271217C00700000','time_in_force':'day',
                              'entry_price':1,'stop_loss':0.5,'take_profit':2,'max_loss_usd':150,'qty':1})
    q=Quote(t=now(),bp=0.999,ap=1)
    svc=Service(settings,broker)
    a=await broker.account()
    decision=assess(s,a,[],[],await broker.asset('',''),q,'regular',challenge(svc.journal,a,[],settings),settings,False)
    assert decision['max_loss_usd']==100
    assert payload(s,decision,'test')['position_intent']=='buy_to_open'


@pytest.mark.asyncio
async def test_unowned_sell_to_close(settings,signal,broker):
    svc=Service(settings,broker);await svc.reconcile()
    s=signal.model_copy(update={'asset_type':'option','symbol':'SPY271217C00700000','time_in_force':'day','position_intent':'sell_to_close'})
    assert 'naked' in (await svc.submit(s))['reason']


@pytest.mark.asyncio
async def test_flatten_dry(settings,broker):
    svc=Service(settings,broker)
    result=await svc.flatten()
    assert result['status']=='DRY_RUN' and svc.journal.get('kill_switch') and not broker.writes


@pytest.mark.parametrize('bid,expected',[(89,'SL'),(126,'TP'),(105,None)])
def test_protection_triggers(settings,bid,expected):
    p={'direction':'LONG','stop':90,'target':125,'opened':now().isoformat()}
    assert protection_trigger(p,Quote(t=now(),bp=bid,ap=bid+0.01),settings)==expected


def test_scanner_no_trade(settings):
    assert evaluate('BTC/USD','crypto',[],[],Quote(t=now(),bp=99.99,ap=100),settings)[1]['decision']=='NO_TRADE'


def test_api_auth_schema_health(settings,broker):
    app=create_app(settings,broker)
    with TestClient(app) as client:
        assert client.get('/health').status_code==200
        assert client.get('/v1/account').status_code==401
        headers={'Authorization':'Bearer '+settings.executor_bearer_token.get_secret_value()}
        assert client.post('/v1/signals',json={},headers=headers).status_code==422
        assert client.post('/v1/kill-switch/on',headers=headers).json()['kill_switch']
        assert not client.post('/v1/kill-switch/off',headers=headers).json()['kill_switch']
        for path in ['/v1/account','/v1/positions','/v1/orders','/v1/signals','/v1/audit','/v1/challenge','/v1/strategies','/v1/scanner/status']:
            assert client.get(path,headers=headers).status_code==200,path


@pytest.mark.asyncio
async def test_uncertain_post_never_repeated(settings):
    calls=[]
    def handler(r):
        calls.append(r.method)
        if r.method=='POST': raise httpx.ReadTimeout('test')
        return httpx.Response(404)
    b=Broker(settings.model_copy(update={'execute_orders':True}),httpx.MockTransport(handler))
    with pytest.raises(UnknownOrder): await b.submit({'client_order_id':'test'})
    assert calls==['GET','POST','GET']
    await b.close()
