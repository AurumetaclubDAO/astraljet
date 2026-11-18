from ..models import datum, missing, parse_time
from .files import rows, number


def collect(config):
    path = config.desktop / 'TQ-Common' / 'funding_oi' / 'funding_oi_snapshots.csv'
    expected = [(source, symbol) for source in ('binance-usdm', 'bybit-linear') for symbol in ('BTCUSDT', 'ETHUSDT')]
    try:
        data = rows(path)
    except (OSError, ValueError):
        data = []
    result = []
    for source, symbol in expected:
        candidates = [r for r in data if r.get('source') == source and r.get('symbol') == symbol]
        ds = missing(str(path), 'Brak wiersza źródłowego')
        try:
            if candidates:
                row = max(candidates, key=lambda x: parse_time(x['collected_at_utc']))
                error = row.get('error') or None
                if error:
                    ds = missing(str(path), 'Najnowszy wiersz źródła zawiera błąd: ' + error)
                else:
                    value = {k: number(row[k]) for k in ('mark_price', 'funding_rate', 'open_interest_contracts', 'open_interest_usd')}
                    value['next_funding_utc'] = row.get('next_funding_utc')
                    source_stamp = row.get('source_time_utc')
                    stamp = min(parse_time(row['collected_at_utc']), parse_time(source_stamp)) if source_stamp else row['collected_at_utc']
                    ds = datum(value, str(path), stamp, config.freshness['funding'], uncertain=not source_stamp,
                               error=None if source_stamp else 'Brak czasu źródła')
        except (ValueError, KeyError, TypeError):
            ds = missing(str(path), 'Nieprawidłowy wiersz lub czas funding/OI')
        result.append(dict(source=source, symbol=symbol, data=ds))
    return result
