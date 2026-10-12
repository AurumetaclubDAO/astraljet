from __future__ import annotations

import tempfile
import time
import unittest

from astraljet.application.status import build_status
from astraljet.domain.enums import TechnicalStatus, TrustStatus
from astraljet.domain.records import SourceRecord
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.repositories import RecordRepository


class StatusPerformanceIntegrationTest(unittest.TestCase):
    def test_status_remains_fast_with_one_hundred_thousand_events(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            database = Database.from_state_dir(state)
            database.initialize()
            source = SourceRecord(
                record_id="SRC-PERFORMANCE",
                version=1,
                owner="tester",
                created_at="2025-01-01T00:00:00Z",
                technical_status=TechnicalStatus.COMPLETED,
                content_hash="A" * 64,
                limitations=("fixture",),
                locator="C:/fixture.md",
                sha256="A" * 64,
                size_bytes=1,
                observed_at="2025-01-01T00:00:00Z",
                author="tester",
                media_type="text/markdown",
                trust_status=TrustStatus.UNVERIFIED,
            )
            RecordRepository(database).save(
                source,
                event_type="source.registered",
                reason="Fixture wydajności.",
                outcome="registered",
                actor="tester",
                idempotency_key="performance-event-000000",
            )
            rows = (
                (
                    f"EVT-PERF-{index:06d}",
                    "2025-01-01T00:00:00Z",
                    "2025-01-01T00:00:00Z",
                    "tester",
                    "performance.fixture",
                    "SRC",
                    source.record_id,
                    1,
                    "Test wydajności statusu.",
                    "recorded",
                    "{}",
                    "CORR-PERFORMANCE",
                    None,
                    f"performance-event-{index:06d}",
                )
                for index in range(1, 100_000)
            )
            with database.transaction() as connection:
                connection.executemany(
                    """
                    INSERT INTO events(
                        event_id, occurred_at, recorded_at, actor, event_type, record_type,
                        record_id, record_version, reason, outcome, payload_json,
                        correlation_id, causation_id, idempotency_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            with database.connect() as connection:
                self.assertEqual(100_000, connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])

            started = time.perf_counter()
            status = build_status(database)
            elapsed = time.perf_counter() - started

            self.assertEqual("SRC", status["stage"])
            self.assertLess(elapsed, 5.0, f"Status trwał {elapsed:.3f} s")


if __name__ == "__main__":
    unittest.main()
