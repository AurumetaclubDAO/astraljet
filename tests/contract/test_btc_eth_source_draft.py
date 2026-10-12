from __future__ import annotations

import json
import unittest
from pathlib import Path

from astraljet.domain.enums import StrategyStatus, TechnicalStatus
from astraljet.lab.strategy import StrategyDefinition, create_strategy, validate_definition


class BtcEthSourceDraftContractTest(unittest.TestCase):
    def test_source_derived_draft_stays_blocked_until_ambiguous_rules_are_decided(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        path = (
            project_root
            / "specs"
            / "001-build-astra-jet"
            / "examples"
            / "btc_eth_strat_source_draft.json"
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        definition = StrategyDefinition.from_dict(value)
        errors = set(validate_definition(definition))

        self.assertTrue(
            {
                "missing_venue",
                "missing_execution_timing",
                "missing_allowed_parameters",
                "unknown_cost_model",
                "ambiguous_entry_rule",
                "ambiguous_exit_rule",
                "ambiguous_sizing_rule",
            }.issubset(errors)
        )
        record = create_strategy(
            candidate_id="CAND-12345678",
            definition=definition,
            owner="Karol",
        )
        self.assertIs(record.strategy_status, StrategyStatus.NEEDS_INPUT)
        self.assertIs(record.technical_status, TechnicalStatus.BLOCKED)
        self.assertIn("nie są zatwierdzonymi kryteriami", record.source_adaptation)


if __name__ == "__main__":
    unittest.main()
