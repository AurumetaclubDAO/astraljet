import asyncio
import time
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from .config import BOTS
from .models import datum, missing, utcnow, age_tree
from .security import redact
from .collectors import mt5, risk, arena, funding, schedule, alpaca, council
from .collectors.files import signal, runner_state, log_errors


def derived(value, sources, label, unit=None, uncertain=False):
    if any(s['state'] == 'MISSING' for s in sources):
        return missing(label, 'Brak pełnych danych do obliczenia')
    stamp = min(s['as_of'] for s in sources if s['as_of'])
    return datum(value, label, stamp, min(s['ttl_s'] for s in sources), unit=unit,
                 uncertain=uncertain or any(s['state'] != 'CONFIRMED' for s in sources),
                 error='Wynik informacyjny; niepełna atrybucja lub dane niepotwierdzone' if uncertain else None)


def compose(config, market, limits, schedules, arena_data, funding_data, runners):
    now = utcnow()
    account, positions, history = (market[k] for k in ('account', 'positions', 'history'))
    pos = positions['value'] or []
    hist = history['value'] or {}
    deals = hist.get('deals', [])
    midnight = now.astimezone(ZoneInfo('Europe/Warsaw')).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    today = [d for d in deals if d['time'] >= midnight]
    currency = (account['value'] or {}).get('currency')
    realized = derived(sum(d['amount'] for d in today), [history], 'MT5 / zrealizowany wynik dziś', currency)
    floating = derived(sum(p['profit'] + p['swap'] for p in pos), [positions], 'MT5 / wynik otwartych pozycji', currency)
    combined = derived((realized['value'] or 0) + (floating['value'] or 0), [realized, floating], 'Wynik dziś + bieżący floating', currency)
    bots = []
    risk_value = limits['config']['value'] or {}
    incomplete = any(d['bot'] == 'other' for d in today)
    for bot_id, name, folder, task, magics in BOTS:
        own = [p for p in pos if p['bot'] == bot_id]
        bot_realized = sum(d['amount'] for d in today if d['bot'] == bot_id)
        bot_floating = sum(p['profit'] + p['swap'] for p in own)
        pnl = derived(bot_realized + bot_floating, [positions, history], 'MT5 / magic → ' + name, currency, uncertain=incomplete)
        sleeve = risk_value.get('sleeves', {}).get(bot_id)
        budget = datum(sleeve, 'TQ-Common / sleeve ' + name, limits['config']['as_of'], limits['config']['ttl_s'],
                       uncertain=limits['config']['state'] != 'CONFIRMED') if sleeve else missing('TQ-Common', 'Brak sleeve')
        usage = missing('Wyliczenie informacyjne', 'Wymagane kompletne dane i waluta USD')
        if sleeve and currency == 'USD' and pnl['state'] != 'MISSING':
            usage = derived(max(0, -pnl['value']) / (sleeve['sleeve_usd'] * sleeve['daily_loss_pct'] / 100) * 100,
                            [pnl, budget], 'Wykorzystanie dziennego limitu straty', '%')
        bots.append(dict(id=bot_id, name=name, magics=list(magics), pnl=pnl, budget=budget, loss_usage=usage,
                         positions=derived(len(own), [positions], 'MT5 / liczba pozycji'),
                         schedule=schedules.get(task, missing('Harmonogram', 'Brak przypisanego zadania wykonawczego')),
                         **runners[bot_id]))
    daily = {}
    for d in sorted(deals, key=lambda x: (x['time'], x['ticket'])):
        day = datetime.fromtimestamp(d['time'], ZoneInfo('Europe/Warsaw')).date().isoformat()
        daily[day] = daily.get(day, 0) + d['amount']
    total, points = 0, []
    for day, amount in sorted(daily.items()):
        total += amount
        points.append({'date': day, 'value': round(total, 2)})
    curve = derived(points, [history], 'MT5 / skumulowany zrealizowany wynik w oknie historii', currency)
    exposure = derived([{'bot': b['name'], 'positions': sum(p['bot'] == b['id'] for p in pos)} for b in bots] +
                       [{'bot': 'Inne/ręczne', 'positions': sum(p['bot'] == 'other' for p in pos)}], [positions], 'MT5 / rozkład liczby pozycji')
    return dict(snapshot_id=str(uuid4()), generated_at=now.isoformat(), refresh_seconds=config.refresh_seconds,
                account=account, terminal=market['terminal'], positions=positions, realized_today=realized,
                floating=floating, pnl_today=combined, bots=bots, risk=limits, arena=arena_data, funding=funding_data,
                schedule=schedules, alpaca=alpaca.collect(), curve=curve, exposure=exposure,
                historical_equity=market.get('historical_equity') or missing('MT5', 'Brak odczytu historii equity'),
                agents=_agents(config, limits, arena_data))


def _agents(config, limits, arena_data):
    try:
        cards = council.collect(config, limits, arena_data)
    except Exception:
        cards = {}
    return [dict(name=n, data=cards.get(n) or missing('Pokój decyzyjny', 'Błąd odczytu źródła')) for n in ('ATLAS', 'VEGA', 'ORION', 'LUNA', 'TITAN', 'NOVA')]


def runner_data(config):
    result = {}
    for bot_id, _, folder, _, _ in BOTS:
        base = config.desktop / folder
        result[bot_id] = dict(signal=signal(base, config.freshness['runner']), runner_state=runner_state(base, config.freshness['runner']),
                              errors=log_errors(base / 'runner.log'))
    result['tq-vb']['shadow'] = signal(config.desktop / 'SHADOW-VB', config.freshness['shadow'], shadow=True)
    return result


class DashboardService:
    def __init__(self, config):
        self.config = config
        self.snapshot = compose(config, mt5.failure('Oczekiwanie na pierwszy odczyt'),
                                {'config': missing('Risk'), 'kill_switch': missing('KILL_SWITCH')}, {}, missing('Arena'), [],
                                {b[0]: dict(signal=missing('Sygnały'), runner_state=missing('Stan'), errors=missing('Log')) for b in BOTS})
        self.task = None
        self.error = False

    async def refresh(self):
        results = await asyncio.gather(*(asyncio.to_thread(fn, self.config) for fn in
                                         (mt5.collect, risk.collect, schedule.collect, arena.collect, funding.collect, runner_data)))
        self.snapshot = compose(self.config, *results)
        self.error = False

    async def loop(self):
        while True:
            started = time.monotonic()
            try:
                await self.refresh()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.error = True
                # Nie zachowuj starego konta po nieznanym wyniku nowego odczytu.
                self.snapshot = compose(self.config, mt5.failure('Błąd rundy odczytu'),
                                        {'config': missing('Risk'), 'kill_switch': missing('KILL_SWITCH')}, {}, missing('Arena'), [],
                                        {b[0]: dict(signal=missing('Sygnały'), runner_state=missing('Stan'), errors=missing('Log')) for b in BOTS})
            await asyncio.sleep(max(1, self.config.refresh_seconds - (time.monotonic() - started)))

    def view(self):
        return redact(age_tree(self.snapshot))
