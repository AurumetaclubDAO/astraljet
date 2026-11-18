"""Hamulec obsunięcia: po spadku kapitału o ustalony ułamek od szczytu wagi idą na zero i system czeka.

Stan jest zatrzaskowy. Po zadziałaniu nie wraca sam do pracy, nawet gdy kapitał odrobi stratę.
Zwolnić go może tylko człowiek, jawnie, z zapisem kto i kiedy. Próg nie ma wartości domyślnej,
bo ustala go właściciel. Moduł nie łączy się z brokerem i niczego nie zapisuje.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal

from astraljet.domain.errors import ValidationError
from astraljet.lab.position_sizing import ONE, ZERO, _number


@dataclass(frozen=True, slots=True)
class BrakeState:
    peak: Decimal                         # najwyższy kapitał od startu albo od ostatniego zwolnienia
    tripped: bool = False
    tripped_at: str | None = None
    tripped_equity: Decimal | None = None
    released_by: str | None = None        # kto ostatnio zwolnił hamulec
    released_at: str | None = None


def start(equity: object) -> BrakeState:
    return BrakeState(peak=_number(equity, "kapitał początkowy", positive=True))


def observe(state: BrakeState, equity: object, *, threshold: object, when: str) -> BrakeState:
    """Uwzględnij nowy stan kapitału. Błędna liczba oznacza odmowę, nie ciche pominięcie."""
    limit = _number(threshold, "próg hamulca", positive=True)
    if limit >= ONE:
        raise ValidationError("Próg hamulca musi być ułamkiem mniejszym od 1, na przykład 0.2.")
    current = _number(equity, "kapitał")
    if state.tripped:
        return state
    peak = max(state.peak, current)
    if peak - current >= limit * peak:
        return replace(state, peak=peak, tripped=True, tripped_at=when, tripped_equity=current)
    return replace(state, peak=peak)


def release(state: BrakeState, equity: object, *, by: str, when: str) -> BrakeState:
    """Zwolnienie po decyzji człowieka. Szczyt liczy się od nowa, od bieżącego kapitału."""
    if not state.tripped:
        raise ValidationError("Hamulec nie jest zaciągnięty; nie ma czego zwalniać.")
    if not isinstance(by, str) or not by.strip():
        raise ValidationError("Zwolnienie hamulca wymaga podania, kto je zatwierdził.")
    return BrakeState(peak=_number(equity, "kapitał przy zwolnieniu", positive=True), released_by=by.strip(), released_at=when)


def gate(state: BrakeState, targets: Mapping[str, object]) -> dict[str, object]:
    """Wagi po hamulcu: bez zmian albo same zera, czyli zamknięcie pozycji."""
    return {name: ZERO for name in targets} if state.tripped else dict(targets)
