from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from astraljet.application.experiments import ExperimentDefinition, freeze_experiment
from astraljet.application.intake import IntakeService
from astraljet.application.lab_pipeline import build_lab_evidence_package
from astraljet.domain.enums import DataStatus, RunOutcome, StrategyStatus
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.repositories import RecordRepository
from astraljet.lab.backtest import run_backtest
from astraljet.lab.data_quality import DataImportSpec, import_market_data, load_market_data
from astraljet.lab.reproduction import compare_runs
from astraljet.lab.strategy import StrategyDefinition, create_strategy


DATES = [f"2025-01-{day:02d}T00:00:00Z" for day in range(1, 13)]
BTC_CLOSES = [100, 100, 100, 100, 110, 120, 115, 105, 95, 90, 100, 115]
ETH_CLOSES = [50, 50, 50, 50, 55, 60, 58, 52, 48, 45, 50, 57]


def write_market_csv(path: Path, *, omit_eth_index: int | None = None) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("timestamp", "instrument", "open", "high", "low", "close"),
        )
        writer.writeheader()
        previous = {"BTCUSD": BTC_CLOSES[0], "ETHUSD": ETH_CLOSES[0]}
        for index, timestamp in enumerate(DATES):
            for instrument, closes in (("BTCUSD", BTC_CLOSES), ("ETHUSD", ETH_CLOSES)):
                if instrument == "ETHUSD" and index == omit_eth_index:
                    continue
                open_price = previous[instrument]
                close = closes[index]
                writer.writerow(
                    {
                        "timestamp": timestamp,
                        "instrument": instrument,
                        "open": str(open_price),
                        "high": str(max(open_price, close) + 2),
                        "low": str(min(open_price, close) - 2),
                        "close": str(close),
                    }
                )
                previous[instrument] = close


def strategy_definition() -> StrategyDefinition:
    return StrategyDefinition(
        instruments=("BTCUSD", "ETHUSD"),
        venue="TEST_SPOT",
        timeframe="1d",
        signal_timing="po zamknięciu dziennej świecy UTC",
        execution_timing="na otwarciu następnej dziennej świecy UTC",
        entry_rule="risk_on gdy BTC close > SMA i SMA > SMA sprzed slope_lookback sesji",
        exit_rule="risk_reduced gdy BTC close <= SMA albo SMA <= SMA sprzed slope_lookback sesji",
        sizing_rule="jawne wagi risk_on i risk_reduced z allowed_parameters",
        cost_model="10 bps od jednostronnego turnover przy każdym rebalansie",
        constraints=("bez dźwigni", "tylko zamknięte świece"),
        missing_data_policy="zablokuj przebieg przy luce w dowolnym instrumencie",
        benchmark="statyczne BTC 80%, ETH 20%, rebalans miesięczny",
        allowed_parameters={
            "ma_window": 3,
            "slope_lookback": 1,
            "cost_bps": "10",
            "initial_equity": "10000",
            "risk_on_btc_weight": "0.70",
            "risk_on_eth_weight": "0.20",
            "risk_reduced_btc_weight": "0.35",
            "risk_reduced_eth_weight": "0.10",
        },
        source_adaptation="Wyłącznie fixture mechaniki; nie jest zatwierdzoną STRAT rynkową.",
    )


