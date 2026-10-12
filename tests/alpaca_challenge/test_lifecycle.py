from datetime import timedelta
import pytest
from astraljet.alpaca_challenge.models import Bar, Quote, now
from astraljet.alpaca_challenge.strategies import evaluate
from astraljet.alpaca_challenge.service import Service


def trend_fixture():
    start=now()-timedelta(minutes=250)
    bars=[]
    for i in range(45):
        price=80+i*0.4
        bars.append(Bar(t=start+timedelta(minutes=i*5),o=price-0.1,h=price+0.3,l=price-0.3,c=price,v=100000))
    # Local range ends five bars before the retest, then a confirmed breakout.
    level=max(b.h for b in bars[-20:])
    for i,(o,h,l,c,v) in enumerate([
        (level-0.1,level+0.8,level-0.2,level+0.5,180000),
        (level+0.5,level+1,level+0.2,level+0.6,160000),
        (level+0.6,level+0.9,level+0.1,level+0.4,140000),
        (level+0.4,level+0.6,level,level+0.3,130000),
        (level+0.2,level+0.6,level-0.02,level+0.4,170000)]):
        bars.append(Bar(t=start+timedelta(minutes=(45+i)*5),o=o,h=h,l=l,c=c,v=v))
    return bars


def test_scanner_valid_a(settings):
    bars=trend_fixture();last=bars[-1].c
    signal,decision=evaluate('BTC/USD','crypto',bars,bars,Quote(t=now(),bp=last-0.01,ap=last),settings)
    assert signal is not None,decision
    assert signal.setup_grade in {'A','A+'},decision
    again,_=evaluate('BTC/USD','crypto',bars,bars,Quote(t=now(),bp=last-0.01,ap=last),settings)
    assert signal.idempotency_key==again.idempotency_key
    assert signal.confidence_components==again.confidence_components


@pytest.mark.asyncio
async def test_fill_restart_tp_and_metrics(settings,signal,broker):
    settings=settings.model_copy(update={'execute_orders':True})
    svc=Service(settings,broker);await svc.reconcile()
    result=await svc.submit(signal,verify_setup=False)
    assert result['status']=='SUBMITTED',result
    assert len(svc.journal.rows('protections'))==1
    restarted=Service(settings,broker);await restarted.reconcile()
    p=restarted.journal.rows('protections')[0]
    assert p['qty']>0
    result=await restarted.close_position(p,'TP')
    assert result['status']=='SUBMITTED'
    assert restarted.journal.rows('protections')[0]['state']=='CLOSED'
    assert restarted.journal.metrics()['number_of_trades']==1
    await restarted.sync_fills()
    assert restarted.journal.metrics()['number_of_trades']==1
    assert (await restarted.submit(signal,verify_setup=False))['status']=='DUPLICATE'


@pytest.mark.asyncio
async def test_flatten_execution_mock(settings,signal,broker):
    svc=Service(settings.model_copy(update={'execute_orders':True}),broker)
    await svc.reconcile();await svc.submit(signal,verify_setup=False)
    result=await svc.flatten()
    assert result['status']=='CLOSING'
    assert not broker.open_positions
    assert svc.journal.get('kill_switch')
    assert any(isinstance(w,tuple) and w[0]=='DELETE' for w in broker.writes)


@pytest.mark.asyncio
async def test_owned_option_sell_to_close(settings,signal,broker):
    svc=Service(settings,broker);await svc.reconcile()
    with svc.journal.connect() as c:
        c.execute('INSERT INTO protections(signal_id,symbol,asset_type,direction,qty,entry,stop,target,initial_risk,opened,state) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                  ('entry-fixture','SPY271217C00700000','option','LONG',1,100,90,125,100,now().isoformat(),'ACTIVE'))
    broker.open_positions=[{'symbol':'SPY271217C00700000','qty':'1','market_value':'10000','unrealized_pl':'0'}]
    s=signal.model_copy(update={'asset_type':'option','symbol':'SPY271217C00700000','time_in_force':'day','position_intent':'sell_to_close','qty':1})
    result=await svc.submit(s)
    assert result['status']=='DRY_RUN',result
    assert result['payload']['position_intent']=='sell_to_close'
    assert result['payload']['side']=='sell'


@pytest.mark.asyncio
async def test_foreign_position_blocks(settings,broker):
    svc=Service(settings,broker)
    broker.open_positions=[{'symbol':'SPY','qty':'1','market_value':'500','unrealized_pl':'0'}]
    with pytest.raises(ValueError,match='Obce'): await svc.reconcile()
    assert svc.journal.get('kill_switch')


def test_process_lock(settings):
    from astraljet.alpaca_challenge.journal import Journal
    a=Journal(settings.challenge_db);b=Journal(settings.challenge_db)
    a.acquire()
    try:
        with pytest.raises(OSError): b.acquire()
    finally:
        a.release();b.release()


@pytest.mark.asyncio
async def test_api_cannot_forge_a_setup(settings,signal,broker):
    svc=Service(settings,broker);await svc.reconcile()
    result=await svc.submit(signal)
    assert result['status']=='NO_TRADE'
    assert not broker.writes
