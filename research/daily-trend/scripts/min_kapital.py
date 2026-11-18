"""Najmniejszy kapitał, przy którym koszyk H2 da się wykonać bez dźwigni na najmniejszych lotach brokera.

Nie liczy wyników strategii. Bierze wagi docelowe z tych samych funkcji co badanie (`run_h2_h3.py`)
i porównuje je z wartością najmniejszego lota z plików meta. Kapitał w USD (waluta rachunku).

    python research/daily-trend/scripts/min_kapital.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_h2_h3 as eng  # noqa: E402

MAIN = (252, 60)
LEVELS = (1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000)
FIRST_DECISION = '2024-12-31'


def load_sizing() -> dict:
    sizing = {}
    for path in sorted(eng.DATA_DIR.glob('*_D1.meta.json')):
        meta = json.loads(path.read_text(encoding='utf-8'))
        if meta.get('market') in eng.BASKET:
            sizing[meta['market']] = {k: meta[k] for k in ('symbol', 'volume_min', 'volume_step', 'trade_contract_size', 'currency_profit')}
    return sizing


def decisions(markets: dict, calendar: list[str]) -> list[tuple[str, dict, dict]]:
    """Dni decyzji (ostatni dzień miesiąca w kalendarzu) z historią zamknięć, tak jak w silniku badania."""
    idx = {n: -1 for n in markets}
    out = []
    for k, day in enumerate(calendar):
        for n in markets:
            j = markets[n]['pos'].get(day)
            if j is not None:
                idx[n] = j
        if k + 1 < len(calendar) and calendar[k + 1][:7] != day[:7] and day >= FIRST_DECISION:
            history = {n: markets[n]['close'][:idx[n] + 1] for n in markets}
            if all(len(h) >= eng.WARMUP for h in history.values()):
                out.append((day, history, {n: h[-1] for n, h in history.items()}))
    return out


def lot_value(sizing: dict, name: str, close: dict, volume: float) -> float:
    s = sizing[name]
    fx = 1.0 if s['currency_profit'] == 'USD' else close['EURUSD'] if s['currency_profit'] == 'EUR' else float('nan')
    return volume * s['trade_contract_size'] * close[name] * fx


def main() -> int:
    markets, dropped = eng.load_markets()
    sizing = load_sizing()
    if len(markets) < eng.MIN_MARKETS or any('volume_min' not in s for s in sizing.values()):
        print('BRAK DANYCH: brak rynków koszyka albo pól wolumenu w plikach meta.')
        return 2
    calendar = eng.build_calendar(markets)
    days = decisions(markets, calendar)
    rules = {'sam koszyk (zawsze w rynku)': eng.decide_trend(*MAIN, always=True), 'H2 (z filtrem trendu)': eng.decide_trend(*MAIN)}
    last_day, last_history, last_close = days[-1]
    lines = ['# Najmniejszy kapitał dla koszyka H2 bez dźwigni', '',
             f'Dni decyzji: {days[0][0]} do {last_day} ({len(days)} decyzji). Kapitał w USD. Nie ma tu wyników strategii.', '',
             '## Najmniejsza pozycja u brokera', '',
             f'Ceny z {last_day}.', '', '| Rynek | Symbol | Najmniejszy lot | Wartość najmniejszego lota |', '|---|---|---|---|']
    for n in markets:
        lines.append(f"| {n} | {sizing[n]['symbol']} | {sizing[n]['volume_min']} | {lot_value(sizing, n, last_close, sizing[n]['volume_min']):,.0f} USD |".replace(',', ' '))
    for title, decide in rules.items():
        needs, per_market = [], {n: [] for n in markets}
        for day, history, close in days:
            targets = decide(history)
            required = {n: lot_value(sizing, n, close, sizing[n]['volume_min']) / w for n, w in targets.items() if w > 0}
            if required:
                needs.append(max(required.values()))
            for n, w in targets.items():
                per_market[n].append(w)
        targets = decide(last_history)
        lines += ['', f'## {title}', '',
                  'Kapitał, przy którym każdy rynek z wagą powyżej zera dostaje choć najmniejszy lot: mediana '
                  + f'{statistics.median(needs):,.0f}'.replace(',', ' ') + ' USD, najwięcej '
                  + f'{max(needs):,.0f}'.replace(',', ' ') + f' USD (z {len(needs)} decyzji).', '',
                  f'Wagi z ostatniej decyzji ({last_day}) i ich zakres od {days[0][0]}:', '',
                  '| Rynek | Waga ostatnio | Zakres wag | Kapitał potrzebny na najmniejszy lot |', '|---|---|---|---|']
        for n in markets:
            w = targets.get(n, 0.0)
            need = f"{lot_value(sizing, n, last_close, sizing[n]['volume_min']) / w:,.0f} USD".replace(',', ' ') if w > 0 else 'poza rynkiem'
            lines.append(f'| {n} | {w:.1%} | {min(per_market[n]):.1%} do {max(per_market[n]):.1%} | {need} |')
        lines += ['', 'Co da się kupić przy danym kapitale (ostatnia decyzja, zaokrąglenie lotów w dół):', '',
                  '| Kapitał | Rynki z pozycją | Rynki pominięte | Zainwestowane | Powinno być |', '|---|---|---|---|---|']
        active = [n for n, w in targets.items() if w > 0]
        for capital in LEVELS:
            invested, held = 0.0, 0
            for n in active:
                step = lot_value(sizing, n, last_close, sizing[n]['volume_step'])
                lots = int(targets[n] * capital / step + 1e-9)
                if lots * sizing[n]['volume_step'] + 1e-9 >= sizing[n]['volume_min']:
                    invested += lots * step
                    held += 1
            lines.append(f"| {capital:,} USD | {held} z {len(active)} | {len(active) - held} | {invested / capital:.0%} | {sum(targets[n] for n in active):.0%} |".replace(',', ' '))
    lines += ['', 'Bez dźwigni oznacza, że suma wartości pozycji nie przekracza kapitału, tak jak w badaniu.']
    eng.OUT_DIR.mkdir(parents=True, exist_ok=True)
    (eng.OUT_DIR / 'MIN_KAPITAL.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
