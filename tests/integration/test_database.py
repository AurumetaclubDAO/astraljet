from __future__ import annotations

import tempfile
import unittest

from astraljet.infrastructure.database import Database
from astraljet.infrastructure.migrations import SCHEMA_VERSION


class DatabaseIntegrationTest(unittest.TestCase):
    def test_initialize_is_idempotent_and_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            first = Database.from_state_dir(state_dir)
            first.initialize()
            first.initialize()

            with first.connect() as connection:
                version = connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone()[0]
                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

            restarted = Database.from_state_dir(state_dir)
            with restarted.connect() as connection:
                table_count = connection.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='events'"
                ).fetchone()[0]

            self.assertEqual(SCHEMA_VERSION, version)
            self.assertEqual("wal", journal_mode.lower())
            self.assertEqual(1, foreign_keys)
            self.assertEqual(1, table_count)


if __name__ == "__main__":
    unittest.main()
