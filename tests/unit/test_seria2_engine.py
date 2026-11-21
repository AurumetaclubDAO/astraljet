"""Silnik serii 2 (H4, H5) na danych sztucznych: księgowość rachunku w lotach, udział rynków, koszty.

Reguły: research/daily-trend/SPEC_SERIA2.md. Testy nie czytają danych rynkowych.
"""
from __future__ import annotations

import random
import sys
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


if __name__ == '__main__':
    unittest.main()
