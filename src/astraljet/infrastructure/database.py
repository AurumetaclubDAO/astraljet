from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from astraljet.config import StateConfig
from astraljet.domain.errors import ValidationError
from astraljet.domain.validation import utc_now

from .migrations import migrate


class Database:
    def __init__(self, config: StateConfig, *, read_only_mode: bool = False) -> None:
        self.config = config
        self.read_only_mode = read_only_mode

    @classmethod
    def from_state_dir(cls, state_dir: str | Path) -> "Database":
        return cls(StateConfig.from_path(state_dir))

    def initialize(self) -> None:
        if self.read_only_mode:
            raise ValidationError("Odczyt nie może inicjalizować ani migrować bazy.")
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            migrate(connection, applied_at=utc_now())
            connection.commit()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if self.read_only_mode:
            with self.read_only() as connection:
                yield connection
            return
        connection = sqlite3.connect(self.config.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @contextmanager
    def read_only(self) -> Iterator[sqlite3.Connection]:
        """One consistent read transaction; never initialize or migrate the store."""
        if not self.config.database_path.is_file():
            raise ValidationError(
                "Brak istniejącej bazy w wybranym katalogu stanu.",
                blocker="database_missing",
                allowed_next_action="Wskaż istniejący --state-dir; odczyt nie tworzy bazy.",
            )
        connection = sqlite3.connect(
            self.config.database_path.as_uri() + "?mode=ro", uri=True, timeout=5,
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA trusted_schema = OFF")
            connection.execute("BEGIN")
            yield connection
        finally:
            connection.close()
