"""Specyfikacja instrumentu, jednostki cenowe, wolumen i przeliczenia walut.

Point, pip i tick to różne pojęcia:
- point: najmniejsza jednostka zapisu ceny (10**-digits),
- tick: najmniejsza dozwolona zmiana ceny (może być wielokrotnością point, np. indeksy),
- pip: konwencja rynku FX; dla kwotowań 5/3-cyfrowych 10 point, w innych przypadkach
  musi być podana jawnie albo równa się point.

Wartości pieniężne są liczone w walucie zysku instrumentu, a do waluty rachunku
przeliczane wyłącznie jawnym kursem z podanym źródłem. Brak kursu daje None, nigdy 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal
from enum import StrEnum


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"

    @property
    def sign(self) -> int:
        return 1 if self is Side.BUY else -1

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


def D(value: object) -> Decimal:
    """Decimal z wartości tekstowej lub liczbowej; float przechodzi przez str()."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


@dataclass(frozen=True, slots=True)
class InstrumentSpec:
    symbol: str
    digits: int
    contract_size: Decimal
    profit_currency: str
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal
    tick_size: Decimal | None = None
    pip_size: Decimal | None = None
    base_currency: str | None = None
    margin_currency: str | None = None
    stops_level_points: int = 0
    freeze_level_points: int = 0
    source: str = "SIMULATED"
    description: str = ""

    def __post_init__(self) -> None:
        if self.digits < 0:
            raise ValueError("digits nie może być ujemne")
        for name in ("contract_size", "volume_min", "volume_max", "volume_step"):
            if D(getattr(self, name)) <= 0:
                raise ValueError(f"{name} musi być dodatnie")
        if D(self.volume_min) > D(self.volume_max):
            raise ValueError("volume_min > volume_max")
        if self.tick_size is not None and D(self.tick_size) <= 0:
            raise ValueError("tick_size musi być dodatnie")

    @property
    def point(self) -> Decimal:
        return Decimal(1).scaleb(-self.digits)

    @property
    def tick(self) -> Decimal:
        return D(self.tick_size) if self.tick_size is not None else self.point

    @property
    def pip(self) -> Decimal:
        if self.pip_size is not None:
            return D(self.pip_size)
        if self.digits in (3, 5):
            return self.point * 10
        return self.point

    def to_points(self, distance: Decimal) -> Decimal:
        return D(distance) / self.point

    def to_pips(self, distance: Decimal) -> Decimal:
        return D(distance) / self.pip

    def from_points(self, points: object) -> Decimal:
        return D(points) * self.point

    def is_on_tick(self, price: Decimal) -> bool:
        return (D(price) / self.tick) % 1 == 0

    def normalize_price(self, price: object) -> Decimal:
        """Najbliższa cena na siatce ticka (połówki do parzystej)."""
        ticks = (D(price) / self.tick).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
        return (ticks * self.tick).quantize(self.point)

    def check_volume(self, volume: object) -> "VolumeCheck":
        v = D(volume)
        if v <= 0:
            return VolumeCheck(False, "Wolumen musi być dodatni.")
        if v < D(self.volume_min):
            return VolumeCheck(False, f"Wolumen {v} poniżej minimum brokera {self.volume_min}; nie podnoszę go automatycznie.")
        if v > D(self.volume_max):
            return VolumeCheck(False, f"Wolumen {v} powyżej maksimum brokera {self.volume_max}.")
        steps = (v - D(self.volume_min)) / D(self.volume_step)
        if steps % 1 != 0:
            return VolumeCheck(False, f"Wolumen {v} nie leży na kroku {self.volume_step} (od {self.volume_min}).")
        return VolumeCheck(True, "Wolumen zgodny ze specyfikacją.")

    def floor_volume(self, volume: object) -> Decimal | None:
        """Zaokrąglenie W DÓŁ do kroku; None, gdy wynik spadłby poniżej minimum.

        Nigdy nie zwiększa wolumenu (konstytucja, zasada I)."""
        v = D(volume)
        if v < D(self.volume_min):
            return None
        steps = ((v - D(self.volume_min)) / D(self.volume_step)).to_integral_value(rounding=ROUND_DOWN)
        result = D(self.volume_min) + steps * D(self.volume_step)
        return min(result, D(self.volume_max))

    def profit(self, side: Side, volume: object, open_price: object, close_price: object) -> Decimal:
        """Wynik brutto w walucie zysku instrumentu (model FX/CFD: różnica × kontrakt × lot)."""
        return (D(close_price) - D(open_price)) * side.sign * D(self.contract_size) * D(volume)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "digits": self.digits,
            "point": str(self.point),
            "tick": str(self.tick),
            "pip": str(self.pip),
            "contract_size": str(self.contract_size),
            "profit_currency": self.profit_currency,
            "base_currency": self.base_currency,
            "volume_min": str(self.volume_min),
            "volume_max": str(self.volume_max),
            "volume_step": str(self.volume_step),
            "stops_level_points": self.stops_level_points,
            "freeze_level_points": self.freeze_level_points,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class VolumeCheck:
    ok: bool
    reason: str


