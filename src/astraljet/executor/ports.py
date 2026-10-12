from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from astraljet.domain.enums import ExecutionEnvironment, ExecutionResultState
from astraljet.domain.records import MandateRecord, RiskDecisionRecord


@dataclass(frozen=True, slots=True)
class FrozenContext:
    mandate: MandateRecord
    risk_decision: RiskDecisionRecord
    strategy_id: str
    strategy_version: int
    code_hash: str
    environment: ExecutionEnvironment
    environment_id: str
    worker_id: str
    lease_id: str
    data_observed_at: str


@dataclass(frozen=True, slots=True)
class OrderIntent:
    intent_id: str
    instrument: str
    side: str
    quantity: Decimal
    reference_price: Decimal
    signal_id: str


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    state: ExecutionResultState
    intent_id: str
    external_reference: str | None
    message: str
    previous_state: ExecutionResultState | None = None


@dataclass(frozen=True, slots=True)
class Health:
    state: ExecutionResultState
    message: str


@dataclass(frozen=True, slots=True)
class Lease:
    environment_id: str
    lease_id: str
    worker_id: str
    expires_at: str
    heartbeat_at: str


@dataclass(frozen=True, slots=True)
class Heartbeat:
    environment_id: str
    lease_id: str
    worker_id: str
    expires_at: str
    heartbeat_at: str


@dataclass(frozen=True, slots=True)
class KillSwitchReceipt:
    environment_id: str
    active: bool
    reason: str
    activated_at: str
    duplicate: bool = False


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    environment_id: str
    quantities: dict[str, str]


class ExecutorPort(Protocol):
    def health(self, mandate: MandateRecord) -> Health: ...

    def submit_intent(
        self,
        context: FrozenContext,
        intent: OrderIntent,
        *,
        idempotency_key: str,
        now: object,
    ) -> ExecutionReceipt: ...

    def positions(self, environment_id: str) -> PositionSnapshot: ...
