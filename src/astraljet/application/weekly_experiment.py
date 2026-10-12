"""Explicit frozen-EXP adapter; offline output only, never registry promotion.

The profile is deliberately narrow. Unknown rules/criteria are blocked, not
translated from free text. Helpers construct specifications, not approvals.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import sqlite3
from dataclasses import asdict, fields
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from astraljet.application.experiments import ExperimentDefinition
from astraljet.domain.enums import DataStatus, StrategyStatus, TechnicalStatus
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.records import DataRecord, ExperimentRecord, StrategyRecord, record_content_hash
from astraljet.domain.validation import canonical_json, sha256_text
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.migrations import SCHEMA_VERSION
from astraljet.infrastructure.repositories import RecordRepository
from astraljet.lab.data_quality import MarketBar, REQUIRED_COLUMNS
from astraljet.lab.portfolio_ledger import finite
from astraljet.lab.strategy import StrategyDefinition
from astraljet.lab.weekly_portfolio import (
    CostScenario, WeeklyProtocol, _daily_bars, simulate_weekly, weekly_engine_fingerprint,
)


MODEL_ID = 'weekly-btc-eth-state-v1'
STOP_RULES = ('validation_error', 'input_or_code_changed')
MAX_CSV_BYTES = 50 * 1024 * 1024
SUPPORTED_METRICS = frozenset((
    'net_return', 'annualized_return', 'max_drawdown', 'total_cost',
    'executed_notional', 'number_of_rebalances', 'mean_gross_exposure_at_close',
))
VARIANT_KEYS = frozenset((
    'model_id', 'ma_window', 'slope_lookback', 'initial_equity',
    'scenario_name', 'cost_bps', 'extra_delay_days',
))


def _block(message: str, code: str) -> None:
    raise DomainBlockedError(message, blocker=code, owner='AJ-05 / AJ-07',
        allowed_next_action='Wyjaśnij rozbieżność; zmiany wymagają nowej, zatwierdzonej wersji STRAT/DATA/EXP.')


def _decimal_string(value: Any) -> Decimal:
    if not isinstance(value, str) or not value or len(value) > 80:
        raise ValidationError('Wymagany jawny, skończony zapis dziesiętny jako tekst.')
    try:
        result = Decimal(value)
        finite(result)
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError('Niepoprawna wartość dziesiętna.') from exc
    return result


def _variants(values: tuple[dict, ...]) -> tuple[CostScenario, ...]:
    if not isinstance(values, tuple) or not 1 <= len(values) <= 8:
        raise ValidationError('Wymagane 1–8 jawnych wariantów, bez przeszukiwania parametrów.')
    scenarios, names, mechanics = [], set(), None
    for value in values:
        if not isinstance(value, dict) or set(value) != VARIANT_KEYS or value['model_id'] != MODEL_ID:
            raise ValidationError('Nieobsługiwany model lub pola wariantu tygodniowego.')
        initial = _decimal_string(value['initial_equity'])
        WeeklyProtocol('2021-01-01', '2021-02-28', '2021-03-01', '2021-03-31',
                       value['ma_window'], value['slope_lookback'], initial).validate()
        current = (value['ma_window'], value['slope_lookback'], value['initial_equity'])
        if mechanics is not None and current != mechanics:
            raise ValidationError('W tym EXP warianty mogą zmieniać wyłącznie koszty i opóźnienie.')
        mechanics = current
        scenario = CostScenario(value['scenario_name'], _decimal_string(value['cost_bps']), value['extra_delay_days'])
        scenario.validate()
        if len(scenario.name) > 80 or scenario.name in names:
            raise ValidationError('Nazwy scenariuszy muszą być unikalne, maks. 80 znaków.')
        names.add(scenario.name)
        scenarios.append(scenario)
    return tuple(scenarios)


def weekly_strategy_definition(*, venue: str, variants: tuple[dict, ...], source_adaptation: str) -> StrategyDefinition:
    """Exact supported rule vocabulary. Calling this does not register/approve it."""
    _variants(variants)
    if not isinstance(venue, str) or not venue.strip():
        raise ValidationError('Wymagany jawny rynek danych.')
    cost_model = canonical_json({'model': 'constant_bps_per_risky_leg_notional', 'scenarios': [
        {k: v[k] for k in ('scenario_name', 'cost_bps', 'extra_delay_days')} for v in variants]})
    return StrategyDefinition(
        instruments=('BTCUSD', 'ETHUSD'), venue=venue, timeframe='1d',
        signal_timing='sunday_closed_daily_bar_utc',
        execution_timing='next_daily_open_plus_explicit_scenario_delay',
        entry_rule='btc_close_gt_sma_and_sma_gt_lagged_sma; two_consecutive_positive_weeks',
        exit_rule='negative_or_equal_signal_resets_to_risk_off',
        sizing_rule='initial_cash; off=35/10/55; rebuild=52.5/15/32.5; on=70/20/10; state_change_only',
        cost_model=cost_model,
        constraints=('spot_long_only', 'no_leverage', 'cash_yield_zero', 'eth_follows_btc', 'self_financing'),
        missing_data_policy='block_on_missing_duplicate_or_invalid_daily_bar',
        benchmark='80/20_btc_eth; same_first_execution; monthly_first_open_plus_scenario_delay',
        allowed_parameters=copy.deepcopy(variants[0]), source_adaptation=source_adaptation,
    )


def _source_hash() -> str:
    package = Path(__file__).resolve().parents[1]
    names = (
        'application/weekly_experiment.py', 'application/experiments.py',
        'application/weekly_recorded.py', 'lab/weekly_run.py', 'lab/reproduction.py',
        'lab/weekly_portfolio.py', 'lab/portfolio_ledger.py', 'lab/data_quality.py', 'lab/strategy.py',
        'domain/records.py', 'domain/enums.py', 'domain/validation.py', 'domain/errors.py',
        'infrastructure/database.py', 'infrastructure/repositories.py', 'infrastructure/migrations.py',
        'infrastructure/event_store.py', 'infrastructure/snapshot_file.py', 'config.py', 'cli.py',
    )
    return sha256_text(canonical_json({name: hashlib.sha256((package / name).read_bytes()).hexdigest()
                                     for name in names}))


def weekly_adapter_fingerprint() -> str:
    if _source_hash() != _LOADED_HASH:
        _block('Pliki adaptera zmieniły się po załadowaniu; uruchom nowy proces.', 'loaded_adapter_changed')
    weekly_engine_fingerprint()
    return _LOADED_HASH


def weekly_binding(strategy: StrategyRecord, data: DataRecord) -> dict[str, Any]:
    """Full snapshots, because legacy DATA.content_hash covers CSV, not metadata."""
    return {'schema': 'weekly-frozen-inputs-v1', 'model_id': MODEL_ID,
            'engine_hash': weekly_engine_fingerprint(),
            'strategy_record_hash': record_content_hash(asdict(strategy)),
            'data_record_hash': record_content_hash(asdict(data))}


def _records(database: Database, record_id: str, version: int):
    if (not isinstance(record_id, str) or not record_id.startswith('EXP-')
            or type(version) is not int or version < 1):
        raise ValidationError('Wskaż EXP i konkretną dodatnią wersję, bez fallbacku do latest.')
    repository = RecordRepository(database)
    try:
        # One read transaction: EXP and both pinned records form one snapshot.
        with database.read_only() as connection:
            schema = connection.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]
            if type(schema) is not int or not 1 <= schema <= SCHEMA_VERSION:
                raise ValidationError('Nieobsługiwany schemat rejestru.')
            experiment = repository._get(connection, record_id, version)
            if not isinstance(experiment, ExperimentRecord):
                raise ValidationError('Wymagany rekord EXP.')
            for value in (experiment.strategy_version, experiment.data_version):
                if type(value) is not int or value < 1:
                    raise ValidationError('EXP musi przypinać dodatnie wersje STRAT i DATA.')
            strategy = repository._get(connection, experiment.strategy_id, experiment.strategy_version)
            data = repository._get(connection, experiment.data_id, experiment.data_version)
            if not isinstance(strategy, StrategyRecord) or not isinstance(data, DataRecord):
                raise ValidationError('Niepoprawne typy przypiętych rekordów.')
    except (sqlite3.DatabaseError, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValidationError('Nie można odczytać kompletnego zamrożonego EXP/STRAT/DATA.') from exc
    return experiment, strategy, data


def _date(value: str) -> str:
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.utcoffset() != timedelta(0) or stamp.time().isoformat() != '00:00:00':
            raise ValueError('daily UTC boundary required')
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError('Granice EXP wymagają dat świec 00:00 UTC, włącznie z ostatnią świecą.') from exc
    return stamp.date().isoformat()


def _validate_plan(experiment: ExperimentRecord, strategy: StrategyRecord, data: DataRecord):
    adapter_hash = weekly_adapter_fingerprint()
    if experiment.code_hash != adapter_hash:
        _block('EXP nie przypina aktualnego adaptera i silnika tygodniowego.', 'weekly_code_mismatch')
    if (experiment.technical_status is not TechnicalStatus.COMPLETED
            or strategy.technical_status is not TechnicalStatus.COMPLETED
            or data.technical_status is not TechnicalStatus.COMPLETED
            or strategy.strategy_status is not StrategyStatus.READY or data.data_status is not DataStatus.READY):
        _block('EXP, STRAT lub DATA nie są gotowe do obliczeń offline.', 'weekly_inputs_not_ready')
    if not isinstance(experiment.criteria, dict) or experiment.criteria.get('weekly_binding') != weekly_binding(strategy, data):
        _block('Pełny zapis STRAT/DATA lub implementacja różni się od powiązania EXP.', 'weekly_binding_mismatch')
    payload = strategy.payload()
    payload.pop('strategy_status')
    if strategy.content_hash != record_content_hash(payload):
        _block('Hash reguł STRAT jest niespójny.', 'strategy_content_mismatch')
    definition_fields = {field.name: getattr(experiment, field.name) for field in fields(ExperimentDefinition)}
    plan_payload = {
        'strategy_id': strategy.record_id, 'strategy_version': strategy.version, 'strategy_hash': strategy.content_hash,
        'data_id': data.record_id, 'data_version': data.version, 'data_hash': data.content_hash,
        **definition_fields, 'cost_model': strategy.cost_model, 'frozen_at': experiment.frozen_at,
    }
    if experiment.plan_hash != record_content_hash(plan_payload) or experiment.content_hash != experiment.plan_hash:
        _block('Zawartość EXP różni się od zamrożonego planu.', 'experiment_plan_mismatch')
    if (set(experiment.criteria) != {'weekly_binding', 'assessment'}
            or experiment.criteria['assessment'] != 'manual_review_required'
            or experiment.stop_rules != STOP_RULES or experiment.budget != '0'
            or type(experiment.seed) is not int or experiment.seed != 0):
        _block('Adapter nie obsługuje tych kryteriów, reguł stop, budżetu lub ziarna.', 'unsupported_weekly_protocol')
    if (not isinstance(experiment.metrics, tuple) or not experiment.metrics
            or any(not isinstance(m, str) or m not in SUPPORTED_METRICS for m in experiment.metrics)
            or len(set(experiment.metrics)) != len(experiment.metrics)
            or not isinstance(experiment.tolerance, dict) or set(experiment.tolerance) != set(experiment.metrics)):
        _block('EXP wymaga nieobsługiwanych metryk lub niepełnych tolerancji.', 'unsupported_weekly_metrics')
    for value in experiment.tolerance.values():
        _decimal_string(value)
    scenarios = _variants(experiment.allowed_variants)
    expected = weekly_strategy_definition(venue=strategy.venue, variants=experiment.allowed_variants,
                                         source_adaptation=strategy.source_adaptation)
    expected_payload = {'candidate_id': strategy.candidate_id, **expected.as_dict()}
    if canonical_json(payload) != canonical_json(expected_payload):
        _block('Reguły STRAT nie odpowiadają dokładnemu profilowi modelu tygodniowego.', 'weekly_rule_mismatch')
    if (data.instruments != strategy.instruments or data.venue != strategy.venue
            or data.timeframe != '1d' or data.timezone != 'UTC' or data.schema_version != 'ohlcv-v1'
            or data.cost_model != strategy.cost_model or experiment.cost_model != strategy.cost_model
            or data.quality_findings or not data.provider.strip()
            or data.available_at_rule != 'bar_close_utc_next_open_proxy'
            or data.content_hash != data.sha256):
        _block('DATA nie pasuje do jawnego profilu STRAT/EXP.', 'weekly_data_profile_mismatch')
    variant = experiment.allowed_variants[0]
    if len(experiment.in_sample) != 2 or len(experiment.out_of_sample) != 2:
        raise ValidationError('Wymagane dwie jawne granice IS i OOS.')
    protocol = WeeklyProtocol(*(_date(t) for t in (*experiment.in_sample, *experiment.out_of_sample)),
                              variant['ma_window'], variant['slope_lookback'], _decimal_string(variant['initial_equity']))
    start, is_end, _, end = protocol.validate()
    eligible = start + timedelta(days=protocol.ma_window - 1 + protocol.slope_lookback)
    first_signal = eligible + timedelta(days=(6 - eligible.weekday()) % 7)
    if first_signal + timedelta(days=1 + max(s.extra_delay_days for s in scenarios)) > is_end:
        _block('Zakres IS nie obejmuje warm-up, pierwszego sygnału i wykonania każdego wariantu.',
               'weekly_insufficient_in_sample')
    return protocol, scenarios, adapter_hash


def _snapshot(data: DataRecord, csv_path: str | Path, protocol: WeeklyProtocol, frozen_at: str):
    path = Path(csv_path).resolve()
    if path != Path(data.locator).resolve():
        _block('Jawnie wskazany CSV nie jest plikiem przypiętym przez DATA.', 'weekly_csv_locator_mismatch')
    try:
        with path.open('rb') as stream:
            content = stream.read(MAX_CSV_BYTES + 1)
    except OSError as exc:
        raise ValidationError('Nie można odczytać wskazanego CSV.') from exc
    if len(content) > MAX_CSV_BYTES:
        raise ValidationError('CSV przekracza limit 50 MiB.')
    digest = hashlib.sha256(content).hexdigest().upper()
    if digest != data.sha256.upper():
        _block('Bajty CSV różnią się od przypiętego DATA.', 'weekly_csv_hash_mismatch')
    bars = []
    try:
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig'), newline=''), strict=True)
        columns = reader.fieldnames or []
        if len(columns) != len(set(columns)) or not set(REQUIRED_COLUMNS) <= set(columns):
            raise ValidationError('Wymagane unikalne kolumny timestamp, instrument i OHLC.')
        for row in reader:
            if None in row or any(row.get(key) is None for key in REQUIRED_COLUMNS):
                raise ValidationError('Niepoprawny wiersz CSV.')
            # Same bytes are hashed and parsed; never reopen via the legacy loader.
            day = _date(row['timestamp'])
            prices = {key: _decimal_string(row[key]) for key in ('open', 'high', 'low', 'close')}
            bars.append(MarketBar(day + 'T00:00:00Z', row['instrument'], **prices))
    except (UnicodeError, csv.Error) as exc:
        raise ValidationError('Niepoprawny CSV UTF-8.') from exc
    if not bars or type(data.row_count) is not int or len(bars) != data.row_count:
        _block('Liczba wierszy CSV jest niespójna z DATA.', 'weekly_csv_metadata_mismatch')
    start, end = _date(data.start), _date(data.end)
    if min(b.timestamp[:10] for b in bars) != start or max(b.timestamp[:10] for b in bars) != end:
        _block('Granice CSV są niespójne z DATA.', 'weekly_csv_metadata_mismatch')
    # Validate the entire registered snapshot, not just a favourable subrange.
    if (date.fromisoformat(end) - date.fromisoformat(start)).days > 36525:
        raise ValidationError('Snapshot przekracza 100 lat.')
    _daily_bars(bars, date.fromisoformat(start), date.fromisoformat(end))
    last_closed = datetime.fromisoformat(end + 'T00:00:00+00:00') + timedelta(days=1)
    if last_closed > datetime.fromisoformat(frozen_at.replace('Z', '+00:00')):
        _block('Snapshot obejmuje świecę niezamkniętą w chwili zamrożenia EXP.', 'weekly_unclosed_bar')
    selected = [b for b in bars if protocol.start <= b.timestamp[:10] <= protocol.end]
    _daily_bars(selected, date.fromisoformat(protocol.start), date.fromisoformat(protocol.end))
    return selected, digest


def _prepare(database: Database, *, experiment_id: str, version: int, csv_path: str | Path):
    experiment, strategy, data = _records(database, experiment_id, version)
    protocol, scenarios, adapter_hash = _validate_plan(experiment, strategy, data)
    bars, csv_hash = _snapshot(data, csv_path, protocol, experiment.frozen_at)
    report = {
        'schema': 'weekly-offline-report-v1', 'status': 'INPUTS_VERIFIED_ONLY',
        'execution_authorized': False, 'run_record_created': False, 'records_written': 0,
        'criteria_status': 'not_evaluated', 'reproduction_status': 'not_independently_verified',
        'experiment': {'record_id': experiment.record_id, 'version': experiment.version, 'plan_hash': experiment.plan_hash},
        'strategy': {'record_id': strategy.record_id, 'version': strategy.version, 'content_hash': strategy.content_hash},
        'data': {'record_id': data.record_id, 'version': data.version, 'csv_sha256': csv_hash,
                 'snapshot_rows': data.row_count, 'selected_rows': len(bars)},
        'binding': experiment.criteria['weekly_binding'], 'adapter_hash': adapter_hash,
        'protocol': json.loads(canonical_json(asdict(protocol))),
        'scenarios': json.loads(canonical_json([asdict(s) for s in scenarios])),
        'limitations': [
            'Zgodność bajtów i deklaracji, nie podpis zatwierdzenia Karola ani dowód prawdziwości danych.',
            'Kryteria wynikowe, niezależne odtworzenie i REVIEW pozostają nieocenione.',
            'Brak potwierdzenia rentowności, nietkniętego OOS, licencji i wykonania brokerskiego.',
            'Dodatkowe kolumny CSV poza timestamp/instrument/OHLC nie uczestniczą w obliczeniach.',
            'Tylko raport offline; nie jest RUN w rejestrze ani wejściem Wykonawcy.',
        ],
    }
    return report, bars, protocol, scenarios


def inspect_weekly_experiment(database: Database, *, experiment_id: str, version: int, csv_path: str | Path) -> dict:
    report, _, _, _ = _prepare(database, experiment_id=experiment_id, version=version, csv_path=csv_path)
    if weekly_adapter_fingerprint() != report['adapter_hash']:
        _block('Kod zmienił się podczas inspekcji.', 'weekly_code_mismatch')
    report['report_hash'] = record_content_hash(report)
    return report


def run_weekly_experiment(database: Database, *, experiment_id: str, version: int, csv_path: str | Path) -> dict:
    report, bars, protocol, scenarios = _prepare(database, experiment_id=experiment_id, version=version, csv_path=csv_path)
    # No overrides: every scenario from EXP, once, in registered order.
    results = [simulate_weekly(bars, protocol=protocol, scenario=scenario,
                              expected_code_hash=report['binding']['engine_hash']) for scenario in scenarios]
    if weekly_adapter_fingerprint() != report['adapter_hash']:
        _block('Kod zmienił się podczas obliczeń.', 'weekly_code_mismatch')
    report.update(status='OFFLINE_UNQUALIFIED', results=results)
    report['report_hash'] = record_content_hash(report)
    return report


_LOADED_HASH = _source_hash()
