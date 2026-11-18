import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS
from zoneinfo import ZoneInfo
import pytest
from astraljet.dashboard.config import Config, BOTS
from astraljet.dashboard.models import utcnow, datum, missing
from astraljet.dashboard.collectors import risk, funding, arena, schedule
from astraljet.dashboard.collectors.files import read_text, log_errors, signal
from astraljet.dashboard.collectors.mt5 import read_sdk
from astraljet.dashboard.service import compose, runner_data
from .test_safety import FakeSDK, DEMO_LOGIN, cfg as demo_cfg


def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data),encoding='utf-8')


def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)


def test_kill_switch_missing_parent_is_unknown(tmp_path):
    assert risk.collect(Config(desktop=tmp_path))['kill_switch']['state']=='MISSING'


def test_kill_switch_absence_is_false_not_missing(tmp_path):
    (tmp_path/'TQ-Common').mkdir()
    ds=risk.collect(Config(desktop=tmp_path))['kill_switch']
    assert ds['state']=='CONFIRMED' and ds['value'] is False


def test_kill_switch_present_is_true(tmp_path):
    p=tmp_path/'TQ-Common'/'KILL_SWITCH';p.parent.mkdir();p.touch()
    assert risk.collect(Config(desktop=tmp_path))['kill_switch']['value'] is True


def test_bad_json_does_not_escape(tmp_path):
    p=tmp_path/'TQ-Arena'/'status.json';p.parent.mkdir();p.write_text('{')
    assert arena.collect(Config(desktop=tmp_path))['state']=='MISSING'


@pytest.mark.parametrize('fresh',[True,False,None,{'readAt':utcnow().isoformat(),'login':str(DEMO_LOGIN),'server':'VantageMarkets-Demo'}])
def test_arena_never_confirms_unsupported_metrics(tmp_path,fresh):
    stamp=utcnow().isoformat()
    write_json(tmp_path/'TQ-Arena'/'status.json',{'refreshed_at':stamp,'freshMt5Read':fresh,'bots':[{'id':'tq-vb','equity':4000,'lastRefresh':stamp,'metrics':{'ret':0,'trades':2}}]})
    ds=arena.collect(demo_cfg(desktop=tmp_path))
    assert ds['state']=='UNCONFIRMED'
    assert ds['value']['bots'][0]['allocation']==4000
    assert ds['value']['bots'][0]['metrics']['state']=='UNCONFIRMED'


def funding_row(stamp,error=''):
    return dict(collected_at_utc=stamp,source='binance-usdm',symbol='BTCUSDT',source_time_utc=stamp,
                mark_price='80000',funding_rate='0.0001',open_interest_contracts='2',open_interest_usd='160000',error=error)


def test_latest_funding_error_not_hidden_by_old_success(tmp_path):
    now=utcnow();p=tmp_path/'TQ-Common/funding_oi/funding_oi_snapshots.csv'
    write_csv(p,[funding_row((now-timedelta(minutes=2)).isoformat()),funding_row(now.isoformat(),'provider unavailable')])
    ds=funding.collect(Config(desktop=tmp_path))[0]['data']
    assert ds['state']=='MISSING' and ds['value'] is None


def test_funding_valid_and_stale(tmp_path):
    p=tmp_path/'TQ-Common/funding_oi/funding_oi_snapshots.csv'
    write_csv(p,[funding_row(utcnow().isoformat())]);assert funding.collect(Config(desktop=tmp_path))[0]['data']['state']=='CONFIRMED'
    write_csv(p,[funding_row((utcnow()-timedelta(hours=1)).isoformat())]);assert funding.collect(Config(desktop=tmp_path))[0]['data']['state']=='UNCONFIRMED'


@pytest.mark.parametrize('number',['nan','inf','bad'])
def test_funding_rejects_nonfinite(tmp_path,number):
    p=tmp_path/'TQ-Common/funding_oi/funding_oi_snapshots.csv';r=funding_row(utcnow().isoformat());r['mark_price']=number
    write_csv(p,[r]);assert funding.collect(Config(desktop=tmp_path))[0]['data']['state']=='MISSING'


def test_signal_uses_evaluation_time_not_mtime(tmp_path):
    write_csv(tmp_path/'signals.csv',[{'eval_time':(utcnow()-timedelta(hours=2)).isoformat(),'symbol':'BTCUSD','signal':'NONE','action':'NO_TRADE','reason':'test'}])
    assert signal(tmp_path,1200)['state']=='UNCONFIRMED'


