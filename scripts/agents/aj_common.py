"""Wspólny zapis heartbeatów AJ. Tylko lokalne pliki JSON; brak sekretów, brak handlu."""
import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(r'D:\Astra Jet\.runtime\agents')
NAMES = {'AJ-00': 'ChatGPT', 'AJ-01': 'Orkiestrator', 'AJ-02': 'Bibliotekarz', 'AJ-03': 'Scout', 'AJ-04': 'Odkrywca wzorców',
         'AJ-05': 'Badacz', 'AJ-06': 'Dane', 'AJ-07': 'Tester', 'AJ-08': 'Krytyk', 'AJ-09': 'Risk Management',
         'AJ-10': 'Analiza techniczna', 'AJ-11': 'Analiza fundamentalna', 'AJ-12': 'News i kalendarz', 'AJ-13': 'Makro',
         'AJ-14': 'Portfel i hedging', 'AJ-15': 'Wykonawca', 'AJ-16': 'Monitoring', 'AJ-17': 'Budżet i utrzymanie', 'AJ-18': 'S.M. Promo'}
STATES = ('OK', 'IDLE', 'BLOCKED', 'ERROR', 'DISABLED')


def now():
    return datetime.now(timezone.utc)


def write(role, state, summary, worker, source, ttl_s, last_run=None, next_run=None, details=None):
    assert role in NAMES and state in STATES
    OUT.mkdir(parents=True, exist_ok=True)
    rec = dict(schema='aj-heartbeat-v1', role=role, name=NAMES[role], state=state, summary=str(summary)[:300],
               worker=worker, source=source, ttl_s=int(ttl_s), written_at=now().isoformat(),
               last_run=(last_run or now()).isoformat(), next_run=next_run.isoformat() if next_run else None,
               details=details or {})
    fd, tmp = tempfile.mkstemp(dir=OUT, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False)
    os.replace(tmp, OUT / f'{role}.json')
    return rec
