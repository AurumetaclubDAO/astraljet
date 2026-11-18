from ..models import datum, missing, parse_time
from .files import read_json


def collect(config):
    path = config.desktop / 'TQ-Arena' / 'status.json'
    try:
        raw = read_json(path)
        stamp = raw.get('refreshed_at')
        read = raw.get('freshMt5Read')
        source_ok = (isinstance(read, dict) and config.demo_login is not None
                     and str(read.get('login')) == str(config.demo_login) and read.get('server') == config.server)
        if source_ok:
            stamp = min(parse_time(stamp), parse_time(read.get('readAt')))
        bots = []
        for bot in raw.get('bots', []):
            if not isinstance(bot, dict):
                continue
            bots.append({k: bot.get(k) for k in ('id', 'name', 'status', 'lastRefresh') } | {
                'allocation': bot.get('equity'),
                'metrics': datum({k: bot.get('metrics', {}).get(k) for k in ('ret', 'maxDd', 'trades', 'winRate')},
                                 str(path), bot.get('lastRefresh'), config.freshness['arena'], uncertain=True,
                                 error='Metryki producenta bez pełnego potwierdzenia pochodzenia')})
        return datum({'bots': bots, 'source_validated': source_ok}, str(path), stamp, config.freshness['arena'],
                     uncertain=True, error='Snapshot Areny; brak trade_mode, metryki i statusy wymagają weryfikacji')
    except (OSError, ValueError, TypeError, AttributeError):
        return missing(str(path), 'Brak poprawnego snapshotu Areny')
