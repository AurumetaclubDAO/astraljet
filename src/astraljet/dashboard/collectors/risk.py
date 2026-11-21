from ..models import datum, missing, utcnow
from .files import read_json, number


def collect(config):
    folder = config.desktop / 'TQ-Common'
    path = folder / 'risk_config.json'
    try:
        raw = read_json(path)
        sleeves = {}
        for name, entry in raw['sleeves'].items():
            sleeves[name] = {k: number(entry[k]) for k in ('sleeve_usd', 'max_risk_pct_per_trade', 'daily_loss_pct', 'max_positions')}
            if any(v <= 0 for v in sleeves[name].values()):
                raise ValueError('Niepoprawny limit')
        value = dict(allowed_login=int(raw['allowed_login']), forbidden_logins=[int(x) for x in raw['forbidden_logins']],
                     max_total_tq_positions=int(raw['max_total_tq_positions']), sleeves=sleeves)
        settings = datum(value, str(path), utcnow(), config.freshness['config'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        settings = missing(str(path), 'Brak poprawnej konfiguracji ryzyka')
    switch = folder / 'KILL_SWITCH'
    try:
        # Iteracja po rodzicu rozróżnia brak pliku i odmowę/brak katalogu.
        exists = any(p.name == 'KILL_SWITCH' for p in folder.iterdir())
        kill = datum(exists, str(switch), utcnow(), config.freshness['config'])
    except OSError:
        kill = missing(str(switch), 'Nie można potwierdzić obecności blokady')
    return {'config': settings, 'kill_switch': kill}
