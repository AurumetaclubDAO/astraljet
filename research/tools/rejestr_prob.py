"""Rejestr prób: zbiera wszystkie uruchomione warianty badań do jednej tabeli.

Czyta pliki wyników (JSON) zapisane przez skrypty badań i pisze `research/REJESTR_PROB.md`.
Niczego nie liczy od nowa i niczego nie pobiera. Uruchomienie z katalogu repozytorium:

    python research/tools/rejestr_prob.py
"""
from __future__ import annotations

import json
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]
H1_FILE = RESEARCH / 'btc-eth-weekly' / 'reports' / 'wynik_h1.json'
H23_FILE = RESEARCH / 'daily-trend' / 'reports' / 'wynik_h2_h3.json'
DIAG_FILE = RESEARCH / 'daily-trend' / 'reports' / 'diag_finansowanie.json'
S2_FILE = RESEARCH / 'daily-trend' / 'reports' / 'wynik_seria2_2500.json'
OUT_FILE = RESEARCH / 'REJESTR_PROB.md'
S2_TITLES = {'H4': 'trend w obie strony, koszyk CFD w lotach', 'H5': 'trend tylko długi, koszyk CFD w lotach'}
# Hipotezy z regułami zapisanymi w SPEC_H2_H3.md; liczba wariantów na każdą wynika z tego pliku.
PLANNED = {'H2': 'podążanie za trendem na koszyku rynków', 'H3': 'rotacja momentum między rynkami'}
PLANNED_TRIALS = 12


def pct(value) -> str:
    return 'brak' if value is None else format(float(value), '+.1%')


def num(value) -> str:
    return 'brak' if value is None else format(float(value), '.2f')


def rows_h1(data: dict) -> list[list[str]]:
    rows = []
    for role, group in (('główny', data['variants']), ('sąsiad', data['neighbours'])):
        for v in group:
            oos = v['strategy']['out_of_sample']
            rows.append(['H1', v['label'], role, f"SMA {v['ma_window']}, nachylenie {v['slope_lookback']}",
                         f"{v['cost_bps']} pb", str(v['extra_delay_days']), pct(oos['net_return']),
                         pct(oos['max_drawdown']).lstrip('+'), num(v['strategy']['oos_sharpe'])])
    return rows


def rows_h23(result: dict) -> list[list[str]]:
    rows = []
    for role, group in (('główny', result['variants']), ('sąsiad', result['neighbours'])):
        for v in group:
            oos = v['out_of_sample'] or {}
            rows.append([result['code'], v['label'], role, ', '.join(str(p) for p in v['params']),
                         {'base': 'bazowy', 'stress': 'stresowy'}.get(v['scenario'], v['scenario']), str(v['delay']),
                         pct(oos.get('net_return')), pct(oos.get('max_drawdown')).lstrip('+'), num(oos.get('sharpe'))])
    return rows


def build() -> str:
    summary, rows = [], []
    if H1_FILE.exists():
        h1 = json.loads(H1_FILE.read_text(encoding='utf-8'))
        passed = sum(1 for c in h1['checks'] if c['passed'])
        summary.append(['H1', 'tygodniowy model BTC/ETH z filtrem reżimu', h1['verdict'],
                        f"{passed} z {len(h1['checks'])}", str(len(h1['variants']) + len(h1['neighbours'])),
                        h1['generated_at'][:10], h1['data_sha256'][:12]])
        rows += rows_h1(h1)
    done = set()
    if H23_FILE.exists():
        h23 = json.loads(H23_FILE.read_text(encoding='utf-8'))
        for r in h23['results']:
            done.add(r['code'])
            passed = sum(1 for c in r['checks'] if c['passed'])
            summary.append([r['code'], r['title'], r['verdict'], f"{passed} z {len(r['checks'])}" if r['checks'] else 'brak',
                            str(len(r['variants']) + len(r['neighbours'])), h23['generated_at'][:10], 'w pliku wyniku'])
            rows += rows_h23(r)
    if S2_FILE.exists():
        s2 = json.loads(S2_FILE.read_text(encoding='utf-8'))
        hashes = s2.get('data_sha256') or {}
        for r in s2['results']:
            passed = sum(1 for c in r['checks'] if c['passed'])
            summary.append([r['hypothesis'], S2_TITLES.get(r['hypothesis'], r['hypothesis']), r['verdict'],
                            f"{passed} z {len(r['checks'])}" if r['checks'] else 'brak',
                            str(len(r['variants']) + len(r['neighbours'])), s2['generated_at'][:10],
                            f'{len(hashes)} plików, w pliku wyniku' if hashes else 'w pliku wyniku'])
            rows += rows_h23({**r, 'code': r['hypothesis']})
    for code, title in PLANNED.items():
        if code not in done:
            summary.append([code, title, 'NIEURUCHOMIONE', 'brak', f'0 z {PLANNED_TRIALS} zapisanych', 'brak', 'brak'])
    total = len(rows)
    lines = ['# Rejestr prób', '',
             'Każdy uruchomiony wariant każdej hipotezy, także nieudany. Plik tworzy `research/tools/rejestr_prob.py`',
             'z plików wyników. Nie edytuj go ręcznie. Zasady: `docs/research/PROTOKOL_WALIDACJI.md`.', '',
             f'Uruchomionych wariantów łącznie: {total}. Im więcej prób, tym większa szansa, że dobry wynik jest',
             'przypadkiem, dlatego ta liczba stoi na górze.', '',
             '## Hipotezy', '',
             '| Hipoteza | Opis | Werdykt | Kryteria spełnione | Warianty | Data | Dane (SHA-256) |', '|---|---|---|---|---|---|---|']
    lines += ['| ' + ' | '.join(r) + ' |' for r in summary]
    lines += ['', '## Warianty', '', 'Liczby dotyczą próby poza strojeniem (od 01.01.2025).', '',
              '| Hipoteza | Wariant | Rola | Parametry | Koszt | Opóźnienie | Zwrot | Obsunięcie | Sharpe |',
              '|---|---|---|---|---|---|---|---|---|']
    lines += ['| ' + ' | '.join(r) + ' |' for r in rows]
    if DIAG_FILE.exists():
        diag = json.loads(DIAG_FILE.read_text(encoding='utf-8'))
        lines += ['', '## Przebiegi diagnostyczne', '',
                  f"Bez werdyktu, na okresie oglądanym wcześniej. Liczba przebiegów: {len(diag['runs'])} "
                  f"({diag['generated_at'][:10]}). Też są spojrzeniem na próbę, więc liczą się do ostrożności.", '',
                  '| Diagnoza | Strategia | Mnożnik finansowania | Zwrot | Obsunięcie | Sharpe |', '|---|---|---|---|---|---|']
        for r in diag['runs']:
            oos = r['out_of_sample']
            lines.append(f"| wpływ finansowania | {r['strategy']} | {r['financing_multiplier']} | {pct(oos['net_return'])} | "
                         f"{pct(oos['max_drawdown']).lstrip('+')} | {num(oos['sharpe'])} |")
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    OUT_FILE.write_text(build(), encoding='utf-8')
    print(f'Zapisano {OUT_FILE}')
