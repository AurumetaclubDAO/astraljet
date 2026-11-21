"""Badania H2 (trend) i H3 (rotacja momentum) na świecach dziennych z MT5.

Reguły, koszty, warianty i kryteria: `research/daily-trend/SPEC_H2_H3.md`
(zapisane przed zobaczeniem danych). Tylko odczyt plików i obliczenia: brak
połączenia z brokerem, brak zleceń, brak rekordów RUN.

    python research/daily-trend/scripts/run_h2_h3.py --selftest
    python research/daily-trend/scripts/run_h2_h3.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from datetime import date, datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE.parent / 'daily-data' / 'data'
OUT_DIR = BASE / 'reports'
BASKET = ('SP500', 'NAS100', 'DAX', 'GOLD', 'BRENT', 'EURUSD', 'BTCUSD')
OOS_START = '2025-01-01'
MIN_BARS_BEFORE_OOS, MIN_MARKETS, WARMUP, MIN_TRADE = 1500, 4, 320, 0.02
MIN_SHARPE, MAX_DD, MIN_POSITIVE = 0.7, 0.25, 0.60


def costs_from_meta(meta: dict, last_close: float, spreads: list[float]) -> dict:
    point = float(meta.get('point') or 0)
    candidates = [float(v) for v in (meta.get('spread_points'), meta.get('spread')) if isinstance(v, (int, float))]
    if spreads:
        candidates.append(statistics.median(spreads))
    spread_rel = max(candidates) * point / last_close if candidates and point > 0 else 0.001
    swap, mode = meta.get('swap_long'), meta.get('swap_mode')
    size = float(meta.get('trade_contract_size') or 0)
    fin, source = 0.07, 'domyślne 7%'
    if isinstance(swap, (int, float)) and isinstance(mode, int):
        cost = max(0.0, -float(swap))
        if mode == 0:
            fin, source = 0.0, 'swap wyłączony'
        elif mode == 1 and point > 0:
            fin, source = cost * point * 365 / last_close, 'swap w punktach'
        elif mode in (5, 6):
            fin, source = cost / 100, 'swap w procentach rocznie'
        elif mode in (2, 3, 4) and size > 0:
            fin, source = cost * 365 / (size * last_close), 'swap kwotowy (przybliżenie)'
    return {'spread_rel': spread_rel, 'fin_source': source,
            'base': {'side': spread_rel / 2 + 0.0001, 'fin': fin},
            'stress': {'side': spread_rel + 0.0002, 'fin': fin * 1.5 + 0.01}}


def make_market(name: str, dates: list[str], opens: list[float], closes: list[float], costs: dict, **extra) -> dict:
    if dates != sorted(set(dates)):
        raise SystemExit(f'{name}: daty nie są rosnące i unikalne')
    return {'name': name, 'dates': dates, 'open': opens, 'close': closes, 'costs': costs,
            'pos': {d: i for i, d in enumerate(dates)}, **extra}


def load_markets() -> tuple[dict, dict]:
    markets, dropped = {}, {}
    for meta_path in sorted(DATA_DIR.glob('*_D1.meta.json')):
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        name = meta.get('market')
        if name not in BASKET:
            continue
        raw = meta_path.with_name(meta_path.name.replace('.meta.json', '.csv')).read_bytes()
        rows = list(csv.DictReader(raw.decode('utf-8').splitlines()))
        dates = [r['date'] for r in rows]
        before = sum(1 for d in dates if d < OOS_START)
        if before < MIN_BARS_BEFORE_OOS:
            dropped[name] = f'{before} świec przed {OOS_START}'
            continue
        closes = [float(r['close']) for r in rows]
        spreads = [float(r['spread']) for r in rows if r.get('spread') not in (None, '')]
        markets[name] = make_market(name, dates, [float(r['open']) for r in rows], closes,
                                    costs_from_meta(meta, closes[-1], spreads),
                                    symbol=meta.get('symbol'), sha256=hashlib.sha256(raw).hexdigest())
    for name in BASKET:
        if name not in markets and name not in dropped:
            dropped[name] = 'brak pliku'
    return markets, dropped


def build_calendar(markets: dict) -> list[str]:
    start = max(m['dates'][0] for m in markets.values())
    end = min(m['dates'][-1] for m in markets.values())
    return sorted({d for m in markets.values() for d in m['dates'] if start <= d <= end})


def simulate(markets: dict, calendar: list[str], decide, scenario: str, delay: int) -> dict:
    names = list(markets)
    idx = {n: -1 for n in names}
    units = {n: 0.0 for n in names}
    cash, total_cost, trades, first_trade = 1.0, 0.0, 0, None
    pending: dict[str, tuple[float, int]] = {}
    rows: list[tuple[str, float]] = []
    previous = None
    for k, day in enumerate(calendar):
        has_bar = set()
        for n in names:
            j = markets[n]['pos'].get(day)
            if j is not None:
                idx[n] = j
                has_bar.add(n)
        ready = []
        for n in names:
            if n in pending and n in has_bar:
                weight, wait = pending[n]
                if wait > 0:
                    pending[n] = (weight, wait - 1)
                else:
                    ready.append(n)
        if ready:
            price = {n: (markets[n]['open'][idx[n]] if n in has_bar else markets[n]['close'][idx[n]]) for n in names}
            equity = cash + sum(units[n] * price[n] for n in names)
            changes = []
            for n in ready:
                weight, _ = pending.pop(n)
                current = units[n] * price[n] / equity
                if abs(weight - current) >= MIN_TRADE or (weight == 0 and units[n] != 0):
                    changes.append((weight - current, n, weight))
            for diff, n, weight in sorted(changes):  # sprzedaże przed kupnami
                cost = abs(diff) * equity * markets[n]['costs'][scenario]['side']
                units[n] = weight * equity / price[n]
                cash -= diff * equity + cost
                total_cost += cost
                trades += 1
                first_trade = first_trade or day
        closing = {n: markets[n]['close'][idx[n]] for n in names}
        if previous is not None:
            days = (date.fromisoformat(day) - date.fromisoformat(previous)).days
            financing = sum(units[n] * closing[n] * markets[n]['costs'][scenario]['fin'] * days / 365 for n in names)
            cash -= financing
            total_cost += financing
        equity = cash + sum(units[n] * closing[n] for n in names)
        if not math.isfinite(equity) or equity <= 0:
            raise SystemExit('Niepoprawna wartość portfela; obliczenie przerwane.')
        rows.append((day, equity))
        previous = day
        if k + 1 < len(calendar) and calendar[k + 1][:7] != day[:7]:
            history = {n: markets[n]['close'][:idx[n] + 1] for n in names}
            if all(len(h) >= WARMUP for h in history.values()):
                targets = decide(history)
                for n in names:
                    pending[n] = (targets.get(n, 0.0), delay)
    return {'rows': rows, 'total_cost': total_cost, 'trades': trades, 'first_trade': first_trade}


def segment(rows: list[tuple[str, float]], first: str | None = None, last: str | None = None) -> dict | None:
    selected = [(d, e) for d, e in rows if (first is None or d >= first) and (last is None or d <= last)]
    if len(selected) < 3:
        return None
    start = rows.index(selected[0])
    equity = [rows[start - 1][1] if start else 1.0] + [e for _, e in selected]
    returns = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity))]
    years = ((date.fromisoformat(selected[-1][0]) - date.fromisoformat(selected[0][0])).days + 1) / 365.25
    peak, drawdown = equity[0], 0.0
    for value in equity:
        peak = max(peak, value)
        drawdown = max(drawdown, (peak - value) / peak)
    deviation = statistics.stdev(returns)
    annual = (equity[-1] / equity[0]) ** (1 / years) - 1
    windows: dict[str, list[float]] = {}
    before = equity[0]
    for day, value in selected:
        windows.setdefault(f'{day[:4]}Q{(int(day[5:7]) - 1) // 3 + 1}', [before, before])[1] = value
        before = value
    window_returns = {k: v[1] / v[0] - 1 for k, v in windows.items()}
    positive = sum(1 for v in window_returns.values() if v > 0)
    return {'start': selected[0][0], 'end': selected[-1][0], 'net_return': equity[-1] / equity[0] - 1,
            'annualized_return': annual, 'max_drawdown': drawdown,
            'sharpe': statistics.fmean(returns) / deviation * math.sqrt(len(returns) / years) if deviation > 0 else None,
            'return_to_drawdown': annual / drawdown if drawdown > 0 else None,
            'windows': window_returns, 'positive_windows': positive, 'window_count': len(window_returns),
            'positive_share': positive / len(window_returns)}


def decide_trend(lookback: int, vol_window: int, always: bool = False):
    def decide(history: dict) -> dict:
        inverse = {}
        for n, closes in history.items():
            changes = [closes[i] / closes[i - 1] - 1 for i in range(len(closes) - vol_window, len(closes))]
            deviation = statistics.pstdev(changes)
            inverse[n] = 1 / deviation if deviation > 0 else 0.0
        total = sum(inverse.values())
        if total <= 0:
            return {}
        return {n: inverse[n] / total if always or history[n][-1] > history[n][-1 - lookback] else 0.0 for n in history}
    return decide


def decide_rotation(lookback: int, top: int):
    def decide(history: dict) -> dict:
        momentum = {n: closes[-1] / closes[-1 - lookback] - 1 for n, closes in history.items()}
        best = sorted(momentum, key=lambda n: (-momentum[n], n))[:top]
        return {n: 1 / top if n in best and momentum[n] > 0 else 0.0 for n in history}
    return decide


def decide_equal(history: dict) -> dict:
    return {n: 1 / len(history) for n in history}


def run_one(markets, calendar, decide, scenario, delay, label, params) -> dict:
    result = simulate(markets, calendar, decide, scenario, delay)
    return {'label': label, 'params': params, 'scenario': scenario, 'delay': delay, 'trades': result['trades'],
            'total_cost': result['total_cost'], 'first_trade': result['first_trade'],
            'in_sample': segment(result['rows'], result['first_trade'], '2024-12-31') if result['first_trade'] else None,
            'out_of_sample': segment(result['rows'], OOS_START)}


def evaluate(code: str, title: str, markets, calendar, maker, main, neighbours, benchmark) -> dict:
    variants = [run_one(markets, calendar, maker(*main), s, d, f'główny_{s}_opóźnienie{d}', list(main))
                for s in ('base', 'stress') for d in (0, 1)]
    near = [run_one(markets, calendar, maker(*p), 'base', 0, f'sąsiad_{p[0]}_{p[1]}', list(p)) for p in neighbours]
    bench = run_one(markets, calendar, benchmark, 'base', 0, 'punkt_odniesienia', [])
    s = variants[0]['out_of_sample']
    stress, b = variants[2]['out_of_sample'], bench['out_of_sample']
    if len(markets) < MIN_MARKETS or s is None or b is None or stress is None:
        return {'code': code, 'title': title, 'verdict': 'BRAK DANYCH', 'checks': [], 'variants': variants,
                'neighbours': near, 'benchmark': bench}
    good = sum(1 for n in near if n['out_of_sample'] and n['out_of_sample']['net_return'] > 0)
    checks = [
        ('1. Wynik po kosztach stresowych dodatni', stress['net_return'] > 0, f"{stress['net_return']:+.1%}"),
        (f'2. Sharpe po kosztach bazowych >= {MIN_SHARPE}', s['sharpe'] is not None and s['sharpe'] >= MIN_SHARPE,
         'brak' if s['sharpe'] is None else f"{s['sharpe']:.2f}"),
        ('3. Zysk do obsunięcia lepszy niż punkt odniesienia',
         None not in (s['return_to_drawdown'], b['return_to_drawdown']) and s['return_to_drawdown'] > b['return_to_drawdown'],
         f"{s['return_to_drawdown']} wobec {b['return_to_drawdown']}" if None in (s['return_to_drawdown'], b['return_to_drawdown'])
         else f"{s['return_to_drawdown']:.2f} wobec {b['return_to_drawdown']:.2f}"),
        (f'4. Największe obsunięcie <= {MAX_DD:.0%}', s['max_drawdown'] <= MAX_DD, f"{s['max_drawdown']:.1%}"),
        (f'5. Dodatnie kwartały >= {MIN_POSITIVE:.0%}', s['positive_share'] >= MIN_POSITIVE,
         f"{s['positive_windows']} z {s['window_count']}"),
        ('6. Wszyscy sąsiedzi dodatni', good == len(near), f'{good} z {len(near)}'),
    ]
    return {'code': code, 'title': title, 'verdict': 'PASS' if all(ok for _, ok, _ in checks) else 'FAIL',
            'checks': [{'criterion': c, 'passed': ok, 'value': v} for c, ok, v in checks],
            'variants': variants, 'neighbours': near, 'benchmark': bench}


def write_report(results: list[dict], markets: dict, dropped: dict, calendar: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    payload = {'generated_at': stamp, 'status': 'OFFLINE_UNQUALIFIED: obliczenie modelu, nie rekord RUN',
               'spec': 'research/daily-trend/SPEC_H2_H3.md', 'calendar': [calendar[0], calendar[-1]], 'dropped': dropped,
               'markets': {n: {'symbol': m.get('symbol'), 'sha256': m.get('sha256'), 'bars': len(m['dates']),
                               'first': m['dates'][0], 'last': m['dates'][-1], 'costs': m['costs']} for n, m in markets.items()},
               'results': results}
    (OUT_DIR / 'wynik_h2_h3.json').write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
    lines = ['# H2 i H3 — wynik badania offline na świecach dziennych z MT5', '',
             f'Wygenerowano: {stamp}. To obliczenie modelu, nie rekord RUN i nie zgoda na handel.',
             'Reguły i kryteria zapisano przed zobaczeniem danych: `research/daily-trend/SPEC_H2_H3.md`.', '',
             f'Kalendarz: {calendar[0]} do {calendar[-1]}. Próba poza strojeniem od {OOS_START}.', '',
             '| Rynek | Symbol | Świece | Od | Do | Spread | Finansowanie bazowe |', '|---|---|---|---|---|---|---|']
    lines += [f"| {n} | {m.get('symbol')} | {len(m['dates'])} | {m['dates'][0]} | {m['dates'][-1]} | "
              f"{m['costs']['spread_rel']:.3%} | {m['costs']['base']['fin']:.1%} ({m['costs']['fin_source']}) |"
              for n, m in markets.items()]
    lines += [f'- Poza koszykiem: {n} ({why}).' for n, why in dropped.items()]
    for r in results:
        lines += ['', f"## {r['code']}: {r['title']} — werdykt {r['verdict']}", '']
        if r['checks']:
            lines += ['| Kryterium | Wynik | Zaliczone |', '|---|---|---|']
            lines += [f"| {c['criterion']} | {c['value']} | {'tak' if c['passed'] else 'NIE'} |" for c in r['checks']]
        lines += ['', '| Wariant | Wynik poza strojeniem | Obsunięcie | Sharpe | Wynik w okresie strojenia |', '|---|---|---|---|---|']
        for v in r['variants'] + [r['benchmark']] + r['neighbours']:
            o, i = v['out_of_sample'], v['in_sample']
            sharpe = 'brak' if not o or o['sharpe'] is None else f"{o['sharpe']:.2f}"
            lines.append(f"| {v['label']} | {'brak' if not o else format(o['net_return'], '+.1%')} | "
                         f"{'brak' if not o else format(o['max_drawdown'], '.1%')} | {sharpe} | "
                         f"{'brak' if not i else format(i['net_return'], '+.1%')} |")
    (OUT_DIR / 'WYNIK_H2_H3.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def selftest() -> int:
    """Księgowość na danych sztucznych: jeden rynek rośnie, drugi spada, koszty zerowe."""
    days = [date.fromordinal(date(2020, 1, 1).toordinal() + i).isoformat() for i in range(900)]
    zero = {'spread_rel': 0.0, 'fin_source': 'test', 'base': {'side': 0.0, 'fin': 0.0}, 'stress': {'side': 0.0, 'fin': 0.0}}
    up = [100 * 1.001 ** i * (1 + 0.002 * (-1) ** i) for i in range(900)]
    down = [100 * 0.999 ** i * (1 + 0.002 * (-1) ** i) for i in range(900)]
    markets = {'UP': make_market('UP', days, [v * 0.999 for v in up], up, zero),
               'DOWN': make_market('DOWN', days, [v * 0.999 for v in down], down, zero)}
    calendar = build_calendar(markets)
    rotation = simulate(markets, calendar, decide_rotation(126, 1), 'base', 0)
    start = rotation['first_trade']
    j = markets['UP']['pos'][start]
    expected = markets['UP']['close'][-1] / markets['UP']['open'][j]
    got = rotation['rows'][-1][1]
    assert abs(got / expected - 1) < 1e-9, (got, expected)
    assert rotation['trades'] == 1, rotation['trades']
    trend = simulate(markets, calendar, decide_trend(252, 60), 'base', 0)
    held = simulate(markets, calendar, decide_trend(252, 60, always=True), 'base', 0)
    assert trend['rows'][-1][1] > 1.0, 'portfel trendowy na rosnącym rynku powinien zyskać'
    assert trend['rows'][-1][1] > held['rows'][-1][1], 'filtr trendu powinien pominąć rynek spadający'
    costly = {**zero, 'base': {'side': 0.001, 'fin': 0.05}}
    paid = simulate({'UP': {**markets['UP'], 'costs': costly}, 'DOWN': {**markets['DOWN'], 'costs': costly}},
                    calendar, decide_rotation(126, 1), 'base', 0)
    assert paid['rows'][-1][1] < got and paid['total_cost'] > 0
    stats = segment(rotation['rows'], '2021-06-01')
    assert stats and stats['net_return'] > 0 and 0 <= stats['max_drawdown'] < 0.05
    print('SELFTEST OK: księgowość, filtr trendu, koszty i statystyki działają na danych sztucznych.')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--selftest', action='store_true')
    if parser.parse_args().selftest:
        return selftest()
    markets, dropped = load_markets()
    if len(markets) < 2:
        print(f'BRAK DANYCH: w {DATA_DIR} jest {len(markets)} rynków koszyka. Poza koszykiem: {dropped}')
        return 2
    calendar = build_calendar(markets)
    trend_near = [(l, v) for l in (202, 252, 302) for v in (48, 60, 72) if (l, v) != (252, 60)]
    rotation_near = [(l, n) for l in (101, 126, 151) for n in (2, 3, 4) if (l, n) != (126, 3)]
    results = [
        evaluate('H2', 'podążanie za trendem', markets, calendar, decide_trend, (252, 60), trend_near,
                 decide_trend(252, 60, always=True)),
        evaluate('H3', 'rotacja momentum', markets, calendar, decide_rotation, (126, 3), rotation_near, decide_equal),
    ]
    write_report(results, markets, dropped, calendar)
    for r in results:
        print(f"{r['code']} ({r['title']}): {r['verdict']}")
        for c in r['checks']:
            print(f"  {'OK ' if c['passed'] else 'NIE'} {c['criterion']}: {c['value']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
