"""Badanie offline H1: tygodniowy model BTC/ETH (pakiet A) na istniejącym silniku.

Tylko odczyt danych i obliczenia. Nie tworzy rekordów RUN, nie łączy się z
brokerem i niczego nie zleca. Parametry główne są stałe (SMA 200, nachylenie 20,
wagi z pakietu A). Kryteria oceny zapisano PRZED testem, 17.11.2026, w
`D:\\CENTRUM\\01_PROJEKTY\\AURUQ-TRADING\\PLAN_BUDOWY.md` (protokół walidacji).

Uruchomienie (z katalogu repozytorium):
    python research/btc-eth-weekly/scripts/run_offline.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))

from astraljet.lab.data_quality import MarketBar  # noqa: E402
from astraljet.lab.weekly_portfolio import (  # noqa: E402
    CostScenario, WeeklyProtocol, simulate_weekly, weekly_engine_fingerprint,
)

CSV_PATH = ROOT / '.runtime' / 'data' / 'alpaca_crypto_us_full_2015-01-01_2026-09-19.csv'
OUT_DIR = Path(__file__).resolve().parents[1] / 'reports'
START, IS_END, OOS_START, END = '2021-01-01', '2024-12-31', '2025-01-01', '2026-09-18'

# Kryteria zapisane przed testem (PLAN_BUDOWY.md, 17.11.2026).
MIN_SHARPE_BASE = 0.7
MAX_DRAWDOWN = 0.25
MIN_POSITIVE_WINDOWS = 0.60


def load_bars() -> tuple[list[MarketBar], str]:
    raw = CSV_PATH.read_bytes()
    reader = csv.DictReader(raw.decode('utf-8').splitlines())
    bars = [MarketBar(r['timestamp'], r['instrument'], D(r['open']), D(r['high']), D(r['low']), D(r['close']))
            for r in reader]
    return bars, hashlib.sha256(raw).hexdigest()


def segment_stats(rows: list[dict], first_date: str) -> dict:
    """Sharpe i okna kwartalne dla odcinka od first_date; punkt odniesienia to poprzednie zamknięcie."""
    idx = next(i for i, r in enumerate(rows) if r['date'] >= first_date)
    equity = [float(rows[idx - 1]['equity_close'])] + [float(r['equity_close']) for r in rows[idx:]]
    returns = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity))]
    mean = sum(returns) / len(returns)
    var = sum((x - mean) ** 2 for x in returns) / (len(returns) - 1)
    sharpe = mean / math.sqrt(var) * math.sqrt(365) if var > 0 else None
    windows: dict[str, list[float]] = {}
    previous = equity[0]
    for row in rows[idx:]:
        year, month = int(row['date'][:4]), int(row['date'][5:7])
        key = f'{year}Q{(month - 1) // 3 + 1}'
        windows.setdefault(key, [previous, previous])[1] = float(row['equity_close'])
        previous = float(row['equity_close'])
    window_returns = {k: v[1] / v[0] - 1 for k, v in windows.items()}
    positive = sum(1 for v in window_returns.values() if v > 0)
    return {'sharpe': sharpe, 'windows': window_returns,
            'positive_windows': positive, 'window_count': len(window_returns),
            'positive_share': positive / len(window_returns)}


def run_variant(bars, code_hash, *, ma: int, slope: int, cost_bps: str, delay: int, label: str) -> dict:
    protocol = WeeklyProtocol(START, IS_END, OOS_START, END, ma_window=ma, slope_lookback=slope)
    scenario = CostScenario(label, D(cost_bps), delay)
    result = simulate_weekly(bars, protocol=protocol, scenario=scenario, expected_code_hash=code_hash)
    out = {'label': label, 'ma_window': ma, 'slope_lookback': slope, 'cost_bps': cost_bps,
           'extra_delay_days': delay, 'input_hash': result['input_hash'], 'output_hash': result['output_hash']}
    for name in ('strategy', 'benchmark'):
        metrics = result['metrics'][name]
        stats = segment_stats(result['daily'][name], OOS_START)
        oos = metrics['out_of_sample']
        ann, dd = float(oos['annualized_return']), float(oos['max_drawdown'])
        out[name] = {
            'in_sample': {k: metrics['in_sample'][k] for k in ('net_return', 'annualized_return', 'max_drawdown')},
            'out_of_sample': {k: oos[k] for k in ('net_return', 'annualized_return', 'max_drawdown', 'total_cost',
                                                 'number_of_rebalances', 'mean_gross_exposure_at_close', 'days')},
            'oos_sharpe': stats['sharpe'], 'oos_return_to_drawdown': ann / dd if dd > 0 else None,
            'oos_windows': stats['windows'], 'oos_positive_windows': stats['positive_windows'],
            'oos_window_count': stats['window_count'], 'oos_positive_share': stats['positive_share'],
        }
    return out


def pct(value) -> str:
    return 'brak' if value is None else f'{float(value) * 100:+.1f}%'


def main() -> int:
    bars, data_hash = load_bars()
    code_hash = weekly_engine_fingerprint()
    variants = [
        run_variant(bars, code_hash, ma=200, slope=20, cost_bps='40', delay=0, label='bazowy_40pb'),
        run_variant(bars, code_hash, ma=200, slope=20, cost_bps='75', delay=0, label='stres_75pb'),
        run_variant(bars, code_hash, ma=200, slope=20, cost_bps='40', delay=1, label='bazowy_40pb_opoznienie'),
        run_variant(bars, code_hash, ma=200, slope=20, cost_bps='75', delay=1, label='stres_75pb_opoznienie'),
    ]
    neighbours = [run_variant(bars, code_hash, ma=ma, slope=slope, cost_bps='40', delay=0,
                              label=f'sasiad_sma{ma}_nach{slope}')
                  for ma in (160, 200, 240) for slope in (16, 20, 24) if (ma, slope) != (200, 20)]
    base, stress = variants[0], variants[1]
    s, b = base['strategy'], base['benchmark']
    checks = [
        ('1. Wynik po kosztach stresowych dodatni',
         float(stress['strategy']['out_of_sample']['net_return']) > 0,
         pct(stress['strategy']['out_of_sample']['net_return'])),
        (f'2. Sharpe po kosztach bazowych >= {MIN_SHARPE_BASE}',
         s['oos_sharpe'] is not None and s['oos_sharpe'] >= MIN_SHARPE_BASE,
         'brak' if s['oos_sharpe'] is None else f"{s['oos_sharpe']:.2f}"),
        ('3. Zysk do obsunięcia lepszy niż dla kup i trzymaj',
         s['oos_return_to_drawdown'] is not None and b['oos_return_to_drawdown'] is not None
         and s['oos_return_to_drawdown'] > b['oos_return_to_drawdown'],
         f"{s['oos_return_to_drawdown']:.2f} wobec {b['oos_return_to_drawdown']:.2f}"),
        (f'4. Największe obsunięcie <= {MAX_DRAWDOWN:.0%}',
         float(s['out_of_sample']['max_drawdown']) <= MAX_DRAWDOWN,
         pct(s['out_of_sample']['max_drawdown']).lstrip('+')),
        (f'5. Dodatnie okna kwartalne >= {MIN_POSITIVE_WINDOWS:.0%}',
         s['oos_positive_share'] >= MIN_POSITIVE_WINDOWS,
         f"{s['oos_positive_windows']} z {s['oos_window_count']}"),
        ('6. Sąsiednie parametry (+/-20%) też dodatnie',
         all(float(n['strategy']['out_of_sample']['net_return']) > 0 for n in neighbours),
         f"{sum(1 for n in neighbours if float(n['strategy']['out_of_sample']['net_return']) > 0)} z {len(neighbours)}"),
    ]
    verdict = 'PASS' if all(ok for _, ok, _ in checks) else 'FAIL'
    report = {
        'hypothesis': 'H1: tygodniowy model BTC/ETH z filtrem reżimu (pakiet A)',
        'status': 'OFFLINE_UNQUALIFIED: obliczenie modelu, nie rekord RUN i nie zgoda na handel',
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'data_file': CSV_PATH.name, 'data_sha256': data_hash, 'engine_hash': code_hash,
        'protocol': {'start': START, 'in_sample_end': IS_END, 'out_of_sample_start': OOS_START, 'end': END},
        'criteria_fixed_before_test': '2026-11-17, PLAN_BUDOWY.md',
        'checks': [{'criterion': c, 'passed': ok, 'value': v} for c, ok, v in checks],
        'verdict': verdict, 'trial_count': len(variants) + len(neighbours),
        'variants': variants, 'neighbours': neighbours,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'wynik_h1.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')

    lines = [
        '# H1: tygodniowy model BTC/ETH (pakiet A) — wynik badania offline', '',
        f"Wygenerowano: {report['generated_at']}. To obliczenie modelu, nie rekord RUN i nie zgoda na handel.", '',
        f"- Dane: `{CSV_PATH.name}`, SHA-256 `{data_hash[:16]}…`, {len(bars)} świec dziennych.",
        f'- Okres strojenia: {START} do {IS_END}. Próba poza strojeniem: {OOS_START} do {END}.',
        f"- Silnik: `astraljet.lab.weekly_portfolio`, odcisk `{code_hash[:16]}…`.",
        f"- Liczba uruchomionych wariantów: {report['trial_count']} (wszystkie w `wynik_h1.json`).",
        '- Kryteria zapisano przed testem (17.11.2026, `PLAN_BUDOWY.md`).', '',
        f'## Werdykt: {verdict}', '',
        '| Kryterium | Wynik | Zaliczone |', '|---|---|---|',
    ]
    lines += [f"| {c} | {v} | {'tak' if ok else 'NIE'} |" for c, ok, v in checks]
    lines += ['', '## Próba poza strojeniem, wariant główny (SMA 200, nachylenie 20)', '',
              '| Wariant | Strategia: wynik | Strategia: obsunięcie | Kup i trzymaj 80/20: wynik | Kup i trzymaj: obsunięcie |',
              '|---|---|---|---|---|']
    for v in variants:
        so, bo = v['strategy']['out_of_sample'], v['benchmark']['out_of_sample']
        lines.append(f"| {v['label']} | {pct(so['net_return'])} | {pct(so['max_drawdown']).lstrip('+')} | "
                     f"{pct(bo['net_return'])} | {pct(bo['max_drawdown']).lstrip('+')} |")
    lines += ['', '## Okres strojenia, wariant bazowy (dla porównania)', '',
              f"- Strategia: {pct(s['in_sample']['net_return'])}, obsunięcie {pct(s['in_sample']['max_drawdown']).lstrip('+')}.",
              f"- Kup i trzymaj 80/20: {pct(b['in_sample']['net_return'])}, obsunięcie {pct(b['in_sample']['max_drawdown']).lstrip('+')}.",
              '', '## Okna kwartalne poza strojeniem, wariant bazowy', '', '| Kwartał | Strategia | Kup i trzymaj |', '|---|---|---|']
    lines += [f"| {k} | {pct(s['oos_windows'][k])} | {pct(b['oos_windows'].get(k))} |" for k in s['oos_windows']]
    lines += ['', '## Sąsiednie parametry, koszty bazowe, próba poza strojeniem', '',
              '| SMA | Nachylenie | Wynik | Obsunięcie |', '|---|---|---|---|']
    lines += [f"| {n['ma_window']} | {n['slope_lookback']} | {pct(n['strategy']['out_of_sample']['net_return'])} | "
              f"{pct(n['strategy']['out_of_sample']['max_drawdown']).lstrip('+')} |" for n in neighbours]
    (OUT_DIR / 'WYNIK_H1.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(f'WERDYKT: {verdict}')
    for c, ok, v in checks:
        print(f"  {'OK ' if ok else 'NIE'} {c}: {v}")
    print(f"OOS bazowy: strategia {pct(s['out_of_sample']['net_return'])} (obsuniecie {pct(s['out_of_sample']['max_drawdown'])}), "
          f"kup i trzymaj {pct(b['out_of_sample']['net_return'])} (obsuniecie {pct(b['out_of_sample']['max_drawdown'])})")
    print(f"IS bazowy: strategia {pct(s['in_sample']['net_return'])}, kup i trzymaj {pct(b['in_sample']['net_return'])}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
