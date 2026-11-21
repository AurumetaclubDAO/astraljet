"""Uniwersum CFD brokera przy danym kapitale: co ma dość mały lot i ile kosztuje trzymanie pozycji.

Czyta lokalną listę symboli (`research/daily-data/data/symbols_all.json`, odczyt tylko do odczytu z terminala)
i nie łączy się z niczym. Nie jest testem strategii. Lista kandydatów do serii 2 jest propozycją
koordynatora, nie wynikiem badania.

    python research/daily-trend/scripts/uniwersum_cfd.py --kapital 2500
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SYMBOLS = BASE.parent / 'daily-data' / 'data' / 'symbols_all.json'
OUT_DIR = BASE / 'reports'
TRADE_MODE = {0: 'wyłączony', 1: 'tylko długie', 2: 'tylko krótkie', 3: 'tylko zamykanie', 4: 'pełny'}
INTEREST = ('INTEREST_CURRENT', 'INTEREST_OPEN')
CANDIDATES = {
    'Akcje USA': ['SPY', 'QQQ', 'IWM', 'XLF', 'XLK', 'SMH', 'SP500.r', 'US2000.r'],
    'Akcje poza USA': ['EFA', 'EEM', 'EWJ', 'FXI', 'MCHI', 'INDA', 'EWZ', 'EWY', 'EWT',
                       'EU50.r', 'UK100.r', 'Nikkei225', 'HK50.r', 'CHINAH.r', 'SPI200.r'],
    'Obligacje': ['TLT', 'USNote10Y', 'EUB10Y', 'EUB5Y', 'EUB2Y', 'EUB30Y', 'LongGilt'],
    'Złoto i metale': ['GLD', 'GDX', 'XPTUSD.r', 'XAUUSD+', 'XAGUSD'],
    'Energia i surowce': ['USO', 'BNO', 'UNG', 'DBC', 'XOP', 'UKOUSD', 'USOUSD', 'Wheat-Cr', 'Soybean-Cr'],
    'Krypto': ['BTCUSD', 'ETHUSD', 'SOLUSD', 'LTCUSD', 'XRPUSD', 'BCHUSD', 'IBIT'],
    'Waluty': ['EURUSD+', 'GBPUSD+', 'USDJPY+', 'AUDUSD+'],
}


def usd(value: float) -> str:
    return f'{value:,.0f}'.replace(',', ' ') + ' USD'


def mode(symbol: dict) -> str:
    return TRADE_MODE.get(int(symbol['trade_mode']), str(symbol['trade_mode']))


def swap_text(symbol: dict) -> str:
    """Koszt trzymania: procent rocznie, gdy broker podaje go w procentach; inaczej surowe wartości i tryb."""
    name = symbol.get('swap_mode_name')
    long, short = symbol['swap_long'], symbol['swap_short']
    if name == 'DISABLED':
        return 'bez swapu'
    if name in INTEREST:
        return f'długa {long:+g}% rocznie, krótka {short:+g}%'.replace('+0%', '0%')
    return f'długa {long:+g}, krótka {short:+g} ({name})'


def lot_units(symbol: dict) -> str:
    return f"{symbol['volume_min']:g} × {symbol['trade_contract_size']:g}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Uniwersum CFD brokera przy danym kapitale.')
    parser.add_argument('--kapital', type=float, default=2500.0)
    capital = parser.parse_args(argv).kapital
    if not SYMBOLS.exists():
        print(f'BRAK DANYCH: nie ma pliku {SYMBOLS.name}.')
        return 2
    doc = json.loads(SYMBOLS.read_text(encoding='utf-8'))
    symbols = doc['symbols']
    by_name = {s['name']: s for s in symbols}
    groups = collections.defaultdict(list)
    for s in symbols:
        groups[s['category']].append(s)
    priced = [s for s in symbols if s.get('min_lot_value_usd') is not None]
    lines = [f'# Uniwersum CFD brokera przy kapitale {usd(capital)}', '',
             f"Źródło: odczyt listy symboli z terminala z {doc['read_at_utc'][:16].replace('T', ' ')} UTC, {len(symbols)} symboli. "
             f'Cenę ma {len(priced)} z nich; dla reszty terminal jej nie podaje bez dodania symbolu do Market Watch.',
             'To nie jest test strategii ani zalecenie, czym handlować.',
             'W koszcie trzymania minus oznacza opłatę, plus wpływ na rachunek. Stawki w punktach albo kwocie zależą od ceny i nie dają się porównać wprost.', '',
             '## Kategorie', '',
             '| Kategoria | Symboli | Tryb pełny | Najczęstszy najmniejszy lot (lot × kontrakt) | Najczęstszy koszt trzymania | Z ceną |',
             '|---|---:|---:|---|---|---:|']
    for category, rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        lot = collections.Counter(lot_units(s) for s in rows).most_common(1)[0]
        swap = collections.Counter(swap_text(s) if s.get('swap_mode_name') in INTEREST + ('DISABLED',) else 'w punktach albo kwocie, różny dla każdego symbolu'
                                   for s in rows).most_common(1)[0]
        lines.append(f"| {category} | {len(rows)} | {sum(1 for s in rows if int(s['trade_mode']) == 4)} | {lot[0]} ({lot[1]} symboli) | "
                     f"{swap[0]} ({swap[1]} symboli) | {sum(1 for s in rows if s.get('min_lot_value_usd') is not None)} |")
    tradable = sorted((s for s in priced if int(s['trade_mode']) == 4), key=lambda s: s['min_lot_value_usd'])
    bands = (('do 10% kapitału', 0.0, 0.10), ('od 10% do 35% kapitału', 0.10, 0.35), ('powyżej 35% kapitału', 0.35, float('inf')))
    lines += ['', '## Symbole z ceną i pełnym trybem handlu: wielkość najmniejszej pozycji', '',
              '| Najmniejsza pozycja | Symboli | Które |', '|---|---:|---|']
    for title, low, high in bands:
        hit = [s for s in tradable if low < s['min_lot_value_usd'] / capital <= high]
        names = ', '.join(f"{s['name']} ({usd(s['min_lot_value_usd'])})" for s in hit[:12]) + (f' i {len(hit) - 12} innych' if len(hit) > 12 else '')
        lines.append(f'| {title} | {len(hit)} | {names} |')
    lines += ['', '## Kandydaci do serii 2 (propozycja)', '',
              'Rynki z różnych klas, wybrane po opisie i parametrach lota. Wartość najmniejszej pozycji jest podana tam, gdzie terminal zna cenę.', '',
              '| Klasa | Symbol | Opis | Najmniejszy lot (lot × kontrakt) | Wartość najmniejszej pozycji | Koszt trzymania | Tryb handlu |',
              '|---|---|---|---|---|---|---|']
    missing_price, absent, total = [], [], 0
    for group, names in CANDIDATES.items():
        for name in names:
            s = by_name.get(name)
            if s is None:
                absent.append(name)
                continue
            total += 1
            value = s.get('min_lot_value_usd')
            if value is None:
                missing_price.append(name)
            worth = f'{usd(value)} ({value / capital:.1%} kapitału)' if value is not None else 'brak ceny'
            lines.append(f"| {group} | `{name}` | {s['description']} | {lot_units(s)} {s['currency_profit']} | {worth} | {swap_text(s)} | {mode(s)} |")
    lines += ['', '## Czego brakuje', '',
              f'- Ceny: {len(missing_price)} z {total} kandydatów nie ma ceny w terminalu, bo nie są w Market Watch.',
              '- Historia dzienna: jest tylko dla 9 rynków z serii 1.',
              '- Prowizja: lista symboli jej nie zawiera. Dla CFD na akcje i ETF-y trzeba ją sprawdzić w specyfikacji brokera.',
              '- Kontrakty oparte na futures (obligacje, symbole z końcówką ft) nie mają swapu; koszt siedzi w cenie i w rolowaniu i trzeba go zmierzyć na historii.']
    if absent:
        lines.append(f"- Symboli z listy kandydatów nie ma u brokera: {', '.join(absent)}.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f'UNIWERSUM_CFD_{capital:.0f}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    print(f'\n[brak ceny: {len(missing_price)}] ' + ' '.join(missing_price))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
