from __future__ import annotations

import random
import unittest
from decimal import Decimal

from astraljet.domain.errors import ValidationError
from astraljet.lab.position_sizing import SizingLimits, size_positions
from astraljet.workspace.instruments import FxRate, FxTable, InstrumentSpec

D = Decimal


def spec(symbol, *, contract='1', vmin='0.1', step='0.1', vmax='100', currency='USD'):
    return InstrumentSpec(symbol=symbol, digits=2, contract_size=D(contract), profit_currency=currency,
                          volume_min=D(vmin), volume_max=D(vmax), volume_step=D(step))


# Najmniejsze loty i ceny zbliżone do odczytu z 18.11.2026 (zaokrąglone, nazwy rynków ogólne).
SPECS = {
    'SP500': spec('SP500'),
    'NAS100': spec('NAS100'),
    'DAX': spec('DAX', currency='EUR'),
    'GOLD': spec('GOLD', contract='100', vmin='0.01', step='0.01'),
    'BRENT': spec('BRENT', contract='1000', vmin='0.01', step='0.01'),
    'EURUSD': spec('EURUSD', contract='100000', vmin='0.01', step='0.01'),
    'BTCUSD': spec('BTCUSD', vmin='0.01', step='0.01'),
}
PRICES = {'SP500': 7590, 'NAS100': 28420, 'DAX': 25797, 'GOLD': 3876, 'BRENT': 116.9, 'EURUSD': 1.116, 'BTCUSD': 77500}
BASKET = {'BTCUSD': 0.057, 'EURUSD': 0.376, 'DAX': 0.151, 'NAS100': 0.105, 'SP500': 0.188, 'BRENT': 0.046, 'GOLD': 0.075}


def eur_usd(rate='1.116'):
    table = FxTable()
    table.add(FxRate('EUR', 'USD', D(rate), 'test'))
    return table


def size(targets, capital, **kwargs):
    kwargs.setdefault('prices', PRICES)
    kwargs.setdefault('specs', SPECS)
    kwargs.setdefault('fx', eur_usd())
    return size_positions(targets, capital=capital, **kwargs)


