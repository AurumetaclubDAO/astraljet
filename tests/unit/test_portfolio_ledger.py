from __future__ import annotations

import random
import unittest
from decimal import Decimal, localcontext

from astraljet.domain.errors import ValidationError
from astraljet.lab.portfolio_ledger import MATH, Portfolio, Weights, rebalance_spot

D = Decimal


class PortfolioLedgerTest(unittest.TestCase):
    def rebalance(self, portfolio=Portfolio(D(100)), weights=Weights(D('.8'), D('.2'), D(0)),
                  btc=D(10), eth=D(5), cost=D(40)):
        return rebalance_spot(portfolio, btc_price=btc, eth_price=eth, target=weights, cost_bps=cost)

    def test_initial_buy_uses_post_fee_targets_without_negative_cash(self):
        result = self.rebalance()
        expected = D(100) / D('1.004')
        self.assertAlmostEqual(expected, result.equity_after, places=20)
        self.assertAlmostEqual(D(100) - expected, result.total_cost, places=20)
        self.assertGreaterEqual(result.portfolio.cash, 0)
        self.assertEqual(2, len(result.fills))
        self.assertTrue(all(fill.side == 'buy' for fill in result.fills))
        self.assertAlmostEqual(D('.8'), result.portfolio.btc_units * 10 / result.equity_after, places=20)

    def test_rotation_charges_both_legs_and_sells_before_buying(self):
        result = self.rebalance(Portfolio(D(0), D(10), D(0)), Weights(D(0), D(1), D(0)))
        expected = D(100) * D('.996') / D('1.004')
        self.assertEqual(['sell', 'buy'], [fill.side for fill in result.fills])
        self.assertEqual(D(100), result.fills[0].notional)
        self.assertAlmostEqual(expected, result.fills[1].notional, places=20)
        self.assertAlmostEqual(D(100) - expected, result.total_cost, places=20)
        self.assertGreater(result.executed_notional, 199)
        self.assertGreater(result.total_cost, D('.79'))
        self.assertGreaterEqual(result.portfolio.cash, 0)

    def test_units_not_weights_remain_constant_when_prices_move(self):
        portfolio = Portfolio(D(10), D('.7'), D('.2'))
        self.assertEqual(D(100), portfolio.equity(D(100), D(100)))
        self.assertEqual(D(170), portfolio.equity(D(200), D(100)))
        self.assertEqual(D('.7'), portfolio.btc_units)

    def test_flat_target_does_not_generate_numerical_dust_orders(self):
        first = self.rebalance()
        second = self.rebalance(first.portfolio)
        self.assertEqual(first.portfolio, second.portfolio)
        self.assertEqual((), second.fills)
        self.assertEqual(D(0), second.total_cost)

    def test_round_trip_to_cash_conserves_equity_and_charges_sales(self):
        first = self.rebalance()
        second = self.rebalance(first.portfolio, Weights(D(0), D(0), D(1)))
        self.assertTrue(all(fill.side == 'sell' for fill in second.fills))
        self.assertEqual(D(0), second.portfolio.btc_units + second.portfolio.eth_units)
        self.assertAlmostEqual(D(100), second.portfolio.cash + first.total_cost + second.total_cost, places=20)

    def test_explicit_zero_cost_is_possible_for_mechanics_not_a_default(self):
        result = self.rebalance(cost=D(0))
        self.assertEqual(D(0), result.total_cost)
        self.assertAlmostEqual(D(100), result.equity_after, places=20)
        with self.assertRaises(ValidationError):
            self.rebalance(cost=None)

    def test_invalid_costs_prices_weights_and_short_positions_fail(self):
        for cost in (D('NaN'), D('Infinity'), D(-1), D(10000), 40, True):
            with self.subTest(cost=cost), self.assertRaises(ValidationError):
                self.rebalance(cost=cost)
        for price in (D('NaN'), D(0), D(-1), D('1e30')):
            with self.subTest(price=price), self.assertRaises(ValidationError):
                self.rebalance(btc=price)
        for target in (Weights(D(1), D(1), D(0)), Weights(D(-1), D(1), D(1)), Weights(D('NaN'), D(0), D(0))):
            with self.assertRaises(ValidationError):
                self.rebalance(weights=target)
        with self.assertRaises(ValidationError):
            self.rebalance(portfolio=Portfolio(D(100), D(-1)))
        with self.assertRaises(ValidationError):
            self.rebalance(portfolio=Portfolio(D(0)))

    def test_seeded_rebalances_preserve_self_financing_and_positive_holdings(self):
        rng = random.Random(1405)
        portfolio = Portfolio(D(100))
        for _ in range(120):
            btc, eth = D(rng.randint(80, 120)), D(rng.randint(20, 40))
            btc_weight = D(rng.randint(0, 100)) / 100
            eth_weight = D(rng.randint(0, int((1 - btc_weight) * 100))) / 100
            rate_bps = D(rng.choice([0, 40, 75, 9999]))
            with localcontext(MATH):
                result = self.rebalance(portfolio, Weights(btc_weight, eth_weight, 1 - btc_weight - eth_weight),
                                        btc, eth, rate_bps)
                self.assertLess(abs(result.equity_before - result.total_cost - result.equity_after), D('1e-35'))
                self.assertEqual(result.total_cost, sum((f.cost for f in result.fills), D(0)))
                self.assertGreaterEqual(result.portfolio.cash, 0)
                self.assertGreaterEqual(result.portfolio.btc_units, 0)
                self.assertGreaterEqual(result.portfolio.eth_units, 0)
                cash = portfolio.cash
                for fill in result.fills:
                    self.assertEqual(fill.notional * rate_bps / 10000, fill.cost)
                    cash += fill.notional if fill.side == 'sell' else -fill.notional
                    cash -= fill.cost
                    self.assertGreaterEqual(cash, 0)
                self.assertEqual(cash, result.portfolio.cash)
                portfolio = result.portfolio


if __name__ == '__main__':
    unittest.main()
