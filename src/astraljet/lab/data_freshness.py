"""Świeżość danych dziennych: zanim policzysz wagi, sprawdź, czy ostatnia zamknięta świeca każdego rynku jest dość nowa.

Stare albo brakujące dane oznaczają odmowę, a nie liczenie na tym, co akurat jest. Świeca z dnia decyzji
też jest odmową, bo mogła się jeszcze nie zamknąć i wynik zaglądałby w przyszłość. Limit wieku nie ma
wartości domyślnej: zależy od rynku (krypto handluje codziennie, indeksy mają weekendy i święta)
i ustala go protokół badania. Daty są dniami serwera, tak jak w plikach danych D1.
Moduł nie łączy się z niczym i niczego nie zapisuje.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from astraljet.domain.errors import ValidationError

ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True, slots=True)
class BarFreshness:
    symbol: str
    last_bar: date | None
    age_days: int | None      # dni kalendarzowe od ostatniej zamkniętej świecy do dnia decyzji
    limit_days: int
    fresh: bool
    reason: str               # pusty, gdy dane są świeże


def _day(value: object, name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and ISO_DAY.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValidationError(f"{name}: oczekiwana data w postaci RRRR-MM-DD, jest {value!r}.")


def _limit(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"{name}: limit wieku danych to liczba całkowita dni, co najmniej 1, jest {value!r}.")
    return value


def check_freshness(last_bars: Mapping[str, object], *, today: object,
                    max_age_days: int | Mapping[str, int]) -> dict[str, BarFreshness]:
    """Ocena każdego rynku. `last_bars` to data ostatniej zamkniętej świecy albo None, gdy danych nie ma."""
    day = _day(today, "dzień decyzji")
    if not last_bars:
        raise ValidationError("Brak rynków do sprawdzenia świeżości danych.")
    report = {}
    for symbol, raw in last_bars.items():
        if isinstance(max_age_days, Mapping):
            if symbol not in max_age_days:
                raise ValidationError(f"{symbol}: brak limitu wieku danych.")
            limit = _limit(max_age_days[symbol], symbol)
        else:
            limit = _limit(max_age_days, "wszystkie rynki")
        if raw is None:
            report[symbol] = BarFreshness(symbol, None, None, limit, False, "brak danych")
            continue
        last = _day(raw, f"{symbol}, ostatnia świeca")
        age = (day - last).days
        if age < 1:
            reason = f"świeca z {last} nie jest starsza niż dzień decyzji {day}; mogła się jeszcze nie zamknąć"
        elif age > limit:
            reason = f"ostatnia świeca z {last} ma {age} dni, limit to {limit}"
        else:
            reason = ""
        report[symbol] = BarFreshness(symbol, last, age, limit, not reason, reason)
    return report


def require_fresh(last_bars: Mapping[str, object], *, today: object,
                  max_age_days: int | Mapping[str, int]) -> dict[str, BarFreshness]:
    """Jak `check_freshness`, ale jeden nieświeży rynek kończy pracę błędem z listą powodów."""
    report = check_freshness(last_bars, today=today, max_age_days=max_age_days)
    stale = [item for item in report.values() if not item.fresh]
    if stale:
        details = "; ".join(f"{item.symbol}: {item.reason}" for item in stale)
        raise ValidationError(f"Dane dzienne nie są świeże, wag nie liczę. {details}.", blocker="nieświeże dane dzienne",
                              allowed_next_action="Odśwież dane dzienne i uruchom ponownie.")
    return report
