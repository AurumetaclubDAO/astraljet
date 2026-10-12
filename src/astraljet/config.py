from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class StateConfig:
    state_dir: Path
    database_path: Path

    @classmethod
    def from_path(cls, value: str | Path | None) -> "StateConfig":
        if value is None or not str(value).strip():
            raise ValidationError("Wymagany jest jawny parametr --state-dir.")
        state_dir = Path(value).expanduser().resolve()
        if state_dir.exists() and not state_dir.is_dir():
            raise ValidationError("--state-dir wskazuje plik zamiast katalogu.")
        return cls(state_dir=state_dir, database_path=state_dir / "astraljet.sqlite3")
