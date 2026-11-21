"""Symulowany broker (adapter SIMULATED). Brak sieci, brak MetaTrader5, brak rachunku.

Zachowania do testów i demonstracji ustawia się skryptem: wykonanie, odrzucenie,
częściowe wykonanie (reszta anulowana), timeout po wykonaniu u brokera, timeout bez
dotarcia żądania. Te same `request_id` są idempotentne: drugi send nie wykonuje
niczego ponownie, tylko zwraca zapisany stan.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Callable

from .instruments import D, FxTable, InstrumentSpec, Side
from .market import DataMode, Quote
from .model import (
    AccountSnapshot,
    Deal,
    DealType,
    MarginMode,
    OrderRequest,
    Position,
    PositionBook,
    RequestKind,
    RequestState,
)
from .plan import check_stop_levels


class AdapterTimeout(Exception):
    """Brak odpowiedzi w limicie czasu. Wynik po stronie brokera NIEZNANY."""


class AdapterUnavailable(Exception):
    """Brak połączenia stwierdzony PRZED przekazaniem żądania."""


class Behaviour(StrEnum):
    FILL = "FILL"
    REJECT = "REJECT"
    PARTIAL = "PARTIAL"
    TIMEOUT_AFTER_EXECUTION = "TIMEOUT_AFTER_EXECUTION"
    TIMEOUT_NOT_RECEIVED = "TIMEOUT_NOT_RECEIVED"


@dataclass(frozen=True, slots=True)
class ScriptStep:
    behaviour: Behaviour
    reason: str = ""
    fraction: Decimal = Decimal("0.5")


@dataclass(frozen=True, slots=True)
class BrokerOrderStatus:
    request_id: str
    state: RequestState
    filled_volume: Decimal = Decimal(0)
    requested_volume: Decimal | None = None
    price: Decimal | None = None
    position_id: str | None = None
    message: str = ""
    deal_ids: tuple[str, ...] = ()
    final: bool = True

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "state": self.state.value,
            "filled_volume": str(self.filled_volume),
            "requested_volume": None if self.requested_volume is None else str(self.requested_volume),
            "price": None if self.price is None else str(self.price),
            "position_id": self.position_id,
            "message": self.message,
            "deal_ids": list(self.deal_ids),
            "final": self.final,
        }


@dataclass(slots=True)
class SimulatedBroker:
    account_id: str
    currency: str
    margin_mode: MarginMode
    specs: dict[str, InstrumentSpec]
    fx: FxTable
    now: Callable[[], datetime]
    balance: Decimal = Decimal(0)
    commission_per_lot_side: Decimal = Decimal(0)
    leverage: Decimal = Decimal(100)
    mode: DataMode = DataMode.SIMULATED
    connected: bool = True
    quotes: dict[str, Quote] = field(default_factory=dict)
    script: deque = field(default_factory=deque)
    book: PositionBook | None = None
    deals: list[Deal] = field(default_factory=list)
    _orders: dict[str, BrokerOrderStatus] = field(default_factory=dict)
    _seq: int = 0

    def __post_init__(self) -> None:
        if self.mode is not DataMode.SIMULATED:
            raise ValueError("SimulatedBroker działa wyłącznie w trybie SIMULATED")
        if self.book is None:
            self.book = PositionBook(self.margin_mode)

    # --- dane rynkowe -----------------------------------------------------
    def set_quote(self, quote: Quote) -> list[Deal]:
        if quote.mode is not DataMode.SIMULATED:
            raise ValueError("Symulator przyjmuje wyłącznie kwotowania SIMULATED")
        self.quotes[quote.symbol] = quote
        return self._check_stops(quote)

    # --- operacje rachunku ------------------------------------------------
    def deposit(self, amount: Decimal, time: datetime) -> Deal:
        amount = D(amount)
        deal = Deal(deal_id=self._next("BAL"), account_id=self.account_id, time=time,
                    type=DealType.DEPOSIT if amount >= 0 else DealType.WITHDRAWAL, amount=amount,
                    source="SIMULATED")
        self.deals.append(deal)
        self.balance += amount
        return deal

    # --- port brokera -----------------------------------------------------
    def send(self, request: OrderRequest) -> BrokerOrderStatus:
        if not self.connected:
            raise AdapterUnavailable("Brak połączenia z symulatorem; żądanie nie zostało przekazane.")
        existing = self._orders.get(request.request_id)
        if existing is not None:
            return existing
        step = self.script.popleft() if self.script else ScriptStep(Behaviour.FILL)
        if step.behaviour is Behaviour.TIMEOUT_NOT_RECEIVED:
            raise AdapterTimeout("Brak odpowiedzi; żądanie nie dotarło do symulatora.")
        if step.behaviour is Behaviour.REJECT:
            status = BrokerOrderStatus(request.request_id, RequestState.REJECTED,
                                       requested_volume=request.volume,
                                       message=step.reason or "Odrzucone przez symulator (scenariusz).")
        else:
            status = self._execute(request, step)
        self._orders[request.request_id] = status
        if step.behaviour is Behaviour.TIMEOUT_AFTER_EXECUTION:
            raise AdapterTimeout("Brak odpowiedzi w limicie czasu (symulator wykonał żądanie).")
        return status

    def lookup(self, request_id: str) -> BrokerOrderStatus | None:
        if not self.connected:
            raise AdapterUnavailable("Brak połączenia; nie można uzgodnić stanu.")
        return self._orders.get(request_id)

    def positions(self) -> list[Position]:
        if not self.connected:
            raise AdapterUnavailable("Brak połączenia; pozycje nieznane.")
        return sorted(self.book.positions.values(), key=lambda p: p.position_id)

    def history(self) -> list[Deal]:
        if not self.connected:
            raise AdapterUnavailable("Brak połączenia; historia nieznana.")
        return list(self.deals)

    def account(self) -> AccountSnapshot:
        if not self.connected:
            raise AdapterUnavailable("Brak połączenia; rachunek nieznany.")
        floating_total: Decimal | None = Decimal(0)
        margin_total: Decimal | None = Decimal(0)
        for pos in self.book.positions.values():
            spec = self.specs[pos.symbol]
            quote = self.quotes.get(pos.symbol)
            if quote is None:
                floating_total = None
                margin_total = None
                break
            close = quote.bid if pos.side is Side.BUY else quote.ask
            pl, _ = self.fx.convert(spec.profit(pos.side, pos.volume, pos.open_price, close),
                                    spec.profit_currency, self.currency)
            notional, _ = self.fx.convert(D(pos.volume) * D(spec.contract_size) * D(pos.open_price),
                                          spec.profit_currency, self.currency)
            if pl is None or notional is None:
                floating_total = None
                margin_total = None
                break
            floating_total += pl
            margin_total += notional / D(self.leverage)
        equity = None if floating_total is None else self.balance + floating_total
        return AccountSnapshot(self.account_id, DataMode.SIMULATED, self.currency, self.margin_mode,
                               self.balance, equity, margin_total, self.now(),
                               f"SIMULATED: model symulatora, dźwignia 1:{self.leverage}")

    # --- wewnętrzne -------------------------------------------------------
    def _next(self, prefix: str) -> str:
        self._seq += 1
        return f"SIM-{prefix}-{self._seq}"

    def _execute(self, request: OrderRequest, step: ScriptStep) -> BrokerOrderStatus:
        spec = self.specs.get(request.symbol)
        if spec is None:
            return BrokerOrderStatus(request.request_id, RequestState.REJECTED, message="Nieznany symbol.")
        quote = self.quotes.get(request.symbol)
        if quote is None:
            return BrokerOrderStatus(request.request_id, RequestState.REJECTED, message="Brak kwotowania w symulatorze.")
        if request.kind is RequestKind.MODIFY_SLTP:
            return self._modify(request, spec, quote)
        if request.kind is RequestKind.OPEN and request.price is not None:
            return BrokerOrderStatus(request.request_id, RequestState.REJECTED,
                                     message="Zlecenia oczekujące nie są obsługiwane przez symulator v0.1.")
        side = request.side
        volume = D(request.volume)
        check = spec.check_volume(volume)
        if not check.ok:
            return BrokerOrderStatus(request.request_id, RequestState.REJECTED, requested_volume=volume, message=check.reason)
        price = D(quote.ask) if side is Side.BUY else D(quote.bid)
        if request.kind is RequestKind.OPEN:
            close_ref = D(quote.bid) if side is Side.BUY else D(quote.ask)
            errors = check_stop_levels(spec, side, close_ref, request.sl, request.tp)
            if errors:
                return BrokerOrderStatus(request.request_id, RequestState.REJECTED, requested_volume=volume,
                                         message="; ".join(errors))
        if request.kind is RequestKind.CLOSE:
            target = self.book.positions.get(request.position_id or "")
            if target is None:
                return BrokerOrderStatus(request.request_id, RequestState.REJECTED, message="Pozycja nie istnieje.")
            if volume > target.volume:
                return BrokerOrderStatus(request.request_id, RequestState.REJECTED,
                                         message="Wolumen zamknięcia większy niż pozycja.")
        filled = volume
        state = RequestState.FILLED
        message = "Wykonane w symulatorze."
        if step.behaviour is Behaviour.PARTIAL:
            partial = spec.floor_volume(volume * D(step.fraction))
            if partial is None or partial >= volume:
                return BrokerOrderStatus(request.request_id, RequestState.REJECTED, requested_volume=volume,
                                         message="Częściowe wykonanie niemożliwe dla tego wolumenu.")
            filled = partial
            state = RequestState.PARTIALLY_FILLED
            message = f"Częściowo wykonane {filled} z {volume}; reszta anulowana (IOC)."
        outcome = self.book.fill(
            account_id=self.account_id, symbol=request.symbol, side=side, volume=filled, price=price,
            time=self.now(), new_position_id=self._next("POS"), deal_id_prefix=self._next("DEAL"),
            profit_of=spec.profit, request_id=request.request_id,
            target_position_id=request.position_id if request.kind is RequestKind.CLOSE else None,
            sl=request.sl, tp=request.tp, commission_per_lot_side=self.commission_per_lot_side,
        )
        self._book_deals(outcome.deals, spec)
        position_id = outcome.opened.position_id if outcome.opened else (outcome.deals[-1].position_id if outcome.deals else None)
        return BrokerOrderStatus(request.request_id, state, filled_volume=filled, requested_volume=volume,
                                 price=price, position_id=position_id, message=message,
                                 deal_ids=tuple(d.deal_id for d in outcome.deals))

    def _book_deals(self, deals: list[Deal], spec: InstrumentSpec) -> list[Deal]:
        booked_all: list[Deal] = []
        for deal in deals:
            profit, _ = self.fx.convert(deal.profit, spec.profit_currency, self.currency)
            if profit is None:
                raise ValueError(f"Brak kursu {spec.profit_currency}->{self.currency} do zaksięgowania wyniku")
            booked = replace(deal, profit=profit)
            self.deals.append(booked)
            self.balance += booked.net
            booked_all.append(booked)
        return booked_all

    def _modify(self, request: OrderRequest, spec: InstrumentSpec, quote: Quote) -> BrokerOrderStatus:
        pos = self.book.positions.get(request.position_id or "")
        if pos is None:
            return BrokerOrderStatus(request.request_id, RequestState.REJECTED, message="Pozycja nie istnieje.")
        close_ref = D(quote.bid) if pos.side is Side.BUY else D(quote.ask)
        errors = check_stop_levels(spec, pos.side, close_ref, request.sl, request.tp)
        freeze = spec.from_points(spec.freeze_level_points)
        if pos.sl is not None and freeze > 0 and abs(close_ref - pos.sl) <= freeze:
            errors.append("Obecny SL w strefie freeze level; modyfikacja zablokowana.")
        if errors:
            return BrokerOrderStatus(request.request_id, RequestState.REJECTED, position_id=pos.position_id,
                                     message="; ".join(errors))
        self.book.positions[pos.position_id] = replace(pos, sl=request.sl, tp=request.tp,
                                                      sl_confirmed_at=self.now() if request.sl is not None else None)
        return BrokerOrderStatus(request.request_id, RequestState.FILLED, position_id=pos.position_id,
                                 price=request.sl, message="SL/TP zmienione w symulatorze.")

    def _check_stops(self, quote: Quote) -> list[Deal]:
        created: list[Deal] = []
        spec = self.specs.get(quote.symbol)
        if spec is None:
            return created
        for pos in list(self.book.positions.values()):
            if pos.symbol != quote.symbol:
                continue
            close = D(quote.bid) if pos.side is Side.BUY else D(quote.ask)
            hit = None
            if pos.sl is not None and (close - pos.sl) * pos.side.sign <= 0:
                hit = "SL"
            elif pos.tp is not None and (close - pos.tp) * pos.side.sign >= 0:
                hit = "TP"
            if hit is None:
                continue
            # Zamknięcie po bieżącej cenie (luka cenowa = poślizg względem poziomu).
            outcome = self.book.fill(
                account_id=self.account_id, symbol=pos.symbol, side=pos.side.opposite, volume=pos.volume,
                price=close, time=quote.time, new_position_id=self._next("POS"),
                deal_id_prefix=self._next(f"DEAL-{hit}"), profit_of=spec.profit, request_id=None,
                target_position_id=pos.position_id, commission_per_lot_side=self.commission_per_lot_side,
            )
            created.extend(self._book_deals(outcome.deals, spec))
        return created
