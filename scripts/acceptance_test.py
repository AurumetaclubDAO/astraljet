"""Rzeczywisty odbiór Paper. Wszystkie mutacje brokera zablokowane."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from astraljet.alpaca_challenge.config import Settings, PAPER_URL
from astraljet.alpaca_challenge.broker import Broker
from astraljet.alpaca_challenge.service import Service
from astraljet.alpaca_challenge.models import Signal, now
from astraljet.alpaca_challenge.strategies import evaluate, WEIGHTS
from astraljet.alpaca_challenge.risk import assess, challenge


async def run():
    checks={}
    def record(name,ok,detail=''):
        checks[name]={'pass':bool(ok),'detail':detail}
        print(f'[{"PASS" if ok else "FAIL"}] {name}'+(f' — {detail}' if detail else ''))
    print('ASTRA / ALPACA ACCEPTANCE TEST')
    try:
        settings=Settings()
        record('PAPER ONLY',settings.paper_only and settings.alpaca_trading_base_url==PAPER_URL)
    except Exception as exc:
        record('PAPER ONLY',False,type(exc).__name__)
        print('RESULT: NOT READY')
        return 1
    with tempfile.TemporaryDirectory(prefix='astra-acceptance-') as directory:
        # Isolated journal and hard forced dry-run: no challenge clock or production kill changes.
        safe=settings.model_copy(update={'execute_orders':False,'challenge_db':Path(directory)/'acceptance.sqlite3','scanner_autostart':False})
        broker=Broker(safe)
        svc=Service(safe,broker)
        account=positions=q=bars=higher=None
        try:
            try:
                account=await broker.account();positions=await broker.positions()
                record('ACCOUNT',account.get('status')=='ACTIVE' and account.get('trading_blocked') is False)
                record('CHALLENGE BALANCE',abs(float(account['equity'])-safe.starting_equity)<=1 and not positions and not await broker.orders(),
                       'dedykowane puste konto Paper, equity 1000 USD')
            except Exception as exc:
                record('ACCOUNT',False,str(exc))
            try:
                q=await broker.quote('BTC/USD','crypto')
                bars=await broker.bars('BTC/USD','crypto',5)
                higher=await broker.bars('BTC/USD','crypto',60)
                for tf in (15,240): await broker.bars('BTC/USD','crypto',tf)
                record('MARKET DATA',True,'BTC/USD quote + 5m/15m/1h/4h closed bars')
            except Exception as exc:
                record('MARKET DATA',False,str(exc))
            if q and bars and higher:
                s,decision=evaluate('BTC/USD','crypto',bars,higher,q,safe)
                svc.journal.audit('scanner.decision',decision)
                scanner_result=await svc.scan_once()
                record('SCANNER',scanner_result['decisions']>0 and svc.last_scan is not None,
                       'pełny scan watchlisty, decyzje w journal; BTC: '+decision['decision'])
                s2,d2=evaluate('BTC/USD','crypto',bars,higher,q,safe)
                record('STRATEGY',decision==d2,'deterministyczny wynik, NO_TRADE jest prawidłowy')
            else:
                record('SCANNER',False,'brak aktualnych danych')
                record('STRATEGY',False,'brak aktualnych danych; testy fixture są osobne')
            if account and positions is not None and q:
                try:
                    svc.ready=True
                    svc.last_reconciled=now()
                    # Diagnostic signal exercises risk/payload, not presented as a live A setup.
                    probe=Signal(idempotency_key='acceptance-diagnostic-'+str(int(now().timestamp())),timestamp=now(),
                        strategy_id='CRYPTO_BREAKOUT',symbol='BTC/USD',asset_type='crypto',setup_grade='A+',
                        entry_price=q.ap,stop_loss=q.ap*0.98,take_profit=q.ap*1.05,max_loss_usd=5,
                        confidence_components={k:1 for k in WEIGHTS},reason='ACCEPTANCE DIAGNOSTIC, NOT A MARKET SETUP',time_in_force='gtc')
                    result=await svc.submit(probe,force_dry=True,verify_setup=False)
                    record('DRY RUN',result['status']=='DRY_RUN',result.get('reason','payload only; POST disabled'))
                    svc.kill(True,'acceptance isolated test')
                    blocked=await svc.submit(probe.model_copy(update={'idempotency_key':probe.idempotency_key+'-kill'}),force_dry=True,verify_setup=False)
                    record('KILL SWITCH',blocked['status']=='NO_TRADE' and 'kill switch' in blocked.get('reason',''))
                    svc.kill(False,'acceptance isolated restore')
                    invalid=await svc.submit(probe.model_copy(update={'idempotency_key':probe.idempotency_key+'-risk','max_loss_usd':safe.max_risk_per_trade_usd+1}),force_dry=True,verify_setup=False)
                    record('RISK ENGINE',invalid['status']=='NO_TRADE' and 'max risk' in invalid.get('reason',''))
                except Exception as exc:
                    record('DRY RUN',False,str(exc))
            for name in ('RISK ENGINE','DRY RUN','KILL SWITCH'):
                if name not in checks: record(name,False,'brak autoryzowanego konta/danych')
            svc.journal.audit('acceptance',{'checks':checks})
            record('JOURNAL',bool(svc.journal.rows('audit')))
        finally:
            await broker.close()
    ready=all(c['pass'] for c in checks.values())
    report={'timestamp':now().isoformat(),'checks':checks,'result':'READY FOR PAPER EXECUTION' if ready else 'NOT READY'}
    target=Path(__file__).resolve().parents[1]/'.runtime/alpaca/acceptance.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('RESULT: '+report['result'])
    return 0 if ready else 1


if __name__=='__main__':
    sys.exit(asyncio.run(run()))
