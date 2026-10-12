from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from astraljet.application.intake import IntakeService
from astraljet.domain.enums import CandidateStatus
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.repositories import RecordRepository


class CandidateIntakeIntegrationTest(unittest.TestCase):
    def test_seeds_exactly_five_unverified_candidates_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as state:
            source_file = Path(workspace) / "strategies.md"
            source_file.write_text("Pięć tez do opracowania", encoding="utf-8")
            database = Database.from_state_dir(state)
            database.initialize()
            repository = RecordRepository(database)
            service = IntakeService(repository)
            source, _ = service.add_source(
                source_file,
                author="unknown",
                idempotency_key="candidate-source-1",
            )

            candidates, created = service.seed_initial_candidates(
                source.record_id,
                idempotency_key="candidate-batch-1",
            )
            repeated, created_again = service.seed_initial_candidates(
                source.record_id,
                idempotency_key="candidate-batch-1",
            )

            self.assertEqual(5, len(candidates))
            self.assertEqual(5, created)
            self.assertEqual(0, created_again)
            self.assertEqual(
                [candidate.record_id for candidate in candidates],
                [candidate.record_id for candidate in repeated],
            )
            self.assertTrue(
                all(candidate.candidate_status is CandidateStatus.NEEDS_INPUT for candidate in candidates)
            )
            self.assertEqual(5, repository.count_by_type("CAND"))
            self.assertEqual(0, repository.count_by_type("RUN"))


if __name__ == "__main__":
    unittest.main()
