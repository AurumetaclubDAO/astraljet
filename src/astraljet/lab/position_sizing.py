"""Wielkość pozycji portfela: wagi docelowe strategii -> wolumeny zgodne ze specyfikacją instrumentu.

Jedno miejsce dla badań, paper i wykonania. Funkcja może pozycję tylko zmniejszyć albo pominąć,
nigdy zwiększyć: wolumen jest zaokrąglany w dół do kroku, a pozycja mniejsza od najmniejszego
lota wypada. Błędne dane (brak ceny, kursu albo specyfikacji, liczba nieskończona) oznaczają
odmowę całego wyliczenia. Moduł nie łączy się z brokerem i niczego nie zapisuje.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, localcontext

from astraljet.domain.errors import ValidationError
from astraljet.workspace.instruments import D, FxTable, InstrumentSpec

ZERO = Decimal(0)
ONE = Decimal(1)
NOISE = Decimal("1e-9")  # nadwyżka sumy wag z arytmetyki zmiennoprzecinkowej; zmniejszamy ją bez opisu


def _number(value: object, name: str, *, positive: bool = False) -> Decimal:
    try:
        number = D(value)
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise ValidationError(f"{name}: wartość nie jest liczbą.") from exc
    if not number.is_finite() or (positive and number <= 0):
        raise ValidationError(f"{name}: wymagana liczba skończona" + (" i dodatnia." if positive else "."))
    return number


@dataclass(frozen=True, slots=True)
class SizingLimits:
    """Limity mogą wynik tylko zmniejszyć. Wartości domyślne to propozycja, nie zatwierdzona polityka."""

    max_gross: Decimal = ONE                  # suma wartości pozycji do kapitału; 1 = bez dźwigni
    max_per_market: Decimal = Decimal("0.5")  # bezpiecznik na błąd wag, nie element strategii
    multiplier: Decimal = ONE                 # część wag z badania, 0 < mnożnik <= 1

    def checked(self) -> tuple[Decimal, Decimal, Decimal]:
        gross = _number(self.max_gross, "limit sumy pozycji", positive=True)
        market = _number(self.max_per_market, "limit jednego rynku", positive=True)
        multiplier = _number(self.multiplier, "mnożnik", positive=True)
        if gross > ONE:
            raise ValidationError("Limit sumy pozycji powyżej 1 oznacza dźwignię; ta funkcja jej nie dopuszcza.")
        if market > ONE or multiplier > ONE:
            raise ValidationError("Limit jednego rynku i mnożnik nie mogą przekraczać 1.")
        return gross, market, multiplier


@dataclass(frozen=True, slots=True)
class SizedPosition:
    symbol: str
    target_weight: Decimal    # waga z reguły strategii
    allowed_weight: Decimal   # po mnożniku i limitach, przed zaokrągleniem do lota
    volume: Decimal           # ze znakiem; 0, gdy pozycja wypadła
    value: Decimal            # wartość pozycji w walucie rachunku, nieujemna
    weight: Decimal           # value / kapitał, ze znakiem
    reasons: tuple[str, ...]  # co i dlaczego zostało zmniejszone albo pominięte

    @property
    def skipped(self) -> bool:
        return self.volume == 0 and self.allowed_weight != 0


def _unit_value(name: str, prices: Mapping[str, object], specs: Mapping[str, InstrumentSpec],
                account_currency: str, fx: FxTable) -> Decimal:
    """Wartość wolumenu 1.0 w walucie rachunku."""
    spec = specs.get(name)
    if spec is None:
        raise ValidationError(f"{name}: brak specyfikacji instrumentu.")
    if name not in prices:
        raise ValidationError(f"{name}: brak ceny.")
    price = _number(prices[name], f"cena {name}", positive=True)
    amount, why = fx.convert(D(spec.contract_size) * price, spec.profit_currency, account_currency)
    if amount is None or amount <= 0:
        raise ValidationError(f"{name}: {why}")
    return amount


def size_positions(
    targets: Mapping[str, object],
    *,
    capital: object,
    prices: Mapping[str, object],
    specs: Mapping[str, InstrumentSpec],
    account_currency: str = "USD",
    fx: FxTable | None = None,
    limits: SizingLimits = SizingLimits(),
) -> dict[str, SizedPosition]:
    """Przelicz wagi (ułamek kapitału, ujemna = pozycja krótka) na wolumeny.

    Kolejność: mnożnik, limit jednego rynku, limit sumy, zaokrąglenie w dół do kroku wolumenu.
    Rynek z wagą zero nie wymaga ceny ani specyfikacji.
    """
    max_gross, max_market, multiplier = limits.checked()
    equity = _number(capital, "kapitał", positive=True)
    wanted = {name: _number(weight, f"waga {name}") for name, weight in targets.items()}
    table = fx if fx is not None else FxTable()
    reasons: dict[str, list[str]] = {name: [] for name in wanted}
    with localcontext() as ctx:
        ctx.rounding = ROUND_DOWN  # każde zaokrąglenie arytmetyki idzie w stronę mniejszej pozycji
        allowed = {}
        for name, weight in wanted.items():
            scaled = weight * multiplier
            if abs(scaled) > max_market:
                scaled = max_market.copy_sign(scaled)
                reasons[name].append(f"przycięty do limitu jednego rynku {max_market:.0%}")
            allowed[name] = scaled
        gross = sum((abs(w) for w in allowed.values()), ZERO)
        if gross > max_gross:
            ratio = max_gross / gross
            for name, weight in allowed.items():
                if weight:
                    allowed[name] = weight * ratio
                    if gross - max_gross > NOISE:
                        reasons[name].append(f"zmniejszony proporcjonalnie: suma wag {gross:.1%} ponad limit {max_gross:.0%}")
        result = {}
        for name, weight in allowed.items():
            if weight == 0:
                result[name] = SizedPosition(name, wanted[name], ZERO, ZERO, ZERO, ZERO, tuple(reasons[name]) or ("waga zero",))
                continue
            unit = _unit_value(name, prices, specs, account_currency, table)
            spec = specs[name]
            budget = abs(weight) * equity
            raw = budget / unit
            volume = spec.floor_volume(raw)
            if volume is None:
                least = D(spec.volume_min) * unit
                reasons[name].append(f"pominięty: najmniejszy lot wart {least:.2f} {account_currency}, przydział {budget:.2f} {account_currency}")
                result[name] = SizedPosition(name, wanted[name], weight, ZERO, ZERO, ZERO, tuple(reasons[name]))
                continue
            if raw > D(spec.volume_max):
                reasons[name].append(f"ograniczony do największego wolumenu instrumentu {spec.volume_max}")
            value = volume * unit
            result[name] = SizedPosition(name, wanted[name], weight, volume.copy_sign(weight), value,
                                         (value / equity).copy_sign(weight), tuple(reasons[name]))
    return result
