from __future__ import annotations

import tempfile
import unittest

from astraljet.application.mandates import MandateRequest, create_mandate
from astraljet.domain.enums import ExecutionEnvironment, ExecutionResultState
from astraljet.domain.errors import DomainBlockedError
from astraljet.executor.demo import DemoAdapter
from astraljet.executor.guard import ExecutorGuard
from astraljet.infrastructure.database import Database

from tests.executor_support import allowed_risk, mandate


class ExecutorPortContractTest(unittest.TestCase):
    def test_real_is_not_a_valid_environment(self) -> None:
        self.assertEqual(
            {"PAPER_CONTINUOUS", "BROKER_DEMO"},
            {environment.value for environment in ExecutionEnvironment},
        )
        with self.assertRaises(ValueError):
            ExecutionEnvironment("REAL")

    def test_demo_mandate_requires_explicit_demo_account(self) -> None:
        with self.assertRaises(DomainBlockedError):
            create_mandate(
                risk_decision=allowed_risk(environment="BROKER_DEMO"),
                request=MandateRequest(
                    authorized_by="Karol",
                    strategy_id="STRAT-12345678",
                    strategy_version=1,
                    code_hash="B" * 64,
                    environment=ExecutionEnvironment.BROKER_DEMO,
                    environment_id="demo-test",
                    account_id=None,
                    instruments=("BTCUSD",),
                    limits={"max_notional": "1000"},
                    starts_at="2025-01-02T00:00:00Z",
                    expires_at="2025-12-30T00:00:00Z",
                    stop_conditions=("kill switch",),
                    max_data_age_seconds=60,
                ),
                owner="Karol",
            )

    def test_demo_adapter_rejects_unconfirmed_account(self) -> None:
        risk, demo_mandate = mandate(
            environment=ExecutionEnvironment.BROKER_DEMO,
            environment_id="demo-test",
            account_id="DEMO-001",
        )
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            adapter = DemoAdapter(
                database,
                ExecutorGuard(database),
                confirmed_demo_account=None,
            )
            receipt = adapter.health(demo_mandate)
            self.assertIs(receipt.state, ExecutionResultState.REJECTED)
            self.assertIn("demo account", receipt.message.lower())


if __name__ == "__main__":
    unittest.main()
