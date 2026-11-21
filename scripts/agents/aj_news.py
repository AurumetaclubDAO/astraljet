"""AJ-12 News i kalendarz: darmowy kalendarz ForexFactory (tydzień), tylko odczyt. Co 60 min."""
import json, sys, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from aj_common import write, now, OUT

URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
CCY = {'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'CAD', 'AUD', 'CHF'}
try:
    req = urllib.request.Request(URL, headers={'User-Agent': 'AstralJet-readonly/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    t = now()
    ev = []
    for e in data:
        d = datetime.fromisoformat(e['date']).astimezone(timezone.utc)
        if e.get('impact') == 'High' and e.get('country') in CCY and t - timedelta(hours=2) <= d <= t + timedelta(hours=48):
            ev.append(dict(time=d.isoformat(), ccy=e['country'], title=e['title'][:80], forecast=e.get('forecast'), previous=e.get('previous')))
    ev.sort(key=lambda x: x['time'])
    nxt = [e for e in ev if e['time'] >= t.isoformat()]
    s = (f"Następne High: {datetime.fromisoformat(nxt[0]['time']).astimezone().strftime('%d.%m %H:%M')} {nxt[0]['ccy']} {nxt[0]['title']}"
         if nxt else 'Brak wydarzeń High w 48 h') + f' · {len(nxt)} w 48 h'
    write('AJ-12', 'OK', s, 'aj_news.py (AJ-News, co 60 min)', URL, 3 * 3600, next_run=t + timedelta(hours=1), details={'events': ev[:15]})
except Exception as e:
    write('AJ-12', 'ERROR', f'Kalendarz niedostępny ({type(e).__name__})', 'aj_news.py', URL, 3 * 3600)