class LabPipelineIntegrationTest(unittest.TestCase):
    def test_gap_in_one_instrument_blocks_data(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            path = Path(workspace) / "gap.csv"
            write_market_csv(path, omit_eth_index=5)
            record = import_market_data(
                path,
                spec=DataImportSpec(
                    provider="synthetic_fixture",
                    venue="TEST_SPOT",
                    instruments=("BTCUSD", "ETHUSD"),
                    timeframe="1d",
                    timezone="UTC",
                    available_at_rule="po zamknięciu świecy",
                    transformations=("brak",),
                    cost_model="10 bps od jednostronnego turnover przy każdym rebalansie",
                ),
                owner="tester",
            )
            self.assertIs(record.data_status, DataStatus.GAPS)
            self.assertTrue(any("missing" in finding for finding in record.quality_findings))

    def test_full_fixture_pipeline_reproduces_result_without_claiming_market_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as state:
            workspace_path = Path(workspace)
            source_file = workspace_path / "strategies.md"
            source_file.write_text("Pięć tez do opracowania", encoding="utf-8")
            data_file = workspace_path / "btc_eth_fixture.csv"
            write_market_csv(data_file)

            database = Database.from_state_dir(state)
            database.initialize()
            repository = RecordRepository(database)
            intake = IntakeService(repository)
            source, _ = intake.add_source(
                source_file,
                author="unknown",
                idempotency_key="lab-source-fixture",
            )
            candidates, _ = intake.seed_initial_candidates(
                source.record_id,
                idempotency_key="lab-candidates-fixture",
            )
            crypto_candidate = candidates[-1]

            strategy = create_strategy(
                candidate_id=crypto_candidate.record_id,
                definition=strategy_definition(),
                owner="tester",
            )
            self.assertIs(strategy.strategy_status, StrategyStatus.READY)
            strategy, _, _ = repository.save(
                strategy,
                event_type="strategy.validated",
                reason="Fixture mechaniki ma kompletne jawne reguły.",
                outcome="ready_test_only",
                actor="tester",
                idempotency_key="lab-strategy-fixture",
            )

            data = import_market_data(
                data_file,
                spec=DataImportSpec(
                    provider="synthetic_fixture",
                    venue="TEST_SPOT",
                    instruments=("BTCUSD", "ETHUSD"),
                    timeframe="1d",
                    timezone="UTC",
                    available_at_rule="po zamknięciu świecy",
                    transformations=("brak",),
                    cost_model="10 bps od jednostronnego turnover przy każdym rebalansie",
                ),
                owner="tester",
            )
            self.assertIs(data.data_status, DataStatus.READY)
            data, _, _ = repository.save(
                data,
                event_type="data.imported",
                reason="Deterministyczny fixture BTC/ETH.",
                outcome="ready_test_only",
                actor="tester",
                idempotency_key="lab-data-fixture",
            )

            experiment = freeze_experiment(
                strategy=strategy,
                data=data,
                definition=ExperimentDefinition(
                    code_hash="A" * 64,
                    hypothesis="Sprawdzenie mechaniki trend filter, nie przewagi rynkowej.",
                    in_sample=(DATES[0], DATES[5]),
                    out_of_sample=(DATES[6], DATES[-1]),
                    allowed_variants=(dict(strategy.allowed_parameters),),
                    criteria={"max_drawdown_lte": "0.50", "min_rebalances_gte": 1},
                    budget="0",
                    seed=42,
                    metrics=("final_equity", "max_drawdown", "total_cost"),
                    tolerance={
                        "final_equity": "0.00000001",
                        "max_drawdown": "0.00000001",
                        "total_cost": "0.00000001",
                    },
                    stop_rules=("przerwij przy luce DATA", "przerwij przy zmianie wersji"),
                ),
                owner="tester",
            )
            experiment, _, _ = repository.save(
                experiment,
                event_type="experiment.frozen",
                reason="Plan fixture zapisany przed wynikiem.",
                outcome="frozen",
                actor="tester",
                idempotency_key="lab-experiment-fixture",
            )

            bars = load_market_data(data)
            first = run_backtest(
                strategy=strategy,
                data=data,
                experiment=experiment,
                bars=bars,
                owner="tester",
            )
            second = run_backtest(
                strategy=strategy,
                data=data,
                experiment=experiment,
                bars=bars,
                owner="independent-reproducer",
            )
            report = compare_runs(first, second, experiment.tolerance)
            package = build_lab_evidence_package(
                source=source,
                candidate=crypto_candidate,
                strategy=strategy,
                data=data,
                experiment=experiment,
                runs=(first, second),
                reproduction=report,
                mechanics_evidence=(
                    "tests/unit/test_strategy_validation.py",
                    "tests/unit/test_backtest_mechanics.py",
                ),
            )

            self.assertIs(first.run_outcome, RunOutcome.PASSED)
            self.assertTrue(first.trades)
            self.assertGreater(float(first.total_cost), 0)
            self.assertEqual("synthetic_fixture", first.reproduction["data_provider"])
            self.assertEqual("test_only", first.reproduction["evidence_strength"])
            self.assertTrue(report.verified)
            self.assertEqual((), report.differences)
            self.assertEqual(12, len(package.stages))
            self.assertEqual(tuple(f"LAB-{index:02d}" for index in range(1, 13)), tuple(stage.stage_id for stage in package.stages))
            self.assertEqual("blocked", package.overall_status)
            self.assertEqual("blocked", package.stages[10].status)
            self.assertEqual("AJ-08 + AJ-09", package.stages[10].owner)
            self.assertIn("REVIEW", package.stages[10].next_action)
            self.assertEqual("blocked", package.stages[11].status)
            self.assertIn("końcowej REVIEW", package.stages[11].next_action)

            repository.save(
                first,
                event_type="run.completed",
                reason="Pierwszy przebieg fixture.",
                outcome=first.run_outcome.value,
                actor="tester",
                idempotency_key="lab-run-fixture-1",
            )
            repository.save(
                second,
                event_type="run.reproduced",
                reason="Drugi niezależny przebieg fixture.",
                outcome=second.run_outcome.value,
                actor="independent-reproducer",
                idempotency_key="lab-run-fixture-2",
            )
            self.assertEqual(2, repository.count_by_type("RUN"))


if __name__ == "__main__":
    unittest.main()
