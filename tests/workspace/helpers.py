from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from astraljet.workspace.instruments import FxTable, Side, eurusd_example
from astraljet.workspace.market import DataMode, Quote
from astraljet.workspace.model import MarginMode
from astraljet.workspace.simulator import SimulatedBroker

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, start: datetime = T0) -> None:
        self.t = start

    def __call__(self) -> datetime:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += timedelta(seconds=seconds)


def quote(symbol: str, bid: str, ask: str, at: datetime = T0) -> Quote:
    return Quote(symbol, Decimal(bid), Decimal(ask), at, "test", DataMode.SIMULATED)


def broker(margin_mode: MarginMode = MarginMode.HEDGING, clock: Clock | None = None, stops: int = 0,
           commission: str = "0") -> tuple[SimulatedBroker, Clock]:
    clock = clock or Clock()
    spec = eurusd_example(stops_level_points=stops)
    b = SimulatedBroker("SIM-T", "USD", margin_mode, {"EURUSD": spec}, FxTable(), clock,
                        commission_per_lot_side=Decimal(commission))
    b.deposit(Decimal("10000"), clock() - timedelta(hours=1))
    b.set_quote(quote("EURUSD", "1.15430", "1.15438", clock()))
    return b, clock


BUY, SELL = Side.BUY, Side.SELL
