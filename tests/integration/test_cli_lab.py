from __future__ import annotations

import io
import json
import tempfile
import sqlite3
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

from astraljet.cli import run
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.repositories import RecordRepository
from astraljet.domain.errors import ValidationError
from tests.contract.test_review import independent_check

from .test_lab_pipeline import DATES, strategy_definition, write_market_csv


def invoke(*arguments: str) -> tuple[int, dict[str, object]]:
    output = io.StringIO()
    with redirect_stdout(output):
        code = run(list(arguments))
    return code, json.loads(output.getvalue())


class LabCliIntegrationTest(unittest.TestCase):
    def test_invalid_report_does_not_initialize_or_migrate_database(self):
        with tempfile.TemporaryDirectory() as state:
            database_path = Path(state)/'astraljet.sqlite3'
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute('CREATE TABLE legacy (id INTEGER)')
                connection.commit()
            before = database_path.read_bytes()
            bad_report = Path(state)/'invalid-check.json'
            bad_report.write_text('{"verified":true}',encoding='utf-8')
            with self.assertRaises(ValidationError):
                invoke('--state-dir',state,'review','create','--run-id','RUN-11111111',
                    '--reviewer','AJ-08','--idempotency-key','invalid-review',
                    '--independent-check',str(bad_report))
            self.assertEqual(before,database_path.read_bytes())

    def test_review_cannot_create_a_new_database_on_bad_input(self):
        with tempfile.TemporaryDirectory() as root:
            state = Path(root)/'missing-state'
            with self.assertRaises(ValidationError):
                invoke('--state-dir',str(state),'review','create','--run-id','RUN-11111111',
                    '--reviewer','AJ-08','--idempotency-key','invalid-review')
            self.assertFalse(state.exists())

    def test_cli_builds_source_to_reproduced_backtest_chain(self) -> None:
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as state:
            workspace_path = Path(workspace)
            source_file = workspace_path / "strategies.md"
            source_file.write_text("Pięć tez", encoding="utf-8")
            data_file = workspace_path / "btc_eth.csv"
            write_market_csv(data_file)
            strategy_config = workspace_path / "strategy.json"
            strategy_config.write_text(
                json.dumps(strategy_definition().as_dict(), ensure_ascii=False),
                encoding="utf-8",
            )

            code, _ = invoke("--state-dir", state, "init")
            self.assertEqual(0, code)
            code, source = invoke(
                "--state-dir",
                state,
                "source",
                "add",
                "--file",
                str(source_file),
                "--idempotency-key",
                "cli-source-v1",
            )
            self.assertEqual(0, code)
            code, candidates = invoke(
                "--state-dir",
                state,
                "candidates",
                "seed-2026",
                "--source-id",
                str(source["source"]["record_id"]),
                "--idempotency-key",
                "cli-candidates-v1",
            )
            self.assertEqual(0, code)
            candidate_id = str(candidates["candidates"][-1]["record_id"])

            code, strategy = invoke(
                "--state-dir",
                state,
                "strategy",
                "validate",
                "--candidate-id",
                candidate_id,
                "--config",
                str(strategy_config),
                "--idempotency-key",
                "cli-strategy-v1",
            )
            self.assertEqual(0, code)
            strategy_id = str(strategy["strategy"]["record_id"])

            code, data = invoke(
                "--state-dir",
                state,
                "data",
                "import",
                "--file",
                str(data_file),
                "--provider",
                "synthetic_fixture",
                "--venue",
                "TEST_SPOT",
                "--instruments",
                "BTCUSD,ETHUSD",
                "--timeframe",
                "1d",
                "--timezone",
                "UTC",
                "--available-at-rule",
                "po zamknięciu świecy",
                "--transformation",
                "brak",
                "--cost-model",
                "10 bps od jednostronnego turnover przy każdym rebalansie",
                "--idempotency-key",
                "cli-data-v1",
            )
            self.assertEqual(0, code)
            data_id = str(data["data"]["record_id"])

            experiment_config = workspace_path / "experiment.json"
            experiment_config.write_text(
                json.dumps(
                    {
                        "code_hash": "A" * 64,
                        "hypothesis": "Test mechaniki, nie przewagi rynkowej.",
                        "in_sample": [DATES[0], DATES[5]],
                        "out_of_sample": [DATES[6], DATES[-1]],
                        "allowed_variants": [strategy_definition().allowed_parameters],
                        "criteria": {"max_drawdown_lte": "0.50", "min_rebalances_gte": 1},
                        "budget": "0",
                        "seed": 42,
                        "metrics": ["final_equity", "max_drawdown", "total_cost"],
                        "tolerance": {
                            "final_equity": "0.00000001",
                            "max_drawdown": "0.00000001",
                            "total_cost": "0.00000001"
                        },
                        "stop_rules": ["przerwij przy luce DATA", "przerwij przy zmianie wersji"]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            code, experiment = invoke(
                "--state-dir",
                state,
                "experiment",
                "freeze",
                "--strategy-id",
                strategy_id,
                "--data-id",
                data_id,
                "--config",
                str(experiment_config),
                "--idempotency-key",
                "cli-experiment-v1",
            )
            self.assertEqual(0, code)
            experiment_id = str(experiment["experiment"]["record_id"])

            code, first = invoke(
                "--state-dir",
                state,
                "run",
                "backtest",
                "--experiment-id",
                experiment_id,
                "--idempotency-key",
                "cli-run-v1",
            )
            self.assertEqual(0, code)
            code, reproduced = invoke(
                "--state-dir",
                state,
                "run",
                "backtest",
                "--experiment-id",
                experiment_id,
                "--compare-run-id",
                str(first["run"]["record_id"]),
                "--idempotency-key",
                "cli-run-v2",
            )
            self.assertEqual(0, code)
            self.assertTrue(reproduced["comparison"]["verified"])
            self.assertEqual([], reproduced["comparison"]["differences"])

            code, review = invoke(
                "--state-dir",
                state,
                "review",
                "create",
                "--run-id",
                str(first["run"]["record_id"]),
                "--run-id",
                str(reproduced["run"]["record_id"]),
                "--reviewer",
                "AJ-08",
                "--evidence",
                "dwa zgodne RUN fixture",
                "--finding",
                "siła dowodowa test_only",
                "--condition",
                "bez awansu do kapitału",
                "--idempotency-key",
                "cli-review-v1",
            )
            self.assertEqual(0, code)
            self.assertEqual("unverified", review["review"]["verdict"])
            self.assertIn('missing_independent_check', review['review']['missing_evidence'])
            _, status = invoke('--state-dir', state, 'status', '--json')
            self.assertEqual('review_not_verified', status['blocker'])

            # A separate, explicitly test-only observation artifact exercises
            # ingestion/binding. It is not an independent market validation.
            repository = RecordRepository(Database.from_state_dir(state))
            stored_runs = tuple(repository.get_latest(r['run']['record_id']) for r in (first,reproduced))
            check_path = workspace_path / 'independent-check-test-only.json'
            check_path.write_text(json.dumps(independent_check(stored_runs,
                repository.get_latest(experiment_id))),encoding='utf-8')
            review_args = ('--state-dir',state,'review','create',
                '--run-id',stored_runs[0].record_id,'--run-id',stored_runs[1].record_id,
                '--reviewer','AJ-08','--evidence','TEST ONLY: obserwacje kontrolne',
                '--independent-check',str(check_path),'--idempotency-key','cli-review-with-check-v2')
            _, review = invoke(*review_args)
            self.assertEqual('verified',review['review']['verdict'])
            _, replay = invoke(*review_args)
            self.assertFalse(replay['created'])
            self.assertEqual(review['review']['record_id'],replay['review']['record_id'])
            self.assertEqual(2,repository.count_by_type('REVIEW'))
            self.assertEqual(review['review']['verification_details'],
                repository.get_latest(review['review']['record_id']).verification_details)
            with self.assertRaises(ValidationError):
                invoke(*review_args,'--finding','zmieniony zakres z tym samym kluczem')
            # An idempotency key used for another record type must not be
            # interpreted as a successful REVIEW or leak an AttributeError.
            with self.assertRaises(ValidationError):
                invoke(*review_args[:-1],'cli-source-v1')
            self.assertEqual(2,repository.count_by_type('REVIEW'))

            limits_file = workspace_path / "risk-limits.json"
            limits_file.write_text(
                json.dumps({"max_notional": "0", "environment": "test_only"}),
                encoding="utf-8",
            )
            code, decision = invoke(
                "--state-dir",
                state,
                "risk",
                "decide",
                "--review-id",
                str(review["review"]["record_id"]),
                "--decision",
                "allowed",
                "--scope",
                "projekt mandatu testowego",
                "--valid-from",
                "2025-01-03T00:00:00Z",
                "--valid-until",
                "2025-01-10T00:00:00Z",
                "--limits",
                str(limits_file),
                "--rationale",
                "zgodność mechaniki fixture",
                "--next-step",
                "przygotować projekt mandatu bez REAL",
                "--idempotency-key",
                "cli-risk-v1",
            )
            self.assertEqual(0, code)
            self.assertEqual("allowed", decision["risk_decision"]["decision"])


if __name__ == "__main__":
    unittest.main()
