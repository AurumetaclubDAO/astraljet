from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from astraljet.domain.enums import ExecutionEnvironment
from astraljet.domain.errors import DomainBlockedError
from astraljet.executor.guard import ExecutorGuard
from astraljet.executor.ports import FrozenContext, OrderIntent
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.event_store import EventStore

from tests.executor_support import mandate


NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def context(*, mandate_record, risk, lease_id: str, worker_id: str = "worker-1", observed_at: str = "2025-06-01T11:59:30Z") -> FrozenContext:
    return FrozenContext(
        mandate=mandate_record,
        risk_decision=risk,
        strategy_id=mandate_record.strategy_id,
        strategy_version=mandate_record.strategy_version,
        code_hash=mandate_record.code_hash,
        environment=mandate_record.environment,
        environment_id=mandate_record.environment_id,
        worker_id=worker_id,
        lease_id=lease_id,
        data_observed_at=observed_at,
    )


def intent(intent_id: str = "INTENT-12345678") -> OrderIntent:
    return OrderIntent(
        intent_id=intent_id,
        instrument="BTCUSD",
        side="buy",
        quantity=Decimal("1"),
        reference_price=Decimal("100"),
        signal_id="SIGNAL-12345678",
    )


class ExecutorGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database.from_state_dir(self.temp_dir.name)
        self.database.initialize()
        self.guard = ExecutorGuard(self.database)
        self.risk, self.mandate = mandate()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_only_one_worker_can_hold_active_lease(self) -> None:
        lease = self.guard.acquire_lease("paper-test", "worker-1", ttl_seconds=120, now=NOW)
        with self.assertRaises(DomainBlockedError):
            self.guard.acquire_lease("paper-test", "worker-2", ttl_seconds=120, now=NOW)
        heartbeat = self.guard.heartbeat(lease.lease_id, "worker-1", now=NOW)
        self.assertEqual(lease.lease_id, heartbeat.lease_id)

    def test_stale_data_kill_switch_and_limit_violation_fail_closed(self) -> None:
        lease = self.guard.acquire_lease("paper-test", "worker-1", ttl_seconds=120, now=NOW)
        with self.assertRaises(DomainBlockedError):
            self.guard.authorize(
                context=context(
                    mandate_record=self.mandate,
                    risk=self.risk,
                    lease_id=lease.lease_id,
                    observed_at="2025-06-01T11:00:00Z",
                ),
                intent=intent(),
                now=NOW,
            )

        too_large = OrderIntent(
            intent_id="INTENT-TOO-LARGE",
            instrument="BTCUSD",
            side="buy",
            quantity=Decimal("1000"),
            reference_price=Decimal("100"),
            signal_id="SIGNAL-12345678",
        )
        with self.assertRaises(DomainBlockedError):
            self.guard.authorize(
                context=context(mandate_record=self.mandate, risk=self.risk, lease_id=lease.lease_id),
                intent=too_large,
                now=NOW,
            )

        self.guard.activate_kill_switch(
            "paper-test",
            reason="test",
            idempotency_key="kill-switch-test",
            now=NOW,
        )
        with self.assertRaises(DomainBlockedError):
            self.guard.authorize(
                context=context(mandate_record=self.mandate, risk=self.risk, lease_id=lease.lease_id),
                intent=intent(),
                now=NOW,
            )

    def test_wrong_environment_or_expired_mandate_is_blocked(self) -> None:
        lease = self.guard.acquire_lease("paper-test", "worker-1", ttl_seconds=120, now=NOW)
        wrong = context(mandate_record=self.mandate, risk=self.risk, lease_id=lease.lease_id)
        wrong = FrozenContext(
            mandate=wrong.mandate,
            risk_decision=wrong.risk_decision,
            strategy_id=wrong.strategy_id,
            strategy_version=wrong.strategy_version,
            code_hash=wrong.code_hash,
            environment=ExecutionEnvironment.BROKER_DEMO,
            environment_id=wrong.environment_id,
            worker_id=wrong.worker_id,
            lease_id=wrong.lease_id,
            data_observed_at=wrong.data_observed_at,
        )
        with self.assertRaises(DomainBlockedError):
            self.guard.authorize(context=wrong, intent=intent(), now=NOW)
        with self.assertRaises(DomainBlockedError):
            self.guard.authorize(
                context=context(mandate_record=self.mandate, risk=self.risk, lease_id=lease.lease_id),
                intent=intent(),
                now=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_non_finite_order_values_fail_closed(self) -> None:
        lease = self.guard.acquire_lease("paper-test", "worker-1", ttl_seconds=120, now=NOW)
        invalid = OrderIntent(
            intent_id="INTENT-NAN",
            instrument="BTCUSD",
            side="buy",
            quantity=Decimal("NaN"),
            reference_price=Decimal("100"),
            signal_id="SIGNAL-NAN",
        )

        with self.assertRaises(DomainBlockedError) as captured:
            self.guard.authorize(
                context=context(mandate_record=self.mandate, risk=self.risk, lease_id=lease.lease_id),
                intent=invalid,
                now=NOW,
            )

        self.assertEqual("invalid_order_values", captured.exception.blocker)

    def test_denial_is_persisted_as_actionable_event(self) -> None:
        lease = self.guard.acquire_lease("paper-test", "worker-1", ttl_seconds=120, now=NOW)
        with self.assertRaises(DomainBlockedError) as captured:
            self.guard.authorize(
                context=context(
                    mandate_record=self.mandate,
                    risk=self.risk,
                    lease_id=lease.lease_id,
                    observed_at="2025-06-01T11:00:00Z",
                ),
                intent=intent(),
                now=NOW,
            )
        events = EventStore(self.database).list_for_record("SYSTEM-EXECUTOR")
        blocked = [event for event in events if event.event_type == "executor.blocked"]

        self.assertTrue(blocked)
        self.assertEqual(captured.exception.blocker, blocked[-1].payload["blocker"])
        self.assertEqual(captured.exception.owner, blocked[-1].payload["owner"])
        self.assertEqual(
            captured.exception.allowed_next_action,
            blocked[-1].payload["allowed_next_action"],
        )


if __name__ == "__main__":
    unittest.main()
