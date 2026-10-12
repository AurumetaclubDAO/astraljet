import json
import pytest
from astraljet.alpaca_challenge.service import Service, ForeignState
from astraljet.alpaca_challenge.models import now


@pytest.mark.asyncio
async def test_native_stop_registered_and_idempotent(settings,signal,broker):
    svc=Service(settings.model_copy(update={'execute_orders':True}),broker)
    await svc.reconcile()
    equity=signal.model_copy(update={'asset_type':'equity','symbol':'NVDA','time_in_force':'day'})
    assert (await svc.submit(equity,verify_setup=False))['status']=='SUBMITTED'
    async def stop_submit(payload):
        broker.writes.append(payload)
        result={'id':'stop-id','client_order_id':payload['client_order_id'],'status':'new','filled_qty':'0'}
        broker.history[payload['client_order_id']]=result
        return result
    broker.submit=stop_submit
    p=svc.journal.rows('protections')[0]
    await svc.ensure_broker_stop(p,'regular')
    await svc.ensure_broker_stop(p,'regular')
    assert sum(isinstance(w,dict) and w.get('type')=='stop' for w in broker.writes)==1
    stop=svc.journal.rows('orders')[0]
    assert json.loads(stop['payload'])['stop_price']=='90.0'
    assert (await svc.close_position(p,'TP'))['status']=='WAIT_PENDING'
    assert ('DELETE','/v2/orders/stop-id') in broker.writes
    assert svc.journal.rows('protections')[0]['reason_exit']=='TP'


@pytest.mark.asyncio
async def test_foreign_flatten_explicit_account_wide(settings,broker):
    svc=Service(settings.model_copy(update={'execute_orders':True}),broker)
    broker.open_positions=[{'symbol':'SPY','asset_class':'us_equity','qty':'1','market_value':'100','unrealized_pl':'0','avg_entry_price':'90'}]
    result=await svc.flatten()
    assert result['status']=='CLOSING'
    assert not broker.open_positions
    assert svc.journal.get('kill_switch')
    assert len(svc.journal.rows('orders'))==1
    assert not svc.journal.rows('trades')  # Do not invent external entry provenance.


@pytest.mark.asyncio
async def test_native_stop_fill_creates_single_trade(settings,signal,broker):
    svc=Service(settings.model_copy(update={'execute_orders':True}),broker)
    await svc.reconcile()
    equity=signal.model_copy(update={'asset_type':'equity','symbol':'NVDA','time_in_force':'day'})
    await svc.submit(equity,verify_setup=False)
    p=svc.journal.rows('protections')[0]
    await svc.ensure_broker_stop(p,'regular')
    await svc.sync_fills();await svc.sync_fills()
    assert svc.journal.rows('protections')[0]['state']=='CLOSED'
    assert svc.journal.metrics()['number_of_trades']==1
    assert svc.journal.rows('trades')[0]['reason_exit']=='BROKER_SL'
