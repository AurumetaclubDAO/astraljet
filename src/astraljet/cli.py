from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from astraljet.application.experiments import ExperimentDefinition, freeze_experiment
from astraljet.application.experiment_inputs import InputWindow, inspect_experiment_inputs
from astraljet.application.weekly_experiment import inspect_weekly_experiment, run_weekly_experiment
from astraljet.application.weekly_recorded import record_weekly_experiment, export_weekly_report
from astraljet.application.intake import IntakeService
from astraljet.application.mandates import (
    MandateRequest,
    RiskDecisionRequest,
    create_incubation,
    create_mandate,
    create_risk_decision,
)
from astraljet.application.reviews import ReviewRequest, create_review, validate_review_replay
from astraljet.application.independent_check import load_independent_check
from astraljet.application.read_model import inspect_system, list_strategies, strategy_lineage, registry_snapshot
from astraljet.application.registry_sync import push as push_registry_sync, sync_status, load_connection, validate_connection
from astraljet.infrastructure.snapshot_file import publish_snapshot
from astraljet.application.status import BudgetStatusRequest, build_status, create_budget_status, export_audit
from astraljet.config import StateConfig
from astraljet.domain.enums import (
    DataStatus,
    ExecutionEnvironment,
    ExecutionResultState,
    IncubationStatus,
    RiskDecisionStatus,
    StrategyStatus,
)
from astraljet.domain.errors import AstralJetError, TechnicalError
from astraljet.domain.records import (
    CandidateRecord,
    DataRecord,
    ExperimentRecord,
    MandateRecord,
    ReviewRecord,
    RunRecord,
    StrategyRecord,
    RiskDecisionRecord,
)
from astraljet.executor.demo import DemoAdapter
from astraljet.executor.guard import ExecutorGuard
from astraljet.executor.paper import PaperExecutor
from astraljet.executor.ports import FrozenContext, OrderIntent
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.alpaca_market_data import (
    AlpacaCryptoDataClient,
    CryptoBarsRequest,
    load_alpaca_credentials,
)
from astraljet.infrastructure.repositories import RecordRepository
from astraljet.lab.backtest import run_backtest
from astraljet.lab.data_quality import DataImportSpec, import_market_data, load_market_data
from astraljet.lab.reproduction import compare_runs
from astraljet.lab.strategy import StrategyDefinition, create_strategy


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(type(value).__name__)


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_default))


def _load_json_object(path_value: str) -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        from astraljet.domain.errors import ValidationError

        raise ValidationError(f"Nie można odczytać konfiguracji JSON: {exc}") from exc
    if not isinstance(value, dict):
        from astraljet.domain.errors import ValidationError

        raise ValidationError("Konfiguracja JSON musi być obiektem.")
    return value


