import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from .broker import Broker, BrokerError, UnknownOrder
from .journal import Journal
from .models import Signal, now
from .risk import assess, challenge, payload, number, symbol_key
from .sessions import session
from .strategies import evaluate, WEIGHTS

LOG=logging.getLogger('astra.paper')
TERMINAL={'filled','canceled','expired','rejected','replaced'}


class ForeignState(ValueError):
    pass


def client_id(key, suffix='entry'):
    return 'astra-'+hashlib.sha256((key+':'+suffix).encode()).hexdigest()[:40]


def protection_trigger(p, quote, settings):
    sign=1 if p['direction']=='LONG' else -1
    price=quote.bp if sign>0 else quote.ap
    if sign*(price-p['stop'])<=0:
        return 'SL'
    if sign*(price-p['target'])>=0:
        return 'TP'
    if (now()-datetime.fromisoformat(p['opened'])).total_seconds()>=settings.time_stop_minutes*60:
        return 'TIME_STOP'
    return None


class Service:
    def __init__(self, settings, broker=None):
        self.settings=settings
        self.broker=broker or Broker(settings)
        self.journal=Journal(settings.challenge_db)
        self.lock=asyncio.Lock()
        self.tasks=[]
        self.scanning=False
        self.ready=False
        self.last_scan=None
        self.last_error=None
        self.stopping=False
        self.last_reconciled=None

    async def start(self):
        self.journal.acquire()
        self.journal.audit('service.start',{'paper_only':True,'execute_orders':self.settings.execute_orders})
        try:
            await self.reconcile()
        except (BrokerError, ValueError, KeyError, TypeError) as exc:
            self.fail('startup',exc)
        self.scanning=self.settings.scanner_autostart
        self.tasks=[asyncio.create_task(self.monitor_loop()),asyncio.create_task(self.scanner_loop())]

    async def stop(self):
        self.stopping=True
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks,return_exceptions=True)
        await self.broker.close()
        self.journal.audit('service.stop',{})
        self.journal.release()

    def fail(self, stage, exc):
        # Only controlled errors are rendered; validation/network objects may contain secrets.
        message=str(exc) if isinstance(exc,(BrokerError,ValueError)) and not hasattr(exc,'errors') else type(exc).__name__
        self.last_error=f'{stage}: {message}'
        self.ready=False
        self.journal.audit('error',{'stage':stage,'error':self.last_error})
        LOG.error('%s',self.last_error)

    def kill(self, enabled, reason):
        self.journal.set('kill_switch',enabled)
        self.journal.audit('kill_switch',{'enabled':enabled,'reason':reason})

    async def state(self):
        async with self.lock:
            account=await self.broker.account()
            positions=await self.broker.positions()
            return challenge(self.journal,account,positions,self.settings)

    async def reconcile(self):
        async with self.lock:
            await self._reconcile()

    async def _reconcile(self):
        account=await self.broker.account()
        positions=await self.broker.positions()
        pending=await self.broker.orders()
        if not isinstance(positions,list):
            raise ValueError('Niepoprawne positions')
        # Query every non-terminal local intent, including interrupted SUBMITTING.
        with self.journal.connect() as c:
            local=[dict(r) for r in c.execute('SELECT * FROM orders')]
        for order in local:
            if order['status'] not in TERMINAL:
                remote=await self.broker.by_client_id(order['client_order_id'])
                if remote is None:
                    self.kill(True,'unresolved order')
                    raise UnknownOrder('Nierozstrzygnięty client_order_id; ręczna kontrola wymagana')
                self.journal.order_update(order['client_order_id'],remote)
                if order['role']=='entry' and remote['status'] not in TERMINAL and self.settings.execute_orders:
                    with self.journal.connect() as c:
                        signal_time=c.execute('SELECT timestamp FROM signals WHERE idempotency_key=?',(order['signal_id'],)).fetchone()
                    if signal_time and (now()-datetime.fromisoformat(signal_time[0])).total_seconds()>self.settings.max_signal_age_seconds:
                        await self.broker.request('DELETE','/v2/orders/'+remote['id'])
                        self.journal.audit('entry.expired',{'client_order_id':order['client_order_id']})
        await self.sync_fills()
        with self.journal.connect() as c:
            protected={symbol_key(r['symbol']) for r in c.execute("SELECT symbol FROM protections WHERE state!='CLOSED'")}
            known={r[0] for r in c.execute('SELECT client_order_id FROM orders')}
        foreign=[p['symbol'] for p in positions if symbol_key(p['symbol']) not in protected]
        if foreign or any(o.get('client_order_id') not in known for o in pending):
            self.kill(True,'unmanaged broker state')
            raise ForeignState('Obce pozycje lub zlecenia; wymagane dedykowane konto challenge')
        # A protection disappearing without our confirmed exit cannot be accounted as a trade.
        live={symbol_key(p['symbol']):abs(number(p['qty'])) for p in positions}
        with self.journal.connect() as c:
            active=[dict(r) for r in c.execute("SELECT * FROM protections WHERE state!='CLOSED'")]
        for p in active:
            if abs(live.get(symbol_key(p['symbol']),0)-p['qty'])>1e-5:
                self.kill(True,'position reconciliation mismatch')
                raise ValueError('Niezgodność ilości pozycji i journal')
        state=challenge(self.journal,account,positions,self.settings)
        if self.settings.execute_orders and not state.get('started_at'):
            if positions or pending or not state['balance_matches_start']:
                raise ValueError('Start wymaga pustego Paper account z equity 1000 USD')
            state.update(started_at=now().isoformat(),high_water_mark=number(account['equity']),day_equity=number(account['equity']))
            self.journal.set('challenge',state)
        self.ready=True
        self.last_reconciled=now()
        self.last_error=None

    async def submit(self, s, *, force_dry=False, verify_setup=True):
        async with self.lock:
            previous=self.journal.reserve(s)
            if previous:
                return {'status':'DUPLICATE','previous_status':previous['status'],'result':json.loads(previous['result'] or '{}')}
            try:
                if s.position_intent=='sell_to_close':
                    return await self.external_close(s,force_dry)
                if not self.ready:
                    raise ValueError('reconciliation not ready')
                if self.last_reconciled is None or (now()-self.last_reconciled).total_seconds()>30:
                    await self._reconcile()
                account=await self.broker.account()
                positions=await self.broker.positions()
                pending=await self.broker.orders()
                with self.journal.connect() as c:
                    exit_ids={r[0] for r in c.execute("SELECT client_order_id FROM orders WHERE role='exit'")}
                pending=[o for o in pending if o.get('client_order_id') not in exit_ids]
                asset=await self.broker.asset(s.symbol,s.asset_type)
                current_session=await session(self.broker,s.asset_type,self.settings)
                quote=await self.broker.quote(s.symbol,s.asset_type,'overnight' if current_session=='overnight' else None)
                if verify_setup:
                    await self.verify_signal(s,quote)
                state=challenge(self.journal,account,positions,self.settings)
                decision=assess(s,account,positions,pending,asset,quote,current_session,state,self.settings,
                                self.journal.get('kill_switch',False))
                # Existing stop/premium budgets plus pending intents reserve loss capacity.
                with self.journal.connect() as c:
                    reserved=c.execute("SELECT COALESCE(SUM(initial_risk),0) FROM protections WHERE state!='CLOSED'").fetchone()[0]
                    waiting=c.execute("SELECT s.body FROM orders o JOIN signals s ON s.idempotency_key=o.signal_id WHERE o.role='entry' AND o.status NOT IN ('filled','canceled','expired','rejected','replaced') AND o.filled_qty=0").fetchall()
                reserved+=sum(Signal.model_validate_json(r[0]).max_loss_usd for r in waiting)
                if reserved+decision['max_loss_usd']>min(self.settings.max_daily_loss_usd-state['daily_loss'],self.settings.max_total_drawdown_usd-state['drawdown']):
                    raise ValueError('aggregate reserved loss budget')
                cid=client_id(s.idempotency_key)
                order_payload=payload(s,decision,cid)
                result={'status':'DRY_RUN','risk':decision,'payload':order_payload}
                if self.settings.execute_orders and not force_dry:
                    # Protect startup readiness even if called without lifecycle.
                    if not state.get('started_at'):
                        raise ValueError('challenge not started')
                    self.journal.order_intent(cid,s.idempotency_key,order_payload,'entry')
                    try:
                        response=await self.broker.submit(order_payload)
                        self.journal.order_update(cid,response)
                        if response['status']=='rejected':
                            raise BrokerError('Broker rejected entry')
                    except (BrokerError,ValueError,KeyError) as exc:
                        self.kill(True,'uncertain/rejected submit: reconcile before next entry')
                        raise UnknownOrder('Zlecenie wymaga reconciliation') from exc
                    result['status']='SUBMITTED'
                    result['order_id']=response['id']
                    await self.sync_fills()
                self.journal.finish(s.idempotency_key,result)
                return result
            except (BrokerError,ValueError,KeyError,TypeError) as exc:
                result={'status':'UNKNOWN' if isinstance(exc,UnknownOrder) else 'NO_TRADE','reason':str(exc)}
                self.journal.finish(s.idempotency_key,result)
                return result

    async def verify_signal(self,s,quote):
        if s.asset_type=='option':
            # Recheck the underlying trigger, while option liquidity/premium is checked by risk.
            from .models import occ
            contract=occ(s.symbol)
            symbol=contract['underlying']
            direction='LONG' if contract['type']=='C' else 'SHORT'
            if direction=='SHORT' and not self.settings.allow_equity_short:
                # A PUT is long premium, so bearish underlying evaluation is allowed.
                strategy_settings=self.settings.model_copy(update={'allow_equity_short':True})
            else:
                strategy_settings=self.settings
            q=await self.broker.quote(symbol,'equity')
            bars=await self.broker.bars(symbol,'equity',5)
            higher=await self.broker.bars(symbol,'equity',60)
            confirmed,_=evaluate(symbol,'equity',bars,higher,q,strategy_settings,strategy=s.strategy_id,direction=direction)
        else:
            market=await session(self.broker,s.asset_type,self.settings)
            feed='boats' if market=='overnight' else None
            bars=await self.broker.bars(s.symbol,s.asset_type,5,feed)
            higher=await self.broker.bars(s.symbol,s.asset_type,60,feed)
            if s.asset_type=='crypto':
                from .strategies import indicators
                for tf in (15,240):
                    context=indicators(await self.broker.bars(s.symbol,'crypto',tf))
                    if context['fast']<context['slow']:
                        raise ValueError('15m/4h trend filter')
            confirmed,_=evaluate(s.symbol,s.asset_type,bars,higher,quote,self.settings,strategy=s.strategy_id,direction=s.direction)
        if confirmed is None or confirmed.setup_grade not in {'A','A+'}:
            raise ValueError('Setup niepotwierdzony bieżącymi danymi strategii')
        if s.asset_type!='option':
            if abs(s.stop_loss-confirmed.stop_loss)>confirmed.entry_price*0.0001:
                raise ValueError('SL różny od deterministycznej strategii')

    async def sync_fills(self):
        with self.journal.connect() as c:
            entries=[dict(r) for r in c.execute("SELECT o.*,s.body FROM orders o JOIN signals s ON s.idempotency_key=o.signal_id WHERE o.role='entry' AND o.filled_qty>0")]
            for o in entries:
                s=Signal.model_validate_json(o['body'])
                p=c.execute('SELECT * FROM protections WHERE signal_id=?',(o['signal_id'],)).fetchone()
                qty=o['filled_qty']-(p['realized_qty'] if p else 0)
                if not p:
                    risk=o['filled_qty']*(o['filled_price']*100 if s.asset_type=='option' else abs(o['filled_price']-s.stop_loss)+o['filled_price']*0.005)
                    response=json.loads(o['response'] or '{}')
                    opened=response.get('filled_at') or response.get('submitted_at') or now().isoformat()
                    c.execute('INSERT INTO protections(signal_id,symbol,asset_type,direction,qty,entry,stop,target,initial_risk,opened,state) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (o['signal_id'],s.symbol,s.asset_type,s.direction,qty,o['filled_price'],s.stop_loss,s.take_profit,risk,opened,'ACTIVE'))
                elif p['state']!='CLOSED':
                    c.execute('UPDATE protections SET qty=?,entry=? WHERE signal_id=?',(qty,o['filled_price'],o['signal_id']))
            exits=[dict(r) for r in c.execute("SELECT * FROM orders WHERE role='exit' AND filled_qty>0")]
            for o in exits:
                p=c.execute('SELECT * FROM protections WHERE signal_id=?',(o['signal_id'],)).fetchone()
                booked=c.execute('SELECT COALESCE(SUM(qty),0),COALESCE(SUM(qty*exit_price),0) FROM trades WHERE id LIKE ?', (o['client_order_id']+':%',)).fetchone()
                delta=o['filled_qty']-booked[0]
                if not p or delta<=1e-9:
                    continue
                exit_price=(o['filled_qty']*o['filled_price']-booked[1])/delta
                sign=1 if p['direction']=='LONG' else -1
                pnl=sign*(exit_price-p['entry'])*delta*(100 if p['asset_type']=='option' else 1)
                s=c.execute('SELECT strategy FROM signals WHERE idempotency_key=?',(o['signal_id'],)).fetchone()
                trade_id=o['client_order_id']+':'+str(o['filled_qty'])
                c.execute('INSERT INTO trades VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                    (trade_id,o['signal_id'],p['opened'],now().isoformat(),p['entry'],exit_price,delta,pnl,
                     sign*(exit_price/p['entry']-1)*100,pnl/p['initial_risk'] if p['initial_risk'] else 0,s[0],p['reason_exit'] or 'BROKER_SL'))
                remaining=max(0,p['qty']-delta)
                c.execute('UPDATE protections SET qty=?,realized_qty=realized_qty+?,state=? WHERE signal_id=?',
                    (remaining,delta,'CLOSED' if remaining<1e-8 else 'ACTIVE',o['signal_id']))

    async def close_position(self,p,reason,*,force_dry=False):
        with self.journal.connect() as c:
            pending=[dict(r) for r in c.execute("SELECT * FROM orders WHERE signal_id=? AND status NOT IN ('filled','canceled','expired','rejected','replaced')",(p['signal_id'],))]
        if pending:
            # Cancel any still-filling entry before closing; verify on next monitoring pass.
            for order in pending:
                if order['role']=='entry' and self.settings.execute_orders and not force_dry and order['alpaca_order_id']:
                    await self.broker.request('DELETE','/v2/orders/'+order['alpaca_order_id'])
                elif order['role']=='exit' and json.loads(order['payload']).get('type')=='stop' and reason!='SL' and self.settings.execute_orders and not force_dry:
                    await self.broker.request('DELETE','/v2/orders/'+order['alpaca_order_id'])
            if self.settings.execute_orders and not force_dry:
                with self.journal.connect() as c:
                    c.execute('UPDATE protections SET reason_exit=? WHERE signal_id=?',(reason,p['signal_id']))
            return {'status':'WAIT_PENDING','reason':reason}
        current_session=await session(self.broker,p['asset_type'],self.settings)
        quote=await self.broker.quote(p['symbol'],p['asset_type'],'overnight' if current_session=='overnight' else None)
        positions=await self.broker.positions()
        position=next((r for r in positions if symbol_key(r['symbol'])==symbol_key(p['symbol'])),None)
        if position is None or number(position['qty'])*(1 if p['direction']=='LONG' else -1)<=0:
            raise ValueError('Closing quantity not confirmed')
        seq=p['exit_sequence']+1
        cid=client_id(p['signal_id'],f'exit-{seq}')
        side='sell' if p['direction']=='LONG' else 'buy'
        order={'symbol':p['symbol'],'qty':str(min(p['qty'],abs(number(position['qty'])))),
               'side':side,'type':'market','time_in_force':'gtc' if p['asset_type']=='crypto' else 'day','client_order_id':cid}
        if p['asset_type']=='option':
            order['position_intent']='sell_to_close'
        if p['asset_type']=='equity' and current_session!='regular':
            asset=await self.broker.asset(p['symbol'],'equity')
            if asset.get('overnight_tradable') is not True or asset.get('overnight_halted') is not False:
                raise ValueError('Extended close unavailable')
            order.update(type='limit',extended_hours=True,limit_price=str(round(quote.bp*0.997 if side=='sell' else quote.ap*1.003,2)))
        self.journal.audit('protection.trigger',{'symbol':p['symbol'],'reason':reason,'payload':order})
        if force_dry or not self.settings.execute_orders:
            return {'status':'DRY_RUN','payload':order}
        with self.journal.connect() as c:
            c.execute('UPDATE protections SET exit_sequence=?,reason_exit=? WHERE signal_id=?',(seq,reason,p['signal_id']))
        self.journal.order_intent(cid,p['signal_id'],order,'exit')
        try:
            remote=await self.broker.submit(order)
            self.journal.order_update(cid,remote)
        except (BrokerError,ValueError) as exc:
            self.kill(True,'uncertain close')
            raise UnknownOrder('Close requires reconciliation') from exc
        await self.sync_fills()
        return {'status':'SUBMITTED','order_id':remote['id']}

    async def external_close(self,s,force_dry):
        if s.asset_type!='option':
            raise ValueError('sell_to_close only options')
        if (now()-s.timestamp).total_seconds()>self.settings.max_signal_age_seconds:
            raise ValueError('stale close signal')
        with self.journal.connect() as c:
            row=c.execute("SELECT * FROM protections WHERE symbol=? AND state!='CLOSED'",(s.symbol,)).fetchone()
        if not row or row['direction']!='LONG':
            raise ValueError('naked option sell rejection')
        p=dict(row)
        if s.qty is not None and s.qty>p['qty']:
            raise ValueError('close exceeds owned contracts')
        if s.qty is not None:
            p['qty']=s.qty
        result=await self.close_position(p,'API_CLOSE',force_dry=force_dry)
        self.journal.finish(s.idempotency_key,result)
        return result

    async def flatten(self):
        async with self.lock:
            self.kill(True,'flatten requested')
            pending=await self.broker.orders()
            positions=await self.broker.positions()
            if not self.settings.execute_orders:
                result={'status':'DRY_RUN','cancel_orders':len(pending),'close_positions':len(positions)}
            else:
                # Explicit endpoint is account-wide by contract. No new entries can race the lock.
                await self.broker.request('DELETE','/v2/orders')
                for attempt in range(10):
                    if not await self.broker.orders():
                        break
                    await asyncio.sleep(0.5)
                else:
                    raise ValueError('Flatten: cancellation not confirmed, no closing orders sent')
                try:
                    await self._reconcile()
                except ForeignState:
                    # Explicit account-wide flatten also owns the authority to close foreign positions.
                    # Unknown POSTs and all other reconciliation errors still stop this operation.
                    self.journal.audit('flatten.foreign_positions',{'action':'explicit account-wide close'})
                positions=await self.broker.positions()
                with self.journal.connect() as c:
                    protected=[dict(r) for r in c.execute("SELECT * FROM protections WHERE state!='CLOSED'")]
                results=[await self.close_position(p,'FLATTEN') for p in protected]
                owned={symbol_key(p['symbol']) for p in protected}
                for position in positions:
                    if symbol_key(position['symbol']) in owned:
                        continue
                    kind={'us_equity':'equity','crypto':'crypto','us_option':'option'}.get(position.get('asset_class'))
                    if kind is None or (kind in {'crypto','option'} and number(position['qty'])<0):
                        raise ValueError('Flatten: unsupported foreign position class/direction')
                    seq=self.journal.get('foreign_flatten_sequence',0)+1
                    self.journal.set('foreign_flatten_sequence',seq)
                    symbol=position['symbol']
                    if kind=='crypto' and '/' not in symbol and symbol.endswith('USD'):
                        symbol=symbol[:-3]+'/USD'
                    self.journal.audit('flatten.foreign_snapshot',{'symbol':symbol,'qty':position['qty'],
                        'avg_entry_price':position.get('avg_entry_price'),'note':'external position, no invented entry trade'})
                    foreign={'signal_id':f'foreign-flatten-{seq}','symbol':symbol,'asset_type':kind,
                             'direction':'LONG' if number(position['qty'])>0 else 'SHORT','qty':abs(number(position['qty'])),'exit_sequence':0}
                    results.append(await self.close_position(foreign,'FLATTEN'))
                result={'status':'CLOSING','results':results}
            self.journal.audit('flatten',result)
            return result

    async def monitor_once(self):
        async with self.lock:
            try:
                await self._reconcile()
            except (BrokerError,ValueError,KeyError,TypeError) as exc:
                self.fail('reconciliation',exc)
                # Blocking entries must never disable monitoring of owned positions.
            state=self.journal.get('challenge',{})
            limit=(state.get('daily_loss',0)>=self.settings.max_daily_loss_usd or
                state.get('drawdown',0)>=self.settings.max_total_drawdown_usd or
                state.get('day_number',0)>self.settings.challenge_days)
            if limit:
                self.kill(True,'challenge risk/end')
            with self.journal.connect() as c:
                active=[dict(r) for r in c.execute("SELECT * FROM protections WHERE state!='CLOSED'")]
            for p in active:
                try:
                    market=await session(self.broker,p['asset_type'],self.settings)
                    q=await self.broker.quote(p['symbol'],p['asset_type'],'overnight' if market=='overnight' else None)
                    reason=p['reason_exit'] or ('CHALLENGE_LIMIT' if limit else protection_trigger(p,q,self.settings))
                    if reason:
                        await self.close_position(p,reason)
                    else:
                        sign=1 if p['direction']=='LONG' else -1
                        price=q.bp if sign>0 else q.ap
                        if sign*(price-p['entry'])>=abs(p['target']-p['entry'])/2 and sign*(p['stop']-p['entry'])<0:
                            with self.journal.connect() as c:
                                c.execute('UPDATE protections SET stop=? WHERE signal_id=?',(p['entry'],p['signal_id']))
                            self.journal.audit('protection.break_even',{'symbol':p['symbol'],'stop':p['entry']})
                            p['stop']=p['entry']
                        await self.ensure_broker_stop(p,market)
                except (BrokerError,ValueError,KeyError,TypeError) as exc:
                    self.fail('protection '+p['symbol'],exc)

    async def ensure_broker_stop(self,p,market):
        """Native equity hard SL; local TP/time exits cancel it before closing."""
        if not self.settings.execute_orders or p['asset_type']!='equity' or p['direction']!='LONG' or market!='regular' or not float(p['qty']).is_integer():
            return
        with self.journal.connect() as c:
            pending=[dict(r) for r in c.execute("SELECT * FROM orders WHERE signal_id=? AND status NOT IN ('filled','canceled','expired','rejected','replaced')",(p['signal_id'],))]
        if pending:
            for order in pending:
                body=json.loads(order['payload'])
                if order['role']=='exit' and body.get('type')=='stop' and (float(body['stop_price'])!=round(p['stop'],2) or float(body['qty'])!=p['qty']):
                    await self.broker.request('DELETE','/v2/orders/'+order['alpaca_order_id'])
                    self.journal.audit('broker_stop.refresh',{'signal_id':p['signal_id']})
            return
        seq=p['exit_sequence']+1
        cid=client_id(p['signal_id'],f'exit-{seq}')
        body={'symbol':p['symbol'],'qty':str(int(p['qty'])),'side':'sell' if p['direction']=='LONG' else 'buy',
              'type':'stop','time_in_force':'gtc','stop_price':str(round(p['stop'],2)),'client_order_id':cid}
        with self.journal.connect() as c:
            c.execute('UPDATE protections SET exit_sequence=? WHERE signal_id=?',(seq,p['signal_id']))
        self.journal.order_intent(cid,p['signal_id'],body,'exit')
        try:
            remote=await self.broker.submit(body)
            self.journal.order_update(cid,remote)
            if remote['status']=='rejected':
                raise BrokerError('Broker rejected native stop')
        except (BrokerError,ValueError) as exc:
            self.kill(True,'unconfirmed native stop')
            raise UnknownOrder('Native SL requires reconciliation') from exc
        self.journal.audit('broker_stop.submitted',{'symbol':p['symbol'],'stop':p['stop']})

    async def monitor_loop(self):
        while not self.stopping:
            try:
                await self.monitor_once()
            except Exception as exc:
                self.fail('monitor',exc)
            await asyncio.sleep(self.settings.monitor_interval_seconds)

    async def scan_once(self):
        count=0
        for kind,watch in (('crypto',self.settings.crypto),('equity',self.settings.equities)):
            for symbol in [x.strip() for x in watch.split(',') if x.strip()]:
                try:
                    market=await session(self.broker,kind,self.settings)
                    q=await self.broker.quote(symbol,kind,'overnight' if market=='overnight' else None)
                    feed='boats' if market=='overnight' else None
                    bars=await self.broker.bars(symbol,kind,5,feed)
                    higher=await self.broker.bars(symbol,kind,60,feed)
                    # Fetch and evaluate multi-timeframe crypto filters; no old snapshots.
                    if kind=='crypto':
                        medium=await self.broker.bars(symbol,kind,15)
                        long=await self.broker.bars(symbol,kind,240)
                        from .strategies import indicators
                        if indicators(medium)['fast']<indicators(medium)['slow'] or indicators(long)['fast']<indicators(long)['slow']:
                            raise ValueError('15m/4h trend filter')
                    benchmark=None
                    reference={'NVDA':'QQQ','AMD':'QQQ','COIN':'BTC/USD'}.get(symbol)
                    if reference:
                        benchmark=await self.broker.bars(reference,'crypto' if '/' in reference else 'equity',5,None if '/' in reference else feed)
                    strategies=['CRYPTO_BREAKOUT'] if kind=='crypto' else ['ORB_RETEST','MOMENTUM']
                    for strategy in strategies:
                        directions=['LONG','SHORT'] if kind=='equity' and self.settings.allow_equity_short else ['LONG']
                        for direction in directions:
                            signal,decision=evaluate(symbol,kind,bars,higher,q,self.settings,benchmark,strategy,direction)
                            self.journal.audit('scanner.decision',decision)
                            if signal:
                                if market in {'extended','overnight'}:
                                    signal=signal.model_copy(update={'extended_hours':True})
                                await self.submit(signal)
                            count+=1
                except Exception as exc:
                    self.journal.audit('scanner.decision',{'symbol':symbol,'decision':'NO_TRADE','reason':str(exc) if isinstance(exc,BrokerError) else type(exc).__name__+': '+str(exc)[:250]})
                    count+=1
        self.last_scan=now().isoformat()
        self.journal.set('scanner_last_scan',self.last_scan)
        return {'decisions':count,'timestamp':self.last_scan}

    async def scanner_loop(self):
        while not self.stopping:
            if self.scanning:
                try:
                    await self.scan_once()
                except Exception as exc:
                    self.fail('scanner',exc)
            await asyncio.sleep(self.settings.scanner_interval_seconds)
