"""Deterministyczne reguły; score to punkty, nigdy prawdopodobieństwo zysku."""
import math
import statistics
from datetime import time, timedelta
from .models import Signal, now
from .sessions import NY

WEIGHTS = {'trend':15,'volume':15,'vwap':10,'retest':15,'relative_strength':5,
           'liquidity':10,'spread':10,'atr':5,'risk_reward':5,'higher_timeframe':10}


def indicators(bars):
    if len(bars)<30:
        raise ValueError('Co najmniej 30 świec')
    close = [b.c for b in bars]
    tr = [max(b.h-b.l,abs(b.h-a.c),abs(b.l-a.c)) for a,b in zip(bars,bars[1:])]
    atr = statistics.mean(tr[-14:])
    total = sum(b.v for b in bars)
    if total <= 0 or atr <= 0:
        raise ValueError('Brak wolumenu/ATR')
    vwap = sum((b.vw or (b.h+b.l+b.c)/3)*b.v for b in bars)/total
    fast,slow = statistics.mean(close[-10:]),statistics.mean(close[-30:])
    rv = statistics.pstdev(math.log(b/a) for a,b in zip(close[-21:],close[-20:]))
    old,new = bars[-12:-6],bars[-6:]
    hhhl = max(b.h for b in new)>max(b.h for b in old) and min(b.l for b in new)>min(b.l for b in old)
    lhll = max(b.h for b in new)<max(b.h for b in old) and min(b.l for b in new)<min(b.l for b in old)
    regime = 'RANGE'
    if fast>slow and close[-1]>vwap and hhhl:
        regime='TREND_UP'
    elif fast<slow and close[-1]<vwap and lhll:
        regime='TREND_DOWN'
    if atr/close[-1]>0.035 or rv>0.025:
        regime='HIGH_VOLATILITY'
    elif atr/close[-1]<0.0003 and rv<0.0002:
        regime='LOW_VOLATILITY'
    return {'atr':atr,'vwap':vwap,'fast':fast,'slow':slow,'realized_volatility':rv,
            'hh_hl':hhhl,'lh_ll':lhll,'regime':regime}


def grade(components, regime):
    score = sum(WEIGHTS[k]*max(0,min(1,components.get(k,0))) for k in WEIGHTS)
    if regime == 'RANGE':
        score -= 15
    if regime in {'HIGH_VOLATILITY','LOW_VOLATILITY'}:
        score -= 25
    return ('A+' if score>=95 else 'A' if score>=85 else 'B' if score>=70 else 'C'), score


def relative_strength(bars, benchmark):
    if not benchmark or len(benchmark)<20:
        return 0
    # Align timestamps rather than comparing mismatched market sessions.
    reference={b.t:b.c for b in benchmark}
    aligned=[(b.c,reference[b.t]) for b in bars if b.t in reference][-20:]
    if len(aligned)<10:
        return 0
    return aligned[-1][0]/aligned[0][0]-aligned[-1][1]/aligned[0][1]


