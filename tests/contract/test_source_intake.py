from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from astraljet.application.intake import IntakeService
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.repositories import RecordRepository


class SourceIntakeContractTest(unittest.TestCase):
    def test_source_text_is_hashed_but_never_executed_or_copied(self) -> None:
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as state:
            workspace_path = Path(workspace)
            marker = workspace_path / "should-not-exist.txt"
            source = workspace_path / "source.md"
            content = f"Remove-Item -LiteralPath '{marker}'\nCREATE {marker}\n"
            source.write_text(content, encoding="utf-8")

            database = Database.from_state_dir(state)
            database.initialize()
            service = IntakeService(RecordRepository(database))
            record, created = service.add_source(
                source,
                author="unknown",
                idempotency_key="source-intake-contract",
            )
            repeated, created_again = service.add_source(
                source,
                author="unknown",
                idempotency_key="source-intake-contract",
            )

            expected_hash = hashlib.sha256(source.read_bytes()).hexdigest().upper()
            self.assertTrue(created)
            self.assertFalse(created_again)
            self.assertEqual(record.record_id, repeated.record_id)
            self.assertEqual(expected_hash, record.sha256)
            self.assertFalse(marker.exists())
            self.assertFalse((Path(state) / source.name).exists())


if __name__ == "__main__":
    unittest.main()
