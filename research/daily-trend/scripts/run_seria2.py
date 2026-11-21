"""Silnik serii 2 (H4, H5): widok rachunku w lotach.

Reguły, koszty i kryteria: `research/daily-trend/SPEC_SERIA2.md`. Do akceptacji reguł przez Karola
silnik działa wyłącznie na danych sztucznych w testach (`tests/unit/test_seria2_engine.py`).
Tylko obliczenia: brak połączenia z brokerem, brak zleceń, brak odczytu plików z danymi rynkowymi.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'src'))  # uruchomienie skryptu bez instalacji pakietu
sys.path.insert(0, str(Path(__file__).resolve().parent))

from astraljet.lab.position_sizing import SizingLimits, size_positions
from astraljet.workspace.instruments import InstrumentSpec

import seria2_koszyk as koszyk
import uniwersum_dane as ud
from run_h2_h3 import MAX_DD, MIN_POSITIVE, MIN_SHARPE, OOS_START, segment  # statystyki i progi jak w serii 1

SPEC_FILE = Path(__file__).resolve().parents[1] / 'SPEC_SERIA2.md'
SPREAD_REPORT = Path(__file__).resolve().parents[2] / 'daily-data' / 'reports' / 'SPREAD_TICKI_SERIA2.md'
ETF_COMMISSION_SIDE = 6.0   # USD za stronę transakcji na CFD na ETF-ie (SPEC_SERIA2.md, punkt 5)
UNKNOWN_FINANCING = 0.07    # gdy stawki swapu nie da się policzyć
EQUITY_PAYOUT = (0.03, 0.05)  # dopłata pozycji krótkiej rocznie: bazowa i stresowa
BOND_PAYOUT = (0.05, 0.07)
BOND_ETFS = frozenset({'TLT'})
EQUITY_SYMBOLS = frozenset(
    symbol for group in ('Akcje USA', 'Akcje poza USA') for _, symbols in koszyk.PRIORITY[group] for symbol in symbols
) | {'GDX', 'XOP'}

IN_SAMPLE_END = '2024-12-31'
MAIN = (252, 60)       # L: świece do porównania ceny, V: świece do zmienności
NEIGHBOURS = [(lookback, window) for lookback in (202, 252, 302) for window in (48, 60, 72)
              if (lookback, window) != MAIN]
CRITERIA = (
    '1. Wynik po kosztach stresowych dodatni',
    f'2. Sharpe po kosztach bazowych >= {MIN_SHARPE}',
    '3. Zysk do obsunięcia lepszy niż punkt odniesienia',
    f'4. Największe obsunięcie <= {MAX_DD:.0%}',
    f'5. Dodatnie kwartały >= {MIN_POSITIVE:.0%}',
    '6. Wszyscy sąsiedzi dodatni',
)
MAX_GAP_DAYS = 10      # dłuższa przerwa w świecach zaczyna ciągłą historię od nowa
MIN_HISTORY = 320      # tyle świec ciągłej historii, żeby rynek brał udział w decyzji
MIN_MARKETS = 6        # tylu uczestników, żeby zapadła decyzja
MARKET_CAP = 0.5       # limit jednego rynku jako część kapitału
STRESS_COMMISSION = 1.5
SIGNALS = {
    'H4': lambda now, then: (now > then) - (now < then),
    'H5': lambda now, then: 1 if now > then else 0,
    'BENCH': lambda now, then: 1,
}


@dataclass(frozen=True)
class Costs:
    """Koszty jednego rynku: spread jako część ceny, prowizja w USD za stronę transakcji, stawki roczne."""

    spread: float = 0.0
    commission_side: float = 0.0
    fin_long: float = 0.0
    fin_short: float = 0.0
    payout_short: float = 0.0
    payout_short_stress: float = 0.0


@dataclass(frozen=True)
class Market:
    name: str
    dates: list[str]
    opens: list[float]
    closes: list[float]
    spec: InstrumentSpec
    costs: Costs


@dataclass(frozen=True)
class Trade:
    date: str
    market: str
    change: float
    volume_after: float
    price: float
    spread_cost: float
    commission: float


@dataclass
class Result:
    rows: list[tuple[str, float]] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    skipped: list[tuple[str, str, str]] = field(default_factory=list)
    costs: dict[str, float] = field(default_factory=lambda: {'spread': 0.0, 'commission': 0.0, 'financing': 0.0})
    ruined: str | None = None  # dzień, w którym kapitał spadł do zera; po nim nie ma już wierszy ani transakcji


def _gap(dates: list[str], index: int) -> int:
    return (date.fromisoformat(dates[index]) - date.fromisoformat(dates[index - 1])).days


def continuous_bars(dates: list[str], index: int) -> int:
    """Liczba świec do `index` włącznie od ostatniej przerwy dłuższej niż MAX_GAP_DAYS."""
    count = 1
    while index > 0 and _gap(dates, index) <= MAX_GAP_DAYS:
        count += 1
        index -= 1
    return count


def side_rate(costs: Costs, scenario: str) -> float:
    """Koszt jednej strony transakcji jako część jej wartości, bez prowizji."""
    return costs.spread + 0.0002 if scenario == 'stress' else costs.spread / 2 + 0.0001


def financing_rate(costs: Costs, scenario: str, sign: int) -> float:
    """Roczny koszt trzymania pozycji: długiej (sign > 0) albo krótkiej razem z dopłatą za wypłaty."""
    base = costs.fin_long if sign > 0 else costs.fin_short
    payout = 0.0 if sign > 0 else (costs.payout_short_stress if scenario == 'stress' else costs.payout_short)
    return (base * 1.5 + 0.01 if scenario == 'stress' else base) + payout


def decide_targets(histories: dict[str, list[float]], *, hypothesis: str, gross: float, lookback: int,
                   vol_window: int) -> dict[str, float]:
    """Wagi docelowe ze znakiem: sygnał × waga odwrotna do zmienności × ekspozycja, z limitem jednego rynku."""
    signal = SIGNALS[hypothesis]
    inverse = {}
    for name, closes in histories.items():
        changes = [closes[i] / closes[i - 1] - 1 for i in range(len(closes) - vol_window, len(closes))]
        deviation = statistics.pstdev(changes)
        inverse[name] = 1 / deviation if deviation > 0 else 0.0
    total = sum(inverse.values())
    if total <= 0:
        return {name: 0.0 for name in histories}
    targets = {}
    for name, closes in histories.items():
        weight = signal(closes[-1], closes[-1 - lookback]) * inverse[name] / total * gross
        targets[name] = max(-MARKET_CAP, min(MARKET_CAP, weight))
    return targets


def simulate_account(markets: dict[str, Market], *, hypothesis: str, capital: float = 2500.0, gross: float = 1.0,
                     lookback: int = 252, vol_window: int = 60, scenario: str = 'base', delay: int = 0) -> Result:
    """Rachunek w USD: decyzja na koniec miesiąca, wykonanie na otwarciu następnej świecy rynku, wolumeny w lotach."""
    if gross > 1:
        raise ValueError('Łączna ekspozycja powyżej 1 oznacza handel z użyciem dźwigni; '
                         'funkcja wielkości pozycji jej nie dopuszcza.')
    for market in markets.values():
        if market.spec.profit_currency != 'USD':
            raise ValueError(f'{market.name}: rynek notowany poza USD ({market.spec.profit_currency}); '
                             'silnik liczy na razie tylko rynki w USD.')
    names = list(markets)
    position = {n: {d: i for i, d in enumerate(markets[n].dates)} for n in names}
    last_common = min(m.dates[-1] for m in markets.values())
    calendar = sorted({d for m in markets.values() for d in m.dates if d <= last_common})
    specs = {n: markets[n].spec for n in names}
    contract = {n: float(markets[n].spec.contract_size) for n in names}
    limits = SizingLimits(max_gross=Decimal(str(gross)), max_per_market=Decimal(str(MARKET_CAP)))
    commission_factor = STRESS_COMMISSION if scenario == 'stress' else 1.0

    index = {n: -1 for n in names}
    volume = {n: 0.0 for n in names}
    targets: dict[str, float] = {}
    pending: dict[str, int] = {}
    cash = capital
    result = Result()
    previous = None
    for k, day in enumerate(calendar):
        has_bar = set()
        for n in names:
            i = position[n].get(day)
            if i is not None:
                index[n] = i
                has_bar.add(n)
        ready = []
        for n in list(pending):
            if n in has_bar:
                if pending[n] > 0:
                    pending[n] -= 1
                else:
                    ready.append(n)
                    del pending[n]
        if ready:
            price = {n: (markets[n].opens[index[n]] if n in has_bar else markets[n].closes[index[n]])
                     for n in names if index[n] >= 0}
            equity = cash + sum(volume[n] * contract[n] * price[n] for n in price)
            if equity <= 0:
                result.rows.append((day, 0.0))
                result.ruined = day
                break
            sized = size_positions(targets, capital=equity, prices=price, specs=specs, limits=limits)
            changes = []
            for n in ready:
                wanted = sized.get(n)
                new_volume = float(wanted.volume) if wanted is not None else 0.0
                if wanted is not None and wanted.skipped:
                    result.skipped.append((day, n, wanted.reasons[-1]))
                if abs(new_volume - volume[n]) > 1e-12:
                    changes.append((new_volume - volume[n], n, new_volume))
            for change, n, new_volume in sorted(changes):  # sprzedaże przed kupnami
                unit = contract[n] * price[n]
                spread_cost = abs(change) * unit * side_rate(markets[n].costs, scenario)
                commission = markets[n].costs.commission_side * commission_factor
                cash -= change * unit + spread_cost + commission
                volume[n] = new_volume
                result.costs['spread'] += spread_cost
                result.costs['commission'] += commission
                result.trades.append(Trade(day, n, change, new_volume, price[n], spread_cost, commission))
        closing = {n: markets[n].closes[index[n]] for n in names if index[n] >= 0}
        if previous is not None:
            held_days = (date.fromisoformat(day) - date.fromisoformat(previous)).days
            financing = sum(abs(volume[n]) * contract[n] * closing[n]
                            * financing_rate(markets[n].costs, scenario, 1 if volume[n] > 0 else -1)
                            for n in closing if volume[n]) * held_days / 365
            cash -= financing
            result.costs['financing'] += financing
        equity = cash + sum(volume[n] * contract[n] * closing[n] for n in closing)
        if equity <= 0:
            result.rows.append((day, 0.0))
            result.ruined = day
            break
        result.rows.append((day, equity))
        previous = day
        if k + 1 < len(calendar) and calendar[k + 1][:7] != day[:7]:
            histories = {}
            for n in names:
                if index[n] >= 0:
                    bars = continuous_bars(markets[n].dates, index[n])
                    if bars >= MIN_HISTORY:
                        histories[n] = markets[n].closes[index[n] + 1 - bars:index[n] + 1]
            if len(histories) >= MIN_MARKETS:
                decided = decide_targets(histories, hypothesis=hypothesis, gross=gross, lookback=lookback,
                                         vol_window=vol_window)
                targets = {n: decided.get(n, 0.0) for n in names if index[n] >= 0}
                for n in targets:
                    pending[n] = delay
    return result


def short_payout(symbol: str) -> tuple[float, float]:
    """Szacowana dopłata pozycji krótkiej za wypłaty funduszu albo indeksu: (bazowa, stresowa)."""
    if symbol in BOND_ETFS:
        return BOND_PAYOUT
    if symbol in EQUITY_SYMBOLS and symbol not in koszyk.FUTURES_BASED:
        return EQUITY_PAYOUT
    return 0.0, 0.0


def market_from_files(folder: Path, symbol: str, *, spread: float | None = None,
                      fx: dict[str, float] | None = None) -> Market:
    """Rynek z plików `<SYMBOL>_D1.csv` i `.meta.json`. `spread` z pomiaru na tickach zastępuje pojedynczy odczyt."""
    meta = json.loads((folder / f'{symbol}_D1.meta.json').read_text(encoding='utf-8'))
    with (folder / f'{symbol}_D1.csv').open(encoding='utf-8', newline='') as handle:
        rows = list(csv.DictReader(handle))
    closes = [float(r['close']) for r in rows]
    read_spreads = [float(r['spread']) for r in rows if r.get('spread') not in (None, '')]
    long_cost, short_cost, _ = ud.holding_cost(meta, closes[-1], fx or {'USD': 1.0})
    payout, payout_stress = short_payout(symbol)
    if spread is None:
        spread = ud.spread_rel(meta, closes[-1], read_spreads) or 0.001
    spec = InstrumentSpec(symbol=symbol, digits=int(meta['digits']), contract_size=Decimal(str(meta['trade_contract_size'])),
                          profit_currency=meta['currency_profit'], volume_min=Decimal(str(meta['volume_min'])),
                          volume_max=Decimal(str(meta['volume_max'])), volume_step=Decimal(str(meta['volume_step'])))
    costs = Costs(
        spread=spread,
        commission_side=ETF_COMMISSION_SIDE if str(meta.get('path', '')).startswith('ETF\\') else 0.0,
        fin_long=UNKNOWN_FINANCING if long_cost is None else max(0.0, long_cost),
        fin_short=UNKNOWN_FINANCING if short_cost is None else max(0.0, short_cost),
        payout_short=payout, payout_short_stress=payout_stress)
    return Market(name=symbol, dates=[r['date'] for r in rows], opens=[float(r['open']) for r in rows],
                  closes=closes, spec=spec, costs=costs)


def load_spreads(report: Path) -> dict[str, float]:
    """Mediana spreadu jako część ceny z raportu pomiaru na tickach; dla ETF-ów z USA z godzin sesji."""
    spreads = {}
    for line in report.read_text(encoding='utf-8').splitlines():
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(cells) < 9 or not (cells[0].startswith('`') and cells[0].endswith('`')):
            continue
        median = cells[6] if len(cells) >= 15 else cells[5]  # tabela z podziałem na sesję ma 15 kolumn
        spreads[cells[0].strip('`')] = float(median) / 100
    return spreads


def acceptance_block(spec_text: str) -> str | None:
    """Powód odmowy uruchomienia na danych rynkowych albo None, gdy reguły są zaakceptowane."""
    if 'Status: PROJEKT' in spec_text:
        return ('Reguły serii 2 mają status PROJEKT i czekają na akceptację Karola. '
                'Do tego czasu silnik nie liczy niczego na danych rynkowych.')
    return None


def choose_basket(data: dict, fx: dict, capital: float, gross: float) -> list[dict]:
    """Koszyk według punktów 2 i 3 specyfikacji, tą samą funkcją co raport doboru koszyka."""
    known = {s: koszyk.facts(s, data[s], fx) for s in koszyk.ALL_SYMBOLS if s in data}
    admitted = {s: f for s, f in known.items() if not koszyk.refusals(f, capital, gross)}
    return koszyk.select_basket(admitted)


def write_report(results: list[dict], markets: dict[str, Market], basket: list[dict], out_dir: Path, *,
                 capital: float, gross: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    name = f'{capital:.0f}'
    payload = {'generated_at': stamp, 'status': 'OFFLINE_UNQUALIFIED: obliczenie modelu, nie rekord RUN',
               'spec': 'research/daily-trend/SPEC_SERIA2.md', 'capital': capital, 'gross': gross,
               'basket': [b['symbol'] for b in basket],
               'costs': {n: asdict(m.costs) for n, m in markets.items()}, 'results': results}
    (out_dir / f'wynik_seria2_{name}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                                       encoding='utf-8')
    amount = f'{capital:,.0f}'.replace(',', ' ')
    lines = [f'# Seria 2 (H4, H5): wynik na danych dziennych, kapitał {amount} USD', '',
             f'Wygenerowano: {stamp}. To obliczenie modelu, nie rekord RUN i nie zgoda na handel.',
             'Reguły i kryteria: `research/daily-trend/SPEC_SERIA2.md`. Kryteria liczone na widoku rachunku w lotach, '
             f'poza strojeniem (od {OOS_START}). Łączna ekspozycja G = {gross:g}.', '',
             '| Klasa | Rynek | Symbol | Spread | Prowizja za stronę | Długa rocznie | Krótka rocznie (z dopłatą) |',
             '|---|---|---|---:|---:|---:|---:|']
    for b in basket:
        costs = markets[b['symbol']].costs if b['symbol'] in markets else None
        if costs:
            lines.append(f"| {b['class']} | {b['market']} | `{b['symbol']}` | {costs.spread:.3%} | "
                         f"{costs.commission_side:.2f} USD | {costs.fin_long:.1%} | "
                         f"{costs.fin_short + costs.payout_short:.1%} |")
    if not koszyk.basket_valid(basket):
        lines += ['', f'Koszyk nieważny: {len(basket)} rynków. Wymagane co najmniej {koszyk.MIN_MARKETS} rynków '
                      f'z {koszyk.MIN_CLASSES} klas.']
    for r in results:
        lines += ['', f"## {r['hypothesis']}: werdykt {r['verdict']}", '']
        if r['checks']:
            lines += ['| Kryterium | Wynik | Zaliczone |', '|---|---|---|']
            lines += [f"| {c['criterion']} | {c['value']} | {'tak' if c['passed'] else 'NIE'} |" for c in r['checks']]
        rows = r['variants'] + ([r['benchmark']] if r['benchmark'] else []) + r['neighbours']
        if rows:
            lines += ['', '| Wariant | Wynik poza strojeniem | Obsunięcie | Sharpe | Transakcje | Koszt spreadu | '
                          'prowizja | finansowanie | Pominięte przez lot | Wynik w okresie strojenia |',
                      '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for v in rows:
            o, i = v['out_of_sample'], v['in_sample']
            sharpe = 'brak' if not o or o['sharpe'] is None else f"{o['sharpe']:.2f}"
            lines.append(
                f"| {v['label']} | {'brak' if not o else format(o['net_return'], '+.1%')} | "
                f"{'brak' if not o else format(o['max_drawdown'], '.1%')} | {sharpe} | {v['trades']} | "
                f"{v['costs']['spread']:.2f} USD | {v['costs']['commission']:.2f} USD | "
                f"{v['costs']['financing']:.2f} USD | {v['skipped']} | "
                f"{'brak' if not i else format(i['net_return'], '+.1%')} |")
    (out_dir / f'WYNIK_SERIA2_{name}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Seria 2 (H4, H5) na danych dziennych koszyka.')
    parser.add_argument('--spec', type=Path, default=SPEC_FILE)
    parser.add_argument('--dane', type=Path, default=ud.DATA_DIR)
    parser.add_argument('--kursy', type=Path, default=ud.SYMBOLS, help='Plik z kursami walut do USD (fx_to_usd).')
    parser.add_argument('--spready', type=Path, default=SPREAD_REPORT, help='Raport pomiaru spreadu na tickach.')
    parser.add_argument('--wyniki', type=Path, default=ud.OUT_DIR)
    parser.add_argument('--kapital', type=float, default=2500.0)
    parser.add_argument('--ekspozycja', type=float, default=None,
                        help='G: największa łączna ekspozycja jako krotność kapitału. Decyzja Karola, bez wartości domyślnej.')
    args = parser.parse_args(argv)
    blocked = acceptance_block(args.spec.read_text(encoding='utf-8'))
    if blocked:
        print(blocked)
        return 2
    if args.ekspozycja is None or args.ekspozycja <= 0 or args.kapital <= 0:
        print('Podaj --ekspozycja (wartość G wybraną przez Karola) i dodatni --kapital.')
        return 2
    data = ud.load(args.dane) if args.dane.is_dir() else {}
    if not data or not args.kursy.exists():
        print(f'BRAK DANYCH: nie ma plików D1 w {args.dane} albo pliku kursów {args.kursy.name}.')
        return 2
    fx = json.loads(args.kursy.read_text(encoding='utf-8'))['fx_to_usd']
    spreads = load_spreads(args.spready) if args.spready.exists() else {}
    basket = choose_basket(data, fx, args.kapital, args.ekspozycja)
    markets = {b['symbol']: market_from_files(args.dane, b['symbol'], spread=spreads.get(b['symbol']), fx=fx)
               for b in basket}
    if koszyk.basket_valid(basket):
        results = [evaluate(markets, hypothesis=code, capital=args.kapital, gross=args.ekspozycja)
                   for code in ('H4', 'H5')]
    else:
        results = [{'hypothesis': code, 'capital': args.kapital, 'gross': args.ekspozycja, 'verdict': 'BRAK DANYCH',
                    'checks': [], 'variants': [], 'neighbours': [], 'benchmark': None} for code in ('H4', 'H5')]
    write_report(results, markets, basket, args.wyniki, capital=args.kapital, gross=args.ekspozycja)
    for r in results:
        print(f"{r['hypothesis']}: {r['verdict']}")
        for c in r['checks']:
            print(f"  {'OK ' if c['passed'] else 'NIE'} {c['criterion']}: {c['value']}")
    return 0


def run_variant(markets: dict[str, Market], *, hypothesis: str, capital: float, gross: float, lookback: int,
                vol_window: int, scenario: str, delay: int, label: str) -> dict:
    result = simulate_account(markets, hypothesis=hypothesis, capital=capital, gross=gross, lookback=lookback,
                              vol_window=vol_window, scenario=scenario, delay=delay)
    first = result.trades[0].date if result.trades else None
    return {'label': label, 'params': [lookback, vol_window], 'scenario': scenario, 'delay': delay,
            'trades': len(result.trades), 'skipped': len(result.skipped), 'costs': dict(result.costs),
            'first_trade': first, 'ruined': result.ruined,
            'in_sample': segment(result.rows, first, IN_SAMPLE_END) if first else None,
            'out_of_sample': segment(result.rows, OOS_START)}


def evaluate(markets: dict[str, Market], *, hypothesis: str, capital: float = 2500.0, gross: float = 1.0) -> dict:
    """Dwanaście wariantów i sześć kryteriów protokołu w wersji 1, liczonych na widoku rachunku poza strojeniem."""
    def run(code, lookback, vol_window, scenario, delay, label):
        return run_variant(markets, hypothesis=code, capital=capital, gross=gross, lookback=lookback,
                           vol_window=vol_window, scenario=scenario, delay=delay, label=label)

    variants = [run(hypothesis, *MAIN, scenario, delay, f'główny_{scenario}_opóźnienie{delay}')
                for scenario in ('base', 'stress') for delay in (0, 1)]
    neighbours = [run(hypothesis, lookback, window, 'base', 0, f'sąsiad_{lookback}_{window}')
                  for lookback, window in NEIGHBOURS]
    benchmark = run('BENCH', *MAIN, 'base', 0, 'punkt_odniesienia')
    outcome = {'hypothesis': hypothesis, 'capital': capital, 'gross': gross, 'checks': [], 'variants': variants,
               'neighbours': neighbours, 'benchmark': benchmark}
    wiped = [v for v in (variants[0], variants[2]) if v['ruined']]
    if wiped:
        why = f"rachunek wyzerowany {wiped[0]['ruined']} ({wiped[0]['label']})"
        return {**outcome, 'verdict': 'FAIL',
                'checks': [{'criterion': name, 'passed': False, 'value': why} for name in CRITERIA]}
    main, stress, bench = variants[0]['out_of_sample'], variants[2]['out_of_sample'], benchmark['out_of_sample']
    if len(markets) < MIN_MARKETS or not variants[0]['first_trade'] or None in (main, stress, bench):
        return {**outcome, 'verdict': 'BRAK DANYCH'}
    good = sum(1 for n in neighbours if n['out_of_sample'] and n['out_of_sample']['net_return'] > 0)
    ratio, bench_ratio = main['return_to_drawdown'], bench['return_to_drawdown']
    values = [
        (stress['net_return'] > 0, f"{stress['net_return']:+.1%}"),
        (main['sharpe'] is not None and main['sharpe'] >= MIN_SHARPE,
         'brak' if main['sharpe'] is None else f"{main['sharpe']:.2f}"),
        (None not in (ratio, bench_ratio) and ratio > bench_ratio,
         f'{ratio} wobec {bench_ratio}' if None in (ratio, bench_ratio) else f'{ratio:.2f} wobec {bench_ratio:.2f}'),
        (main['max_drawdown'] <= MAX_DD, f"{main['max_drawdown']:.1%}"),
        (main['positive_share'] >= MIN_POSITIVE, f"{main['positive_windows']} z {main['window_count']}"),
        (good == len(neighbours), f'{good} z {len(neighbours)}'),
    ]
    checks = [{'criterion': name, 'passed': bool(ok), 'value': value} for name, (ok, value) in zip(CRITERIA, values)]
    return {**outcome, 'checks': checks, 'verdict': 'PASS' if all(c['passed'] for c in checks) else 'FAIL'}


if __name__ == "__main__":
    raise SystemExit(main())
