"""Najmniejszy kapitał, przy którym koszyk H2 da się wykonać bez dźwigni na najmniejszych lotach brokera.

Nie liczy wyników strategii. Bierze wagi docelowe z tych samych funkcji co badanie (`run_h2_h3.py`)
i porównuje je z wartością najmniejszego lota z plików meta. Kapitał w USD (waluta rachunku).

    python research/daily-trend/scripts/min_kapital.py
    python research/daily-trend/scripts/min_kapital.py --skala-lota 0.1   # wariant hipotetyczny
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_h2_h3 as eng  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'src'))
from astraljet.lab.position_sizing import SizingLimits, size_positions  # noqa: E402
from astraljet.workspace.instruments import D, FxRate, FxTable, InstrumentSpec  # noqa: E402

STUDY_LIMITS = SizingLimits(max_per_market=D(1))  # badanie nie miało limitu jednego rynku
MAIN = (252, 60)
LEVELS = (1_000, 2_500, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000)
FIRST_DECISION = '2024-12-31'


def load_sizing() -> dict:
    sizing = {}
    for path in sorted(eng.DATA_DIR.glob('*_D1.meta.json')):
        meta = json.loads(path.read_text(encoding='utf-8'))
        if meta.get('market') in eng.BASKET:
            sizing[meta['market']] = {k: meta[k] for k in ('symbol', 'volume_min', 'volume_step', 'volume_max', 'trade_contract_size', 'currency_profit')}
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Najmniejszy kapitał dla koszyka H2 bez dźwigni.')
    parser.add_argument('--skala-lota', type=float, default=1.0,
                        help='Mnożnik najmniejszego lota i kroku. Inny niż 1 daje wariant hipotetyczny w osobnym pliku.')
    scale = parser.parse_args(argv).skala_lota
    markets, dropped = eng.load_markets()
    sizing = load_sizing()
    if len(markets) < eng.MIN_MARKETS or any('volume_min' not in s for s in sizing.values()):
        print('BRAK DANYCH: brak rynków koszyka albo pól wolumenu w plikach meta.')
        return 2
    for s in sizing.values():
        s['volume_min'] = round(s['volume_min'] * scale, 10)
        s['volume_step'] = round(s['volume_step'] * scale, 10)
    specs = {n: InstrumentSpec(symbol=s['symbol'], digits=0, contract_size=D(s['trade_contract_size']),
                               profit_currency=s['currency_profit'], volume_min=D(s['volume_min']),
                               volume_max=D(s['volume_max']), volume_step=D(s['volume_step'])) for n, s in sizing.items()}
    calendar = eng.build_calendar(markets)
    days = decisions(markets, calendar)
    rules = {'sam koszyk (zawsze w rynku)': eng.decide_trend(*MAIN, always=True), 'H2 (z filtrem trendu)': eng.decide_trend(*MAIN)}
    last_day, last_history, last_close = days[-1]
    lines = ['# Najmniejszy kapitał dla koszyka H2 bez dźwigni', '',
             f'Dni decyzji: {days[0][0]} do {last_day} ({len(days)} decyzji). Kapitał w USD. Nie ma tu wyników strategii.', '']
    if scale != 1.0:
        lines += [f'**Wariant hipotetyczny:** najmniejszy lot i krok pomnożone przez {scale:g}. To nie są warunki obecnego brokera.', '']
    lines += ['## Najmniejsza pozycja u brokera' if scale == 1.0 else '## Najmniejsza pozycja w wariancie hipotetycznym', '',
             f'Ceny z {last_day}.', '', '| Rynek | Symbol | Najmniejszy lot | Wartość najmniejszego lota |', '|---|---|---|---|']
    for n in markets:
        lines.append(f"| {n} | {sizing[n]['symbol']} | {sizing[n]['volume_min']:g} | {lot_value(sizing, n, last_close, sizing[n]['volume_min']):,.0f} USD |".replace(',', ' '))
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
        active = {n: w for n, w in targets.items() if w > 0}
        fx = FxTable()
        fx.add(FxRate('EUR', 'USD', D(last_close['EURUSD']), 'zamknięcie EURUSD z danych D1', last_day))
        for capital in LEVELS:
            # Ta sama funkcja wielkości pozycji, której użyje paper i wykonanie.
            sized = size_positions(active, capital=capital, prices=last_close, specs=specs, fx=fx, limits=STUDY_LIMITS)
            held = sum(1 for p in sized.values() if p.volume)
            invested = float(sum(p.value for p in sized.values()))
            lines.append(f"| {capital:,} USD | {held} z {len(active)} | {len(active) - held} | {invested / capital:.0%} | {sum(active.values()):.0%} |".replace(',', ' '))
    lines += ['', 'Bez dźwigni oznacza, że suma wartości pozycji nie przekracza kapitału, tak jak w badaniu.']
    eng.OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = 'MIN_KAPITAL.md' if scale == 1.0 else f'MIN_KAPITAL_LOT_x{scale:g}.md'
    (eng.OUT_DIR / name).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
