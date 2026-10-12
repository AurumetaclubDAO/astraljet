from datetime import timedelta
import json
import sqlite3
import httpx
import pytest
from astraljet.alpaca_challenge.broker import Broker, BrokerError, UnknownOrder
from astraljet.alpaca_challenge.models import Quote, now
from astraljet.alpaca_challenge.service import Service, client_id
from astraljet.alpaca_challenge.risk import assess, challenge


@pytest.mark.asyncio
async def test_post_timeout_found_by_id(settings):
    calls=[]
    def handler(request):
        calls.append(request.method)
        if request.method=='POST': raise httpx.ReadTimeout('test')
        if len(calls)==1: return httpx.Response(404)
        return httpx.Response(200,json={'id':'accepted','client_order_id':'cid','status':'accepted'})
    b=Broker(settings.model_copy(update={'execute_orders':True}),httpx.MockTransport(handler))
    assert (await b.submit({'client_order_id':'cid'}))['id']=='accepted'
    assert calls==['GET','POST','GET']
    await b.close()


@pytest.mark.asyncio
async def test_redirect_not_followed(settings):
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302,headers={'location':'https://api.alpaca.markets/v2/account'})
    b=Broker(settings,httpx.MockTransport(handler))
    with pytest.raises(BrokerError): await b.account()
    assert len(calls)==1 and 'paper-api' in calls[0]
    await b.close()


@pytest.mark.asyncio
async def test_unknown_intent_survives_restart(settings,signal,broker):
    svc=Service(settings,broker)
    svc.journal.reserve(signal)
    cid=client_id(signal.idempotency_key)
    svc.journal.order_intent(cid,signal.idempotency_key,{'symbol':signal.symbol,'qty':'1','side':'buy'},'entry')
    other=Service(settings,broker)
    with pytest.raises(UnknownOrder): await other.reconcile()
    assert other.journal.get('kill_switch')
    assert not broker.writes


@pytest.mark.asyncio
async def test_kill_persistent(settings,broker):
    Service(settings,broker).kill(True,'test')
    assert Service(settings,broker).journal.get('kill_switch')


@pytest.mark.asyncio
async def test_idempotency_conflict(settings,signal,broker):
    svc=Service(settings,broker);await svc.reconcile()
    await svc.submit(signal,verify_setup=False)
    with pytest.raises(ValueError,match='innego'):
        await svc.submit(signal.model_copy(update={'entry_price':101}),verify_setup=False)


@pytest.mark.asyncio
async def test_extended_limit_valid_and_overnight_halt(settings,signal,broker):
    settings=settings.model_copy(update={'allow_extended_hours':True})
    signal=signal.model_copy(update={'symbol':'NVDA','asset_type':'equity','time_in_force':'day','extended_hours':True})
    svc=Service(settings,broker);a=await broker.account();q=await broker.quote('','');asset=await broker.asset('','')
    state=challenge(svc.journal,a,[],settings)
    assert assess(signal,a,[],[],asset,q,'extended',state,settings,False)['qty']>0
    asset['overnight_halted']=True
    with pytest.raises(ValueError,match='extended-hours'):
        assess(signal,a,[],[],asset,q,'overnight',state,settings,False)


@pytest.mark.asyncio
async def test_correlation_pending_and_stale_quote(settings,signal,broker):
    svc=Service(settings,broker);a=await broker.account();q=await broker.quote('','');asset=await broker.asset('','')
    state=challenge(svc.journal,a,[],settings)
    positions=[{'symbol':'COIN','market_value':'600'}]
    signal=signal.model_copy(update={'qty':2})
    with pytest.raises(ValueError,match='correlated'):
        assess(signal,a,positions,[],asset,q,'crypto',state,settings,False)
    with pytest.raises(ValueError,match='held/pending'):
        assess(signal,a,[],[{'symbol':'BTCUSD'}],asset,q,'crypto',state,settings,False)
    with pytest.raises(ValueError,match='stale quote'):
        assess(signal,a,[],[],asset,q.model_copy(update={'t':now()-timedelta(minutes=10)}),'crypto',state,settings,False)


def test_audit_append_only(settings,broker):
    j=Service(settings,broker).journal;j.audit('test',{})
    with pytest.raises(sqlite3.IntegrityError):
        with j.connect() as c: c.execute('DELETE FROM audit')


@pytest.mark.asyncio
async def test_partial_fills_booked_once(settings,signal,broker):
    svc=Service(settings.model_copy(update={'execute_orders':True}),broker)
    await svc.reconcile();await svc.submit(signal,verify_setup=False)
    p=svc.journal.rows('protections')[0]
    cid=client_id(signal.idempotency_key,'exit-1')
    svc.journal.order_intent(cid,signal.idempotency_key,{'qty':str(p['qty']),'side':'sell'},'exit')
    half=p['qty']/2
    svc.journal.order_update(cid,{'id':'exit','client_order_id':cid,'status':'partially_filled','filled_qty':str(half),'filled_avg_price':'110'})
    await svc.sync_fills();await svc.sync_fills()
    assert svc.journal.rows('protections')[0]['qty']==pytest.approx(half)
    assert svc.journal.metrics()['number_of_trades']==0
    svc.journal.order_update(cid,{'id':'exit','client_order_id':cid,'status':'filled','filled_qty':str(p['qty']),'filled_avg_price':'115'})
    await svc.sync_fills();await svc.sync_fills()
    assert svc.journal.rows('protections')[0]['state']=='CLOSED'
    assert sum(t['qty']*t['exit_price'] for t in svc.journal.rows('trades'))==pytest.approx(p['qty']*115)


@pytest.mark.asyncio
@pytest.mark.parametrize('price,reason',[(80,'SL'),(130,'TP')])
async def test_monitor_executes_protection(settings,signal,broker,price,reason):
    svc=Service(settings.model_copy(update={'execute_orders':True}),broker)
    await svc.reconcile();await svc.submit(signal,verify_setup=False)
    async def quote(*args): return Quote(t=now(),bp=price,ap=price+0.01)
    broker.quote=quote
    await svc.monitor_once()
    assert svc.journal.rows('protections')[0]['state']=='CLOSED'
    assert svc.journal.rows('trades')[0]['reason_exit']==reason


@pytest.mark.asyncio
async def test_break_even_persisted(settings,signal,broker):
    svc=Service(settings.model_copy(update={'execute_orders':True}),broker)
    await svc.reconcile();await svc.submit(signal,verify_setup=False)
    async def quote(*args): return Quote(t=now(),bp=114,ap=114.01)
    broker.quote=quote
    await svc.monitor_once()
    assert Service(settings,broker).journal.rows('protections')[0]['stop']==100
