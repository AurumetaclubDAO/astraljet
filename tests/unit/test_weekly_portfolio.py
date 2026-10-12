from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, localcontext
from unittest.mock import patch

from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.lab.data_quality import MarketBar
from astraljet.lab.weekly_portfolio import (
    CostScenario, WeeklyProtocol, next_weekly_state, simulate_weekly, weekly_engine_fingerprint,
)

D = Decimal


def fixture_bars(days=90, *, flat=False):
    result = []
    for i in range(days):
        timestamp = (date(2021, 1, 1) + timedelta(days=i)).isoformat() + 'T00:00:00Z'
        for symbol in ('BTCUSD', 'ETHUSD'):
            price = D(100 if flat else 100 + i * (2 if symbol == 'BTCUSD' else 1))
            result.append(MarketBar(timestamp, symbol, price, price + 1, price - 1, price))
    return result


class WeeklyPortfolioTest(unittest.TestCase):
    def setUp(self):
        self.protocol = WeeklyProtocol('2021-01-01', '2021-02-28', '2021-03-01', '2021-03-31', 3, 1)
        self.scenario = CostScenario('fixture-base', D(40))

    def run_model(self, bars=None, *, scenario=None, protocol=None, **kwargs):
        return simulate_weekly(fixture_bars() if bars is None else bars, protocol=protocol or self.protocol,
                               scenario=scenario or self.scenario,
                               expected_code_hash=kwargs.get('expected_code_hash', weekly_engine_fingerprint()))

    def test_state_machine_rebuilds_after_two_consecutive_positive_weeks(self):
        state, observed = None, []
        for positive in (True, True, True, False, True, False, True, True):
            state = next_weekly_state(state, positive)
            observed.append(state)
        self.assertEqual(['rebuild_1', 'risk_on', 'risk_on', 'risk_off', 'rebuild_1', 'risk_off', 'rebuild_1', 'risk_on'], observed)
        self.assertEqual('risk_off', next_weekly_state(None, False))
        with self.assertRaises(ValidationError):
            next_weekly_state(None, 1)

    def test_only_sunday_signals_two_tranches_and_next_day_execution(self):
        result = self.run_model()
        signals = result['signals']
        self.assertTrue(all(date.fromisoformat(s['bar_date']).weekday() == 6 for s in signals))
        orders = [o for o in result['orders'] if o['portfolio'] == 'strategy']
        self.assertEqual(['rebuild_1', 'risk_on'], [o['reason'] for o in orders])
        self.assertEqual(['2021-01-11', '2021-01-18'], [o['execution_date'] for o in orders])
        self.assertEqual({'btc': '0.525', 'eth': '0.15', 'cash': '0.325'}, orders[0]['target'])
        for order in orders:
            self.assertEqual(1, (date.fromisoformat(order['execution_date']) - date.fromisoformat(order['signal_bar_date'])).days)

    def test_220_daily_observations_are_required_for_200_plus_20(self):
        protocol = WeeklyProtocol('2021-01-01', '2021-12-31', '2022-01-01', '2022-02-04')
        result = self.run_model(fixture_bars(400), protocol=protocol)
        self.assertEqual('2021-08-08', result['signals'][0]['bar_date'])
        self.assertEqual('2021-08-09', result['orders'][0]['execution_date'])

    def test_negative_week_resets_actual_rebuild_orders(self):
        bars = fixture_bars()
        bars[32] = replace(bars[32], open=D(1), close=D(1), high=D(2), low=D('.5'))  # Sunday Jan 17
        result = self.run_model(bars)
        orders = [o for o in result['orders'] if o['portfolio'] == 'strategy']
        self.assertEqual(['rebuild_1', 'risk_off', 'rebuild_1', 'risk_on'], [o['reason'] for o in orders])
        self.assertEqual(['2021-01-11', '2021-01-18', '2021-01-25', '2021-02-01'], [o['execution_date'] for o in orders])

    def test_equal_price_and_sma_is_risk_off_not_risk_on(self):
        result = self.run_model(fixture_bars(flat=True))
        self.assertTrue(all(not s['positive'] and s['state'] == 'risk_off' for s in result['signals']))
        self.assertEqual(1, sum(o['portfolio'] == 'strategy' for o in result['orders']))

    def test_no_hidden_rebalance_and_weights_drift(self):
        rows = self.run_model()['daily']['strategy']
        monday, tuesday = rows[17], rows[18]
        self.assertEqual(monday['btc_units'], tuesday['btc_units'])
        self.assertEqual(monday['eth_units'], tuesday['eth_units'])
        self.assertEqual(monday['cash'], tuesday['cash'])
        self.assertNotEqual(monday['gross_exposure'], tuesday['gross_exposure'])
        self.assertFalse(tuesday['rebalance_executed'])
        self.assertEqual(D(0), D(tuesday['cost']))

    def test_execution_uses_next_open_not_signal_close(self):
        bars = fixture_bars(flat=True)
        bars[18] = replace(bars[18], close=D(1000), high=D(1000))  # Sunday Jan 10
        bars[20] = replace(bars[20], open=D(120), close=D(120), high=D(121))
        result = self.run_model(bars)
        order = next(o for o in result['orders'] if o['portfolio'] == 'strategy')
        self.assertEqual('rebuild_1', order['reason'])
        self.assertEqual('120', next(f for f in order['fills'] if f['instrument'] == 'BTCUSD')['price'])

    def test_future_data_cannot_change_past_signals_fills_or_holdings(self):
        bars = fixture_bars()
        original = self.run_model(bars)
        changed = [replace(b, open=D(20), close=D(20), low=D(19), high=D(21))
                   if b.timestamp >= '2021-03-05' else b for b in bars]
        mutated = self.run_model(changed)
        for key, date_key in (('signals', 'bar_date'), ('orders', 'execution_date')):
            self.assertEqual([r for r in original[key] if r[date_key] < '2021-03-05'],
                             [r for r in mutated[key] if r[date_key] < '2021-03-05'])
        for name in ('strategy', 'benchmark'):
            self.assertEqual([r for r in original['daily'][name] if r['date'] < '2021-03-05'],
                             [r for r in mutated['daily'][name] if r['date'] < '2021-03-05'])

    def test_one_extra_day_delay_applies_to_both_portfolios_and_monthly_rebalance(self):
        result = self.run_model(scenario=CostScenario('delay', D(40), 1))
        strategy = [o['execution_date'] for o in result['orders'] if o['portfolio'] == 'strategy']
        benchmark = [o['execution_date'] for o in result['orders'] if o['portfolio'] == 'benchmark']
        self.assertEqual(['2021-01-12', '2021-01-19'], strategy)
        self.assertEqual(['2021-01-12', '2021-02-02', '2021-03-02'], benchmark)

    def test_oos_carries_units_and_includes_first_overnight_gap_and_costs(self):
        bars = fixture_bars()
        bars = [replace(b, open=D(500), close=D(500), high=D(501), low=D(499))
                if b.timestamp >= '2021-03-01' else b for b in bars]
        result = self.run_model(bars)
        for name in ('strategy', 'benchmark'):
            rows = result['daily'][name]
            previous = next(r for r in rows if r['date'] == '2021-02-28')
            first = next(r for r in rows if r['date'] == '2021-03-01')
            metrics = result['metrics'][name]
            self.assertEqual(previous['equity_close'], metrics['out_of_sample']['initial_equity'])
            self.assertNotEqual(first['equity_open_before_orders'], metrics['out_of_sample']['initial_equity'])
            combined = (1 + D(metrics['in_sample']['net_return'])) * (1 + D(metrics['out_of_sample']['net_return'])) - 1
            self.assertAlmostEqual(combined, D(metrics['full']['net_return']), places=24)
        previous, first = result['daily']['strategy'][58:60]
        self.assertEqual(previous['btc_units'], first['btc_units'])
        self.assertEqual(previous['cash'], first['cash'])

    def test_benchmark_uses_month_start_and_same_initial_allocation_date(self):
        result = self.run_model()
        dates = [o['execution_date'] for o in result['orders'] if o['portfolio'] == 'benchmark']
        self.assertEqual(['2021-01-11', '2021-02-01', '2021-03-01'], dates)
        self.assertEqual(31, result['metrics']['benchmark']['out_of_sample']['days'])
        self.assertEqual(49, result['metrics']['benchmark']['in_sample']['days'])

    def test_initial_cost_is_in_drawdown_and_warmup_is_not_performance(self):
        result = self.run_model(fixture_bars(flat=True))
        for name in ('strategy', 'benchmark'):
            metrics = result['metrics'][name]['full']
            self.assertEqual('2021-01-11', metrics['start'])
            self.assertGreater(D(metrics['max_drawdown']), 0)
            self.assertAlmostEqual(-D(metrics['net_return']), D(metrics['max_drawdown']), places=24)
            self.assertIsNone(metrics['profit_factor'])

    def test_four_fixed_scenarios_repeat_exactly_without_qualification(self):
        bars = fixture_bars(flat=True)
        results = {}
        for delay in (0, 1):
            for cost in (40, 75):
                scenario = CostScenario(f'{cost}-{delay}', D(cost), delay)
                with patch('urllib.request.urlopen', side_effect=AssertionError('network')):
                    one = self.run_model(bars, scenario=scenario)
                    two = self.run_model(list(reversed(bars)), scenario=scenario)
                self.assertEqual(one['output_hash'], two['output_hash'])
                self.assertEqual(one['input_hash'], two['input_hash'])
                self.assertEqual('OFFLINE_UNQUALIFIED', one['status'])
                self.assertFalse(one['execution_authorized'])
                self.assertFalse(one['run_record_created'])
                results[(cost, delay)] = one
            self.assertGreater(D(results[(40, delay)]['metrics']['strategy']['full']['net_return']),
                               D(results[(75, delay)]['metrics']['strategy']['full']['net_return']))

    def test_changed_hash_or_changed_loaded_files_fail_before_simulation(self):
        with self.assertRaises(DomainBlockedError) as caught:
            self.run_model([], expected_code_hash='0' * 64)
        self.assertEqual('engine_hash_mismatch', caught.exception.blocker)
        with patch('astraljet.lab.weekly_portfolio._source_hash', return_value='0' * 64), self.assertRaises(DomainBlockedError) as caught:
            weekly_engine_fingerprint()
        self.assertEqual('loaded_code_changed', caught.exception.blocker)

    def test_decimal_callers_context_does_not_change_results(self):
        normal = self.run_model()
        with localcontext() as context:
            context.prec = 8
            reduced = self.run_model()
        self.assertEqual(normal['output_hash'], reduced['output_hash'])

    def test_code_change_during_computation_rejects_the_entire_output(self):
        code_hash = weekly_engine_fingerprint()
        with patch('astraljet.lab.weekly_portfolio._source_hash', side_effect=[code_hash, '0' * 64]):
            with self.assertRaises(DomainBlockedError) as caught:
                simulate_weekly(fixture_bars(), protocol=self.protocol, scenario=self.scenario,
                                expected_code_hash=code_hash)
        self.assertEqual('loaded_code_changed', caught.exception.blocker)

    def test_missing_duplicate_unknown_and_invalid_bars_fail_closed(self):
        bars = fixture_bars()
        changes = [bars[2:], bars[:20] + bars[22:], bars + [bars[0]],
                   [replace(bars[0], timestamp='2021-01-01T01:00:00Z'), *bars[1:]],
                   [replace(bars[0], instrument='ETHBTC'), *bars[1:]],
                   [replace(bars[0], close=D('NaN')), *bars[1:]],
                   [replace(bars[0], low=D(1000)), *bars[1:]]]
        for changed in changes:
            with self.subTest(first=changed[0]), self.assertRaises((ValidationError, DomainBlockedError)):
                self.run_model(changed)

    def test_last_sunday_signal_is_recorded_as_unfilled_not_same_bar_trade(self):
        protocol = replace(self.protocol, end='2021-03-28')
        bars = fixture_bars(87)
        bars[-2] = replace(bars[-2], open=D(1), close=D(1), high=D(2), low=D('.5'))
        result = self.run_model(bars, protocol=protocol)
        self.assertEqual('2021-03-28', result['unfilled'][-1]['bar_date'])
        self.assertEqual('no_next_bar_for_execution', result['unfilled'][-1]['reason'])
        self.assertFalse(any(o['signal_bar_date'] == '2021-03-28' for o in result['orders']))

    def test_invalid_protocol_scenario_and_insufficient_history(self):
        for protocol in (replace(self.protocol, ma_window=True), replace(self.protocol, out_of_sample_start='2021-02-28')):
            with self.assertRaises(ValidationError):
                self.run_model(protocol=protocol)
        for scenario in (CostScenario('bad', D('NaN')), CostScenario('bad', D(40), -1), CostScenario('bad', D(40), True)):
            with self.assertRaises(ValidationError):
                self.run_model(scenario=scenario)
        with self.assertRaises(DomainBlockedError) as caught:
            self.run_model(protocol=replace(self.protocol, ma_window=200, slope_lookback=20))
        self.assertEqual('insufficient_history', caught.exception.blocker)


if __name__ == '__main__':
    unittest.main()
