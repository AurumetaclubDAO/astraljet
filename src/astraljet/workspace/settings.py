"""Ustawienia interfejsu. Nie mają wpływu na automatykę (BE, trailing, triggery, zlecenia).

Dozwolona jest wyłącznie biała lista kluczy wyglądu. Klucz spoza listy jest odrzucany,
więc zmiana motywu czy układu nie może niejawnie włączyć ani zmienić automatyzacji.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

ALLOWED = {
    "theme": {"dark", "light"},
    "density": {"compact", "comfortable"},
    "font_size": {"small", "standard", "large"},
    "show_grid": {True, False},
    "show_volume_labels": {True, False},
    "panel_order": None,  # lista nazw paneli, walidowana osobno
}
PANELS = {"chart", "plan", "positions", "triggers", "review", "widgets", "requests"}


@dataclass(frozen=True, slots=True)
class UISettings:
    theme: str = "dark"
    density: str = "comfortable"
    font_size: str = "standard"
    show_grid: bool = True
    show_volume_labels: bool = True
    panel_order: tuple[str, ...] = ("chart", "plan", "positions", "triggers", "widgets", "review", "requests")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["panel_order"] = list(self.panel_order)
        return data


def apply_ui_settings(current: UISettings, patch: dict) -> UISettings:
    changes: dict = {}
    for key, value in patch.items():
        if key not in ALLOWED:
            raise ValueError(f"Klucz '{key}' nie jest ustawieniem wyglądu; automatyki nie zmienia się w ustawieniach UI.")
        if key == "panel_order":
            order = tuple(value)
            if set(order) != PANELS or len(order) != len(PANELS):
                raise ValueError("panel_order musi zawierać każdy panel dokładnie raz.")
            changes[key] = order
            continue
        if value not in ALLOWED[key]:
            raise ValueError(f"Niedozwolona wartość {value!r} dla {key}.")
        changes[key] = value
    return replace(current, **changes)
