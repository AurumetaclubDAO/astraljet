"""Role AJ-00..18: odczyt heartbeatów D:\\Astra Jet\\.runtime\\agents\\AJ-xx.json. Tylko odczyt.
Pole trzymane poza /api/summary, aby nie łamać ścisłego schematu ingest witryny."""
from pathlib import Path
from ..models import datum, missing, utcnow
from .files import read_json

AGENTS = Path(r'D:\Astra Jet\.runtime\agents')
ROLES = [f'AJ-{i:02d}' for i in range(19)]
STATES = {'OK', 'IDLE', 'BLOCKED', 'ERROR', 'DISABLED'}


def collect(folder=AGENTS):
    out = []
    for role in ROLES:
        path = folder / f'{role}.json'
        try:
            r = read_json(path)
            if r.get('schema') != 'aj-heartbeat-v1' or r.get('role') != role or r.get('state') not in STATES:
                raise ValueError('schema')
            ttl = max(60, min(int(r.get('ttl_s', 900)), 10 ** 9))
            val = {k: r.get(k) for k in ('name', 'state', 'summary', 'worker', 'source', 'last_run', 'next_run')}
            data = datum(val, str(path), r.get('written_at'), ttl,
                         uncertain=r['state'] in ('ERROR', 'BLOCKED'),
                         error=None if r['state'] not in ('ERROR', 'BLOCKED') else r.get('summary'))
            if r['state'] == 'DISABLED':
                data['state'] = 'CONFIRMED'
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            data = missing(str(path), 'Brak heartbeatu roli')
        out.append(dict(role=role, data=data))
    return dict(generated_at=utcnow().isoformat(), roles=out)
