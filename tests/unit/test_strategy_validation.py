from __future__ import annotations

import unittest

from astraljet.domain.enums import StrategyStatus, TechnicalStatus
from astraljet.lab.strategy import StrategyDefinition, create_strategy, validate_definition


def complete_definition() -> StrategyDefinition:
    return StrategyDefinition(
        instruments=("BTCUSD", "ETHUSD"),
        venue="TEST_SPOT",
        timeframe="1d",
        signal_timing="po zamknięciu dziennej świecy UTC",
        execution_timing="na otwarciu następnej dziennej świecy UTC",
        entry_rule="risk_on gdy BTC close > SMA i SMA > SMA sprzed slope_lookback sesji",
        exit_rule="risk_reduced gdy BTC close <= SMA albo SMA <= SMA sprzed slope_lookback sesji",
        sizing_rule="risk_on BTC 70%, ETH 20%, cash 10%; risk_reduced BTC 35%, ETH 10%, cash 55%",
        cost_model="10 bps od jednostronnego turnover przy każdym rebalansie",
        constraints=("bez dźwigni", "tylko zamknięte świece"),
        missing_data_policy="zablokuj przebieg przy luce w dowolnym instrumencie",
        benchmark="statyczne BTC 80%, ETH 20%, rebalans miesięczny",
        allowed_parameters={"ma_window": 200, "slope_lookback": 20, "cost_bps": 10},
        source_adaptation="testowa formalizacja; wymaga zatwierdzenia przed ocenianym EXP",
    )


class StrategyValidationTest(unittest.TestCase):
    def test_complete_definition_is_ready(self) -> None:
        record = create_strategy(
            candidate_id="CAND-12345678",
            definition=complete_definition(),
            owner="Karol",
        )
        self.assertEqual((), validate_definition(complete_definition()))
        self.assertIs(record.strategy_status, StrategyStatus.READY)
        self.assertIs(record.technical_status, TechnicalStatus.COMPLETED)

    def test_each_required_rule_blocks_ready(self) -> None:
        fields = (
            "instruments",
            "venue",
            "timeframe",
            "signal_timing",
            "execution_timing",
            "entry_rule",
            "exit_rule",
            "sizing_rule",
            "cost_model",
            "constraints",
            "missing_data_policy",
            "benchmark",
            "allowed_parameters",
        )
        base = complete_definition()
        for field in fields:
            with self.subTest(field=field):
                values = dict(base.as_dict())
                values[field] = () if field in {"instruments", "constraints"} else (
                    {} if field == "allowed_parameters" else ""
                )
                definition = StrategyDefinition.from_dict(values)
                errors = validate_definition(definition)
                self.assertIn(f"missing_{field}", errors)
                record = create_strategy(
                    candidate_id="CAND-12345678",
                    definition=definition,
                    owner="Karol",
                )
                self.assertIs(record.strategy_status, StrategyStatus.NEEDS_INPUT)
                self.assertIs(record.technical_status, TechnicalStatus.BLOCKED)

    def test_vague_market_structure_and_unknown_cost_are_blocked(self) -> None:
        values = complete_definition().as_dict()
        values["exit_rule"] = "redukcja po pogorszeniu struktury trendu"
        values["cost_model"] = "unknown"
        errors = validate_definition(StrategyDefinition.from_dict(values))
        self.assertIn("ambiguous_exit_rule", errors)
        self.assertIn("unknown_cost_model", errors)


if __name__ == "__main__":
    unittest.main()
