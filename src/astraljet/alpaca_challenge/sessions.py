from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from .models import now

NY = ZoneInfo('America/New_York')


async def session(broker, kind, settings):
    if kind == 'crypto':
        return 'crypto'
    clock = await broker.clock()
    timestamp = datetime.fromisoformat(clock['timestamp'].replace('Z','+00:00'))
    if abs((now()-timestamp).total_seconds()) > 60:
        raise ValueError('Nieaktualny zegar brokera')
    local = timestamp.astimezone(NY)
    if clock.get('is_open') is True:
        return 'regular'
    if kind == 'option' or not settings.allow_extended_hours:
        raise ValueError('Rynek zamknięty')
    trade_date = local.date() + timedelta(days=1) if local.time() >= time(20) else local.date()
    days = await broker.calendar(trade_date,trade_date)
    if not days or days[0]['date'] != trade_date.isoformat():
        raise ValueError('Brak potwierdzonej sesji')
    close_time = time.fromisoformat(days[0]['close'])
    if local.time() >= time(20) or local.time() < time(4):
        return 'overnight'
    if close_time < time(16) and local.time() >= close_time:
        raise ValueError('Skrócona sesja: extended zablokowane')
    if time(4) <= local.time() < time(20):
        return 'extended'
    raise ValueError('Niepotwierdzona sesja')
