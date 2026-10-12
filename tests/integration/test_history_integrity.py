from __future__ import annotations

import sqlite3
import tempfile
import unittest

from astraljet.infrastructure.database import Database
from astraljet.infrastructure.migrations import MIGRATION_1, MIGRATION_2, MIGRATION_4, SCHEMA_VERSION


class HistoryIntegrityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Database.from_state_dir(self.temp.name)
        # A real v4 schema, not a second initialization of the new schema.
        with self.database.connect() as connection:
            connection.executescript(MIGRATION_1 + MIGRATION_2 + MIGRATION_4)
            connection.executemany(
                "INSERT INTO schema_migrations VALUES (?, ?)",
                [(v, "2026-09-19T00:00:00Z") for v in range(1, 5)],
            )
            connection.execute(
                "INSERT INTO records VALUES ('SRC', 'SRC-fixture', 1, 'tester', ?, "
                "'completed', ?, '[]', NULL, '{}')",
                ("2026-09-19T00:00:00Z", "a" * 64),
            )
            connection.execute(
                "INSERT INTO events VALUES ('EVT-fixture', ?, ?, 'tester', 'fixture', "
                "'SRC', 'SRC-fixture', 1, 'fixture', 'recorded', '{}', "
                "'CORR-fixture', NULL, 'fixture-key')",
                ("2026-09-19T00:00:00Z", "2026-09-19T00:00:00Z"),
            )
            connection.commit()

    def test_upgrade_preserves_history_and_repeated_init(self) -> None:
        with self.database.connect() as connection:
            before = tuple(connection.execute("SELECT * FROM records").fetchone())
            event = tuple(connection.execute("SELECT * FROM events").fetchone())
        self.database.initialize()
        self.database.initialize()
        with self.database.connect() as connection:
            self.assertEqual(SCHEMA_VERSION, connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0])
            self.assertEqual(before, tuple(connection.execute("SELECT * FROM records WHERE record_id='SRC-fixture'").fetchone()))
            self.assertEqual(event, tuple(connection.execute("SELECT * FROM events").fetchone()))
            connection.execute(
                "INSERT INTO records SELECT record_type, record_id, 2, owner, created_at, "
                "technical_status, content_hash, limitations_json, 'SRC-fixture:1', "
                "payload_json FROM records WHERE record_id='SRC-fixture' AND version=1"
            )
            connection.commit()
            self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM records WHERE record_id='SRC-fixture'").fetchone()[0])

    def test_records_reject_update_delete_and_replace_even_without_events(self) -> None:
        self.database.initialize()
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO records SELECT record_type, 'SRC-noevent', version, owner, "
                "created_at, technical_status, content_hash, limitations_json, supersedes, "
                "payload_json FROM records WHERE record_id='SRC-fixture'"
            )
            connection.commit()
            for sql in (
                "UPDATE records SET payload_json='{}' WHERE record_id='SRC-noevent'",
                "DELETE FROM records WHERE record_id='SRC-noevent'",
                "INSERT OR REPLACE INTO records SELECT * FROM records WHERE record_id='SRC-noevent'",
            ):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(sql)

    def test_event_replace_cannot_bypass_append_only_or_idempotency(self) -> None:
        self.database.initialize()
        with self.database.connect() as connection:
            self.assertEqual(0, connection.execute("PRAGMA recursive_triggers").fetchone()[0])
            for sql in (
                "INSERT OR REPLACE INTO events SELECT * FROM events",
                "INSERT OR REPLACE INTO events SELECT 'EVT-other', occurred_at, recorded_at, "
                "actor, event_type, record_type, record_id, record_version, reason, outcome, "
                "payload_json, correlation_id, causation_id, idempotency_key FROM events",
            ):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(sql)
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
