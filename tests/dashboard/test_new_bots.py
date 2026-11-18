import json
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from astraljet.dashboard.config import BOTS, MAGIC, TASKS
from astraljet.dashboard.collectors.files import signal, runner_state

spec = importlib.util.spec_from_file_location('dsp_newbots', Path(__file__).resolve().parents[2] / 'scripts/dashboard_site_publish.py')
publisher = importlib.util.module_from_spec(spec); spec.loader.exec_module(publisher)


def test_new_bots_registered():
    ids = {b[0]: b for b in BOTS}
    assert ids['tq-mr-rsi2'][2] == 'TQ-MR-RSI2' and ids['tq-mr-rsi2'][4] == (2026101606,)
    assert ids['tq-tpb'][2] == 'TQ-TPB' and ids['tq-tpb'][4] == (2026101607,)
    assert MAGIC[2026101606] == 'tq-mr-rsi2' and MAGIC[2026101607] == 'tq-tpb'
    assert 'TQ-MRRSI2-Demo' in TASKS and 'TQ-TPB-Demo' in TASKS
    assert len(BOTS) == 8


def test_d1_signals_last_batch_and_state(tmp_path):
    (tmp_path / 'signals.csv').write_text(
        'eval_time,symbol,bar_d1,signal,indicators,atr14,lot,sl,tp,action,detail\n'
        '2026-10-15T05:30:00+02:00,SP500,2026-10-14,NONE,{},1,,,,NONE,\n'
        '2026-10-16T05:30:29+02:00,SP500,2026-10-15,NONE,{},1,,,,NONE,\n'
        '2026-10-16T05:30:29+02:00,BTCUSD,2026-10-15,LONG,{},1,,,,FILLED,\n', encoding='utf-8')
    s = signal(tmp_path, 86400)
    assert s['state'] != 'MISSING'
    assert [r['symbol'] for r in s['value']['last_batch']] == ['SP500', 'BTCUSD']
    (tmp_path / 'state.json').write_text(json.dumps({'last_eval_bar': {}, 'kill_stats': {'trades': 6, 'dd_usd': 10.0, 'loss_streak': 6, 'pf': 0.5},
                                                      'paused': True, 'paused_reason': 'LOSS_STREAK'}), encoding='utf-8')
    v = runner_state(tmp_path, 300)['value']
    assert v['paused'] is True and v['status'] == 'PAUSED DEMO' and v['kill_stats']['loss_streak'] == 6
    (tmp_path / 'state.json').write_text(json.dumps({'kill_stats': {'trades': 0}}), encoding='utf-8')
    assert runner_state(tmp_path, 300)['value']['status'] == 'RUNNING DEMO'


def test_legacy_state_unchanged(tmp_path):
    (tmp_path / 'state.json').write_text(json.dumps({'a': 1}), encoding='utf-8')
    assert runner_state(tmp_path, 300)['value'] == {'keys_count': 1}


def test_publisher_keeps_site_schema_six_bots():
    snap = {'generated_at': datetime.now(timezone.utc).isoformat(), 'positions': {'value': []},
            'account': {'value': {'login': 90000001, 'server': 'VantageMarkets-Demo', 'mode': 'DEMO'}},
            'bots': [{'id': b[0]} for b in BOTS]}
    out = json.loads(publisher.prepare(snap, 90000001))  # fikcyjny numer testowy
    assert [b['id'] for b in out['bots']] == list(publisher.SITE_BOT_IDS)
    assert len(out['bots']) == 6
