import math
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from .models import now, occ
from .strategies import grade


def number(value):
    result=float(value)
    if not math.isfinite(result):
        raise ValueError('Niepoprawna liczba brokera')
    return result


def symbol_key(symbol):
    return symbol.replace('/','')


def challenge(journal, account, positions, settings):
    equity=number(account['equity'])
    if equity<=0:
        raise ValueError('Niepoprawne equity')
    state=journal.get('challenge',{})
    metrics=journal.metrics()
    unrealized=sum(number(p['unrealized_pl']) for p in positions)
    if not state:
        # Broker equity is observed; no invented $1000 broker balance.
        state={'started_at':None,'starting_equity':settings.starting_equity,
               'high_water_mark':settings.starting_equity,'max_drawdown':0,
               'day_date':now().date().isoformat(),'day_equity':equity}
    if state['day_date']!=now().date().isoformat():
        # Last broker mark from previous day: keep overnight P&L in daily loss.
        state['day_equity']=state.get('current_equity',equity)
        state['day_date']=now().date().isoformat()
    active=bool(state.get('started_at'))
    if active:
        state['high_water_mark']=max(state['high_water_mark'],equity)
    state.update(metrics)
    state['gross_realized_pnl']=metrics['realized_pnl']
    state['realized_pnl']=equity-settings.starting_equity-unrealized if active else 0
    state['journal_pnl_basis']='gross fills; account realized includes broker costs, dedicated account without transfers required'
    state.update(current_equity=equity,unrealized_pnl=unrealized,
        day_number=(now()-datetime.fromisoformat(state['started_at'])).days+1 if active else 0,
        drawdown=max(0,state['high_water_mark']-equity),
        daily_loss=max(0,state['day_equity']-equity),
        return_pct=(equity/settings.starting_equity-1)*100,
        mode='EXECUTION' if settings.execute_orders else 'DRY_RUN',
        balance_matches_start=abs(equity-settings.starting_equity)<=1 if not active else True)
    state['max_drawdown']=max(state['max_drawdown'],state['drawdown'])
    journal.set('challenge',state)
    return state