@dataclass(frozen=True, slots=True)
class FxRate:
    base: str
    quote: str
    rate: Decimal
    source: str
    as_of: str | None = None


@dataclass(slots=True)
class FxTable:
    """Jawne kursy do przeliczeń; brak kursu -> None z przyczyną."""

    rates: dict[tuple[str, str], FxRate] = field(default_factory=dict)

    def add(self, rate: FxRate) -> None:
        if D(rate.rate) <= 0:
            raise ValueError("Kurs musi być dodatni")
        self.rates[(rate.base, rate.quote)] = rate

    def convert(self, amount: Decimal | None, from_ccy: str, to_ccy: str) -> tuple[Decimal | None, str]:
        if amount is None:
            return None, "Brak kwoty do przeliczenia."
        if from_ccy == to_ccy:
            return D(amount), "Ta sama waluta."
        direct = self.rates.get((from_ccy, to_ccy))
        if direct:
            return D(amount) * D(direct.rate), f"Kurs {from_ccy}{to_ccy} {direct.rate} ({direct.source})."
        inverse = self.rates.get((to_ccy, from_ccy))
        if inverse:
            return D(amount) / D(inverse.rate), f"Odwrotność kursu {to_ccy}{from_ccy} {inverse.rate} ({inverse.source})."
        return None, f"Brak kursu {from_ccy}->{to_ccy}; wartości w walucie rachunku nie da się podać."


def eurusd_example(stops_level_points: int = 0) -> InstrumentSpec:
    """Założenia z zlecenia odbiorczego: point 0,00001, kontrakt 100 000, USD."""
    return InstrumentSpec(
        symbol="EURUSD",
        digits=5,
        contract_size=Decimal("100000"),
        profit_currency="USD",
        base_currency="EUR",
        margin_currency="EUR",
        volume_min=Decimal("0.01"),
        volume_max=Decimal("100"),
        volume_step=Decimal("0.01"),
        stops_level_points=stops_level_points,
        source="SIMULATED: jawne założenia testu odbiorczego",
        description="Euro vs US Dollar (specyfikacja przykładowa, nie odczyt brokera)",
    )


def usdjpy_example() -> InstrumentSpec:
    return InstrumentSpec(
        symbol="USDJPY",
        digits=3,
        contract_size=Decimal("100000"),
        profit_currency="JPY",
        base_currency="USD",
        margin_currency="USD",
        volume_min=Decimal("0.01"),
        volume_max=Decimal("100"),
        volume_step=Decimal("0.01"),
        source="SIMULATED: specyfikacja przykładowa",
    )


def xauusd_example() -> InstrumentSpec:
    return InstrumentSpec(
        symbol="XAUUSD",
        digits=2,
        contract_size=Decimal("100"),
        profit_currency="USD",
        volume_min=Decimal("0.01"),
        volume_max=Decimal("50"),
        volume_step=Decimal("0.01"),
        pip_size=Decimal("0.1"),
        source="SIMULATED: specyfikacja przykładowa",
    )


def index_example() -> InstrumentSpec:
    """Indeks z tickiem 0,25 przy zapisie 2 miejsc (tick != point)."""
    return InstrumentSpec(
        symbol="US500",
        digits=2,
        tick_size=Decimal("0.25"),
        contract_size=Decimal("1"),
        profit_currency="USD",
        volume_min=Decimal("0.1"),
        volume_max=Decimal("100"),
        volume_step=Decimal("0.1"),
        source="SIMULATED: specyfikacja przykładowa",
    )
