from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from astraljet.domain.enums import ExecutionEnvironment, TechnicalStatus, TrustStatus
from astraljet.domain.records import SourceRecord
from astraljet.domain.validation import new_record_id, utc_now
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.event_store import EventStore
from astraljet.infrastructure.repositories import RecordRepository


class EventStoreContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database.from_state_dir(self.temp_dir.name)
        self.database.initialize()
        self.repository = RecordRepository(self.database)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _source(self) -> SourceRecord:
        now = utc_now()
        return SourceRecord(
            record_id=new_record_id("SRC"),
            version=1,
            owner="Karol",
            created_at=now,
            technical_status=TechnicalStatus.COMPLETED,
            content_hash="A" * 64,
            limitations=("Twierdzenia niezweryfikowane.",),
            locator="C:/material.md",
            sha256="A" * 64,
            size_bytes=1,
            observed_at=now,
            author="unknown",
            media_type="text/markdown",
            trust_status=TrustStatus.UNVERIFIED,
        )

    def test_duplicate_key_returns_original_record_without_second_event(self) -> None:
        first, first_event, created = self.repository.save(
            self._source(),
            event_type="source.registered",
            reason="test kontraktu",
            outcome="registered",
            actor="tester",
            idempotency_key="contract-source-1",
        )
        second, second_event, created_again = self.repository.save(
            self._source(),
            event_type="source.registered",
            reason="ponowienie",
            outcome="registered",
            actor="tester",
            idempotency_key="contract-source-1",
        )

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.record_id, second.record_id)
        self.assertEqual(first_event.event_id, second_event.event_id)
        self.assertEqual(1, len(EventStore(self.database).list_for_record(first.record_id)))

    def test_events_are_append_only(self) -> None:
        record, event, _ = self.repository.save(
            self._source(),
            event_type="source.registered",
            reason="test append-only",
            outcome="registered",
            actor="tester",
            idempotency_key="contract-source-2",
        )
        with self.database.connect() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE events SET outcome = 'changed' WHERE event_id = ?",
                    (event.event_id,),
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM events WHERE event_id = ?", (event.event_id,))

    def test_execution_environment_has_no_real_value(self) -> None:
        self.assertEqual(
            {"PAPER_CONTINUOUS", "BROKER_DEMO"},
            {environment.value for environment in ExecutionEnvironment},
        )
        with self.assertRaises(ValueError):
            ExecutionEnvironment("REAL")


if __name__ == "__main__":
    unittest.main()
