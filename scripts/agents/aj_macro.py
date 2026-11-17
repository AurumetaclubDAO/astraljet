"""AJ-13 Makro: darmowe CSV FRED bez klucza (fredgraph.csv), tylko odczyt. Co 6 h."""
import csv, io, sys, urllib.request
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from aj_common import write, now

SERIES = {'DGS10': 'US10Y %', 'DFF': 'Fed Funds %', 'T10Y2Y': '10Y-2Y %', 'DCOILBRENTEU': 'Brent $', 'VIXCLS': 'VIX'}
out, errs = {}, []
for sid, label in SERIES.items():
    try:
        req = urllib.request.Request(f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}', headers={'User-Agent': 'AstralJet-readonly/1.0'})
        with urllib.request.urlopen(req, timeout=60) as r:
            rows = [x for x in csv.reader(io.StringIO(r.read().decode('utf-8'))) if len(x) == 2 and x[1] not in ('', '.')][1:]
        if rows:
            d, v = rows[-1]
            prev = rows[-2][1] if len(rows) > 1 else None
            out[sid] = dict(label=label, date=d, value=float(v), prev=float(prev) if prev else None)
    except Exception as e:
        errs.append(f'{sid}:{type(e).__name__}')
t = now()
s = ' · '.join(f"{x['label']} {x['value']:g} ({x['date']})" for x in out.values()) or 'Brak danych FRED'
state = 'OK' if out and not errs else ('IDLE' if out else 'ERROR')
write('AJ-13', state, s + (f' · błędy: {len(errs)}' if errs else ''), 'aj_macro.py (AJ-Makro, co 6 h)', 'fred.stlouisfed.org fredgraph.csv',
      18 * 3600, next_run=t + timedelta(hours=6), details={'series': out, 'errors': errs})
