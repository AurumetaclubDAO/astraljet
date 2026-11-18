"""Pokój decyzyjny: adapter tylko do odczytu. Nie generuje decyzji ani zleceń."""
from ..models import datum, missing, parse_time
from .files import read_json, rows

TECH_HORMUZ = (('TECH', 'TQ-TECH-VOL'), ('HORMUZ', 'TQ-HORMUZ'))
ORDER_BOTS = ('TQ-HORMUZ', 'TQ-TECH-VOL', 'TQ-XASSET-LAG', 'TQ-ALT-SPEC', 'TQ-MR-RSI2', 'TQ-TPB')


def _oldest(stamps):
    return min(stamps) if stamps else None


def atlas(arena_data):
    if arena_data['state'] == 'MISSING':
        return missing('Pokój decyzyjny / Arena', 'Brak snapshotu Areny')
    bots = (arena_data['value'] or {}).get('bots', [])
    active = sum(1 for b in bots if str(b.get('status', '')).upper() not in ('PAUSED', 'STOPPED', 'REMOVED'))
    value = {'summary': f'Arena: {len(bots)} botów, aktywne {active}', 'bots': len(bots), 'active': active}
    return datum(value, arena_data['source'], arena_data['as_of'], arena_data['ttl_s'], uncertain=True,
                 error='Snapshot Areny bez pełnego potwierdzenia pochodzenia')


def vega(config):
    parts, stamps = [], []
    try:
        for label, folder in TECH_HORMUZ:
            data = rows(config.desktop / folder / 'signals.csv')
            for tf in ('H1', 'M15'):
                sel = [r for r in data if r.get('tf') == tf]
                if not sel:
                    continue
                last_time = max(parse_time(r['eval_time']) for r in sel)
                batch = [r for r in sel if parse_time(r['eval_time']) == last_time]
                hits = [f"{r['symbol']} {r['signal']}" for r in batch if r.get('signal') not in (None, '', 'NONE')]
                parts.append(f"{label} {tf}: " + (', '.join(hits) if hits else 'brak sygnału'))
                stamps.append(last_time)
        if not stamps:
            return missing('Pokój decyzyjny / sygnały', 'Brak ewaluacji TECH/HORMUZ')
        return datum({'summary': ' · '.join(parts), 'items': parts}, 'TQ-TECH-VOL + TQ-HORMUZ signals.csv',
                     _oldest(stamps), config.freshness['runner'])
    except (OSError, ValueError, KeyError, TypeError):
        return missing('Pokój decyzyjny / sygnały', 'Brak poprawnych sygnałów TECH/HORMUZ')


def titan(config, limits):
    path = config.desktop / 'TQ-Common' / 'risk_config.json'
    cfg, kill = limits.get('config'), limits.get('kill_switch')
    if not cfg or cfg['state'] == 'MISSING' or not kill or kill['state'] == 'MISSING':
        return missing(str(path), 'Brak potwierdzonego stanu bramki ryzyka')
    try:
        raw = read_json(path)
        paused = sorted(k for k, v in raw.get('sleeves', {}).items() if isinstance(v, dict) and v.get('paused') is True)
    except (OSError, ValueError, TypeError, AttributeError):
        return missing(str(path), 'Nie można odczytać pauz botów')
    v = cfg['value']
    caps = {k: int(s['max_positions']) for k, s in v['sleeves'].items()}
    summary = (('KILL SWITCH AKTYWNY' if kill['value'] else 'Kill switch: wyłączony') +
               f" · limit łącznie {v['max_total_tq_positions']} · wstrzymane: {', '.join(paused) or 'brak'}"
               ' · alarm koncentracji: brak lokalnego zapisu')
    return datum({'summary': summary, 'kill_switch': kill['value'], 'max_total': v['max_total_tq_positions'],
                  'caps': caps, 'paused': paused, 'concentration_alarm': None}, str(path),
                 _oldest([parse_time(cfg['as_of']), parse_time(kill['as_of'])]), config.freshness['config'],
                 uncertain=True, error='Alarm koncentracji Risk Managera nie ma lokalnego źródła')


def nova(config):
    best = None
    try:
        for folder in ORDER_BOTS:
            path = config.desktop / folder / 'signals.csv'
            try:
                data = rows(path)
            except OSError:
                continue
            for r in data:
                if r.get('action') in (None, '', 'NONE'):
                    continue
                t = parse_time(r['eval_time'])
                if best is None or t > best[0]:
                    best = (t, folder, r)
        if best is None:
            return missing('Pokój decyzyjny / bramka', 'Brak zapisanych decyzji bramki')
        t, folder, r = best
        summary = f"{folder}: {r.get('symbol')} {r.get('signal')} → {r.get('action')}"
        if r.get('action') != 'FILLED' and r.get('detail'):
            summary += f" ({r['detail'][:80]})"
        # Ostatnia decyzja jest zdarzeniem historycznym: wiek pokazuje, jak dawno była.
        return datum({'summary': summary, 'bot': folder, 'symbol': r.get('symbol'), 'action': r.get('action'), 'tf': r.get('tf')},
                     f'{folder} signals.csv', t, 86400)
    except (ValueError, KeyError, TypeError):
        return missing('Pokój decyzyjny / bramka', 'Brak poprawnego zapisu decyzji')


def collect(config, limits, arena_data):
    return {'ATLAS': atlas(arena_data), 'VEGA': vega(config),
            'ORION': missing('Pokój decyzyjny', 'Brak podłączonego źródła newsów'),
            'LUNA': missing('Pokój decyzyjny', 'Brak podłączonego źródła sentymentu'),
            'TITAN': titan(config, limits), 'NOVA': nova(config)}