def evaluate(symbol, kind, bars, higher, quote, settings, benchmark=None, strategy=None, direction='LONG'):
    strategy = strategy or ('CRYPTO_BREAKOUT' if kind=='crypto' else 'ORB_RETEST')
    no = lambda reason,details={}: (None, {'symbol':symbol,'strategy':strategy,'decision':'NO_TRADE','reason':reason,**details})
    if len(bars)<35 or len(higher)<30:
        return no('insufficient bars')
    ind=indicators(bars)
    hi=indicators(higher)
    last=bars[-1]
    sign=1 if direction=='LONG' else -1
    if sign<0 and (kind!='equity' or not settings.allow_equity_short):
        return no('short disabled')
    if strategy=='ORB_RETEST':
        local=last.t.astimezone(NY)
        start=local.replace(hour=9,minute=30,second=0,microsecond=0)
        end=start+timedelta(minutes=settings.orb_minutes)
        opening=[b for b in bars if start<=b.t.astimezone(NY)<end]
        if len(opening)!=settings.orb_minutes//5 or local<end+timedelta(minutes=10):
            return no('opening range incomplete')
        level=max(b.h for b in opening) if sign>0 else min(b.l for b in opening)
        prior=[b for b in bars[:-1] if b.t.astimezone(NY)>=end][-4:]
        breakout=any(sign*(b.c-level)>0 for b in prior)
    elif strategy=='MOMENTUM':
        consolidation=bars[-5:-1]
        impulse=sign*(bars[-5].c-bars[-12].c)
        if impulse<2*ind['atr'] or max(b.h for b in consolidation)-min(b.l for b in consolidation)>2*ind['atr']:
            return no('no impulse/consolidation')
        level=max(b.h for b in consolidation) if sign>0 else min(b.l for b in consolidation)
        breakout=sign*(last.c-level)>0
    else:
        window=bars[-25:-5]
        level=max(b.h for b in window) if sign>0 else min(b.l for b in window)
        breakout=any(sign*(b.c-level)>0 for b in bars[-5:-1])
    retest=(last.l<=level+0.15*ind['atr'] and last.l>=level-0.4*ind['atr'] and last.c>level) if sign>0 else (
        last.h>=level-0.15*ind['atr'] and last.h<=level+0.4*ind['atr'] and last.c<level)
    if strategy=='MOMENTUM':
        retest = breakout and sign*(last.c-last.o)>0
    volumes=[b.v for b in bars[-25:-5]]
    avg=statistics.mean(volumes)
    ratio=max(b.v for b in bars[-5:])/avg if avg else 0
    details={'breakout':breakout,'retest':retest,'level':level,'volume_ratio':ratio,**ind}
    if not breakout or not retest:
        return no('no confirmed breakout/retest',details)
    # VWAP for equities uses current regular session only.
    if kind=='equity':
        local=last.t.astimezone(NY)
        if local.time()>=time(20):
            start=local.replace(hour=20,minute=0,second=0,microsecond=0)
        elif local.time()<time(4):
            start=(local-timedelta(days=1)).replace(hour=20,minute=0,second=0,microsecond=0)
        elif local.time()<time(9,30):
            start=local.replace(hour=4,minute=0,second=0,microsecond=0)
        else:
            start=local.replace(hour=9,minute=30,second=0,microsecond=0)
        session_bars=[b for b in bars if b.t.astimezone(NY)>=start]
        if not session_bars or sum(b.v for b in session_bars)<=0:
            return no('no session VWAP')
        ind['vwap']=sum((b.vw or (b.h+b.l+b.c)/3)*b.v for b in session_bars)/sum(b.v for b in session_bars)
    trend=sign*(ind['fast']-ind['slow'])>0
    htf=sign*(hi['fast']-hi['slow'])>0 and sign*(higher[-1].c-hi['slow'])>0
    if not htf or sign*(last.c-ind['vwap'])<=0 or ratio<1.3:
        return no('volume/VWAP/higher timeframe filter',details)
    entry=quote.ap if sign>0 else quote.bp
    stop=min(last.l,level)-0.2*ind['atr'] if sign>0 else max(last.h,level)+0.2*ind['atr']
    distance=sign*(entry-stop)
    if distance<=0 or distance>3*ind['atr'] or abs(entry-last.c)>0.8*ind['atr']:
        return no('entry moved away / invalid stop',details)
    components={'trend':float(trend),'volume':float(ratio>=1.5),'vwap':1,'retest':1,
                'relative_strength':float(sign*relative_strength(bars,benchmark)>0),
                'liquidity':float(sum(b.c*b.v for b in bars[-20:])/20>=100000),
                'spread':float(quote.spread_bps<=settings.max_spread_bps),
                'atr':float(0.0003<ind['atr']/entry<0.035),'risk_reward':1,'higher_timeframe':1}
    g,score=grade(components,ind['regime'])
    if not components['spread'] or not components['liquidity']:
        return no('liquidity/spread filter',details)
    signal=Signal(idempotency_key=f'{strategy}:{symbol.replace("/","")}:{int(last.t.timestamp())}:{direction}',
        timestamp=now(),strategy_id=strategy,symbol=symbol,asset_type=kind,direction=direction,
        setup_grade=g,entry_price=entry,stop_loss=stop,take_profit=entry+sign*distance*2,
        max_loss_usd=settings.max_risk_per_trade_usd,confidence_components=components,
        reason=f'confirmed {strategy}; score={score}; regime={ind["regime"]}',time_in_force='gtc' if kind=='crypto' else 'day')
    return signal,{'symbol':symbol,'strategy':strategy,'decision':g,'score':score,'components':components,**details}
