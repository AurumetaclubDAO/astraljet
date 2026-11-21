"""AJ heartbeat: wyprowadza stan ról z istniejących workerów (tylko odczyt). Uruchamiany co 5 min."""
import json, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from aj_common import write, now

DESK = Path(r'C:\Users\karol\Desktop')
TTL = 900  # 3 przebiegi po 5 min


def summary():
    with urllib.request.urlopen('http://127.0.0.1:8877/api/summary', timeout=20) as r:
        return json.load(r)


def mtime(p):
    return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)


def st(d):
    return {'CONFIRMED': 'OK', 'UNCONFIRMED': 'IDLE', 'MISSING': 'ERROR'}.get((d or {}).get('state'), 'ERROR')


def safe(role, fn):
    try:
        fn()
    except Exception as e:
        write(role, 'ERROR', f'Błąd odczytu: {type(e).__name__}', 'aj_heartbeat.py', '-', TTL)


def main():
    s = summary()
    agents = {a['name']: a['data'] for a in s.get('agents', [])}

    def aj01():
        sch = s.get('schedule') or {}
        bad = [k for k, v in sch.items() if isinstance(v, dict) and v.get('state') != 'CONFIRMED']
        write('AJ-01', 'OK' if sch and not bad else 'IDLE', f'Harmonogram: {len(sch)} zadań, bez potwierdzenia: {len(bad)}',
              'Windows Task Scheduler (TQ-*)', '8877 /api/summary schedule', TTL, details={'unconfirmed': bad[:10]})

    def aj03():
        p = DESK / 'TQ-Arena' / 'status.json'
        t = mtime(p)
        a = agents.get('ATLAS') or {}
        write('AJ-03', 'OK' if now() - t < timedelta(minutes=40) else 'IDLE', (a.get('value') or {}).get('summary', 'Arena'),
              'TQ-Arena-Refresh', str(p), TTL, last_run=t)

    def aj06():
        f = s.get('funding') or []
        ok = sum(1 for x in f if (x.get('data') or {}).get('state') == 'CONFIRMED')
        acc = s.get('account') or {}
        write('AJ-06', 'OK' if acc.get('state') == 'CONFIRMED' else 'ERROR',
              f"MT5 odczyt: {acc.get('state')} · funding/OI potwierdzone {ok}/{len(f)}", 'MT5 SDK + TQ-FundingOI-Collector', '8877 /api/summary', TTL)

    def aj07():
        p = Path(r'D:\Astra Jet\.runtime\agents\tester_last.json')
        if p.exists():
            r = json.loads(p.read_text(encoding='utf-8'))
            write('AJ-07', 'IDLE', r.get('summary', 'Ostatni backtest'), 'backtesty offline (box /workspace/bt)', str(p), 7 * 86400,
                  last_run=datetime.fromisoformat(r['last_run']))
        else:
            write('AJ-07', 'IDLE', 'Brak zapisu wyniku testów', 'backtesty offline', str(p), 7 * 86400)

    def aj09():
        a = agents.get('TITAN') or {}
        write('AJ-09', 'OK' if a.get('state') in ('CONFIRMED', 'UNCONFIRMED') else 'ERROR', (a.get('value') or {}).get('summary', a.get('error')),
              'risk_gate.py + risk_config.json + KILL_SWITCH', 'TQ-Common', TTL)

    def aj10():
        a = agents.get('VEGA') or {}
        write('AJ-10', st(a), (a.get('value') or {}).get('summary', a.get('error')), 'TQ-TECHVOL-Demo + TQ-HORMUZ-Demo', 'signals.csv', TTL)

    def aj15():
        a = agents.get('NOVA') or {}
        n = len((s.get('positions') or {}).get('value') or [])
        write('AJ-15', 'OK' if a.get('state') != 'MISSING' else 'IDLE',
              f"{(a.get('value') or {}).get('summary', 'brak decyzji')} · otwarte pozycje: {n}", 'TQ runners + gated_order.py', 'signals.csv + MT5', TTL,
              last_run=datetime.fromisoformat(a['as_of']) if a.get('as_of') else None)

    def aj16():
        p = Path(r'D:\Astra Jet\.runtime\dashboard\publisher-status.json')
        r = json.loads(p.read_text(encoding='utf-8'))
        ack = datetime.fromisoformat(r['acknowledged_at'])
        fresh = r.get('ok') and now() - ack < timedelta(minutes=5)
        write('AJ-16', 'OK' if fresh else 'ERROR', f"Publikator: {'OK' if fresh else 'BRAK ACK'} · ostatni ACK {ack.astimezone().strftime('%H:%M:%S')}",
              'dashboard 8877 + publisher', str(p), TTL, last_run=ack)

    for role, fn in (('AJ-01', aj01), ('AJ-03', aj03), ('AJ-06', aj06), ('AJ-07', aj07), ('AJ-09', aj09),
                     ('AJ-10', aj10), ('AJ-15', aj15), ('AJ-16', aj16)):
        safe(role, fn)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        write('AJ-16', 'ERROR', f'Panel 8877 niedostępny ({type(e).__name__})', 'aj_heartbeat.py', '127.0.0.1:8877', TTL)