def assess(s, account, positions, pending, asset, quote, session, state, settings, kill):
    def require(condition, reason):
        if not condition:
            raise ValueError(reason)
    require(not kill,'kill switch')
    require(-5<=(now()-s.timestamp).total_seconds()<=settings.max_signal_age_seconds,'stale signal')
    require(account.get('status')=='ACTIVE' and account.get('trading_blocked') is False
            and account.get('account_blocked') is False,'account blocked/unverified')
    require(asset.get('tradable') is True and asset.get('status')=='active','asset not tradable')
    require(state.get('day_number',0)<=settings.challenge_days,'challenge ended')
    require(state['daily_loss']<settings.max_daily_loss_usd,'daily loss limit')
    require(state['drawdown']<settings.max_total_drawdown_usd and
            settings.starting_equity-state['current_equity']<settings.max_total_drawdown_usd,'total drawdown limit')
    require(s.setup_grade in {'A','A+'},'grade not executable')
    computed,_=grade(s.confidence_components,'TREND_UP')
    require(computed in {'A','A+'},'unverified score')
    require(quote.spread_bps<=settings.max_spread_bps,'spread limit')
    require(-5<=(now()-quote.t).total_seconds()<=settings.max_quote_age_seconds,'stale quote')
    multiplier=100 if s.asset_type=='option' else 1
    if s.asset_type=='crypto':
        require(asset.get('class') in {None,'crypto'},'asset class mismatch')
        require(s.direction=='LONG','crypto short forbidden')
        require(s.time_in_force in {'gtc','ioc'} and not s.extended_hours,'crypto order validation')
    elif s.asset_type=='option':
        contract=occ(s.symbol)
        require(session=='regular' and not s.extended_hours and s.time_in_force=='day','option market closed/order type')
        require(contract['expiry']>now().date(),'expiry day blocked')
        require(number(asset.get('size',0))==100,'nonstandard option contract')
        require(number(account.get('options_trading_level',0))>=2,'options level unverified')
        require(s.direction=='LONG' and s.position_intent=='buy_to_open','naked sell forbidden')
    else:
        require(asset.get('class') in {None,'us_equity'},'asset class mismatch')
        require(s.time_in_force=='day','equity TIF must be day')
        if session!='regular':
            require(settings.allow_extended_hours and s.extended_hours and s.entry_type=='limit'
                and asset.get('overnight_tradable') is True and asset.get('overnight_halted') is False,
                'extended-hours order validation')
        if s.direction=='SHORT':
            require(settings.allow_equity_short and asset.get('shortable') is True
                    and asset.get('easy_to_borrow') is True,'short unavailable')
    require(s.position_intent=='buy_to_open','closing signal uses separate close path')
    key=symbol_key(s.symbol)
    require(not any(symbol_key(p['symbol'])==key for p in positions+pending),'symbol already held/pending')
    require(len({symbol_key(p['symbol']) for p in positions+pending})<settings.max_open_positions,'max positions')
    entry=quote.ap if s.direction=='LONG' else quote.bp
    require(abs(entry/s.entry_price-1)<=0.005,'entry price moved')
    if s.entry_type=='limit':
        entry=max(entry,s.entry_price) if s.direction=='LONG' else min(entry,s.entry_price)
    require(s.stop_loss<entry<s.take_profit if s.direction=='LONG' else s.take_profit<entry<s.stop_loss,
            'price crossed protection levels')
    unit_risk=entry*multiplier if s.asset_type=='option' else abs(entry-s.stop_loss)+entry*0.005
    require(s.max_loss_usd<=settings.max_risk_per_trade_usd,'max risk violation')
    cap=min(s.max_loss_usd,settings.max_daily_loss_usd-state['daily_loss'],
            settings.max_total_drawdown_usd-state['drawdown'])
    # No margin allocation beyond the challenge's cash equity.
    exposure=sum(abs(number(p['market_value'])) for p in positions)
    reserved=sum(number(p.get('qty',0))*number(p.get('limit_price') or p.get('_price',0))*
                 (100 if p.get('asset_class')=='us_option' else 1) for p in pending)
    require(all(p.get('limit_price') or p.get('_price') for p in pending),'unknown pending notional')
    buying=min(number(account['buying_power']),max(0,state['current_equity']-exposure-reserved))
    if s.asset_type=='option':
        buying=min(buying,number(account['options_buying_power']))
    max_qty=min(cap/unit_risk,settings.max_position_notional_usd/(entry*multiplier),buying/(entry*multiplier))
    # Whole equities permit a broker-native stop; crypto remains fractional.
    increment=Decimal('1') if s.asset_type in {'option','equity'} else Decimal('0.000001')
    qty=float(Decimal(str(s.qty if s.qty is not None else max_qty)).quantize(increment,rounding=ROUND_DOWN))
    require(qty>0,'insufficient buying power/size')
    risk=qty*unit_risk
    notional=qty*entry*multiplier
    require(risk<=cap+1e-7,'max risk violation')
    require(notional<=settings.max_position_notional_usd+1e-7,'max notional')
    require(notional<=buying+1e-7,'buying power')
    for group in ({'QQQ','NVDA','AMD'},{'BTCUSD','COIN'}):
        if key in group:
            group_value=sum(abs(number(p['market_value'])) for p in positions if symbol_key(p['symbol']) in group)
            group_value+=sum(number(p['qty'])*number(p.get('limit_price') or p.get('_price',0)) for p in pending if symbol_key(p['symbol']) in group)
            require(group_value+notional<=settings.max_correlated_notional_usd,'correlated exposure')
    require(abs(s.take_profit-entry)/abs(entry-s.stop_loss)>=1.5,'risk reward')
    return {'qty':qty,'max_loss_usd':risk,'notional':notional,'reference_price':entry}


def payload(s, decision, cid):
    p={'symbol':s.symbol,'qty':str(decision['qty']),'side':'buy' if s.direction=='LONG' else 'sell',
       'type':s.entry_type,'time_in_force':s.time_in_force,'client_order_id':cid}
    if s.entry_type=='limit':
        # Buy down / sell up: rounding must not increase allocated risk.
        decimals=2 if s.entry_price>=1 else 4
        value=Decimal(str(s.entry_price)).quantize(Decimal('0.01') if decimals==2 else Decimal('0.0001'),
               rounding=ROUND_DOWN if s.direction=='LONG' else 'ROUND_UP')
        p['limit_price']=str(value)
        if value<=0:
            raise ValueError('limit price below supported tick')
    if s.asset_type=='equity':
        p['extended_hours']=s.extended_hours
    if s.asset_type=='option':
        p['position_intent']='buy_to_open'
    return p
