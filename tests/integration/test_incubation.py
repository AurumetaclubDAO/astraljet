from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from astraljet.cli import run as run_cli
from astraljet.domain.enums import ExecutionEnvironment, ExecutionResultState
from astraljet.domain.errors import DomainBlockedError
from astraljet.executor.demo import DemoAdapter
from astraljet.executor.guard import ExecutorGuard
from astraljet.executor.paper import PaperExecutor
from astraljet.executor.ports import OrderIntent
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.event_store import EventStore
from astraljet.infrastructure.repositories import RecordRepository

from tests.executor_support import allowed_risk, mandate
from tests.unit.test_executor_guard import context, intent


NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


class IncubationIntegrationTest(unittest.TestCase):
    @staticmethod
    def _cli(arguments: list[str]) -> dict[str, object]:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = run_cli(arguments)
        if exit_code != 0:
            raise AssertionError(output.getvalue())
        return json.loads(output.getvalue())

    def test_paper_restart_does_not_duplicate_fill_or_position(self) -> None:
        risk, paper_mandate = mandate()
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            guard = ExecutorGuard(database)
            lease = guard.acquire_lease("paper-test", "worker-1", ttl_seconds=120, now=NOW)
            frozen = context(mandate_record=paper_mandate, risk=risk, lease_id=lease.lease_id)
            first_executor = PaperExecutor(database, guard)
            first = first_executor.submit_intent(
                frozen,
                intent(),
                idempotency_key="paper-intent-v1",
                now=NOW,
            )

            restarted = PaperExecutor(Database.from_state_dir(state), ExecutorGuard(Database.from_state_dir(state)))
            duplicate = restarted.submit_intent(
                frozen,
                intent(),
                idempotency_key="paper-intent-v1",
                now=NOW,
            )
            positions = restarted.positions("paper-test")

            self.assertIs(first.state, ExecutionResultState.ACCEPTED)
            self.assertIs(duplicate.state, ExecutionResultState.DUPLICATE)
            self.assertEqual("1", positions.quantities["BTCUSD"])
            event_types = {
                event.event_type for event in EventStore(database).list_for_record("SYSTEM-EXECUTOR")
            }
            self.assertIn("executor.paper_accepted", event_types)

    def test_paper_rejects_replayed_signal_with_a_new_idempotency_key(self) -> None:
        risk, paper_mandate = mandate()
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            guard = ExecutorGuard(database)
            lease = guard.acquire_lease("paper-test", "worker-1", ttl_seconds=120, now=NOW)
            frozen = context(mandate_record=paper_mandate, risk=risk, lease_id=lease.lease_id)
            executor = PaperExecutor(database, guard)
            executor.submit_intent(
                frozen,
                intent("INTENT-FIRST"),
                idempotency_key="paper-signal-first",
                now=NOW,
            )

            with self.assertRaises(DomainBlockedError) as captured:
                executor.submit_intent(
                    frozen,
                    intent("INTENT-REPLAY"),
                    idempotency_key="paper-signal-replay",
                    now=NOW,
                )

            self.assertEqual("duplicate_signal", captured.exception.blocker)
            self.assertEqual("1", executor.positions("paper-test").quantities["BTCUSD"])

    def test_paper_rejects_resulting_position_above_mandate_limit(self) -> None:
        risk, paper_mandate = mandate()
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            guard = ExecutorGuard(database)
            lease = guard.acquire_lease("paper-test", "worker-1", ttl_seconds=120, now=NOW)
            frozen = context(mandate_record=paper_mandate, risk=risk, lease_id=lease.lease_id)
            executor = PaperExecutor(database, guard)
            first = OrderIntent(
                intent_id="INTENT-SIX-ONE",
                instrument="BTCUSD",
                side="buy",
                quantity=Decimal("6"),
                reference_price=Decimal("100"),
                signal_id="SIGNAL-SIX-ONE",
            )
            second = OrderIntent(
                intent_id="INTENT-SIX-TWO",
                instrument="BTCUSD",
                side="buy",
                quantity=Decimal("6"),
                reference_price=Decimal("100"),
                signal_id="SIGNAL-SIX-TWO",
            )
            executor.submit_intent(
                frozen,
                first,
                idempotency_key="paper-position-one",
                now=NOW,
            )

            with self.assertRaises(DomainBlockedError) as captured:
                executor.submit_intent(
                    frozen,
                    second,
                    idempotency_key="paper-position-two",
                    now=NOW,
                )

            self.assertEqual("position_limit_exceeded", captured.exception.blocker)
            self.assertEqual("6", executor.positions("paper-test").quantities["BTCUSD"])

    def test_demo_uncertain_requires_reconciliation_before_new_risk(self) -> None:
        risk, demo_mandate = mandate(
            environment=ExecutionEnvironment.BROKER_DEMO,
            environment_id="demo-test",
            account_id="DEMO-001",
        )
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            guard = ExecutorGuard(database)
            lease = guard.acquire_lease("demo-test", "worker-1", ttl_seconds=120, now=NOW)
            frozen = context(mandate_record=demo_mandate, risk=risk, lease_id=lease.lease_id)
            adapter = DemoAdapter(
                database,
                guard,
                confirmed_demo_account="DEMO-001",
                simulate_next_uncertain=True,
            )
            uncertain = adapter.submit_intent(
                frozen,
                intent(),
                idempotency_key="demo-intent-v1",
                now=NOW,
            )
            retry = adapter.submit_intent(
                frozen,
                intent(),
                idempotency_key="demo-intent-v1",
                now=NOW,
            )
            self.assertIs(uncertain.state, ExecutionResultState.UNCERTAIN)
            self.assertIs(retry.state, ExecutionResultState.DUPLICATE)
            with self.assertRaises(DomainBlockedError):
                adapter.submit_intent(
                    frozen,
                    intent("INTENT-SECOND"),
                    idempotency_key="demo-intent-v2",
                    now=NOW,
                )

            adapter.set_reconciliation_result(
                uncertain.external_reference,
                ExecutionResultState.ACCEPTED,
            )
            reconciled = adapter.reconcile(
                uncertain.external_reference,
                idempotency_key="demo-reconcile-v1",
                now=NOW,
            )
            self.assertIs(reconciled.state, ExecutionResultState.ACCEPTED)

    def test_demo_rejects_replayed_signal_after_reconciliation(self) -> None:
        risk, demo_mandate = mandate(
            environment=ExecutionEnvironment.BROKER_DEMO,
            environment_id="demo-replay",
            account_id="DEMO-REPLAY",
        )
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            guard = ExecutorGuard(database)
            lease = guard.acquire_lease("demo-replay", "worker-1", ttl_seconds=120, now=NOW)
            frozen = context(mandate_record=demo_mandate, risk=risk, lease_id=lease.lease_id)
            adapter = DemoAdapter(database, guard, confirmed_demo_account="DEMO-REPLAY")
            adapter.submit_intent(
                frozen,
                intent("INTENT-DEMO-FIRST"),
                idempotency_key="demo-signal-first",
                now=NOW,
            )

            with self.assertRaises(DomainBlockedError) as captured:
                adapter.submit_intent(
                    frozen,
                    intent("INTENT-DEMO-REPLAY"),
                    idempotency_key="demo-signal-replay",
                    now=NOW,
                )

            self.assertEqual("duplicate_signal", captured.exception.blocker)

    def test_cli_exposes_mandate_paper_heartbeat_reconcile_and_kill_switch(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            repository = RecordRepository(database)
            risk, _event, _created = repository.save(
                allowed_risk(),
                event_type="risk.test_fixture",
                reason="Fixture CLI wykonawcy.",
                outcome="allowed",
                actor="AJ-09",
                idempotency_key="cli-risk-fixture-v1",
            )
            root = Path(state)
            mandate_config = root / "mandate.json"
            mandate_config.write_text(
                json.dumps(
                    {
                        "authorized_by": "Karol",
                        "strategy_id": "STRAT-12345678",
                        "strategy_version": 1,
                        "code_hash": "B" * 64,
                        "environment": "PAPER_CONTINUOUS",
                        "environment_id": "paper-cli",
                        "account_id": None,
                        "instruments": ["BTCUSD"],
                        "limits": {"max_notional": "10000", "max_position_quantity": "10"},
                        "starts_at": "2025-01-02T00:00:00Z",
                        "expires_at": "2025-12-30T00:00:00Z",
                        "stop_conditions": ["kill switch", "stale data"],
                        "max_data_age_seconds": 60,
                    }
                ),
                encoding="utf-8",
            )
            intent_config = root / "intent.json"
            intent_config.write_text(
                json.dumps(
                    {
                        "intent_id": "INTENT-CLI-12345678",
                        "instrument": "BTCUSD",
                        "side": "buy",
                        "quantity": "1",
                        "reference_price": "100",
                        "signal_id": "SIGNAL-CLI-12345678",
                    }
                ),
                encoding="utf-8",
            )
            created = self._cli(
                [
                    "--state-dir", state, "mandate", "create",
                    "--risk-decision-id", risk.record_id,
                    "--config", str(mandate_config),
                    "--idempotency-key", "cli-mandate-v1",
                ]
            )
            mandate_id = created["mandate"]["record_id"]
            lease = self._cli(
                [
                    "--state-dir", state, "executor", "lease",
                    "--environment-id", "paper-cli", "--worker-id", "worker-cli",
                    "--ttl-seconds", "120", "--now", "2025-06-01T12:00:00Z",
                ]
            )["lease"]
            heartbeat = self._cli(
                [
                    "--state-dir", state, "executor", "heartbeat",
                    "--lease-id", lease["lease_id"], "--worker-id", "worker-cli",
                    "--now", "2025-06-01T12:00:01Z",
                ]
            )
            self.assertEqual(lease["lease_id"], heartbeat["heartbeat"]["lease_id"])
            paper = self._cli(
                [
                    "--state-dir", state, "paper", "submit",
                    "--mandate-id", mandate_id, "--worker-id", "worker-cli",
                    "--lease-id", lease["lease_id"],
                    "--data-observed-at", "2025-06-01T11:59:45Z",
                    "--intent", str(intent_config), "--idempotency-key", "cli-paper-intent-v1",
                    "--now", "2025-06-01T12:00:02Z",
                ]
            )
            self.assertEqual("accepted", paper["execution"]["state"])
            self.assertTrue(str(paper["incubation"]["record_id"]).startswith("INCU-"))
            killed = self._cli(
                [
                    "--state-dir", state, "executor", "kill-switch",
                    "--environment-id", "paper-cli", "--reason", "odbiór testowy",
                    "--idempotency-key", "cli-kill-switch-v1",
                    "--now", "2025-06-01T12:00:03Z",
                ]
            )
            self.assertTrue(killed["kill_switch"]["active"])

            # Sam parser i ścieżka reconciliation są testowane na trwałym stanie
            # utworzonym przez adapter, bez połączenia z brokerem.
            _demo_risk, demo_mandate = mandate(
                environment=ExecutionEnvironment.BROKER_DEMO,
                environment_id="demo-cli",
                account_id="DEMO-CLI",
            )
            repository.save(
                demo_mandate,
                event_type="mandate.test_fixture",
                reason="Fixture DEMO CLI.",
                outcome="BROKER_DEMO",
                actor="Karol",
                idempotency_key="cli-demo-mandate-v1",
            )
            demo_lease = self._cli(
                [
                    "--state-dir", state, "executor", "lease",
                    "--environment-id", "demo-cli", "--worker-id", "worker-demo",
                    "--ttl-seconds", "120", "--now", "2025-06-01T12:00:00Z",
                ]
            )["lease"]
            demo = self._cli(
                [
                    "--state-dir", state, "demo", "submit",
                    "--mandate-id", demo_mandate.record_id, "--worker-id", "worker-demo",
                    "--lease-id", demo_lease["lease_id"],
                    "--data-observed-at", "2025-06-01T11:59:45Z",
                    "--intent", str(intent_config), "--idempotency-key", "cli-demo-intent-v1",
                    "--confirmed-demo-account", "DEMO-CLI", "--simulate-uncertain",
                    "--now", "2025-06-01T12:00:02Z",
                ]
            )
            self.assertEqual("uncertain", demo["execution"]["state"])
            reconciled = self._cli(
                [
                    "--state-dir", state, "demo", "reconcile",
                    "--external-reference", demo["execution"]["external_reference"],
                    "--result", "accepted", "--idempotency-key", "cli-demo-reconcile-v1",
                    "--now", "2025-06-01T12:00:03Z",
                ]
            )
            self.assertEqual("accepted", reconciled["reconciliation"]["state"])


if __name__ == "__main__":
    unittest.main()
