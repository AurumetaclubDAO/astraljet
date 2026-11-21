"""Diagnoza: ile wynik H2 i jej punktu odniesienia zależy od kosztu finansowania pozycji.

To nie jest test hipotezy i nie daje werdyktu. Reguły H2 są bez zmian (252, 60), koszty transakcyjne
bazowe, a finansowanie jest mnożone przez 0, 0,5 i 1. Okres próby był już oglądany w serii 1,
więc ten wynik służy tylko do zrozumienia, skąd bierze się koszt. Nie wolno na nim stroić reguł.

    python research/daily-trend/scripts/diag_finansowanie.py
"""
from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_h2_h3 as eng  # noqa: E402

MULTIPLIERS = (0.0, 0.5, 1.0)
MAIN = (252, 60)


def main() -> int:
    markets, dropped = eng.load_markets()
    if len(markets) < eng.MIN_MARKETS:
        print(f'BRAK DANYCH: {len(markets)} rynków koszyka. Poza koszykiem: {dropped}')
        return 2
    calendar = eng.build_calendar(markets)
    runs = []
    for mult in MULTIPLIERS:
        scaled = copy.deepcopy(markets)
        for market in scaled.values():
            market['costs']['base']['fin'] *= mult
        for name, decide in (('H2', eng.decide_trend(*MAIN)), ('punkt_odniesienia', eng.decide_trend(*MAIN, always=True))):
            result = eng.run_one(scaled, calendar, decide, 'base', 0, f'{name}_finansowanie_x{mult}', list(MAIN))
            runs.append({'strategy': name, 'financing_multiplier': mult, **result})
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    eng.OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {'generated_at': stamp, 'status': 'DIAGNOZA: bez werdyktu, okres próby oglądany wcześniej',
               'multipliers': list(MULTIPLIERS), 'runs': runs}
    (eng.OUT_DIR / 'diag_finansowanie.json').write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
    lines = ['# Diagnoza: wpływ kosztu finansowania na H2', '',
             f'Wygenerowano: {stamp}. To nie jest test hipotezy i nie daje werdyktu.',
             'Reguły H2 bez zmian, koszty transakcyjne bazowe. Zmienia się tylko mnożnik finansowania pozycji.',
             f'Okres próby (od {eng.OOS_START}) był już oglądany w serii 1.', '',
             '| Strategia | Finansowanie | Zwrot na próbie | Rocznie | Obsunięcie | Sharpe | Rocznie w strojeniu | Sharpe w strojeniu | Koszt łączny |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in runs:
        o, i = r['out_of_sample'], r['in_sample']
        lines.append(f"| {r['strategy']} | x{r['financing_multiplier']} | {o['net_return']:+.1%} | {o['annualized_return']:+.1%} | "
                     f"{o['max_drawdown']:.1%} | {o['sharpe']:.2f} | {i['annualized_return']:+.1%} | {i['sharpe']:.2f} | {r['total_cost']:.2f} |")
    lines += ['', 'Koszt łączny to suma kosztów z całej historii w relacji do kapitału początkowego.']
    (eng.OUT_DIR / 'DIAG_FINANSOWANIE.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[6:]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
