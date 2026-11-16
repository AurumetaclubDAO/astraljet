"""Wspólny model danych: rachunek, żądanie (order request), deal, pozycja.

Rozróżnienie:
- PLANOWANE: `plan.TradePlan` — nie trafiło do brokera,
- ŻĄDANE: `OrderRequest` + `RequestState` — wysłane lub w drodze; wysłanie nie jest wykonaniem,
- POTWIERDZONE: `Deal` i `Position` odczytane od brokera (tu: symulatora).

Pozycje wylicza `PositionBook` z deali, wspólnie dla symulatora i analityki,
z obsługą rachunku NETTING i HEDGING oraz częściowych zamknięć.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from .instruments import D, Side
from .market import DataMode, utc


class MarginMode(StrEnum):
    NETTING = "NETTING"
    HEDGING = "HEDGING"


class RequestKind(StrEnum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    MODIFY_SLTP = "MODIFY_SLTP"


class RequestState(StrEnum):
    SENT = "SENT"                    # zapisane i przekazane do adaptera, brak odpowiedzi
    ACCEPTED = "ACCEPTED"            # broker przyjął, brak (pełnego) wykonania
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"                # potwierdzone dealami / zmianą pozycji
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"          # timeout/brak odpowiedzi: wynik nieznany, NIE ponawiać w ciemno
    NOT_FOUND = "NOT_FOUND"          # uzgodnienie potwierdziło brak żądania u brokera
    NOT_SENT = "NOT_SENT"            # zablokowane lokalnie albo brak połączenia przed przekazaniem
    CANCELLED = "CANCELLED"

    @property
    def terminal(self) -> bool:
        return self in {
            RequestState.FILLED, RequestState.PARTIALLY_FILLED, RequestState.REJECTED,
            RequestState.NOT_FOUND, RequestState.NOT_SENT, RequestState.CANCELLED,
        }


class DealEntry(StrEnum):
    IN = "IN"
    OUT = "OUT"


class DealType(StrEnum):
    TRADE = "TRADE"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    FEE = "FEE"            # osobna operacja kosztowa brokera (nie przypisywana automatycznie do transakcji)


@dataclass(frozen=True, slots=True)
class OrderRequest:
    request_id: str
    account_id: str
    kind: RequestKind
    symbol: str
    side: Side | None = None
    volume: Decimal | None = None
    price: Decimal | None = None
    sl: Decimal | None = None
    tp: Decimal | None = None
    position_id: str | None = None
    origin: str = "manual"   # manual / trigger:<id> / protection:<rule>
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "account_id": self.account_id,
            "kind": self.kind.value,
            "symbol": self.symbol,
            "side": None if self.side is None else self.side.value,
            "volume": None if self.volume is None else str(self.volume),
            "price": None if self.price is None else str(self.price),
            "sl": None if self.sl is None else str(self.sl),
            "tp": None if self.tp is None else str(self.tp),
            "position_id": self.position_id,
            "origin": self.origin,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OrderRequest":
        def dec(key: str) -> Decimal | None:
            return None if data.get(key) is None else Decimal(data[key])

        return cls(
            request_id=data["request_id"],
            account_id=data["account_id"],
            kind=RequestKind(data["kind"]),
            symbol=data["symbol"],
            side=None if data.get("side") is None else Side(data["side"]),
            volume=dec("volume"),
            price=dec("price"),
            sl=dec("sl"),
            tp=dec("tp"),
            position_id=data.get("position_id"),
            origin=data.get("origin", "manual"),
            created_at=data.get("created_at", ""),
        )


@dataclass(frozen=True, slots=True)
class Deal:
    deal_id: str
    account_id: str
    time: datetime
    type: DealType
    symbol: str = ""
    side: Side | None = None
    entry: DealEntry | None = None
    volume: Decimal = Decimal(0)
    price: Decimal = Decimal(0)
    position_id: str | None = None
    request_id: str | None = None
    profit: Decimal = Decimal(0)
    commission: Decimal = Decimal(0)
    swap: Decimal = Decimal(0)
    fee: Decimal = Decimal(0)
    amount: Decimal = Decimal(0)   # dla DEPOSIT/WITHDRAWAL/FEE: kwota w walucie rachunku (ze znakiem)
    source: str = "SIMULATED"

    @property
    def net(self) -> Decimal:
        if self.type is DealType.TRADE:
            return D(self.profit) + D(self.commission) + D(self.swap) + D(self.fee)
        return D(self.amount)

    def to_dict(self) -> dict:
        return {
            "deal_id": self.deal_id,
            "account_id": self.account_id,
            "time": utc(self.time).isoformat(),
            "type": self.type.value,
            "symbol": self.symbol,
            "side": None if self.side is None else self.side.value,
            "entry": None if self.entry is None else self.entry.value,
            "volume": str(self.volume),
            "price": str(self.price),
            "position_id": self.position_id,
            "request_id": self.request_id,
            "profit": str(self.profit),
            "commission": str(self.commission),
            "swap": str(self.swap),
            "fee": str(self.fee),
            "amount": str(self.amount),
            "net": str(self.net),
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class Position:
    position_id: str
    account_id: str
    symbol: str
    side: Side
    volume: Decimal
    open_price: Decimal
    opened_at: datetime
    sl: Decimal | None = None
    tp: Decimal | None = None
    sl_confirmed_at: datetime | None = None
    source: str = "SIMULATED"

    def to_dict(self) -> dict:
        return {
            "position_id": self.position_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "volume": str(self.volume),
            "open_price": str(self.open_price),
            "opened_at": utc(self.opened_at).isoformat(),
            "sl": None if self.sl is None else str(self.sl),
            "tp": None if self.tp is None else str(self.tp),
            "sl_confirmed_at": None if self.sl_confirmed_at is None else utc(self.sl_confirmed_at).isoformat(),
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    account_id: str
    mode: DataMode
    currency: str
    margin_mode: MarginMode
    balance: Decimal | None
    equity: Decimal | None
    margin: Decimal | None
    as_of: datetime
    source: str

    def to_dict(self) -> dict:
        def s(value: Decimal | None) -> str | None:
            return None if value is None else str(value)

        return {
            "account_id": self.account_id,
            "mode": self.mode.value,
            "currency": self.currency,
            "margin_mode": self.margin_mode.value,
            "balance": s(self.balance),
            "equity": s(self.equity),
            "margin": s(self.margin),
            "as_of": utc(self.as_of).isoformat(),
            "source": self.source,
        }


@dataclass(slots=True)
class FillOutcome:
    """Skutek jednego wykonania w księdze pozycji (dla deali IN/OUT)."""

    deals: list[Deal]
    opened: Position | None = None
    closed_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PositionBook:
    """Księga pozycji wyliczana z wykonań. NETTING: jedna pozycja na symbol;
    przeciwny kierunek zmniejsza, zamyka lub odwraca pozycję. HEDGING: każde
    otwarcie to osobna pozycja, zamknięcie musi wskazać position_id."""

    margin_mode: MarginMode
    positions: dict[str, Position] = field(default_factory=dict)

    def by_symbol(self, symbol: str) -> list[Position]:
        return [p for p in self.positions.values() if p.symbol == symbol]

    def fill(
        self,
        *,
        account_id: str,
        symbol: str,
        side: Side,
        volume: Decimal,
        price: Decimal,
        time: datetime,
        new_position_id: str,
        deal_id_prefix: str,
        profit_of: "callable",
        request_id: str | None,
        target_position_id: str | None = None,
        sl: Decimal | None = None,
        tp: Decimal | None = None,
        commission_per_lot_side: Decimal = Decimal(0),
    ) -> FillOutcome:
        volume = D(volume)
        outcome = FillOutcome(deals=[])
        remaining = volume
        counter = 0

        def deal_id() -> str:
            nonlocal counter
            counter += 1
            return f"{deal_id_prefix}-{counter}"

        def commission(vol: Decimal) -> Decimal:
            return -(D(commission_per_lot_side) * vol)

        # Redukcja istniejącej pozycji: netting automatycznie, hedging tylko wskazana.
        targets: list[Position] = []
        if target_position_id is not None:
            target = self.positions.get(target_position_id)
            if target is None:
                raise KeyError(f"Brak pozycji {target_position_id}")
            if target.side is side:
                raise ValueError("Zamknięcie musi mieć kierunek przeciwny do pozycji")
            targets = [target]
        elif self.margin_mode is MarginMode.NETTING:
            targets = [p for p in self.by_symbol(symbol) if p.side is not side]

        for pos in targets:
            if remaining <= 0:
                break
            closed = min(remaining, pos.volume)
            outcome.deals.append(Deal(
                deal_id=deal_id(), account_id=account_id, time=time, type=DealType.TRADE, symbol=symbol,
                side=side, entry=DealEntry.OUT, volume=closed, price=price, position_id=pos.position_id,
                request_id=request_id, profit=profit_of(pos.side, closed, pos.open_price, price),
                commission=commission(closed),
            ))
            remaining -= closed
            if closed == pos.volume:
                del self.positions[pos.position_id]
                outcome.closed_ids.append(pos.position_id)
            else:
                self.positions[pos.position_id] = replace(pos, volume=pos.volume - closed)

        if target_position_id is not None:
            if remaining > 0:
                raise ValueError("Wolumen zamknięcia większy niż pozycja")
            return outcome

        if remaining > 0:
            # NETTING: dołożenie do istniejącej pozycji w tym samym kierunku (średnia cena).
            same = [p for p in self.by_symbol(symbol) if p.side is side] if self.margin_mode is MarginMode.NETTING else []
            if same:
                pos = same[0]
                total = pos.volume + remaining
                avg = (pos.open_price * pos.volume + D(price) * remaining) / total
                self.positions[pos.position_id] = replace(pos, volume=total, open_price=avg)
                position_id = pos.position_id
            else:
                position_id = new_position_id
                opened = Position(position_id=position_id, account_id=account_id, symbol=symbol, side=side,
                                  volume=remaining, open_price=D(price), opened_at=time, sl=sl, tp=tp,
                                  sl_confirmed_at=time if sl is not None else None)
                self.positions[position_id] = opened
                outcome.opened = opened
            outcome.deals.append(Deal(
                deal_id=deal_id(), account_id=account_id, time=time, type=DealType.TRADE, symbol=symbol,
                side=side, entry=DealEntry.IN, volume=remaining, price=price, position_id=position_id,
                request_id=request_id, commission=commission(remaining),
            ))
        return outcome