def _parse_time(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        from astraljet.domain.errors import ValidationError

        raise ValidationError("--now musi być czasem ISO-8601 UTC.") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        from astraljet.domain.errors import ValidationError

        raise ValidationError("--now musi mieć jawną strefę UTC.")
    return parsed


def _intent_from_file(path: str) -> OrderIntent:
    value = _load_json_object(path)
    try:
        return OrderIntent(
            intent_id=str(value["intent_id"]),
            instrument=str(value["instrument"]),
            side=str(value["side"]),
            quantity=Decimal(str(value["quantity"])),
            reference_price=Decimal(str(value["reference_price"])),
            signal_id=str(value["signal_id"]),
        )
    except (KeyError, ValueError) as exc:
        from astraljet.domain.errors import ValidationError

        raise ValidationError(f"Niepoprawny ORDER-INTENT: {exc}") from exc


def _frozen_context(
    repository: RecordRepository,
    mandate_id: str,
    *,
    worker_id: str,
    lease_id: str,
    data_observed_at: str,
) -> FrozenContext:
    from astraljet.domain.errors import ValidationError

    mandate = repository.get_latest(mandate_id)
    if not isinstance(mandate, MandateRecord):
        raise ValidationError("--mandate-id musi wskazywać MANDATE.")
    risk = repository.get_latest(mandate.risk_decision_id)
    if not isinstance(risk, RiskDecisionRecord):
        raise ValidationError("MANDATE wskazuje nieobsługiwaną RISK-DECISION.")
    return FrozenContext(
        mandate=mandate,
        risk_decision=risk,
        strategy_id=mandate.strategy_id,
        strategy_version=mandate.strategy_version,
        code_hash=mandate.code_hash,
        environment=mandate.environment,
        environment_id=mandate.environment_id,
        worker_id=worker_id,
        lease_id=lease_id,
        data_observed_at=data_observed_at,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="astraljet")
    parser.add_argument("--state-dir", required=True, help="Jawny katalog trwałego stanu")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("init", help="Zainicjalizuj lokalny rejestr")

    source = subcommands.add_parser("source", help="Operacje na źródłach")
    source_commands = source.add_subparsers(dest="source_command", required=True)
    source_add = source_commands.add_parser("add", help="Zarejestruj lokalny plik")
    source_add.add_argument("--file", required=True)
    source_add.add_argument("--author", default="unknown")
    source_add.add_argument("--idempotency-key", required=True)

    candidates = subcommands.add_parser("candidates", help="Operacje na kandydatach")
    candidate_commands = candidates.add_subparsers(dest="candidate_command", required=True)
    seed = candidate_commands.add_parser("seed-2026", help="Zarejestruj pięć kandydatów")
    seed.add_argument("--source-id", required=True)
    seed.add_argument("--idempotency-key", required=True)

    strategy = subcommands.add_parser("strategy", help="Formalizacja strategii")
    strategy_commands = strategy.add_subparsers(dest="strategy_command", required=True)
    strategy_commands.add_parser("list", help="Odczytaj wersje strategii bez migracji bazy")
    lineage = strategy_commands.add_parser("lineage", help="Odczytaj rzeczywiste powiązania STRAT")
    lineage.add_argument("--strategy-id", required=True)
    lineage.add_argument("--version", type=int, help="Dokładna wersja; domyślnie najnowsza STRAT")
    strategy_validate = strategy_commands.add_parser("validate", help="Sprawdź i zapisz STRAT")
    strategy_validate.add_argument("--candidate-id", required=True)
    strategy_validate.add_argument("--config", required=True)
    strategy_validate.add_argument("--idempotency-key", required=True)

    data = subcommands.add_parser("data", help="Wersjonowane dane rynkowe")
    data_commands = data.add_subparsers(dest="data_command", required=True)
    data_import = data_commands.add_parser("import", help="Zaimportuj lokalny CSV DATA")
    data_import.add_argument("--file", required=True)
    data_import.add_argument("--provider", required=True)
    data_import.add_argument("--venue", required=True)
    data_import.add_argument("--instruments", required=True, help="Lista rozdzielona przecinkami")
    data_import.add_argument("--timeframe", required=True)
    data_import.add_argument("--timezone", required=True)
    data_import.add_argument("--available-at-rule", required=True)
    data_import.add_argument("--transformation", action="append", default=[])
    data_import.add_argument("--cost-model", required=True)
    data_import.add_argument("--idempotency-key", required=True)
    data_fetch = data_commands.add_parser(
        "fetch-alpaca",
        help="Pobierz historyczne świece crypto z Alpaca do lokalnego snapshotu",
    )
    data_fetch.add_argument("--output", required=True, help="Docelowy plik CSV poza Git")
    data_fetch.add_argument("--start", required=True, help="Początek zakresu ISO-8601 UTC")
    data_fetch.add_argument("--end", required=True, help="Koniec zakresu ISO-8601 UTC")
    data_fetch.add_argument("--symbols", default="BTC/USD,ETH/USD")
    data_fetch.add_argument("--timeframe", default="1Day", choices=("1Day",))
    data_fetch.add_argument("--location", default="us", choices=("us", "us-1", "eu-1"))
    data_fetch.add_argument("--limit", type=int, default=10_000)
    data_fetch.add_argument("--env-file", default=".env")

    experiment = subcommands.add_parser("experiment", help="Zamrożone plany eksperymentów")
    experiment_commands = experiment.add_subparsers(dest="experiment_command", required=True)
    inspect_inputs = experiment_commands.add_parser("inspect-inputs", help="Sprawdź wejścia szkicu EXP bez zapisów do baz")
    inspect_inputs.add_argument("--strategy-id", required=True)
    inspect_inputs.add_argument("--strategy-version", type=int, required=True)
    inspect_inputs.add_argument("--data-state-dir", required=True)
    inspect_inputs.add_argument("--data-id", required=True)
    inspect_inputs.add_argument("--data-version", type=int, required=True)
    inspect_inputs.add_argument("--csv", required=True)
    inspect_inputs.add_argument("--metadata", required=True)
    inspect_inputs.add_argument("--start", required=True)
    inspect_inputs.add_argument("--is-end", required=True)
    inspect_inputs.add_argument("--oos-start", required=True)
    inspect_inputs.add_argument("--end", required=True)
    inspect_inputs.add_argument("--ma-window", type=int, required=True)
    inspect_inputs.add_argument("--slope-lookback", type=int, required=True)
    inspect_inputs.add_argument("--signal-weekday", type=int, required=True, help="Poniedziałek=0, niedziela=6; propozycja, nie zatwierdzenie")
    inspect_inputs.add_argument("--output", help="Opcjonalny nowy JSON; brak nadpisywania")
    inspect_weekly = experiment_commands.add_parser("inspect-weekly", help="Sprawdź zamrożony EXP modelu tygodniowego bez obliczeń")
    _add_weekly_arguments(inspect_weekly)
    experiment_freeze = experiment_commands.add_parser("freeze", help="Zamroź EXP")
    experiment_freeze.add_argument("--strategy-id", required=True)
    experiment_freeze.add_argument("--data-id", required=True)
    experiment_freeze.add_argument("--config", required=True)
    experiment_freeze.add_argument("--idempotency-key", required=True)

    run_parser = subcommands.add_parser("run", help="Przebiegi badawcze")
    run_commands = run_parser.add_subparsers(dest="run_command", required=True)
    weekly = run_commands.add_parser("weekly-offline", help="Raport modelu z zamrożonego EXP; bez RUN i bez zleceń")
    _add_weekly_arguments(weekly)
    recorded = run_commands.add_parser("weekly-recorded", help="Zapisz wszystkie scenariusze zamrożonego EXP jako RUN; bez kwalifikacji i zleceń")
    recorded.add_argument('--experiment-id', required=True)
    recorded.add_argument('--version', type=int, required=True)
    recorded.add_argument('--csv', required=True)
    recorded.add_argument('--owner', default='AJ-07 — model tygodniowy')
    recorded.add_argument('--idempotency-key', required=True)
    weekly_export = run_commands.add_parser('weekly-export', help='Odtwórz zapisany raport serii RUN; tylko odczyt')
    weekly_export.add_argument('--idempotency-key', required=True)
    weekly_export.add_argument('--output', required=True)
    backtest = run_commands.add_parser("backtest", help="Uruchom deterministyczny BACKTEST")
    backtest.add_argument("--experiment-id", required=True)
    backtest.add_argument("--compare-run-id")
    backtest.add_argument("--idempotency-key", required=True)

    review = subcommands.add_parser("review", help="Niezależny przegląd RUN")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    review_create = review_commands.add_parser("create", help="Utwórz REVIEW")
    review_create.add_argument("--run-id", action="append", required=True)
    review_create.add_argument("--reviewer", required=True)
    review_create.add_argument("--evidence", action="append", default=[])
    review_create.add_argument("--finding", action="append", default=[])
    review_create.add_argument("--missing-evidence", action="append", default=[])
    review_create.add_argument("--condition", action="append", default=[])
    review_create.add_argument("--reject-reason", action="append", default=[])
    review_create.add_argument("--idempotency-key", required=True)
    review_create.add_argument("--independent-check", action="append", default=[],
        help="Lokalny JSON obserwacji niezależnego sprawdzenia, przypięty do EXP/RUN; bez wykonywania pliku")

    risk = subcommands.add_parser("risk", help="Decyzje ryzyka")
    risk_commands = risk.add_subparsers(dest="risk_command", required=True)
    risk_decide = risk_commands.add_parser("decide", help="Zapisz RISK-DECISION")
    risk_decide.add_argument("--review-id", required=True)
    risk_decide.add_argument("--decision", choices=("allowed", "blocked"), required=True)
    risk_decide.add_argument("--scope", required=True)
    risk_decide.add_argument("--valid-from", required=True)
    risk_decide.add_argument("--valid-until", required=True)
    risk_decide.add_argument("--limits", required=True, help="Plik JSON z limitami")
    risk_decide.add_argument("--rationale", required=True)
    risk_decide.add_argument("--next-step", required=True)
    risk_decide.add_argument("--idempotency-key", required=True)

    mandate = subcommands.add_parser("mandate", help="Datowane upoważnienia wykonawcy")
    mandate_commands = mandate.add_subparsers(dest="mandate_command", required=True)
    mandate_create = mandate_commands.add_parser("create", help="Utwórz MANDATE")
    mandate_create.add_argument("--risk-decision-id", required=True)
    mandate_create.add_argument("--config", required=True)
    mandate_create.add_argument("--idempotency-key", required=True)

    executor = subcommands.add_parser("executor", help="Sterowanie bezpiecznym wykonawcą")
    executor_commands = executor.add_subparsers(dest="executor_command", required=True)
    lease = executor_commands.add_parser("lease", help="Uzyskaj wyłączny lease")
    lease.add_argument("--environment-id", required=True)
    lease.add_argument("--worker-id", required=True)
    lease.add_argument("--ttl-seconds", type=int, required=True)
    lease.add_argument("--now")
    heartbeat = executor_commands.add_parser("heartbeat", help="Odśwież aktywny lease")
    heartbeat.add_argument("--lease-id", required=True)
    heartbeat.add_argument("--worker-id", required=True)
    heartbeat.add_argument("--now")
    kill = executor_commands.add_parser("kill-switch", help="Nieodwracalnie zablokuj nowe ryzyko środowiska")
    kill.add_argument("--environment-id", required=True)
    kill.add_argument("--reason", required=True)
    kill.add_argument("--idempotency-key", required=True)
    kill.add_argument("--now")

    paper = subcommands.add_parser("paper", help="Deterministyczny PAPER_CONTINUOUS")
    paper_commands = paper.add_subparsers(dest="paper_command", required=True)
    paper_submit = paper_commands.add_parser("submit", help="Zapisz ORDER-INTENT i symulowaną realizację")
    _add_submit_arguments(paper_submit)
    paper_positions = paper_commands.add_parser("positions", help="Pokaż trwałe pozycje PAPER")
    paper_positions.add_argument("--environment-id", required=True)

    demo = subcommands.add_parser("demo", help="Testowy adapter BROKER_DEMO")
    demo_commands = demo.add_subparsers(dest="demo_command", required=True)
    demo_submit = demo_commands.add_parser("submit", help="Przekaż ORDER-INTENT do adaptera testowego")
    _add_submit_arguments(demo_submit)
    demo_submit.add_argument("--confirmed-demo-account", required=True)
    demo_submit.add_argument("--simulate-uncertain", action="store_true")
    demo_reconcile = demo_commands.add_parser("reconcile", help="Rozstrzygnij wynik uncertain")
    demo_reconcile.add_argument("--external-reference", required=True)
    demo_reconcile.add_argument("--result", choices=("accepted", "rejected"), required=True)
    demo_reconcile.add_argument("--idempotency-key", required=True)
    demo_reconcile.add_argument("--now")

    budget = subcommands.add_parser("budget", help="Jawny stan budżetu")
    budget_commands = budget.add_subparsers(dest="budget_command", required=True)
    budget_set = budget_commands.add_parser("set", help="Zapisz BUDGET-STATUS")
    budget_set.add_argument("--config", required=True)
    budget_set.add_argument("--idempotency-key", required=True)

    status = subcommands.add_parser("status", help="Czytelna projekcja stanu")
    status.add_argument("--json", action="store_true", help="Kontrakt JSON (domyślny format MVP)")

    audit = subcommands.add_parser("audit", help="Audyt tylko do odczytu")
    audit_commands = audit.add_subparsers(dest="audit_command", required=True)
    audit_export = audit_commands.add_parser("export", help="Eksportuj zredagowany łańcuch audytowy")
    audit_export.add_argument("--output", help="Opcjonalny plik JSON; bez parametru wypisuje eksport")

    system = subcommands.add_parser("system", help="Diagnostyka istniejącego rejestru")
    system_commands = system.add_subparsers(dest="system_command", required=True)
    system_commands.add_parser(
        "inspect", help="Sprawdź stan i braki powiązań bez tworzenia ani migracji bazy",
    )
    snapshot = system_commands.add_parser("snapshot", help="Eksportuj metadane do lokalnego podglądu w Astrze")
    snapshot.add_argument("--registry-id", required=True, help="Własna etykieta rejestru, np. quickstart-2026-09-19")
    snapshot.add_argument("--output", required=True, help="Nowy plik JSON; istniejący nie zostanie nadpisany")

    registry = subcommands.add_parser("registry", help="Jednokierunkowy transport metadanych badań")
    registry_commands = registry.add_subparsers(dest="registry_command", required=True)
    sync_push = registry_commands.add_parser("sync-push", help="Wyślij allowlistę metadanych do skonfigurowanego Command Center")
    sync_push.add_argument("--registry-id", required=True)
    sync_push.add_argument("--endpoint")
    sync_push.add_argument("--key-id")
    sync_push.add_argument("--connection-file", help="Prywatny plik pobrany z istniejącego panelu; poza repozytorium")
    sync_push.add_argument("--batch-id")
    registry_commands.add_parser("sync-status", help="Pokaż stan wysyłek bez sekretów i treści")

    return parser


def _add_weekly_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--experiment-id", required=True)
    command.add_argument("--version", type=int, required=True)
    command.add_argument("--csv", required=True, help="Jawny plik zgodny z przypiętym DATA")
    command.add_argument("--output", help="Nowy plik JSON; nie nadpisuje istniejącego")


def _add_submit_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--mandate-id", required=True)
    command.add_argument("--worker-id", required=True)
    command.add_argument("--lease-id", required=True)
    command.add_argument("--data-observed-at", required=True)
    command.add_argument("--intent", required=True, help="Plik JSON ORDER-INTENT")
    command.add_argument("--idempotency-key", required=True)
    command.add_argument("--now")


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = StateConfig.from_path(args.state_dir)
    read_only = args.command in ("status", "audit", "system") or (
        args.command == "strategy" and args.strategy_command in ("list", "lineage")
    ) or (
        args.command == "experiment" and args.experiment_command in ("inspect-inputs", "inspect-weekly")
    ) or (
        args.command == "run" and args.run_command in ("weekly-offline", "weekly-export")
    ) or (
        args.command == "registry" and args.registry_command == "sync-status"
    )
    database = Database(config, read_only_mode=read_only)

    if args.command == 'run' and args.run_command == 'weekly-export':
        report = export_weekly_report(database, idempotency_key=args.idempotency_key)
        artifact = publish_snapshot(report, args.output, max_bytes=64 * 1024 * 1024)
        _print_json({'artifact': artifact, 'report_hash': report['report_hash'],
                     'execution_authorized': False, 'records_written': 0})
        return 0

    # Explicit new write path: existing current registry, no initialize/migrate.
    if args.command == 'run' and args.run_command == 'weekly-recorded':
        _print_json(record_weekly_experiment(database, experiment_id=args.experiment_id,
            version=args.version, csv_path=args.csv, owner=args.owner, idempotency_key=args.idempotency_key))
        return 0

    # These read paths deliberately precede initialize(): inspecting a legacy
    # registry must not silently migrate it or create a new, misleading empty one.
    if args.command == "registry" and args.registry_command == "sync-status":
        _print_json(sync_status(database))
        return 0
    if ((args.command == "experiment" and args.experiment_command == "inspect-weekly")
            or (args.command == "run" and args.run_command == "weekly-offline")):
        if args.output and (os.path.lexists(Path(args.output).expanduser()) or Path(args.output).suffix.lower() != '.json'):
            from astraljet.domain.errors import ValidationError

            raise ValidationError('Wybierz nowy plik .json; istniejące pliki nie są nadpisywane.')
        action = inspect_weekly_experiment if args.command == "experiment" else run_weekly_experiment
        report = action(database, experiment_id=args.experiment_id, version=args.version, csv_path=args.csv)
        if args.output:
            published = publish_snapshot(report, args.output, max_bytes=64 * 1024 * 1024)
            _print_json({'status': report['status'], 'artifact': published,
                         'experiment': report['experiment'], 'report_hash': report['report_hash'],
                         'execution_authorized': False, 'run_record_created': False, 'records_written': 0})
        else:
            _print_json(report)
        return 0
    if args.command == "experiment" and args.experiment_command == "inspect-inputs":
        report = inspect_experiment_inputs(
            database, Database(StateConfig.from_path(args.data_state_dir), read_only_mode=True),
            strategy_id=args.strategy_id, strategy_version=args.strategy_version,
            data_id=args.data_id, data_version=args.data_version,
            csv_path=args.csv, metadata_path=args.metadata,
            window=InputWindow(args.start, args.is_end, args.oos_start, args.end,
                               args.ma_window, args.slope_lookback, args.signal_weekday),
        )
        if args.output:
            published = publish_snapshot(report, args.output)
            _print_json({**published, "inspection_status": report["status"],
                         "can_freeze": False, "blockers": report["blockers"]})
        else:
            _print_json(report)
        return 0  # inspection completed; not research eligibility or approval
    if args.command == "system" and args.system_command == "inspect":
        _print_json(inspect_system(database))
        return 0
    if args.command == "system" and args.system_command == "snapshot":
        _print_json(publish_snapshot(registry_snapshot(database, args.registry_id), args.output))
        return 0
    if args.command == "strategy" and args.strategy_command == "list":
        _print_json(list_strategies(database))
        return 0
    if args.command == "strategy" and args.strategy_command == "lineage":
        _print_json(strategy_lineage(database, args.strategy_id, version=args.version))
        return 0

    if args.command == "init":
        database.initialize()
        _print_json({"status": "initialized", "database": str(config.database_path)})
        return 0

    if args.command == "registry" and args.registry_command == "sync-push":
        from astraljet.domain.errors import ValidationError
        if not config.database_path.is_file():
            raise ValidationError('Synchronizacja wymaga istniejącej bazy. Wskaż poprawny --state-dir.', blocker='database_missing')
        credentials = load_connection(args.connection_file) if args.connection_file else dict(
            endpoint=args.endpoint or '', device_token=os.environ.get('ASTRA_REGISTRY_DEVICE_TOKEN', ''),
            key_id=args.key_id or 'local-v1', signing_secret=os.environ.get('ASTRA_REGISTRY_SYNC_HMAC', ''),
            dispatch_token=os.environ.get('ASTRA_SITE_DISPATCH_TOKEN'))
        if args.connection_file and ((args.endpoint and args.endpoint != credentials['endpoint']) or
                                     (args.key_id and args.key_id != credentials['key_id'])):
            raise ValidationError('Argumenty nie odpowiadają prywatnemu plikowi połączenia.')
        validate_connection(**credentials)
        database.initialize()
        _print_json(push_registry_sync(database, args.registry_id, batch_id=args.batch_id, **credentials))
        return 0

    independent_checks = ()
    if args.command == 'review' and args.review_command == 'create':
        from astraljet.domain.errors import ValidationError
        if not config.database_path.is_file():
            raise ValidationError('REVIEW wymaga istniejącego rejestru z RUN; nie tworzę pustej bazy.')
        if len(args.run_id) > 100 or len(args.independent_check) > 8:
            raise ValidationError('Wskaż maksymalnie 100 RUN i 8 raportów kontrolnych.')
        independent_checks = tuple(load_independent_check(path) for path in args.independent_check)
    if not read_only:
        database.initialize()
    repository = RecordRepository(database)
    service = IntakeService(repository)

    if args.command == "source" and args.source_command == "add":
        record, created = service.add_source(
            args.file,
            author=args.author,
            idempotency_key=args.idempotency_key,
        )
        _print_json({"created": created, "source": asdict(record)})
        return 0

    if args.command == "candidates" and args.candidate_command == "seed-2026":
        records, created_count = service.seed_initial_candidates(
            args.source_id,
            idempotency_key=args.idempotency_key,
        )
        _print_json(
            {
                "created_count": created_count,
                "candidate_count": len(records),
                "candidates": [asdict(record) for record in records],
            }
        )
        return 0

    if args.command == "strategy" and args.strategy_command == "validate":
        candidate = repository.get_latest(args.candidate_id)
        if not isinstance(candidate, CandidateRecord):
            from astraljet.domain.errors import ValidationError

            raise ValidationError("--candidate-id musi wskazywać CAND.")
        definition = StrategyDefinition.from_dict(_load_json_object(args.config))
        strategy_record = create_strategy(
            candidate_id=candidate.record_id,
            definition=definition,
            owner="Karol",
        )
        strategy_record, _event, created = repository.save(
            strategy_record,
            event_type="strategy.validated",
            reason="Zapisano wynik walidacji jednoznaczności STRAT.",
            outcome=strategy_record.strategy_status.value,
            actor="ASTRA Pro — Badacz strategii",
            idempotency_key=args.idempotency_key,
        )
        _print_json({"created": created, "strategy": asdict(strategy_record)})
        return 0 if strategy_record.strategy_status is StrategyStatus.READY else 3

    if args.command == "data" and args.data_command == "fetch-alpaca":
        symbols = tuple(value.strip().upper() for value in args.symbols.split(",") if value.strip())
        credentials, base_url = load_alpaca_credentials(args.env_file)
        result = AlpacaCryptoDataClient(credentials, base_url=base_url).fetch_to_csv(
            CryptoBarsRequest(
                symbols=symbols,
                start=args.start,
                end=args.end,
                timeframe=args.timeframe,
                location=args.location,
                limit=args.limit,
            ),
            args.output,
        )
        _print_json(
            {
                "status": "snapshot_created",
                "csv_path": str(result.csv_path),
                "metadata_path": str(result.metadata_path),
                "csv_sha256": result.csv_sha256,
                "raw_payload_sha256": result.raw_payload_sha256,
                "row_count": result.row_count,
                "page_count": result.page_count,
                "start": result.start,
                "end": result.end,
                "retrieved_at": result.retrieved_at,
                "registered_as_data": False,
                "next_step": "Zweryfikuj metadane i model kosztów, potem użyj data import.",
            }
        )
        return 0

    if args.command == "data" and args.data_command == "import":
        instruments = tuple(value.strip() for value in args.instruments.split(",") if value.strip())
        data_record = import_market_data(
            args.file,
            spec=DataImportSpec(
                provider=args.provider,
                venue=args.venue,
                instruments=instruments,
                timeframe=args.timeframe,
                timezone=args.timezone,
                available_at_rule=args.available_at_rule,
                transformations=tuple(args.transformation),
                cost_model=args.cost_model,
            ),
            owner="Karol",
        )
        data_record, _event, created = repository.save(
            data_record,
            event_type="data.imported",
            reason="Zarejestrowano lokalny, wersjonowany snapshot DATA.",
            outcome=data_record.data_status.value,
            actor="AJ-06 Dane i jakość danych",
            idempotency_key=args.idempotency_key,
        )
        _print_json({"created": created, "data": asdict(data_record)})
        return 0 if data_record.data_status is DataStatus.READY else 3

    if args.command == "experiment" and args.experiment_command == "freeze":
        strategy_record = repository.get_latest(args.strategy_id)
        data_record = repository.get_latest(args.data_id)
        if not isinstance(strategy_record, StrategyRecord) or not isinstance(data_record, DataRecord):
            from astraljet.domain.errors import ValidationError

            raise ValidationError("EXP wymaga poprawnych identyfikatorów STRAT i DATA.")
        config_value = _load_json_object(args.config)
        definition = ExperimentDefinition(
            code_hash=str(config_value["code_hash"]),
            hypothesis=str(config_value["hypothesis"]),
            in_sample=tuple(config_value["in_sample"]),
            out_of_sample=tuple(config_value["out_of_sample"]),
            allowed_variants=tuple(dict(value) for value in config_value["allowed_variants"]),
            criteria=dict(config_value["criteria"]),
            budget=str(config_value["budget"]),
            seed=int(config_value["seed"]),
            metrics=tuple(config_value["metrics"]),
            tolerance={str(key): str(value) for key, value in config_value["tolerance"].items()},
            stop_rules=tuple(config_value["stop_rules"]),
        )
        experiment_record = freeze_experiment(
            strategy=strategy_record,
            data=data_record,
            definition=definition,
            owner="Karol",
        )
        experiment_record, _event, created = repository.save(
            experiment_record,
            event_type="experiment.frozen",
            reason="Zamrożono EXP przed poznaniem wyniku.",
            outcome="frozen",
            actor="ASTRA Pro — Tester strategii",
            idempotency_key=args.idempotency_key,
        )
        _print_json({"created": created, "experiment": asdict(experiment_record)})
        return 0

    if args.command == "run" and args.run_command == "backtest":
        experiment_record = repository.get_latest(args.experiment_id)
        if not isinstance(experiment_record, ExperimentRecord):
            from astraljet.domain.errors import ValidationError

            raise ValidationError("--experiment-id musi wskazywać EXP.")
        strategy_record = repository.get(
            experiment_record.strategy_id,
            experiment_record.strategy_version,
        )
        data_record = repository.get(experiment_record.data_id, experiment_record.data_version)
        if not isinstance(strategy_record, StrategyRecord) or not isinstance(data_record, DataRecord):
            from astraljet.domain.errors import ValidationError

            raise ValidationError("EXP wskazuje nieobsługiwaną wersję STRAT lub DATA.")
        comparison_target = None
        if args.compare_run_id:
            comparison_target = repository.get_latest(args.compare_run_id)
            if not isinstance(comparison_target, RunRecord):
                from astraljet.domain.errors import ValidationError

                raise ValidationError("--compare-run-id musi wskazywać RUN.")
        run_record = run_backtest(
            strategy=strategy_record,
            data=data_record,
            experiment=experiment_record,
            bars=load_market_data(data_record),
            owner="independent-reproducer" if comparison_target else "ASTRA Pro — Tester strategii",
        )
        run_record, _event, created = repository.save(
            run_record,
            event_type="run.reproduced" if comparison_target else "run.completed",
            reason=(
                "Odtworzono RUN z zamrożonych artefaktów."
                if comparison_target
                else "Wykonano RUN z zamrożonych artefaktów."
            ),
            outcome=run_record.run_outcome.value,
            actor=run_record.owner,
            idempotency_key=args.idempotency_key,
        )
        comparison = (
            asdict(compare_runs(comparison_target, run_record, experiment_record.tolerance))
            if comparison_target
            else None
        )
        _print_json({"created": created, "run": asdict(run_record), "comparison": comparison})
        return 0

    if args.command == "review" and args.review_command == "create":
        run_records: list[RunRecord] = []
        experiments: list[ExperimentRecord] = []
        # Resolve the whole evidence set in one consistent SQLite snapshot.
        with database.read_only() as connection:
            for run_id in args.run_id:
                row = connection.execute(
                    'SELECT * FROM records WHERE record_id = ? ORDER BY version DESC LIMIT 1',
                    (run_id,),
                ).fetchone()
                if row is None:
                    raise ValidationError('Nie znaleziono wymaganego RUN.')
                record = repository._record_from_row(row)
                if not isinstance(record, RunRecord):
                    raise ValidationError("Każde --run-id musi wskazywać RUN.")
                experiment_record = repository._get(connection, record.experiment_id, record.experiment_version)
                if not isinstance(experiment_record, ExperimentRecord):
                    raise ValidationError("RUN wskazuje nieobsługiwany EXP.")
                run_records.append(record)
                experiments.append(experiment_record)
        reproduction = (
            compare_runs(run_records[0], run_records[1], experiments[0].tolerance)
            if len(run_records) >= 2
            else None
        )
        review_record = create_review(
            runs=tuple(run_records),
            experiments=tuple(experiments),
            request=ReviewRequest(
                reviewer=args.reviewer,
                evidence=tuple(args.evidence),
                findings=tuple(args.finding),
                missing_evidence=tuple(args.missing_evidence),
                conditions=tuple(args.condition),
                rejection_reasons=tuple(args.reject_reason),
            ),
            reproduction=reproduction,
            owner=args.reviewer,
            independent_checks=independent_checks,
        )
        requested_review = review_record
        review_record, _event, created = repository.save(
            review_record,
            event_type="review.completed",
            reason="Niezależny recenzent ocenił pełny pakiet RUN.",
            outcome=review_record.verdict.value,
            actor=args.reviewer,
            idempotency_key=args.idempotency_key,
        )
        # Duplicate save never changes the old record/event. Check the returned
        # record before reporting success, including collisions with other types.
        validate_review_replay(review_record, requested_review)
        _print_json(
            {
                "created": created,
                "review": asdict(review_record),
                "summary": {
                    "verdict": review_record.verdict.value,
                    "comparability": review_record.comparability_status,
                    "missing_evidence": list(review_record.missing_evidence),
                    "next_step": list(review_record.conditions),
                },
            }
        )
        return 0

    if args.command == "risk" and args.risk_command == "decide":
        review_record = repository.get_latest(args.review_id)
        if not isinstance(review_record, ReviewRecord):
            from astraljet.domain.errors import ValidationError

            raise ValidationError("--review-id musi wskazywać REVIEW.")
        limits = _load_json_object(args.limits)
        requested = RiskDecisionStatus(args.decision)
        decision_record = create_risk_decision(
            review=review_record,
            request=RiskDecisionRequest(
                requested_decision=requested,
                scope=args.scope,
                valid_from=args.valid_from,
                valid_until=args.valid_until,
                limits=limits,
                rationale=args.rationale,
                permitted_next_step=args.next_step,
            ),
            owner="AJ-09",
        )
        decision_record, _event, created = repository.save(
            decision_record,
            event_type="risk.decided",
            reason="Zapisano ograniczoną i datowaną decyzję ryzyka.",
            outcome=decision_record.decision.value,
            actor="AJ-09",
            idempotency_key=args.idempotency_key,
        )
        _print_json(
            {
                "created": created,
                "risk_decision": asdict(decision_record),
                "summary": {
                    "decision": decision_record.decision.value,
                    "blockers": list(decision_record.blockers),
                    "permitted_next_step": decision_record.permitted_next_step,
                },
            }
        )
        if requested is RiskDecisionStatus.ALLOWED and decision_record.decision is RiskDecisionStatus.BLOCKED:
            return 3
        return 0

    if args.command == "mandate" and args.mandate_command == "create":
        from astraljet.domain.errors import ValidationError

        risk_record = repository.get_latest(args.risk_decision_id)
        if not isinstance(risk_record, RiskDecisionRecord):
            raise ValidationError("--risk-decision-id musi wskazywać RISK-DECISION.")
        value = _load_json_object(args.config)
        try:
            request = MandateRequest(
                authorized_by=str(value["authorized_by"]),
                strategy_id=str(value["strategy_id"]),
                strategy_version=int(value["strategy_version"]),
                code_hash=str(value["code_hash"]),
                environment=ExecutionEnvironment(str(value["environment"])),
                environment_id=str(value["environment_id"]),
                account_id=(str(value["account_id"]) if value.get("account_id") is not None else None),
                instruments=tuple(str(item) for item in value["instruments"]),
                limits=dict(value["limits"]),
                starts_at=str(value["starts_at"]),
                expires_at=str(value["expires_at"]),
                stop_conditions=tuple(str(item) for item in value["stop_conditions"]),
                max_data_age_seconds=int(value["max_data_age_seconds"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"Niepoprawna konfiguracja MANDATE: {exc}") from exc
        mandate_record = create_mandate(risk_decision=risk_record, request=request, owner="Karol")
        mandate_record, _event, created = repository.save(
            mandate_record,
            event_type="mandate.authorized",
            reason="Karol zatwierdził ograniczony mandat PAPER/DEMO.",
            outcome=mandate_record.environment.value,
            actor=mandate_record.authorized_by,
            idempotency_key=args.idempotency_key,
        )
        _print_json({"created": created, "mandate": asdict(mandate_record)})
        return 0

    if args.command == "executor":
        guard = ExecutorGuard(database)
        if args.executor_command == "lease":
            result = guard.acquire_lease(
                args.environment_id,
                args.worker_id,
                ttl_seconds=args.ttl_seconds,
                now=_parse_time(args.now),
            )
            _print_json({"lease": asdict(result)})
            return 0
        if args.executor_command == "heartbeat":
            result = guard.heartbeat(args.lease_id, args.worker_id, now=_parse_time(args.now))
            _print_json({"heartbeat": asdict(result)})
            return 0
        if args.executor_command == "kill-switch":
            result = guard.activate_kill_switch(
                args.environment_id,
                reason=args.reason,
                idempotency_key=args.idempotency_key,
                now=_parse_time(args.now),
            )
            _print_json({"kill_switch": asdict(result)})
            return 0

    if args.command == "paper":
        paper_executor = PaperExecutor(database, ExecutorGuard(database))
        if args.paper_command == "positions":
            _print_json({"positions": asdict(paper_executor.positions(args.environment_id))})
            return 0
        frozen = _frozen_context(
            repository,
            args.mandate_id,
            worker_id=args.worker_id,
            lease_id=args.lease_id,
            data_observed_at=args.data_observed_at,
        )
        receipt = paper_executor.submit_intent(
            frozen,
            _intent_from_file(args.intent),
            idempotency_key=args.idempotency_key,
            now=_parse_time(args.now),
        )
        incubation = None
        if receipt.state is not ExecutionResultState.DUPLICATE:
            incubation_record = create_incubation(
                mandate=frozen.mandate,
                lease_id=frozen.lease_id,
                worker_id=frozen.worker_id,
                last_heartbeat_at=_parse_time(args.now).isoformat().replace("+00:00", "Z"),
                status=IncubationStatus.ACTIVE,
                owner="Wykonawca AstralJet",
            )
            incubation_record, _event, _created = repository.save(
                incubation_record,
                event_type="incubation.paper_fill",
                reason="Zapisano deterministyczną realizację PAPER.",
                outcome=receipt.state.value,
                actor=frozen.worker_id,
                idempotency_key=f"{args.idempotency_key}-incu",
            )
            incubation = asdict(incubation_record)
        _print_json({"execution": asdict(receipt), "incubation": incubation})
        return 0

    if args.command == "demo":
        if args.demo_command == "reconcile":
            adapter = DemoAdapter(database, ExecutorGuard(database), confirmed_demo_account=None)
            result_state = ExecutionResultState(args.result)
            adapter.set_reconciliation_result(args.external_reference, result_state)
            receipt = adapter.reconcile(
                args.external_reference,
                idempotency_key=args.idempotency_key,
                now=_parse_time(args.now),
            )
            _print_json({"reconciliation": asdict(receipt)})
            return 0
        frozen = _frozen_context(
            repository,
            args.mandate_id,
            worker_id=args.worker_id,
            lease_id=args.lease_id,
            data_observed_at=args.data_observed_at,
        )
        adapter = DemoAdapter(
            database,
            ExecutorGuard(database),
            confirmed_demo_account=args.confirmed_demo_account,
            simulate_next_uncertain=args.simulate_uncertain,
        )
        receipt = adapter.submit_intent(
            frozen,
            _intent_from_file(args.intent),
            idempotency_key=args.idempotency_key,
            now=_parse_time(args.now),
        )
        incubation = None
        if receipt.state is not ExecutionResultState.DUPLICATE:
            status = (
                IncubationStatus.UNCERTAIN
                if receipt.state is ExecutionResultState.UNCERTAIN
                else IncubationStatus.ACTIVE
            )
            incubation_record = create_incubation(
                mandate=frozen.mandate,
                lease_id=frozen.lease_id,
                worker_id=frozen.worker_id,
                last_heartbeat_at=_parse_time(args.now).isoformat().replace("+00:00", "Z"),
                status=status,
                owner="Wykonawca AstralJet",
                alerts=("Wymagane reconciliation.",) if status is IncubationStatus.UNCERTAIN else (),
            )
            incubation_record, _event, _created = repository.save(
                incubation_record,
                event_type="incubation.demo_result",
                reason="Zapisano wynik testowego adaptera BROKER_DEMO.",
                outcome=receipt.state.value,
                actor=frozen.worker_id,
                idempotency_key=f"{args.idempotency_key}-incu",
            )
            incubation = asdict(incubation_record)
        _print_json({"execution": asdict(receipt), "incubation": incubation})
        return 0

    if args.command == "budget" and args.budget_command == "set":
        from astraljet.domain.errors import ValidationError

        value = _load_json_object(args.config)
        try:
            budget_record = create_budget_status(
                BudgetStatusRequest(
                    currency=str(value["currency"]),
                    limit=str(value["limit"]),
                    settled_cost=str(value["settled_cost"]),
                    active_reservation=str(value["active_reservation"]),
                    unresolved_cost=str(value["unresolved_cost"]),
                    scope=str(value["scope"]),
                ),
                owner="Karol",
            )
        except KeyError as exc:
            raise ValidationError(f"Niepoprawna konfiguracja BUDGET-STATUS: brak {exc}.") from exc
        budget_record, _event, created = repository.save(
            budget_record,
            event_type="budget.status_recorded",
            reason="Zapisano jawny limit, koszty, rezerwację i koszt nierozstrzygnięty.",
            outcome="recorded",
            actor="Karol",
            idempotency_key=args.idempotency_key,
        )
        _print_json({"created": created, "budget_status": asdict(budget_record)})
        return 0

    if args.command == "status":
        _print_json(build_status(database))
        return 0

    if args.command == "audit" and args.audit_command == "export":
        exported = export_audit(database)
        if args.output:
            output_path = Path(args.output).expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(exported, ensure_ascii=False, sort_keys=True, indent=2),
                encoding="utf-8",
            )
            _print_json(
                {
                    "status": "exported",
                    "output": str(output_path),
                    "export_hash": exported["export_hash"],
                    "record_count": len(exported["records"]),
                    "event_count": len(exported["events"]),
                }
            )
        else:
            _print_json(exported)
        return 0

    raise TechnicalError("Nieobsługiwana komenda CLI.")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except AstralJetError as exc:
        _print_json(exc.as_dict())
        return exc.exit_code
    except Exception as exc:  # pragma: no cover - ostatnia granica CLI
        error = TechnicalError(f"Błąd techniczny: {exc}")
        _print_json(error.as_dict())
        return error.exit_code


if __name__ == "__main__":
    sys.exit(main())