def test_naive_time_not_assumed_utc(tmp_path):
    write_csv(tmp_path/'signals.csv',[{'eval_time':'2026-10-13 12:00:00','signal':'NONE'}])
    assert signal(tmp_path,1200)['state']=='MISSING'


def test_log_partial_and_secret_not_returned(tmp_path):
    p=tmp_path/'runner.log';stamp=utcnow().isoformat()
    p.write_text('\n'.join([f'{stamp} ERROR password=secret-value']*2002),encoding='utf-8')
    ds=log_errors(p)
    assert ds['state']=='UNCONFIRMED' and ds['value']['count']==2000
    assert 'secret-value' not in json.dumps(ds)


def test_log_undated_traceback_not_false_zero(tmp_path):
    p=tmp_path/'runner.log';p.write_text('Traceback secret data',encoding='utf-8')
    ds=log_errors(p);assert ds['state']=='UNCONFIRMED' and ds['value']['partial']


def test_file_size_bound(tmp_path):
    p=tmp_path/'source.json';p.write_text('12345')
    with pytest.raises(ValueError): read_text(p,4)


def test_schedule_allowlisted_query_only(tmp_path):
    def fake(args,**kwargs):
        import base64
        text=base64.b64decode(args[-1]).decode('utf-16-le')
        assert 'Get-ScheduledTask' in text
        assert not any(x in text for x in ('Start-Scheduled','Stop-Scheduled','Set-Scheduled','Register-Scheduled'))
        return NS(returncode=0,stdout=json.dumps([dict(name='TQ-HORMUZ-Demo',state='Ready',last_run=utcnow().isoformat(),last_result=0,next_run=utcnow().isoformat())]).encode())
    result=schedule.collect(Config(desktop=tmp_path),fake)
    assert result['TQ-HORMUZ-Demo']['state']=='CONFIRMED'
    assert result['TQ-HORMUZ-Signal']['state']=='MISSING'


def deal(ticket,magic,time,profit=-10,commission=-1,entry=1,position_id=1):
    return NS(ticket=ticket,magic=magic,time=int(time.timestamp()),profit=profit,commission=commission,swap=-2,fee=-.5,type=0,entry=entry,position_id=position_id)


def test_deals_deduplicated_and_costs_included():
    sdk=FakeSDK();d=deal(1,2026101301,utcnow());sdk.deals=[d,d]
    h=read_sdk(sdk,demo_cfg())['history']['value']
    assert len(h['deals'])==1 and h['deals'][0]['amount']==-13.5


def test_position_id_attributes_manual_exit_when_entry_known():
    sdk=FakeSDK();now=utcnow()
    sdk.deals=[deal(1,2026101301,now,entry=0),deal(2,0,now)]
    h=read_sdk(sdk,demo_cfg())['history']['value']
    assert h['deals'][1]['bot']=='tq-hormuz'


def test_unmapped_exit_not_invented():
    sdk=FakeSDK();sdk.deals=[deal(2,0,utcnow())]
    h=read_sdk(sdk,demo_cfg())['history']['value'];assert h['unassigned']==1


def test_cash_movement_not_trading_profit():
    sdk=FakeSDK();d=deal(1,0,utcnow(),profit=10000);d.type=2;sdk.deals=[d]
    assert read_sdk(sdk,demo_cfg())['history']['value']['deals']==[]


def test_day_boundary_dst_is_timezone_aware():
    warsaw=ZoneInfo('Europe/Warsaw')
    a=datetime(2026,10,25,tzinfo=warsaw);b=datetime(2026,10,26,tzinfo=warsaw)
    assert (b.timestamp()-a.timestamp())==25*3600


def test_foreign_currency_suppresses_usd_usage(tmp_path):
    cfg=demo_cfg(desktop=tmp_path,mt5_enabled=False,schedule_enabled=False)
    sdk=FakeSDK();sdk.account.currency='EUR';market=read_sdk(sdk,cfg)
    sleeve=dict(sleeve_usd=3000,max_risk_pct_per_trade=1,daily_loss_pct=3,max_positions=2)
    limits={'config':datum({'sleeves':{'tq-hormuz':sleeve}},'config',utcnow()),'kill_switch':datum(False,'switch',utcnow())}
    snap=compose(cfg,market,limits,{},missing('arena'),[],runner_data(cfg))
    assert snap['bots'][0]['loss_usage']['state']=='MISSING'
