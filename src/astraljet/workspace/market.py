"""Kwotowania, świece, tryb danych i świeżość.

Słownik stanów jest wspólny z Obserwatorium: CONFIRMED / UNCONFIRMED / MISSING.
Tryb danych (SIMULATED / DEMO / LIVE) jest częścią każdego kwotowania i każdej serii.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum

from .instruments import D, InstrumentSpec


class DataMode(StrEnum):
    SIMULATED = "SIMULATED"
    DEMO = "DEMO"
    LIVE = "LIVE"


class Freshness(StrEnum):
    CONFIRMED = "CONFIRMED"
    UNCONFIRMED = "UNCONFIRMED"
    MISSING = "MISSING"


class Timeframe(StrEnum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

    @property
    def seconds(self) -> int:
        return {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}[self.value]


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Czas bez strefy czasowej")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class Quote:
    symbol: str
    bid: Decimal
    ask: Decimal
    time: datetime
    source: str
    mode: DataMode

    def __post_init__(self) -> None:
        if D(self.ask) < D(self.bid):
            raise ValueError("Ask poniżej Bid")
        utc(self.time)

    def spread_points(self, spec: InstrumentSpec) -> Decimal:
        return spec.to_points(D(self.ask) - D(self.bid))

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bid": str(self.bid),
            "ask": str(self.ask),
            "time": utc(self.time).isoformat(),
            "source": self.source,
            "mode": self.mode.value,
        }


@dataclass(frozen=True, slots=True)
class QuoteStatus:
    state: Freshness
    age_s: float | None
    reason: str


def assess_quote(quote: Quote | None, now: datetime, ttl_s: float, connected: bool = True) -> QuoteStatus:
    """Świeżość kwotowania. Brak połączenia nie zeruje ceny, tylko obniża status."""
    if quote is None:
        return QuoteStatus(Freshness.MISSING, None, "Brak kwotowania.")
    age = (utc(now) - utc(quote.time)).total_seconds()
    if not connected:
        return QuoteStatus(Freshness.UNCONFIRMED, round(age, 1), "Brak połączenia ze źródłem; ostatnie znane kwotowanie.")
    if age < -5:
        return QuoteStatus(Freshness.UNCONFIRMED, round(age, 1), "Czas kwotowania z przyszłości.")
    if age > ttl_s:
        return QuoteStatus(Freshness.UNCONFIRMED, round(age, 1), f"Kwotowanie starsze niż {ttl_s:g} s.")
    return QuoteStatus(Freshness.CONFIRMED, round(age, 1), "Świeże kwotowanie.")


@dataclass(frozen=True, slots=True)
class Candle:
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def to_dict(self) -> dict:
        return {
            "t": utc(self.time).isoformat(),
            "o": str(self.open),
            "h": str(self.high),
            "l": str(self.low),
            "c": str(self.close),
        }


@dataclass(slots=True)
class CandleSeries:
    symbol: str
    timeframe: Timeframe
    source: str
    mode: DataMode
    candles: list[Candle] = field(default_factory=list)

    def closed(self, now: datetime) -> list[Candle]:
        """Świece zamknięte względem `now`; świeca w trakcie nie jest sygnałem."""
        limit = utc(now) - timedelta(seconds=self.timeframe.seconds)
        return [c for c in self.candles if utc(c.time) <= limit]

    def update_with_price(self, price: Decimal, at: datetime) -> None:
        """Aktualizuje bieżącą świecę albo otwiera nową na granicy interwału."""
        at = utc(at)
        start = bar_start(at, self.timeframe)
        if self.candles and utc(self.candles[-1].time) == start:
            last = self.candles[-1]
            self.candles[-1] = Candle(last.time, last.open, max(last.high, price), min(last.low, price), price)
        else:
            self.candles.append(Candle(start, price, price, price, price))


def bar_start(at: datetime, timeframe: Timeframe) -> datetime:
    epoch = int(utc(at).timestamp())
    return datetime.fromtimestamp(epoch - epoch % timeframe.seconds, tz=timezone.utc)


def synthetic_series(
    spec: InstrumentSpec,
    timeframe: Timeframe,
    end: datetime,
    count: int,
    start_price: Decimal,
    seed: int,
    volatility_points: int = 60,
) -> CandleSeries:
    """Deterministyczny spacer losowy oznaczony jako SIMULATED. Nie jest danymi rynkowymi."""
    rng = random.Random(seed)
    point = spec.point
    last_start = bar_start(end, timeframe)
    first = last_start - timedelta(seconds=timeframe.seconds * (count - 1))
    price = D(start_price)
    candles: list[Candle] = []
    for i in range(count):
        t = first + timedelta(seconds=timeframe.seconds * i)
        o = price
        moves = [o]
        for _ in range(4):
            price = spec.normalize_price(price + point * rng.randint(-volatility_points, volatility_points))
            moves.append(price)
        c = price
        h = max(moves) + spec.tick * rng.randint(0, 3)
        lo = min(moves) - spec.tick * rng.randint(0, 3)
        candles.append(Candle(t, o, spec.normalize_price(h), spec.normalize_price(lo), c))
    return CandleSeries(spec.symbol, timeframe, f"SIMULATED: syntetyczny spacer losowy seed={seed}", DataMode.SIMULATED, candles)
