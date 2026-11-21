"""Co oznacza najmniejsza pozycja CFD przy danym kapitale: ekspozycja, finansowanie, wahania.

To nie jest test strategii i nie daje werdyktu ani oczekiwanego zysku. Dla każdego rynku z danych D1
liczy wartość najmniejszego lota, roczny koszt finansowania pozycji długiej oraz to, ile kapitału
ruszał typowy i najgorszy dzień. Dla zestawów „po jednym najmniejszym locie" pokazuje łączną
ekspozycję i przeprowadza dzisiejsze wartości pozycji przez dzienne zmiany cen od marca 2018.

    python research/daily-trend/scripts/cfd_ekspozycja.py --kapital 2500
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_h2_h3 as eng  # noqa: E402

START = '2018-03-19'  # początek wspólnej, ciągłej historii u brokera (jak w badaniu H2/H3)


def usd(value: float) -> str:
    return f'{value:,.0f}'.replace(',', ' ') + ' USD'


def load_all(price_day: str) -> dict:
    data = {}
    for meta_path in sorted(eng.DATA_DIR.glob('*_D1.meta.json')):
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        text = meta_path.with_name(meta_path.name.replace('.meta.json', '.csv')).read_text(encoding='utf-8')
        rows = [r for r in csv.DictReader(text.splitlines()) if START <= r['date'] <= price_day]
        closes = [float(r['close']) for r in rows]
        costs = eng.costs_from_meta(meta, closes[-1], [])
        data[meta['market']] = {
            'meta': meta, 'close': closes[-1], 'last_date': rows[-1]['date'], 'fin': costs['base']['fin'],
            'returns': {rows[i]['date']: closes[i] / closes[i - 1] - 1 for i in range(1, len(rows))}}
    return data


def lot_value(data: dict, name: str) -> float:
    meta = data[name]['meta']
    fx = 1.0 if meta['currency_profit'] == 'USD' else data['EURUSD']['close'] if meta['currency_profit'] == 'EUR' else float('nan')
    return meta['volume_min'] * meta['trade_contract_size'] * data[name]['close'] * fx


def replay(names: list[str], data: dict, values: dict) -> dict:
    """Stałe, dzisiejsze wartości pozycji przeprowadzone przez historyczne dzienne zmiany cen, bez kosztów."""
    days = sorted({d for n in names for d in data[n]['returns']})
    pnl = [sum(values[n] * data[n]['returns'].get(d, 0.0) for n in names) for d in days]
    total = peak = 0.0
    peak_day = days[0]
    worst = {'drawdown': 0.0, 'from': days[0], 'to': days[0]}
    for day, change in zip(days, pnl):
        total += change
        if total > peak:
            peak, peak_day = total, day
        if peak - total > worst['drawdown']:
            worst = {'drawdown': peak - total, 'from': peak_day, 'to': day}
    low = min(range(len(pnl)), key=pnl.__getitem__)
    return {**worst, 'typical': statistics.pstdev(pnl[-252:]), 'worst_day': pnl[low], 'worst_day_date': days[low]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Ekspozycja i koszt najmniejszych pozycji CFD przy danym kapitale.')
    parser.add_argument('--kapital', type=float, default=2500.0)
    parser.add_argument('--dzien', default='2026-10-31', help='Dzień cen; domyślnie ten sam co w MIN_KAPITAL.md.')
    args = parser.parse_args(argv)
    capital = args.kapital
    data = load_all(args.dzien)
    values = {n: lot_value(data, n) for n in data}
    order = sorted(data, key=values.__getitem__)
    lines = [f'# Najmniejsze pozycje CFD przy kapitale {usd(capital)}', '',
             f'Ceny z {args.dzien}, najmniejsze loty i stawki finansowania z odczytu terminala. Historia zmian cen od {START}.',
             'To nie jest test strategii. Tabele pokazują ryzyko i koszt trzymania pozycji długiej, a nie oczekiwany zysk.', '',
             '## Jedna najmniejsza pozycja długa', '',
             '| Rynek | Symbol | Wartość | Część kapitału | Finansowanie rocznie | Typowy dzień | Najgorszy dzień od 2018 |',
             '|---|---|---|---|---|---|---|']
    for n in order:
        r = list(data[n]['returns'].values())
        worst_date = min(data[n]['returns'], key=data[n]['returns'].get)
        fin = values[n] * data[n]['fin']
        lines.append(f"| {n} | {data[n]['meta']['symbol']} | {usd(values[n])} | {values[n] / capital:.0%} | {usd(fin)} ({fin / capital:.1%} kapitału) | "
                     f"±{usd(statistics.pstdev(r[-252:]) * values[n])} | {usd(min(r) * values[n])} ({min(r) * values[n] / capital:.1%} kapitału, {worst_date}) |")
    basket = [n for n in order if n in eng.BASKET]
    sets = {'Cztery najtańsze rynki koszyka': basket[:4], 'Cały koszyk z badania (7 rynków)': basket,
            'Wszystko, co pojedynczo mieści się w kapitale': [n for n in order if values[n] <= capital]}
    lines += ['', '## Zestawy: po jednej najmniejszej pozycji długiej na każdym rynku', '',
              'Obsunięcie liczone tak: dzisiejsze wartości pozycji przechodzą przez dzienne zmiany cen od 2018 roku, bez kosztów.', '',
              '| Zestaw | Rynki | Łączna wartość pozycji | Razy kapitał | Finansowanie rocznie | Typowy dzień | Najgorszy dzień | Największe obsunięcie |',
              '|---|---|---|---|---|---|---|---|']
    for title, names in sets.items():
        gross = sum(values[n] for n in names)
        fin = sum(values[n] * data[n]['fin'] for n in names)
        r = replay(names, data, values)
        lines.append(f"| {title} | {', '.join(names)} | {usd(gross)} | {gross / capital:.1f} | {usd(fin)} ({fin / capital:.1%} kapitału) | ±{usd(r['typical'])} ({r['typical'] / capital:.1%}) | "
                     f"{usd(r['worst_day'])} ({r['worst_day'] / capital:.1%}, {r['worst_day_date']}) | {usd(-r['drawdown'])} ({-r['drawdown'] / capital:.0%} kapitału, {r['from']} do {r['to']}) |")
    lines += ['', 'Obsunięcie większe niż 100% kapitału oznacza, że rachunek zostałby zamknięty przez brokera, zanim okres by się skończył.',
              'Finansowanie dotyczy pozycji długich i pochodzi z jednego odczytu stawek; dodatni swap liczę jako zero.']
    eng.OUT_DIR.mkdir(parents=True, exist_ok=True)
    (eng.OUT_DIR / f'CFD_EKSPOZYCJA_{capital:.0f}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
