from __future__ import annotations

import unittest
from decimal import Decimal

from astraljet.domain.errors import DomainBlockedError
from astraljet.lab.backtest import (
    apply_turnover_cost,
    calculate_profit_factor,
    generate_trend_targets,
    resolve_intrabar_exit,
)


class BacktestMechanicsTest(unittest.TestCase):
    def test_signal_uses_only_closed_data_and_becomes_effective_next_bar(self) -> None:
        closes = [Decimal(value) for value in ("10", "10", "10", "10", "50")]
        targets = generate_trend_targets(closes, ma_window=3, slope_lookback=1)

        self.assertEqual(4, targets[0].signal_index)
        self.assertEqual(5, targets[0].effective_index)
        self.assertEqual("risk_on", targets[0].regime)
        self.assertTrue(all(target.effective_index > target.signal_index for target in targets))

    def test_cost_is_deducted_and_never_assumed_zero(self) -> None:
        cost, net_equity = apply_turnover_cost(
            equity=Decimal("10000"),
            one_way_turnover=Decimal("0.90"),
            cost_bps=Decimal("10"),
        )
        self.assertEqual(Decimal("9.00000"), cost)
        self.assertEqual(Decimal("9991.00000"), net_equity)

        with self.assertRaises(DomainBlockedError):
            apply_turnover_cost(
                equity=Decimal("10000"),
                one_way_turnover=Decimal("0.90"),
                cost_bps=None,
            )

    def test_same_bar_stop_and_target_requires_explicit_policy(self) -> None:
        with self.assertRaises(DomainBlockedError):
            resolve_intrabar_exit(
                open_price=Decimal("100"),
                high=Decimal("111"),
                low=Decimal("89"),
                stop=Decimal("90"),
                target=Decimal("110"),
                policy=None,
            )
        self.assertEqual(
            ("stop", Decimal("90")),
            resolve_intrabar_exit(
                open_price=Decimal("100"),
                high=Decimal("111"),
                low=Decimal("89"),
                stop=Decimal("90"),
                target=Decimal("110"),
                policy="stop_first",
            ),
        )

    def test_no_closed_trades_has_no_artificial_profit_factor(self) -> None:
        value, reason = calculate_profit_factor([])
        self.assertIsNone(value)
        self.assertEqual("no_closed_trades", reason)


if __name__ == "__main__":
    unittest.main()
