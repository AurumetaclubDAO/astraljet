from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from astraljet.application.status import BudgetStatusRequest, authorize_cost, build_status, create_budget_status
from astraljet.cli import run as run_cli
from astraljet.lab.strategy import StrategyDefinition, create_strategy
from astraljet.domain.errors import DomainBlockedError
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.repositories import RecordRepository


class StatusContractTest(unittest.TestCase):
    @staticmethod
    def _cli(arguments: list[str]) -> dict[str, object]:
        output = io.StringIO()
        with redirect_stdout(output):
            result = run_cli(arguments)
        if result != 0:
            raise AssertionError(output.getvalue())
        return json.loads(output.getvalue())

    def test_empty_status_and_errors_expose_actionable_contract(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            status = build_status(database)

        self.assertEqual("unknown", status["object"])
        self.assertEqual("unknown", status["stage"])
        self.assertEqual("unknown", status["result"])
        for name in ("blocker", "owner", "allowed_next_action"):
            self.assertIn(name, status)
            self.assertTrue(status[name])

        error = DomainBlockedError(
            "Brak decyzji.",
            blocker="decision_missing",
            owner="Karol",
            allowed_next_action="Podejmij jawną decyzję.",
        ).as_dict()["error"]
        self.assertEqual(
            {"code", "message", "blocker", "owner", "allowed_next_action"},
            set(error),
        )

    def test_budget_status_accounts_for_settled_reserved_and_unresolved_cost(self) -> None:
        budget = create_budget_status(
            BudgetStatusRequest(
                currency="PLN",
                limit="100",
                settled_cost="20",
                active_reservation="10",
                unresolved_cost="5",
                scope="MVP",
            ),
            owner="Karol",
        )
        self.assertEqual("65", budget.available_amount)
        authorize_cost(budget, "65")
        with self.assertRaises(DomainBlockedError):
            authorize_cost(budget, "65.01")

    def test_cli_status_budget_and_audit_export_use_json_contract(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            root = Path(state)
            budget_path = root / "budget.json"
            budget_path.write_text(
                json.dumps(
                    {
                        "currency": "PLN",
                        "limit": "100",
                        "settled_cost": "20",
                        "active_reservation": "10",
                        "unresolved_cost": "5",
                        "scope": "MVP",
                    }
                ),
                encoding="utf-8",
            )
            self._cli(
                [
                    "--state-dir", state, "budget", "set", "--config", str(budget_path),
                    "--idempotency-key", "status-budget-v1",
                ]
            )
            status = self._cli(["--state-dir", state, "status", "--json"])
            self.assertEqual("65", status["budget"]["available"])
            output_path = root / "audit.json"
            exported = self._cli(
                ["--state-dir", state, "audit", "export", "--output", str(output_path)]
            )
            self.assertEqual("exported", exported["status"])
            self.assertTrue(output_path.is_file())
            self.assertIn("export_hash", json.loads(output_path.read_text(encoding="utf-8")))

    def test_blocked_strategy_status_does_not_suggest_skipping_to_data(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            strategy = create_strategy(
                candidate_id="CAND-12345678",
                definition=StrategyDefinition(
                    instruments=("BTCUSD", "ETHUSD"),
                    venue="",
                    timeframe="1d",
                    signal_timing="weekly close",
                    execution_timing="",
                    entry_rule="BTC nad SMA i średnia rośnie",
                    exit_rule="pogorszenie struktury trendu",
                    sizing_rule="odbudowa w 2–3 transzach",
                    cost_model="unknown",
                    constraints=("bez dźwigni",),
                    missing_data_policy="block",
                    benchmark="80/20",
                    allowed_parameters={},
                    source_adaptation="draft",
                ),
                owner="Karol",
            )
            RecordRepository(database).save(
                strategy,
                event_type="strategy.validated",
                reason="Test projekcji blokady.",
                outcome="needs_input",
                actor="tester",
                idempotency_key="status-blocked-strategy",
            )
            status = build_status(database)

        self.assertEqual("strategy_needs_input", status["blocker"])
        self.assertEqual("needs_input", status["result"])
        self.assertIn("Uzupełnij", status["allowed_next_action"])
        self.assertTrue(status["blocking_details"])


if __name__ == "__main__":
    unittest.main()