class PositionSizingTest(unittest.TestCase):
    def test_rounds_down_to_step_and_never_up(self):
        result = size({'SP500': 0.3}, 10_000)['SP500']  # 3000 / 7590 = 0.395 lota
        self.assertEqual(D('0.3'), result.volume)
        self.assertEqual(D('2277.0'), result.value)
        self.assertLess(result.weight, D('0.3'))
        self.assertEqual((), result.reasons)

    def test_position_below_minimum_lot_is_skipped_not_raised_to_minimum(self):
        result = size({'SP500': 0.188}, 2_500)['SP500']  # przydział 470 USD, najmniejszy lot 759 USD
        self.assertEqual(0, result.volume)
        self.assertEqual(0, result.value)
        self.assertTrue(result.skipped)
        self.assertIn('pominięty', result.reasons[0])
        self.assertIn('759.00', result.reasons[0])

    def test_basket_from_study_is_not_executable_at_2500_usd(self):
        result = size(BASKET, 2_500)
        self.assertTrue(all(p.skipped for p in result.values()))
        self.assertEqual(0, sum(p.value for p in result.values()))

    def test_basket_at_5000_and_100000_usd_matches_capital_report(self):
        small = size(BASKET, 5_000)
        self.assertEqual({'EURUSD', 'SP500'}, {n for n, p in small.items() if p.volume})
        self.assertEqual(D('0.01'), small['EURUSD'].volume)
        self.assertEqual(D('0.1'), small['SP500'].volume)
        self.assertAlmostEqual(0.375, float(sum(p.value for p in small.values())) / 5_000, places=3)
        large = size(BASKET, 100_000)
        self.assertTrue(all(p.volume > 0 for p in large.values()))
        self.assertAlmostEqual(0.91, float(sum(p.value for p in large.values())) / 100_000, delta=0.02)

    def test_profit_currency_is_converted_with_explicit_rate_only(self):
        result = size({'DAX': 0.3}, 100_000)['DAX']  # 0.1 lota = 25797 * 1.116 * 0.1 = 2878.95 USD
        self.assertEqual(D('1.0'), result.volume)
        self.assertAlmostEqual(28789.452, float(result.value), places=3)
        with self.assertRaises(ValidationError) as caught:
            size({'DAX': 0.3}, 100_000, fx=FxTable())
        self.assertIn('Brak kursu EUR->USD', caught.exception.message)

    def test_per_market_limit_clips_and_explains(self):
        result = size({'EURUSD': 0.8}, 100_000)['EURUSD']
        self.assertEqual(D('0.5'), result.allowed_weight)
        self.assertEqual(D('0.44'), result.volume)  # 50000 / 111600 = 0.448
        self.assertIn('limitu jednego rynku 50%', result.reasons[0])

    def test_gross_limit_scales_everything_proportionally(self):
        result = size({'SP500': 0.5, 'NAS100': 0.5, 'EURUSD': 0.5}, 1_000_000)
        self.assertTrue(all(abs(p.allowed_weight - D(1) / 3) < D('1e-20') for p in result.values()))
        self.assertLessEqual(sum(p.value for p in result.values()), 1_000_000)
        self.assertTrue(all('suma wag 150.0% ponad limit 100%' in p.reasons[0] for p in result.values()))

    def test_float_noise_above_full_allocation_is_reduced_without_a_reason(self):
        targets = {'SP500': 0.1 + 0.2, 'NAS100': 0.3, 'EURUSD': 0.4}  # 0.30000000000000004 + 0.3 + 0.4 > 1
        result = size(targets, 1_000_000)
        self.assertTrue(all(p.allowed_weight < D(str(targets[n])) for n, p in result.items()))
        self.assertEqual([(), (), ()], [p.reasons for p in result.values()])
        self.assertLessEqual(sum(p.value for p in result.values()), 1_000_000)

    def test_multiplier_scales_down_and_cannot_scale_up(self):
        half = size({'SP500': 0.4}, 100_000, limits=SizingLimits(multiplier=D('0.5')))['SP500']
        self.assertEqual(D('0.2'), half.allowed_weight)
        self.assertEqual(D('2.6'), half.volume)  # 20000 / 7590 = 2.63
        for bad in ('1.01', '0', '-0.5', 'NaN'):
            with self.assertRaises(ValidationError):
                size({'SP500': 0.4}, 100_000, limits=SizingLimits(multiplier=D(bad)))

    def test_leverage_is_refused_by_construction(self):
        for limits in (SizingLimits(max_gross=D('1.5')), SizingLimits(max_per_market=D('1.2')), SizingLimits(max_gross=D(0))):
            with self.assertRaises(ValidationError):
                size({'SP500': 0.4}, 100_000, limits=limits)

    def test_short_target_gives_negative_volume_rounded_toward_zero(self):
        result = size({'SP500': -0.3}, 10_000)['SP500']
        self.assertEqual(D('-0.3'), result.volume)
        self.assertEqual(D('2277.0'), result.value)
        self.assertLess(result.weight, 0)
        self.assertGreater(result.weight, D('-0.3'))

    def test_zero_weight_needs_no_price_or_spec(self):
        result = size({'NIEZNANY': 0, 'SP500': 0.3}, 10_000)
        self.assertEqual(0, result['NIEZNANY'].volume)
        self.assertFalse(result['NIEZNANY'].skipped)
        self.assertEqual(('waga zero',), result['NIEZNANY'].reasons)

    def test_volume_is_capped_at_instrument_maximum(self):
        specs = {'SP500': spec('SP500', vmax='0.5')}
        result = size({'SP500': 0.5}, 100_000, specs=specs)['SP500']
        self.assertEqual(D('0.5'), result.volume)
        self.assertIn('największego wolumenu', result.reasons[0])

    def test_bad_data_refuses_the_whole_sizing(self):
        cases = {
            'brak ceny': dict(prices={'NAS100': 28420}),
            'cena zero': dict(prices={**PRICES, 'SP500': 0}),
            'cena ujemna': dict(prices={**PRICES, 'SP500': -1}),
            'cena NaN': dict(prices={**PRICES, 'SP500': float('nan')}),
            'cena nieskończona': dict(prices={**PRICES, 'SP500': float('inf')}),
            'cena tekstem': dict(prices={**PRICES, 'SP500': 'abc'}),
            'cena None': dict(prices={**PRICES, 'SP500': None}),
            'brak specyfikacji': dict(specs={'NAS100': SPECS['NAS100']}),
        }
        for name, override in cases.items():
            with self.subTest(name), self.assertRaises(ValidationError):
                size({'SP500': 0.2, 'NAS100': 0.2}, 100_000, **override)
        for capital in (0, -100, float('nan'), float('inf'), None):
            with self.subTest(capital=capital), self.assertRaises(ValidationError):
                size({'SP500': 0.2}, capital)
        for weight in (float('nan'), float('inf'), 'dużo', None):
            with self.subTest(weight=weight), self.assertRaises(ValidationError):
                size({'SP500': weight}, 100_000)

    def test_random_portfolios_never_exceed_capital_targets_or_volume_grid(self):
        rng = random.Random(20261118)
        names = list(SPECS)
        for _ in range(500):
            targets = {n: rng.choice((0, 1, 1, -1)) * rng.random() * rng.choice((0.05, 0.3, 1.5)) for n in names}
            capital = rng.choice((500, 2_500, 10_000, 250_000)) * (0.5 + rng.random())
            prices = {n: PRICES[n] * (0.5 + rng.random()) for n in names}
            limits = SizingLimits(max_gross=D(rng.choice(('1', '0.6'))), max_per_market=D(rng.choice(('0.5', '0.2', '1'))),
                                  multiplier=D(rng.choice(('1', '0.5', '0.25'))))
            result = size(targets, capital, prices=prices, limits=limits)
            self.assertLessEqual(sum(p.value for p in result.values()), D(str(capital)) * limits.max_gross)
            for name, position in result.items():
                self.assertLessEqual(abs(position.weight), abs(position.allowed_weight))
                self.assertLessEqual(abs(position.allowed_weight), abs(D(str(targets[name]))) * limits.multiplier)
                self.assertLessEqual(abs(position.allowed_weight), limits.max_per_market)
                if position.volume:
                    self.assertTrue(SPECS[name].check_volume(abs(position.volume)).ok)
                    self.assertEqual(position.volume > 0, targets[name] > 0)


if __name__ == '__main__':
    unittest.main()
