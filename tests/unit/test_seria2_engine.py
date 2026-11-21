"""Silnik serii 2 (H4, H5) na danych sztucznych: księgowość rachunku w lotach, udział rynków, koszty.

Reguły: research/daily-trend/SPEC_SERIA2.md. Testy nie czytają danych rynkowych.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from astraljet.workspace.instruments import InstrumentSpec

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'research' / 'daily-trend' / 'scripts'))

import run_seria2 as s2  # noqa: E402

D = Decimal
START = date(2022, 1, 1)
DAYS = 900


def days(count: int = DAYS, first: date = START) -> list[str]:
    return [(first + timedelta(days=i)).isoformat() for i in range(count)]


def series(drift: float, count: int = DAYS) -> list[float]:
    """Cena ze stałym dryfem i drobnym szumem, żeby zmienność była dodatnia."""
    return [100 * drift ** i * (1 + 0.002 * (-1) ** i) for i in range(count)]


def spec(symbol: str, *, vmin: str = '0.01', step: str = '0.01') -> InstrumentSpec:
    return InstrumentSpec(symbol=symbol, digits=2, contract_size=D('1'), profit_currency='USD',
                          volume_min=D(vmin), volume_max=D('100000'), volume_step=D(step))


def noisy(drift: float, count: int, seed: str) -> list[float]:
    """Cena z dryfem i losowym szumem dziennym 0,5% (stałe ziarno), żeby portfel miał obsunięcia."""
    generator = random.Random(seed)
    closes, price = [], 100.0
    for _ in range(count):
        price *= drift * (1 + generator.gauss(0, 0.005))
        closes.append(price)
    return closes


def market(name: str, drift: float, *, costs: s2.Costs | None = None, dates: list[str] | None = None,
           vmin: str = '0.01', closes: list[float] | None = None) -> s2.Market:
    dates = dates or days()
    closes = closes or series(drift, len(dates))
    return s2.Market(name=name, dates=dates, opens=[c * 0.999 for c in closes], closes=closes,
                     spec=spec(name, vmin=vmin, step=vmin), costs=costs or s2.Costs())


def basket(**overrides) -> dict[str, s2.Market]:
    made = {name: market(name, 1.001) for name in ('UP1', 'UP2', 'UP3')}
    made.update({name: market(name, 0.999) for name in ('DN1', 'DN2', 'DN3')})
    made.update(overrides)
    return made


class Signals(unittest.TestCase):
    def test_h5_holds_rising_markets_and_never_falling(self):
        result = s2.simulate_account(basket(), hypothesis='H5')
        self.assertTrue(result.trades)
        self.assertEqual({t.market for t in result.trades} & {'DN1', 'DN2', 'DN3'}, set())
        self.assertGreater(result.rows[-1][1], 2500.0)

    def test_h4_shorts_falling_markets(self):
        both = s2.simulate_account(basket(), hypothesis='H4')
        long_only = s2.simulate_account(basket(), hypothesis='H5')
        shorts = [t for t in both.trades if t.market.startswith('DN') and t.volume_after < 0]
        self.assertTrue(shorts)
        self.assertGreater(both.rows[-1][1], long_only.rows[-1][1])

    def test_benchmark_holds_every_market_long(self):
        result = s2.simulate_account(basket(), hypothesis='BENCH')
        self.assertEqual({t.market for t in result.trades}, set(basket()))
        self.assertTrue(all(t.volume_after >= 0 for t in result.trades))


class Participation(unittest.TestCase):
    def test_first_decision_waits_for_six_participating_markets(self):
        five = basket()
        del five['DN3']
        result = s2.simulate_account(five, hypothesis='H5')
        self.assertEqual(result.trades, [])
        self.assertEqual({round(equity, 6) for _, equity in result.rows}, {2500.0})

    def test_market_joins_only_after_320_continuous_bars(self):
        late_dates = days(DAYS - 400, START + timedelta(days=400))
        result = s2.simulate_account(basket(LATE=market('LATE', 1.001, dates=late_dates)), hypothesis='H5')
        first = min(t.date for t in result.trades if t.market == 'LATE')
        self.assertGreater(first, late_dates[319])

    def test_continuous_bars_restart_after_gap_longer_than_ten_days(self):
        dates = days(100) + days(50, START + timedelta(days=115))
        self.assertEqual(s2.continuous_bars(dates, 99), 100)
        self.assertEqual(s2.continuous_bars(dates, 100), 1)
        self.assertEqual(s2.continuous_bars(dates, 149), 50)

    def test_gap_of_ten_days_does_not_restart_history(self):
        dates = days(100) + days(50, START + timedelta(days=109))
        self.assertEqual(s2.continuous_bars(dates, 149), 150)


class Sizing(unittest.TestCase):
    def test_position_below_min_lot_is_skipped_and_reported(self):
        result = s2.simulate_account(basket(UP1=market('UP1', 1.001, vmin='100')), hypothesis='H5')
        self.assertNotIn('UP1', {t.market for t in result.trades})
        self.assertIn('UP1', {name for _, name, _ in result.skipped})

    def test_volumes_are_multiples_of_lot_step(self):
        result = s2.simulate_account(basket(UP2=market('UP2', 1.001, vmin='0.5')), hypothesis='H5')
        volumes = [t.volume_after for t in result.trades if t.market == 'UP2']
        self.assertTrue(volumes)
        self.assertTrue(all(abs(v / 0.5 - round(v / 0.5)) < 1e-9 for v in volumes))

    def test_gross_exposure_above_one_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            s2.simulate_account(basket(), hypothesis='H5', gross=1.5)
        self.assertIn('dźwigni', str(caught.exception))

    def test_market_quoted_outside_usd_is_refused(self):
        yen = market('UP3', 1.001)
        yen = s2.Market(name='UP3', dates=yen.dates, opens=yen.opens, closes=yen.closes, costs=yen.costs,
                        spec=InstrumentSpec(symbol='UP3', digits=2, contract_size=D('1'), profit_currency='JPY',
                                            volume_min=D('0.01'), volume_max=D('1000'), volume_step=D('0.01')))
        with self.assertRaises(ValueError) as caught:
            s2.simulate_account(basket(UP3=yen), hypothesis='H5')
        self.assertIn('USD', str(caught.exception))

    def test_target_weight_is_capped_at_half_of_capital(self):
        calm = [100 + 0.0001 * (-1) ** i for i in range(400)]
        histories = {name: series(1.001, 400) for name in ('A', 'B', 'C', 'D', 'E')}
        histories['CALM'] = [c * 1.0001 ** i for i, c in enumerate(calm)]
        targets = s2.decide_targets(histories, hypothesis='H5', gross=1.0, lookback=252, vol_window=60)
        self.assertAlmostEqual(targets['CALM'], 0.5)
        self.assertLessEqual(sum(abs(w) for w in targets.values()), 1.0 + 1e-9)


class CostsCharged(unittest.TestCase):
    def test_commission_is_charged_per_trade_side_only_where_set(self):
        paid = basket(UP1=market('UP1', 1.001, costs=s2.Costs(commission_side=6.0)))
        result = s2.simulate_account(paid, hypothesis='H5')
        on_up1 = [t for t in result.trades if t.market == 'UP1']
        self.assertTrue(on_up1)
        self.assertAlmostEqual(result.costs['commission'], 6.0 * len(on_up1))
        self.assertTrue(all(t.commission == 0 for t in result.trades if t.market != 'UP1'))

    def test_stress_scenario_charges_one_and_a_half_commission(self):
        paid = basket(UP1=market('UP1', 1.001, costs=s2.Costs(commission_side=6.0)))
        result = s2.simulate_account(paid, hypothesis='H5', scenario='stress')
        self.assertEqual({t.commission for t in result.trades if t.market == 'UP1'}, {9.0})

    def test_commission_lowers_final_equity(self):
        free = s2.simulate_account(basket(), hypothesis='H5')
        paid = s2.simulate_account({n: market(n, 1.001 if n.startswith('UP') else 0.999,
                                              costs=s2.Costs(commission_side=6.0)) for n in basket()},
                                   hypothesis='H5')
        self.assertLess(paid.rows[-1][1], free.rows[-1][1])

    def test_account_wiped_out_by_costs_stops_and_is_reported(self):
        ruinous = {n: market(n, 1.001 if n.startswith('UP') else 0.999, costs=s2.Costs(commission_side=600.0))
                   for n in basket()}
        result = s2.simulate_account(ruinous, hypothesis='H5')
        self.assertIsNotNone(result.ruined)
        self.assertEqual(result.rows[-1][0], result.ruined)
        self.assertEqual([t for t in result.trades if t.date > result.ruined], [])

    def test_solvent_account_is_not_marked_as_wiped_out(self):
        self.assertIsNone(s2.simulate_account(basket(), hypothesis='H5').ruined)

    def test_side_rate_is_half_spread_plus_one_basis_point(self):
        costs = s2.Costs(spread=0.0010)
        self.assertAlmostEqual(s2.side_rate(costs, 'base'), 0.0006)
        self.assertAlmostEqual(s2.side_rate(costs, 'stress'), 0.0012)

    def test_financing_rate_depends_on_side_and_scenario(self):
        costs = s2.Costs(fin_long=0.06, fin_short=0.02, payout_short=0.03, payout_short_stress=0.05)
        self.assertAlmostEqual(s2.financing_rate(costs, 'base', 1), 0.06)
        self.assertAlmostEqual(s2.financing_rate(costs, 'base', -1), 0.05)
        self.assertAlmostEqual(s2.financing_rate(costs, 'stress', 1), 0.06 * 1.5 + 0.01)
        self.assertAlmostEqual(s2.financing_rate(costs, 'stress', -1), 0.02 * 1.5 + 0.01 + 0.05)

    def test_financing_is_charged_for_calendar_days_held(self):
        financed = {n: market(n, 1.001 if n.startswith('UP') else 0.999, costs=s2.Costs(fin_long=0.06))
                    for n in basket()}
        result = s2.simulate_account(financed, hypothesis='H5')
        free = s2.simulate_account(basket(), hypothesis='H5')
        self.assertGreater(result.costs['financing'], 0)
        self.assertLess(result.rows[-1][1], free.rows[-1][1])


LONG = 1500  # 2022-01-01 .. 2026-02-08, żeby próba poza strojeniem (od 2025) miała ponad rok


def long_basket(costs: s2.Costs | None = None, count: int = 6) -> dict[str, s2.Market]:
    names = ['UP1', 'UP2', 'UP3', 'DN1', 'DN2', 'DN3'][:count]
    return {n: market(n, 0, costs=costs, dates=days(LONG),
                      closes=noisy(1.001 if n.startswith('UP') else 0.999, LONG, n)) for n in names}


class Evaluation(unittest.TestCase):
    def test_clean_trend_passes_all_six_criteria(self):
        outcome = s2.evaluate(long_basket(), hypothesis='H4')
        self.assertEqual(outcome['verdict'], 'PASS', outcome['checks'])
        self.assertEqual(len(outcome['checks']), 6)
        self.assertTrue(all(check['passed'] for check in outcome['checks']))

    def test_heavy_commission_turns_the_same_trend_into_fail(self):
        outcome = s2.evaluate(long_basket(s2.Costs(commission_side=60.0)), hypothesis='H4')
        self.assertEqual(outcome['verdict'], 'FAIL')
        self.assertFalse(outcome['checks'][0]['passed'])

    def test_too_small_basket_gives_brak_danych(self):
        outcome = s2.evaluate(long_basket(count=5), hypothesis='H4')
        self.assertEqual(outcome['verdict'], 'BRAK DANYCH')
        self.assertEqual(outcome['checks'], [])

    def test_twelve_variants_are_four_main_and_eight_neighbours(self):
        outcome = s2.evaluate(long_basket(), hypothesis='H5')
        self.assertEqual([(v['scenario'], v['delay']) for v in outcome['variants']],
                         [('base', 0), ('base', 1), ('stress', 0), ('stress', 1)])
        self.assertEqual(sorted(tuple(v['params']) for v in outcome['neighbours']),
                         sorted((l, v) for l in (202, 252, 302) for v in (48, 60, 72) if (l, v) != (252, 60)))

    def test_criteria_use_only_the_out_of_sample_period(self):
        outcome = s2.evaluate(long_basket(), hypothesis='H4')
        self.assertGreaterEqual(outcome['variants'][0]['out_of_sample']['start'], '2025-01-01')
        self.assertLessEqual(outcome['variants'][0]['in_sample']['end'], '2024-12-31')

    def test_benchmark_is_reported_but_not_counted_as_variant(self):
        outcome = s2.evaluate(long_basket(), hypothesis='H5')
        self.assertEqual(outcome['benchmark']['label'], 'punkt_odniesienia')
        self.assertEqual(len(outcome['variants']) + len(outcome['neighbours']), 12)


def write_symbol(folder: Path, symbol: str, *, path: str, swap=(-6.0, 2.0, 5), bars: int = 5, spread_points: int = 4,
                 extra: dict | None = None) -> None:
    rows = ['date,open,high,low,close,tick_volume,spread']
    for i in range(bars):
        day = (START + timedelta(days=i)).isoformat()
        rows.append(f'{day},{100 + i},{101 + i},{99 + i},{100.5 + i},10,0')
    (folder / f'{symbol}_D1.csv').write_text('\n'.join(rows) + '\n', encoding='utf-8')
    meta = {'symbol': symbol, 'market': symbol, 'path': path, 'digits': 2, 'point': 0.01, 'trade_contract_size': 1.0,
            'volume_min': 1.0, 'volume_step': 1.0, 'volume_max': 1000.0, 'currency_profit': 'USD',
            'swap_long': swap[0], 'swap_short': swap[1], 'swap_mode': swap[2], 'spread_points': spread_points}
    meta.update(extra or {})
    (folder / f'{symbol}_D1.meta.json').write_text(json.dumps(meta), encoding='utf-8')


class LoadingMarketData(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def test_reads_prices_and_lot_specification(self):
        write_symbol(self.folder, 'IWM', path='ETF\\ETF-C\\IWM')
        loaded = s2.market_from_files(self.folder, 'IWM')
        self.assertEqual(loaded.dates[0], '2022-01-01')
        self.assertEqual((loaded.opens[0], loaded.closes[-1]), (100.0, 104.5))
        self.assertEqual((loaded.spec.volume_min, loaded.spec.volume_step), (D('1.0'), D('1.0')))
        self.assertEqual(loaded.spec.profit_currency, 'USD')

    def test_etf_pays_commission_per_side_and_other_folders_do_not(self):
        write_symbol(self.folder, 'IWM', path='ETF\\ETF-C\\IWM')
        write_symbol(self.folder, 'ETHUSD', path='Crypto Currency\\Crypto Major\\ETHUSD', swap=(-8.33, 0.0, 5))
        self.assertEqual(s2.market_from_files(self.folder, 'IWM').costs.commission_side, 6.0)
        self.assertEqual(s2.market_from_files(self.folder, 'ETHUSD').costs.commission_side, 0.0)

    def test_swap_credit_counts_as_zero_cost(self):
        write_symbol(self.folder, 'IWM', path='ETF\\ETF-C\\IWM', swap=(-6.0, 2.0, 5))
        costs = s2.market_from_files(self.folder, 'IWM').costs
        self.assertAlmostEqual(costs.fin_long, 0.06)
        self.assertEqual(costs.fin_short, 0.0)

    def test_unknown_swap_mode_falls_back_to_seven_percent(self):
        write_symbol(self.folder, 'ODD', path='Other\\ODD', swap=(-1.0, -1.0, 9))
        costs = s2.market_from_files(self.folder, 'ODD').costs
        self.assertEqual((costs.fin_long, costs.fin_short), (0.07, 0.07))

    def test_tick_spread_replaces_single_reading(self):
        write_symbol(self.folder, 'IWM', path='ETF\\ETF-C\\IWM', spread_points=40)
        self.assertAlmostEqual(s2.market_from_files(self.folder, 'IWM').costs.spread, 40 * 0.01 / 104.5)
        self.assertEqual(s2.market_from_files(self.folder, 'IWM', spread=0.000072).costs.spread, 0.000072)

    def test_short_side_pays_estimated_payouts_on_equity_and_bond_etfs(self):
        write_symbol(self.folder, 'IWM', path='ETF\\ETF-C\\IWM')
        write_symbol(self.folder, 'TLT', path='ETF\\ETF-R\\TLT')
        write_symbol(self.folder, 'USO', path='ETF\\ETF-C\\USO')
        equity, bond, oil = (s2.market_from_files(self.folder, n).costs for n in ('IWM', 'TLT', 'USO'))
        self.assertEqual((equity.payout_short, equity.payout_short_stress), (0.03, 0.05))
        self.assertEqual((bond.payout_short, bond.payout_short_stress), (0.05, 0.07))
        self.assertEqual((oil.payout_short, oil.payout_short_stress), (0.0, 0.0))

    def test_spreads_come_from_tick_report_session_median(self):
        report = self.folder / 'spread.md'
        report.write_text(
            '## ETF-y z USA: sesja USA i pozostałe godziny\n\n'
            '| Symbol | Ticki | Od | Do | Dni | Sesja USA: ticki | mediana | p75 | p95 | ≤ 0 | Poza sesją: ticki |'
            ' mediana | p75 | p95 | ≤ 0 |\n|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n'
            '| `IWM` | 360106 | 2026-10-22 | 2026-11-20 | 22 | 360106 | 0.0072 | 0.0106 | 0.0113 | 0.3% | 0 | — | — | — | — |\n'
            '\n## Pozostałe (całość, bez podziału)\n\n| Symbol | Ticki | Od | Do | Dni | mediana | p75 | p95 | ≤ 0 |\n'
            '|---|---:|---|---|---:|---:|---:|---:|---:|\n'
            '| `ETHUSD` | 7700677 | 2026-10-22 | 2026-11-20 | 30 | 0.1178 | 0.1371 | 0.1438 | 0.0% |\n', encoding='utf-8')
        spreads = s2.load_spreads(report)
        self.assertAlmostEqual(spreads['IWM'], 0.000072)
        self.assertAlmostEqual(spreads['ETHUSD'], 0.001178)


class AcceptanceGate(unittest.TestCase):
    def test_draft_rules_block_a_run_on_market_data(self):
        self.assertIn('akceptac', s2.acceptance_block('**Status: PROJEKT. Czeka na akceptację Karola**'))

    def test_accepted_rules_do_not_block(self):
        self.assertIsNone(s2.acceptance_block('**Status: ZAAKCEPTOWANE przez Karola 22.11.2026**'))

    def test_main_refuses_before_touching_data_while_rules_are_a_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_file = Path(tmp) / 'SPEC.md'
            spec_file.write_text('**Status: PROJEKT.**', encoding='utf-8')
            code = s2.main(['--spec', str(spec_file), '--dane', str(Path(tmp) / 'nie-ma-takiego-folderu')])
        self.assertEqual(code, 2)


ETF_PATH = 'ETF\\ETF-C\\'
SYNTHETIC = {'IWM': 1.001, 'XLF': 1.0008, 'EFA': 0.9995, 'EEM': 1.0006, 'GDX': 0.9992, 'USO': 1.0007, 'DBC': 0.9996,
             'ETHUSD': 1.0012}


def write_long_symbol(folder: Path, symbol: str, drift: float) -> None:
    """Pliki D1 jak z odczytu terminala, ale z cenami sztucznymi na 1500 dni od 2022-01-01."""
    closes = noisy(drift, LONG, symbol)
    rows = ['date,open,high,low,close,tick_volume,spread']
    for day, close in zip(days(LONG), closes):
        rows.append(f'{day},{close * 0.999:.4f},{close * 1.01:.4f},{close * 0.99:.4f},{close:.4f},10,0')
    (folder / f'{symbol}_D1.csv').write_text('\n'.join(rows) + '\n', encoding='utf-8')
    etf = symbol != 'ETHUSD'
    meta = {'symbol': symbol, 'market': symbol, 'path': (ETF_PATH if etf else 'Crypto Currency\\Crypto Major\\') + symbol,
            'digits': 2, 'point': 0.01, 'trade_contract_size': 1.0, 'volume_min': 0.01, 'volume_step': 0.01,
            'volume_max': 1000.0, 'currency_profit': 'USD', 'currency_base': 'USD', 'currency_margin': 'USD',
            'trade_mode': 'FULL', 'swap_long': -6.0 if etf else -8.33, 'swap_short': 2.0 if etf else 0.0,
            'swap_mode': 5, 'spread_points': 2}
    (folder / f'{symbol}_D1.meta.json').write_text(json.dumps(meta), encoding='utf-8')


class RunOnFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'dane'
        self.data.mkdir()
        self.out = self.root / 'wyniki'
        self.spec = self.root / 'SPEC.md'
        self.spec.write_text('**Status: ZAAKCEPTOWANE przez Karola (test).**', encoding='utf-8')
        self.fx = self.root / 'symbols.json'
        self.fx.write_text(json.dumps({'fx_to_usd': {'USD': 1.0}}), encoding='utf-8')
        self.spreads = self.root / 'spread.md'
        self.spreads.write_text('brak tabel\n', encoding='utf-8')

    def run_main(self, *extra: str) -> int:
        return s2.main(['--spec', str(self.spec), '--dane', str(self.data), '--kursy', str(self.fx),
                        '--spready', str(self.spreads), '--wyniki', str(self.out), *extra])

    def test_accepted_rules_run_both_hypotheses_and_write_report(self):
        for symbol, drift in SYNTHETIC.items():
            write_long_symbol(self.data, symbol, drift)
        self.assertEqual(self.run_main('--ekspozycja', '1'), 0)
        payload = json.loads((self.out / 'wynik_seria2_2500.json').read_text(encoding='utf-8'))
        self.assertEqual([r['hypothesis'] for r in payload['results']], ['H4', 'H5'])
        self.assertTrue(all(r['verdict'] in ('PASS', 'FAIL') for r in payload['results']))
        self.assertEqual(sorted(payload['basket']), sorted(SYNTHETIC))
        text = (self.out / 'WYNIK_SERIA2_2500.md').read_text(encoding='utf-8')
        for fragment in ('# Seria 2 (H4, H5): wynik na danych dziennych, kapitał 2 500 USD', '## H4: werdykt',
                         '## H5: werdykt', 'prowizja', 'widoku rachunku', 'Widok modelu'):
            self.assertIn(fragment, text)
        expected = {s: hashlib.sha256((self.data / f'{s}_D1.csv').read_bytes()).hexdigest() for s in SYNTHETIC}
        self.assertEqual(payload['data_sha256'], expected)

    def test_missing_gross_exposure_is_refused_after_acceptance(self):
        write_long_symbol(self.data, 'IWM', 1.001)
        self.assertEqual(self.run_main(), 2)
        self.assertFalse(self.out.exists())

    def test_too_small_basket_is_reported_as_brak_danych(self):
        for symbol in ('IWM', 'XLF', 'ETHUSD'):
            write_long_symbol(self.data, symbol, SYNTHETIC[symbol])
        self.assertEqual(self.run_main('--ekspozycja', '1'), 0)
        payload = json.loads((self.out / 'wynik_seria2_2500.json').read_text(encoding='utf-8'))
        self.assertEqual([r['verdict'] for r in payload['results']], ['BRAK DANYCH', 'BRAK DANYCH'])


if __name__ == '__main__':
    unittest.main()
