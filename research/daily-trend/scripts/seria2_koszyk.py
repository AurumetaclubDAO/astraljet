"""Koszyk serii 2: dopuszczenie symboli i wybór rynków według `SPEC_SERIA2.md`, punkty 2 i 3.

Czyta lokalne pliki (`research/daily-data/data/uniwersum/` i `symbols_all.json`) i nie łączy się z niczym.
Nie jest testem strategii. Progi i kolejność rynków są przepisane ze specyfikacji i nie wolno ich tu zmieniać.

    python research/daily-trend/scripts/seria2_koszyk.py --kapital 2500
    python research/daily-trend/scripts/seria2_koszyk.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uniwersum_cfd as uni  # noqa: E402
import uniwersum_dane as ud  # noqa: E402

CUTOFF = '2025-01-01'       # początek próby poza strojeniem
MIN_BARS = 500              # świec ciągłej historii przed CUTOFF
MAX_GAP_DAYS = 10           # dłuższa przerwa zrywa ciągłość historii
LOT_DIVISOR = 8             # najmniejsza pozycja <= kapitał * G / 8
MAX_SPREAD = 0.005          # 0,50% ceny
MAX_HOLD = 0.10             # przynajmniej jedna strona z kosztem trzymania <= 10% rocznie
PER_CLASS = 3
MIN_MARKETS, MIN_CLASSES = 6, 4
# Bez swapu, koszt w cenie i rolowaniu. Poza koszykiem do potwierdzenia rozliczenia rolowania.
FUTURES_BASED = frozenset({'SP500ft.r', 'UK100ft.r', 'HK50ft.r', 'JPN225ft', 'CL-OIL', 'UKOUSDft',
                           'USNote10Y', 'EUB10Y', 'EUB5Y', 'EUB2Y', 'EUB30Y', 'LongGilt'})
# Klasa -> rynki w kolejności ze specyfikacji; każdy rynek ma swoje symbole.
PRIORITY = {
    'Akcje USA': [('S&P 500', ('SPY', 'SP500.r', 'SP500ft.r')), ('USA małe spółki', ('IWM', 'US2000.r')),
                  ('Nasdaq 100', ('QQQ',)), ('USA finanse', ('XLF',)), ('USA technologia', ('XLK',)),
                  ('USA półprzewodniki', ('SMH',))],
    'Akcje poza USA': [('Rynki rozwinięte', ('EFA',)), ('Rynki wschodzące', ('EEM',)),
                       ('Japonia', ('EWJ', 'Nikkei225', 'JPN225ft')), ('Strefa euro', ('EU50.r',)),
                       ('Wielka Brytania', ('UK100.r', 'UK100ft.r')), ('Chiny', ('FXI', 'MCHI', 'CHINAH.r')),
                       ('Indie', ('INDA',)), ('Brazylia', ('EWZ',)), ('Korea', ('EWY',)), ('Tajwan', ('EWT',)),
                       ('Hongkong', ('HK50.r', 'HK50ft.r')), ('Australia', ('SPI200.r',))],
    'Obligacje': [('USA długie', ('TLT',)), ('USA 10 lat', ('USNote10Y',)), ('Niemcy 10 lat', ('EUB10Y',)),
                  ('Wielka Brytania, obligacje', ('LongGilt',)), ('Niemcy 5 lat', ('EUB5Y',)),
                  ('Niemcy 30 lat', ('EUB30Y',)), ('Niemcy 2 lata', ('EUB2Y',))],
    'Złoto i metale': [('Złoto', ('GLD', 'XAUUSD+')), ('Srebro', ('XAGUSD',)), ('Platyna', ('XPTUSD.r',)),
                       ('Spółki złota', ('GDX',))],
    'Energia i surowce': [('Ropa WTI', ('USO', 'USOUSD', 'CL-OIL')), ('Koszyk surowców', ('DBC',)),
                          ('Gaz ziemny', ('UNG',)), ('Ropa Brent', ('BNO', 'UKOUSD', 'UKOUSDft')),
                          ('Pszenica', ('Wheat-Cr',)), ('Soja', ('Soybean-Cr',)), ('Spółki naftowe', ('XOP',))],
    'Krypto': [('Bitcoin', ('IBIT', 'BTCUSD')), ('Ethereum', ('ETHUSD',)), ('Solana', ('SOLUSD',)),
               ('Litecoin', ('LTCUSD',)), ('XRP', ('XRPUSD',)), ('Bitcoin Cash', ('BCHUSD',))],
    'Waluty': [('EURUSD', ('EURUSD+',)), ('USDJPY', ('USDJPY+',)), ('GBPUSD', ('GBPUSD+',)), ('AUDUSD', ('AUDUSD+',))],
}
ALL_SYMBOLS = [symbol for markets in PRIORITY.values() for _, symbols in markets for symbol in symbols]


def continuous_start(dates: list[str], max_gap: int = MAX_GAP_DAYS) -> int:
    """Indeks pierwszej świecy po ostatniej przerwie dłuższej niż `max_gap` dni kalendarzowych."""
    start = 0
    for i in range(1, len(dates)):
        if (date.fromisoformat(dates[i]) - date.fromisoformat(dates[i - 1])).days > max_gap:
            start = i
    return start


def facts(symbol: str, d: dict, fx: dict) -> dict:
    meta, close = d['meta'], d['close'][-1]
    start = continuous_start(d['dates'])
    long, short, note = ud.holding_cost(meta, close, fx)
    return {'symbol': symbol, 'mode': meta.get('trade_mode'), 'from': d['dates'][start], 'last': d['dates'][-1],
            'bars_before': sum(1 for day in d['dates'][start:] if day < CUTOFF),
            'value': ud.min_lot_usd(meta, close, fx), 'spread': ud.spread_rel(meta, close, d['spread']),
            'long': long, 'short': short, 'swap_note': note, 'vol': ud.annual_vol(d['dates'], d['close']),
            'futures': symbol in FUTURES_BASED or meta.get('swap_mode') == 0}


def hold_sum(f: dict) -> float:
    """Suma kosztu trzymania obu stron; wpływ na rachunek liczy się jako zero."""
    return max(f['long'], 0.0) + max(f['short'], 0.0)


def refusals(f: dict, capital: float, gross: float) -> list[str]:
    """Powody odrzucenia według punktu 2 specyfikacji. Pusta lista oznacza dopuszczenie."""
    out = []
    if f['mode'] != 'FULL':
        out.append(f"tryb handlu {f['mode']}")
    if f['bars_before'] < MIN_BARS:
        out.append(f"{f['bars_before']} świec ciągłej historii przed {CUTOFF}, wymagane {MIN_BARS}")
    limit = capital * gross / LOT_DIVISOR
    if f['value'] is None:
        out.append('brak kursu waluty do wyceny najmniejszej pozycji')
    elif f['value'] > limit:
        out.append(f"najmniejsza pozycja {ud.usd(f['value'])}, limit {ud.usd(limit)}")
    if f['spread'] is None:
        out.append('brak danych o spreadzie')
    elif f['spread'] > MAX_SPREAD:
        out.append(f"spread {f['spread']:.2%} ceny, limit {MAX_SPREAD:.2%}")
    if f['long'] is None or f['short'] is None:
        out.append(f"koszt trzymania nieznany ({f['swap_note']})")
    elif min(max(f['long'], 0.0), max(f['short'], 0.0)) > MAX_HOLD:
        out.append(f"obie strony kosztują ponad {MAX_HOLD:.0%} rocznie")
    if f['futures']:
        out.append('oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie')
    return out


def select_basket(admitted: dict[str, dict]) -> list[dict]:
    """Punkt 3: jeden symbol na rynek, najwyżej trzy rynki z klasy, w kolejności ze specyfikacji."""
    basket = []
    for group, markets in PRIORITY.items():
        taken = 0
        for market, symbols in markets:
            options = [admitted[s] for s in symbols if s in admitted]
            if not options or taken == PER_CLASS:
                continue
            best = min(options, key=lambda f: (hold_sum(f), f['value']))
            basket.append({**best, 'class': group, 'market': market})
            taken += 1
    return basket


def basket_valid(basket: list[dict]) -> bool:
    return len(basket) >= MIN_MARKETS and len({b['class'] for b in basket}) >= MIN_CLASSES


def report(data: dict, fx: dict, capital: float, gross: float, source: str) -> list[str]:
    def pct(value, digits=1):
        return '—' if value is None else f'{value:.{digits}%}'

    known = {s: facts(s, data[s], fx) for s in ALL_SYMBOLS if s in data}
    why = {s: refusals(f, capital, gross) for s, f in known.items()}
    admitted = {s: f for s, f in known.items() if not why[s]}
    basket = select_basket(admitted)
    chosen = {b['symbol'] for b in basket}
    missing = [s for s in ALL_SYMBOLS if s not in data]
    lines = [f'# Seria 2: koszyk według reguł z `SPEC_SERIA2.md` przy kapitale {ud.usd(capital)}', '',
             f"Źródło: {source}. Symboli z danymi: {len(known)} z {len(ALL_SYMBOLS)}. Największa łączna ekspozycja G = {gross:g}.",
             'To zastosowanie zapisanych wcześniej reguł doboru, nie test strategii ani zalecenie, czym handlować.',
             'Stawki swapu pochodzą z jednego odczytu. Koszt trzymania to roczny ułamek wartości pozycji.', '',
             '## Koszyk', '']
    if basket_valid(basket):
        lines.append(f"**Koszyk ważny: {len(basket)} rynków z {len({b['class'] for b in basket})} klas.**")
    else:
        lines.append(f"**BRAK DANYCH: koszyk ma {len(basket)} rynków z {len({b['class'] for b in basket})} klas, "
                     f"wymagane co najmniej {MIN_MARKETS} rynków z {MIN_CLASSES} klas.**")
    if missing:
        lines.append(f'Uwaga: brakuje danych dla {len(missing)} symboli, więc skład nie jest ostateczny.')
    if basket:
        lines += ['', '| Klasa | Rynek | Symbol | Ciągła historia od | Najmniejsza pozycja | Długa rocznie | Krótka rocznie | Spread | Zmienność roczna |',
                  '|---|---|---|---|---|---|---|---:|---:|']
        lines += [f"| {b['class']} | {b['market']} | `{b['symbol']}` | {b['from']} | {ud.usd(b['value'])} ({b['value'] / capital:.1%}) | "
                  f"{ud.cost_text(b['long'], b['swap_note'])} | {ud.cost_text(b['short'], b['swap_note'])} | {pct(b['spread'], 3)} | "
                  f"{pct(b['vol'], 0)} |" for b in basket]
        total = sum(b['value'] for b in basket)
        lines += ['', f'Po jednym najmniejszym locie na każdym rynku: {ud.usd(total)}, czyli {total / capital:.0%} kapitału.']
    lines += ['', '## Wszystkie symbole z danymi', '',
              '| Klasa | Rynek | Symbol | Wynik | Powód |', '|---|---|---|---|---|']
    for group, markets in PRIORITY.items():
        for market, symbols in markets:
            for s in symbols:
                if s not in known:
                    continue
                if s in chosen:
                    verdict, reason = 'w koszyku', ''
                elif not why[s]:
                    same = next((b for b in basket if b['market'] == market), None)
                    verdict = 'dopuszczony, poza koszykiem'
                    reason = f"na tym rynku wygrał `{same['symbol']}`" if same else f'klasa ma już {PER_CLASS} rynki'
                else:
                    verdict, reason = 'odrzucony', '; '.join(why[s])
                lines.append(f'| {group} | {market} | `{s}` | {verdict} | {reason} |')
    lines += ['', '## Czego brakuje', '',
              ('- Brak danych dla: ' + ', '.join(f'`{s}`' for s in missing) + '.') if missing else '- Dane są dla wszystkich 61 symboli.',
              '- Prowizja od CFD na akcje i ETF-y: bez niej test serii 2 nie rusza dla koszyka z ETF-ami.',
              '- Rozliczenie rolowania kontraktów opartych na futures: do potwierdzenia te symbole są poza koszykiem.',
              '- Wypłaty na CFD (dywidendy, odsetki): do potwierdzenia zostaje szacunek ze specyfikacji.']
    return lines


def selftest() -> int:
    wanted = [n for names in uni.CANDIDATES.values() for n in names] + [fut for _, fut in ud.PAIRS]
    assert len(ALL_SYMBOLS) == len(set(ALL_SYMBOLS)) == 61 and set(ALL_SYMBOLS) == set(wanted)
    assert list(PRIORITY) == list(uni.CANDIDATES)
    assert continuous_start(['2020-01-01', '2020-01-02', '2020-01-20', '2020-01-21', '2020-01-31']) == 2
    assert continuous_start(['2020-01-01', '2020-01-11']) == 0 and continuous_start(['2020-01-01']) == 0

    def fact(symbol, **changes):
        base = {'symbol': symbol, 'mode': 'FULL', 'from': '2020-01-01', 'last': '2026-11-19', 'bars_before': 900,
                'value': 100.0, 'spread': 0.001, 'long': 0.06, 'short': -0.02, 'swap_note': 'procent rocznie',
                'vol': 0.2, 'futures': False}
        return {**base, **changes}

    assert refusals(fact('SPY'), 2500, 1.0) == []
    assert refusals(fact('SPY', value=312.5), 2500, 1.0) == [] and len(refusals(fact('SPY', value=312.6), 2500, 1.0)) == 1
    assert refusals(fact('SPY', value=600.0), 2500, 2.0) == []                      # limit rośnie z G
    assert refusals(fact('SPY', bars_before=499), 2500, 1.0)[0].startswith('499 świec')
    assert 'tryb handlu CLOSEONLY' in refusals(fact('SPY', mode='CLOSEONLY'), 2500, 1.0)
    assert len(refusals(fact('SPY', spread=0.005), 2500, 1.0)) == 0 and len(refusals(fact('SPY', spread=0.0051), 2500, 1.0)) == 1
    assert refusals(fact('BTCUSD', long=0.25, short=0.0), 2500, 1.0) == []          # krótka strona tania
    assert len(refusals(fact('X', long=0.22, short=0.22), 2500, 1.0)) == 1
    assert len(refusals(fact('X', long=None, short=None), 2500, 1.0)) == 1
    assert len(refusals(fact('X', value=None, spread=None), 2500, 1.0)) == 2
    assert refusals(fact('CL-OIL', futures=True), 2500, 1.0)[0].startswith('oparty na futures')
    assert len(refusals(fact('X', mode='LONGONLY', bars_before=0, value=9e9, spread=1.0, long=1.0, short=1.0, futures=True), 2500, 1.0)) == 6

    admitted = {s: fact(s) for s in ('SPY', 'IWM', 'QQQ', 'XLF', 'EFA', 'TLT', 'GLD', 'XAUUSD+', 'IBIT', 'BTCUSD', 'ETHUSD')}
    admitted['XAUUSD+'] = fact('XAUUSD+', long=0.07, short=0.0, value=50.0)        # droższy w trzymaniu niż GLD (0,06)
    admitted['BTCUSD'] = fact('BTCUSD', long=0.06, short=0.0, value=40.0)          # remis kosztu z IBIT, mniejsza pozycja
    basket = select_basket(admitted)
    assert [b['symbol'] for b in basket] == ['SPY', 'IWM', 'QQQ', 'EFA', 'TLT', 'GLD', 'BTCUSD', 'ETHUSD'], basket
    assert [b['market'] for b in basket][:3] == ['S&P 500', 'USA małe spółki', 'Nasdaq 100'] and basket_valid(basket)
    del admitted['SPY']                                                            # czwarty rynek klasy wchodzi na zwolnione miejsce
    assert [b['symbol'] for b in select_basket(admitted)][:3] == ['IWM', 'QQQ', 'XLF']
    assert not basket_valid(select_basket({s: fact(s) for s in ('SPY', 'IWM', 'QQQ', 'XLF', 'EFA', 'EEM', 'EWJ')}))   # 6 rynków, 2 klasy
    assert not basket_valid(select_basket({s: fact(s) for s in ('SPY', 'EFA', 'TLT', 'GLD', 'ETHUSD')}))               # 5 rynków, 5 klas
    assert basket_valid(select_basket({s: fact(s) for s in ('SPY', 'IWM', 'EFA', 'TLT', 'GLD', 'ETHUSD')}))
    print('SELFTEST OK')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Koszyk serii 2 według SPEC_SERIA2.md.')
    parser.add_argument('--kapital', type=float, default=2500.0)
    parser.add_argument('--ekspozycja', type=float, default=1.0, help='G: największa łączna ekspozycja jako krotność kapitału.')
    parser.add_argument('--dane', type=Path, default=ud.DATA_DIR, help='Katalog z plikami <SYMBOL>_D1.csv i .meta.json.')
    parser.add_argument('--raport', type=Path, default=None, help='Plik raportu; domyślnie reports/SERIA2_KOSZYK_<kapitał>.md.')
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.kapital <= 0 or args.ekspozycja <= 0:
        print('Kapitał i ekspozycja muszą być dodatnie.')
        return 2
    data = ud.load(args.dane) if args.dane.is_dir() else {}
    if not data or not ud.SYMBOLS.exists():
        print(f'BRAK DANYCH: nie ma plików D1 w {args.dane} albo pliku {ud.SYMBOLS.name}.')
        return 2
    fx = json.loads(ud.SYMBOLS.read_text(encoding='utf-8'))['fx_to_usd']
    lines = report(data, fx, args.kapital, args.ekspozycja, f'pliki D1 z `{args.dane.name}/`')
    target = args.raport or ud.OUT_DIR / f'SERIA2_KOSZYK_{args.kapital:.0f}.md'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
