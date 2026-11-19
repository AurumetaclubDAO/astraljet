"""Uniwersum CFD na danych dziennych: historia, najmniejsza pozycja, koszt trzymania, spread, zmienność.

Czyta lokalne pliki (`research/daily-data/data/uniwersum/` i `symbols_all.json`) i nie łączy się z niczym.
Nie jest testem strategii i niczego nie wybiera: zbiera fakty potrzebne do spisania reguł serii 2.
Stawki swapu pochodzą z jednego odczytu i mogą się zmieniać.

    python research/daily-trend/scripts/uniwersum_dane.py --kapital 2500
    python research/daily-trend/scripts/uniwersum_dane.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uniwersum_cfd as uni  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE.parent / 'daily-data' / 'data' / 'uniwersum'
SYMBOLS = BASE.parent / 'daily-data' / 'data' / 'symbols_all.json'
OUT_DIR = BASE / 'reports'
SHORT_HISTORY = 500        # mniej świec dostaje uwagę „krótka historia"
ACCOUNT_CURRENCY = 'USD'
# Wersja kasowa i wersja oparta na futures tego samego rynku.
PAIRS = (('SP500.r', 'SP500ft.r'), ('UK100.r', 'UK100ft.r'), ('HK50.r', 'HK50ft.r'),
         ('Nikkei225', 'JPN225ft'), ('USOUSD', 'CL-OIL'), ('UKOUSD', 'UKOUSDft'))
# Różne symbole tego samego rynku liczą się w koszyku jako jeden rynek.
SAME_MARKET = {'S&P 500': ('SPY', 'SP500.r', 'SP500ft.r'), 'USA małe spółki': ('IWM', 'US2000.r'),
               'Japonia': ('EWJ', 'Nikkei225', 'JPN225ft'), 'Wielka Brytania': ('UK100.r', 'UK100ft.r'),
               'Hongkong': ('HK50.r', 'HK50ft.r'), 'Złoto': ('GLD', 'XAUUSD+'), 'Bitcoin': ('IBIT', 'BTCUSD'),
               'Ropa WTI': ('USO', 'USOUSD', 'CL-OIL'), 'Ropa Brent': ('BNO', 'UKOUSD', 'UKOUSDft')}
MARKET_OF = {symbol: market for market, symbols in SAME_MARKET.items() for symbol in symbols}
CLASS_OF = {name: group for group, names in uni.CANDIDATES.items() for name in names}
CLASS_OF.update({fut: CLASS_OF[cash] for cash, fut in PAIRS if cash in CLASS_OF})


def usd(value: float) -> str:
    return f'{value:,.0f}'.replace(',', ' ') + ' USD'


def load(folder: Path) -> dict:
    data = {}
    for meta_path in sorted(folder.glob('*_D1.meta.json')):
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        text = meta_path.with_name(meta_path.name.replace('.meta.json', '.csv')).read_text(encoding='utf-8')
        rows = list(csv.DictReader(text.splitlines()))
        if len(rows) < 2:
            continue
        data[meta['symbol']] = {'meta': meta, 'dates': [r['date'] for r in rows], 'close': [float(r['close']) for r in rows],
                                'spread': [float(r['spread']) for r in rows if r.get('spread') not in (None, '')]}
    return data


def min_lot_usd(meta: dict, close: float, fx: dict) -> float | None:
    """Wartość najmniejszej pozycji: lot × kontrakt × cena, przeliczona z waluty zysku na USD."""
    rate = fx.get(meta.get('currency_profit'))
    if not rate:
        return None
    return float(meta['volume_min']) * float(meta['trade_contract_size']) * close * float(rate)


def min_lot_usd_by_tick(meta: dict, close: float) -> float | None:
    """To samo z wyceny ticka podanej przez brokera w walucie rachunku. Służy tylko do kontroli."""
    size, value = float(meta.get('trade_tick_size') or 0), float(meta.get('trade_tick_value') or 0)
    return float(meta['volume_min']) * close / size * value if size > 0 and value > 0 else None


def holding_cost(meta: dict, close: float, fx: dict) -> tuple[float | None, float | None, str]:
    """Roczny koszt trzymania pozycji długiej i krótkiej jako ułamek jej wartości. Plus to koszt, minus to wpływ."""
    mode, long, short = meta.get('swap_mode'), meta.get('swap_long'), meta.get('swap_short')
    if not isinstance(mode, int) or not all(isinstance(v, (int, float)) for v in (long, short)) or close <= 0:
        return None, None, 'brak danych o swapie'
    size, point = float(meta.get('trade_contract_size') or 0), float(meta.get('point') or 0)
    if mode == 0:
        return 0.0, 0.0, 'bez swapu, koszt w cenie'
    if mode == 1 and point > 0:
        scale, note = point * 365 / close, 'swap w punktach'
    elif mode in (5, 6):
        scale, note = 0.01, 'procent rocznie'
    elif mode in (2, 3, 4) and size > 0:
        currency = {2: meta.get('currency_base'), 3: meta.get('currency_margin'), 4: ACCOUNT_CURRENCY}[mode]
        paid, profit = fx.get(currency), fx.get(meta.get('currency_profit'))
        if not paid or not profit:
            return None, None, f'brak kursu waluty {currency}'
        scale, note = float(paid) * 365 / (size * close * float(profit)), f'kwota w {currency} za lot dziennie'
    else:
        return None, None, f'nieobsługiwany tryb swapu {mode}'
    return -float(long) * scale, -float(short) * scale, note


def spread_rel(meta: dict, close: float, spreads: list[float]) -> float | None:
    """Większy z dwóch: spread z odczytu i mediana ze świec dziennych. Tak samo liczy silnik badań serii 1."""
    point = float(meta.get('point') or 0)
    points = [float(v) for v in (meta.get('spread_points'), meta.get('spread')) if isinstance(v, (int, float))]
    if spreads:
        points.append(statistics.median(spreads))
    return max(points) * point / close if point > 0 and points and close > 0 else None


def annual_vol(dates: list[str], closes: list[float], window: int = 252) -> float | None:
    start = max(1, len(closes) - window)
    returns = [closes[i] / closes[i - 1] - 1 for i in range(start, len(closes))]
    if len(returns) < 60:
        return None
    years = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[start - 1])).days / 365.25
    return statistics.pstdev(returns) * math.sqrt(len(returns) / years) if years > 0 else None


def largest_equal_basket(values: dict[str, float], capital: float) -> list[str]:
    """Najwięcej rynków, które przy równych wagach i ekspozycji 1 razy kapitał dostają choć najmniejszy lot."""
    order = sorted(values, key=values.__getitem__)
    best: list[str] = []
    for n in range(1, len(order) + 1):
        if values[order[n - 1]] <= capital / n:
            best = order[:n]
    return best


def roll_carry(cash: dict[str, float], fut: dict[str, float]) -> dict | None:
    """Ile wersja futures traci do kasowej między skokami rolowania. To koszt pozycji długiej ukryty w cenie.

    Baza to cena futures do ceny kasowej minus 1. W obrębie jednego kontraktu baza schodzi do zera,
    a przy rolowaniu skacze. Skok to dzienna zmiana bazy dużo większa od typowej.
    """
    days = sorted(set(cash) & set(fut))
    if len(days) < 250:
        return None
    basis = [fut[d] / cash[d] - 1 for d in days]
    steps = [basis[i] - basis[i - 1] for i in range(1, len(basis))]
    typical = statistics.median(steps)
    spread = statistics.median(abs(s - typical) for s in steps)
    limit = max(8 * spread, 0.001)
    jumps = [s for s in steps if abs(s - typical) > limit]
    years = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days / 365.25
    return {'days': len(days), 'from': days[0], 'to': days[-1], 'jumps': len(jumps),
            'jump_per_year': sum(jumps) / years, 'decay_per_year': -(sum(steps) - sum(jumps)) / years}


def cost_text(value: float | None, note: str) -> str:
    if value is None:
        return note
    if note.startswith('bez swapu'):
        return 'w cenie'
    return f'koszt {value:.1%}' if value > 0 else f'wpływ {-value:.1%}' if value < 0 else '0%'


def analyse(data: dict, fx: dict, capital: float) -> list[dict]:
    newest = max(d['dates'][-1] for d in data.values())
    rows = []
    for symbol, d in data.items():
        meta, close = d['meta'], d['close'][-1]
        value, by_tick = min_lot_usd(meta, close, fx), min_lot_usd_by_tick(meta, close)
        long, short, note = holding_cost(meta, close, fx)
        notes = []
        if meta.get('trade_mode') not in (None, 'FULL'):
            notes.append(f"tryb {meta['trade_mode']}")
        if len(d['close']) < SHORT_HISTORY:
            notes.append('krótka historia')
        gaps = [g for g in meta.get('gaps_over_5_days') or [] if g.get('after', '') >= '2018-01-01']
        if gaps:
            notes.append(f'{len(gaps)} luk ponad 5 dni od 2018')
        if value and by_tick and abs(value / by_tick - 1) > 0.03:
            notes.append(f'wycena z ticka daje {usd(by_tick)}')
        if (date.fromisoformat(newest) - date.fromisoformat(d['dates'][-1])).days > 7:
            notes.append(f"ostatnia świeca {d['dates'][-1]}")
        if long is None:
            notes.append(note)
        rows.append({'symbol': symbol, 'class': CLASS_OF.get(symbol, 'spoza listy'), 'market': MARKET_OF.get(symbol, symbol),
                     'first': d['dates'][0], 'last': d['dates'][-1], 'bars': len(d['close']), 'value': value,
                     'share': value / capital if value else None, 'long': long, 'short': short, 'swap_note': note,
                     'spread': spread_rel(meta, close, d['spread']), 'vol': annual_vol(d['dates'], d['close']),
                     'full': meta.get('trade_mode') in (None, 'FULL'), 'notes': notes})
    order = list(uni.CANDIDATES)
    return sorted(rows, key=lambda r: (order.index(r['class']) if r['class'] in order else len(order), r['market'], r['value'] or 0))


def report(rows: list[dict], data: dict, fx: dict, capital: float, source: str) -> list[str]:
    def pct(value, digits=1):
        return '—' if value is None else f'{value:.{digits}%}'

    lines = [f'# Uniwersum CFD na danych dziennych przy kapitale {usd(capital)}', '',
             f"Źródło: {source}, {len(rows)} symboli, ostatnia świeca {max(r['last'] for r in rows)}.",
             'To nie jest test strategii ani zalecenie, czym handlować. Stawki swapu pochodzą z jednego odczytu.',
             'Koszt trzymania to roczny ułamek wartości pozycji; „wpływ" oznacza, że broker dopisuje pieniądze.',
             'Spread to większy z dwóch: z odczytu i mediana ze świec dziennych, w procentach ceny. Zmienność liczona z ostatnich 252 świec.', '',
             '## Symbole', '',
             '| Klasa | Rynek | Symbol | Historia od | Świece | Najmniejsza pozycja | Długa rocznie | Krótka rocznie | Spread | Zmienność roczna | Uwagi |',
             '|---|---|---|---|---:|---|---|---|---:|---:|---|']
    for r in rows:
        worth = f"{usd(r['value'])} ({r['share']:.1%} kapitału)" if r['value'] else 'brak kursu waluty'
        lines.append(f"| {r['class']} | {r['market']} | `{r['symbol']}` | {r['first']} | {r['bars']} | {worth} | "
                     f"{cost_text(r['long'], r['swap_note'])} | {cost_text(r['short'], r['swap_note'])} | {pct(r['spread'], 3)} | "
                     f"{pct(r['vol'], 0)} | {'; '.join(r['notes'])} |")
    usable = [r for r in rows if r['value'] and r['full'] and r['bars'] >= SHORT_HISTORY]
    cheapest: dict[str, dict] = {}
    for r in usable:
        if r['market'] not in cheapest or r['value'] < cheapest[r['market']]['value']:
            cheapest[r['market']] = r
    basket = largest_equal_basket({m: r['value'] for m, r in cheapest.items()}, capital)
    lines += ['', '## Największy równy koszyk bez dźwigni', '',
              f'Liczę tylko symbole z pełnym trybem handlu i co najmniej {SHORT_HISTORY} świecami. Z kilku symboli tego samego rynku '
              'biorę ten o najmniejszej pozycji. Równe wagi są tu miarą wykonalności, nie propozycją strategii.', '']
    if basket:
        classes = sorted({cheapest[m]['class'] for m in basket})
        lines += [f'**Rynków w koszyku: {len(basket)}** z {len(cheapest)}. Każdy ma wtedy {usd(capital / len(basket))} '
                  f"({1 / len(basket):.1%} kapitału) i dostaje choć najmniejszy lot. Klasy: {', '.join(classes)}.", '',
                  '| Rynek | Symbol | Najmniejsza pozycja | Klasa |', '|---|---|---|---|']
        lines += [f"| {m} | `{cheapest[m]['symbol']}` | {usd(cheapest[m]['value'])} | {cheapest[m]['class']} |" for m in basket]
        left = [m for m in sorted(cheapest, key=lambda m: cheapest[m]['value']) if m not in basket]
        if left:
            lines += ['', 'Poza koszykiem, bo najmniejsza pozycja jest za duża: '
                      + ', '.join(f"{m} ({usd(cheapest[m]['value'])})" for m in left) + '.']
    else:
        lines.append('Żaden rynek nie mieści się w kapitale.')
    lines += ['', '## Kontrakty oparte na futures a wersja kasowa', '',
              'Baza to cena wersji futures do ceny kasowej minus 1. Między skokami rolowania baza schodzi do zera i tyle wersja',
              'futures traci do kasowej. Zakładam, że skok ceny przy rolowaniu broker wyrównuje na rachunku; to trzeba potwierdzić',
              'w specyfikacji brokera. Wersja kasowa ma osobno swap, a dywidend tu nie liczę.', '',
              '| Rynek | Kasowy | Futures | Wspólne dni | Wykryte skoki | Spadek bazy rocznie (koszt długiej w cenie) | Swap długiej kasowej rocznie |',
              '|---|---|---|---:|---:|---:|---|']
    by_symbol = {r['symbol']: r for r in rows}
    measured = 0
    for cash, fut in PAIRS:
        if cash not in data or fut not in data:
            continue
        result = roll_carry(dict(zip(data[cash]['dates'], data[cash]['close'])), dict(zip(data[fut]['dates'], data[fut]['close'])))
        if result is None:
            continue
        measured += 1
        lines.append(f"| {MARKET_OF.get(cash, cash)} | `{cash}` | `{fut}` | {result['days']} | {result['jumps']} | "
                     f"{result['decay_per_year']:.1%} | {cost_text(by_symbol[cash]['long'], by_symbol[cash]['swap_note'])} |")
    if not measured:
        lines.append('| — | — | — | — | — | brak par z danymi | — |')
    wanted = [n for names in uni.CANDIDATES.values() for n in names] + [fut for _, fut in PAIRS]
    missing = [n for n in wanted if n not in data]
    lines += ['', '## Czego brakuje', '',
              ('- Brak danych dla: ' + ', '.join(f'`{n}`' for n in missing) + '.') if missing else '- Dane są dla wszystkich kandydatów.',
              '- Prowizja od CFD na akcje i ETF-y: nie ma jej w danych terminala, trzeba ją wziąć ze specyfikacji brokera.',
              '- Kontrakty na obligacje nie mają wersji kasowej, więc ich kosztu rolowania nie da się zmierzyć tą metodą.']
    return lines


def selftest() -> int:
    fx = {'USD': 1.0, 'EUR': 1.1, 'JPY': 0.00625, 'HKD': 0.1275}
    index = {'swap_mode': 2, 'swap_long': -1.6217, 'swap_short': 0.3178, 'trade_contract_size': 1.0, 'point': 0.01,
             'currency_base': 'USD', 'currency_margin': 'USD', 'currency_profit': 'USD', 'volume_min': 0.1,
             'trade_tick_size': 0.01, 'trade_tick_value': 0.01}
    long, short, _ = holding_cost(index, 7215.0, fx)
    assert abs(long - 0.08204) < 1e-4 and abs(short + 0.01608) < 1e-4, (long, short)
    assert abs(min_lot_usd(index, 7215.0, fx) - 721.5) < 1e-9 and abs(min_lot_usd_by_tick(index, 7215.0) - 721.5) < 1e-6
    etf = {**index, 'swap_mode': 5, 'swap_long': -6.0, 'swap_short': 2.0, 'volume_min': 1.0}
    assert holding_cost(etf, 650.0, fx)[:2] == (0.06, -0.02)
    gold = {**index, 'swap_mode': 1, 'swap_long': -69.21, 'swap_short': 30.92, 'trade_contract_size': 100.0}
    long, short, _ = holding_cost(gold, 3674.5, fx)
    assert abs(long - 0.06875) < 1e-4 and short < 0, (long, short)
    hk = {**index, 'swap_long': -3.7983, 'swap_short': 0.4587, 'currency_base': 'HKD', 'currency_profit': 'HKD'}
    assert abs(holding_cost(hk, 26000.0, fx)[0] - 3.7983 * 365 / 26000) < 1e-9          # kurs HKD się skraca
    assert abs(min_lot_usd(hk, 26000.0, fx) - 0.1 * 26000 * 0.1275) < 1e-9
    assert holding_cost({**index, 'swap_mode': 0}, 100.0, fx) == (0.0, 0.0, 'bez swapu, koszt w cenie')
    assert holding_cost({**hk, 'currency_base': 'XXX'}, 100.0, fx)[0] is None
    assert holding_cost({**index, 'swap_mode': 7}, 100.0, fx)[0] is None
    jpy = {**index, 'trade_contract_size': 100000.0, 'volume_min': 0.01, 'currency_profit': 'JPY'}
    assert abs(min_lot_usd(jpy, 160.0, fx) - 1000.0) < 1e-9
    assert largest_equal_basket({'a': 20, 'b': 100, 'c': 240, 'd': 700, 'e': 2800}, 2500) == ['a', 'b', 'c']
    assert largest_equal_basket({'a': 3000}, 2500) == []
    assert cost_text(0.06, 'x') == 'koszt 6.0%' and cost_text(-0.02, 'x') == 'wpływ 2.0%' and cost_text(0.0, 'bez swapu, koszt w cenie') == 'w cenie'
    rng = random.Random(7)
    day, price, cash, fut = date(2022, 1, 3), 100.0, {}, {}
    for i in range(783):                                    # trzy lata dni roboczych, rolowanie co 63 świece
        while day.weekday() > 4:
            day += timedelta(days=1)
        price *= 1 + rng.gauss(0, 0.01)
        cash[day.isoformat()] = price
        fut[day.isoformat()] = price * (1 + 0.04 * (63 - i % 63) / 261 + rng.gauss(0, 0.0001))
        day += timedelta(days=1)
    result = roll_carry(cash, fut)
    assert result['jumps'] == 12 and abs(result['decay_per_year'] - 0.04) < 0.004, result
    assert roll_carry({'2026-01-01': 1.0}, {'2026-01-01': 1.0}) is None
    assert annual_vol(['2026-01-01'] * 10, [1.0] * 10) is None
    print('SELFTEST OK')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Uniwersum CFD na danych dziennych przy danym kapitale.')
    parser.add_argument('--kapital', type=float, default=2500.0)
    parser.add_argument('--dane', type=Path, default=DATA_DIR, help='Katalog z plikami <SYMBOL>_D1.csv i .meta.json.')
    parser.add_argument('--raport', type=Path, default=None, help='Plik raportu; domyślnie reports/UNIWERSUM_DANE_<kapitał>.md.')
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    data = load(args.dane) if args.dane.is_dir() else {}
    if not data or not SYMBOLS.exists():
        print(f'BRAK DANYCH: nie ma plików D1 w {args.dane} albo pliku {SYMBOLS.name}.')
        return 2
    fx = json.loads(SYMBOLS.read_text(encoding='utf-8'))['fx_to_usd']
    lines = report(analyse(data, fx, args.kapital), data, fx, args.kapital, f'pliki D1 z `{args.dane.name}/`')
    target = args.raport or OUT_DIR / f'UNIWERSUM_DANE_{args.kapital:.0f}.md'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
