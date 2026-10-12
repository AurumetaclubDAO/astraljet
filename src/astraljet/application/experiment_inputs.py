"""Read-only, bounded input inspection. This is not an EXP or an approval path."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from astraljet.domain.errors import ValidationError
from astraljet.domain.validation import canonical_json, sha256_text, utc_now
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.migrations import SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class InputWindow:
    start: str
    in_sample_end: str
    out_of_sample_start: str
    end: str
    ma_window: int
    slope_lookback: int
    signal_weekday: int

    def dates(self) -> tuple[date, date, date, date]:
        try:
            values = tuple(date.fromisoformat(v) for v in (
                self.start, self.in_sample_end, self.out_of_sample_start, self.end,
            ))
        except (TypeError, ValueError) as exc:
            raise ValidationError('Zakres inspekcji wymaga dat YYYY-MM-DD.') from exc
        if any(v.isoformat() != raw for v, raw in zip(values, (
            self.start, self.in_sample_end, self.out_of_sample_start, self.end,
        ))):
            raise ValidationError('Zakres inspekcji wymaga dat YYYY-MM-DD.')
        start, is_end, oos_start, end = values
        if not start <= is_end < oos_start <= end or oos_start != is_end + timedelta(days=1):
            raise ValidationError('Wymagane są kolejne, niepokrywające się zakresy IS i OOS.')
        if (end - start).days > 36525:
            raise ValidationError('Zakres inspekcji przekracza 100 lat.')
        if (type(self.ma_window) is not int or not 2 <= self.ma_window <= 10000
                or type(self.slope_lookback) is not int or not 1 <= self.slope_lookback <= 10000
                or type(self.signal_weekday) is not int or not 0 <= self.signal_weekday <= 6):
            raise ValidationError('Niepoprawne okna SMA/nachylenia lub dzień tygodnia (0–6).')
        return values


def _read(path: Path, limit: int) -> bytes:
    try:
        with path.open('rb') as stream:
            content = stream.read(limit + 1)
    except OSError as exc:
        raise ValidationError('Nie można odczytać jawnie wskazanego pliku wejściowego.') from exc
    if len(content) > limit:
        raise ValidationError('Plik przekracza limit inspekcji.')
    return content


def _utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError('UTC required')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError('UTC required')
    return parsed


def _exact(database: Database, record_id: str, version: int, kind: str) -> tuple[dict, dict]:
    if type(version) is not int or version < 1 or not record_id.startswith(kind + '-'):
        raise ValidationError('Wymagane są właściwe ID i jawna dodatnia wersja rekordu.')
    try:
        with database.read_only() as connection:
            schema = connection.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]
            if type(schema) is not int or not 1 <= schema <= SCHEMA_VERSION:
                raise ValidationError('Nieobsługiwany schemat rejestru.')
            row = connection.execute(
                'SELECT record_type, record_id, version, content_hash, technical_status, payload_json '
                'FROM records WHERE record_id=? AND version=? AND record_type=?',
                (record_id, version, kind),
            ).fetchone()
        if row is None:
            raise ValidationError('Brak wskazanej wersji rekordu; nie zastępujemy jej najnowszą.')
        payload = json.loads(row['payload_json'])
        if not isinstance(payload, dict):
            raise ValidationError('Niepoprawny payload rekordu.')
    except (sqlite3.DatabaseError, json.JSONDecodeError) as exc:
        raise ValidationError('Nie można odczytać wskazanego rekordu.') from exc
    observed = {name: row[name] for name in row.keys() if name != 'payload_json'}
    observed['payload'] = payload
    reference = {key: row[key] for key in ('record_id', 'version', 'content_hash', 'technical_status')}
    reference['observation_sha256'] = sha256_text(canonical_json(observed))
    reference['storage_schema_version'] = schema
    return reference, payload


def inspect_experiment_inputs(
    strategy_database: Database, data_database: Database, *,
    strategy_id: str, strategy_version: int, data_id: str, data_version: int,
    csv_path: str | Path, metadata_path: str | Path, window: InputWindow,
) -> dict[str, Any]:
    """Inspect explicit versions and exact bytes, with no network, migration or writes.

    Report status is ALWAYS a blocked draft. No flag, record status or fee string
    can turn this diagnostic into a frozen experiment or an execution mandate.
    """
    start, is_end, oos_start, end = window.dates()
    strat_ref, strategy = _exact(strategy_database, strategy_id, strategy_version, 'STRAT')
    data_ref, data = _exact(data_database, data_id, data_version, 'DATA')
    content = _read(Path(csv_path), 50 * 1024 * 1024)
    metadata_bytes = _read(Path(metadata_path), 1024 * 1024)
    digest = hashlib.sha256(content).hexdigest().upper()
    try:
        metadata = json.loads(metadata_bytes.decode('utf-8-sig'))
        if not isinstance(metadata, dict):
            raise ValueError('metadata object required')
        text = content.decode('utf-8-sig')
    except (UnicodeError, ValueError) as exc:
        raise ValidationError('Niepoprawny CSV UTF-8 lub JSON metadanych.') from exc
    instruments = data.get('instruments')
    if (not isinstance(instruments, list) or not instruments
            or any(not isinstance(s, str) or not s for s in instruments)
            or len(set(instruments)) != len(instruments) or len(instruments) > 20):
        raise ValidationError('DATA wymaga jawnej, unikalnej listy instrumentów (maks. 20).')
    if data.get('timeframe') != '1d' or data.get('timezone') != 'UTC':
        raise ValidationError('Ta inspekcja obsługuje wyłącznie dzienne dane UTC (1d).')
    issues: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = {}

    def issue(code: str, **detail: Any) -> None:
        issues[code] += 1
        if detail and len(examples.setdefault(code, [])) < 5:
            examples[code].append(detail)

    if not isinstance(data.get('sha256'), str) or data['sha256'].upper() != digest:
        issue('registered_csv_hash_mismatch')
    if data_ref['content_hash'].upper() != digest:
        issue('data_content_hash_mismatch')
    if not isinstance(metadata.get('csv_sha256'), str) or metadata['csv_sha256'].upper() != digest:
        issue('sidecar_csv_hash_mismatch')
    if metadata.get('provider') != data.get('provider') or metadata.get('venue') != data.get('venue'):
        issue('sidecar_provider_venue_mismatch')
    request = metadata.get('request')
    if (not isinstance(request, dict) or request.get('timeframe') != '1Day'
            or request.get('normalized_instruments') != instruments):
        issue('sidecar_request_mismatch')
    try:
        retrieved = _utc(metadata.get('retrieved_at'))
        if retrieved > datetime.now(timezone.utc) + timedelta(minutes=5):
            issue('retrieval_in_future')
    except (ValueError, TypeError):
        retrieved = None
        issue('invalid_retrieval_time')

    seen: set[tuple[str, date]] = set()
    dates_by_symbol: dict[str, set[date]] = {s: set() for s in instruments}
    row_counts: Counter[str] = Counter()
    optional_missing: Counter[str] = Counter()
    zero_volume = 0
    reader = csv.DictReader(io.StringIO(text, newline=''))
    fields = reader.fieldnames or []
    required = {'timestamp', 'instrument', 'open', 'high', 'low', 'close'}
    if len(fields) != len(set(fields)) or not required <= set(fields):
        raise ValidationError('CSV wymaga unikalnych kolumn timestamp, instrument i OHLC.')
    row_count = 0
    for row_count, row in enumerate(reader, 1):
        line = row_count + 1
        if None in row or any(row.get(k) is None for k in required):
            issue('malformed_csv_row', line=line)
            continue
        symbol = row['instrument']
        if symbol not in dates_by_symbol:
            issue('unexpected_instrument', line=line)
            continue
        row_counts[symbol] += 1
        try:
            timestamp = _utc(row['timestamp'])
            if timestamp.time().isoformat() != '00:00:00':
                raise ValueError('daily UTC boundary required')
        except (ValueError, TypeError):
            issue('invalid_daily_timestamp', line=line)
            continue
        day = timestamp.date()
        key = (symbol, day)
        if key in seen:
            issue('duplicate_bar', line=line)
        seen.add(key)
        dates_by_symbol[symbol].add(day)
        if retrieved is not None and timestamp + timedelta(days=1) > retrieved:
            issue('bar_not_closed_at_retrieval', line=line)
        try:
            prices = [Decimal(row[k]) for k in ('open', 'high', 'low', 'close')]
            if any(not p.is_finite() or p <= 0 for p in prices):
                raise ValueError('invalid price')
            opening, high, low, close = prices
            if low > min(opening, close) or high < max(opening, close) or high < low:
                raise ValueError('invalid OHLC')
        except (InvalidOperation, ValueError, TypeError):
            issue('invalid_ohlc', line=line)
        for column in ('volume', 'trade_count', 'vwap'):
            raw = row.get(column)
            if raw is None or not raw.strip():
                optional_missing[column] += 1
                continue
            try:
                number = Decimal(raw)
                if not number.is_finite() or number < 0 or (
                    column == 'trade_count' and number != number.to_integral_value()
                ):
                    raise ValueError('invalid optional number')
                if column == 'volume' and number == 0:
                    zero_volume += 1
            except (InvalidOperation, ValueError):
                issue('invalid_' + column, line=line)
    if not row_count:
        issue('empty_csv')
    for label, recorded in (('registered', data.get('row_count')), ('sidecar', metadata.get('row_count'))):
        if type(recorded) is not int or recorded != row_count:
            issue(label + '_row_count_mismatch')

    all_days = set().union(*dates_by_symbol.values())
    common_days = set.intersection(*dates_by_symbol.values())
    observed_start = min(all_days).isoformat() + 'T00:00:00Z' if all_days else None
    observed_end = max(all_days).isoformat() + 'T00:00:00Z' if all_days else None
    if (data.get('start'), data.get('end')) != (observed_start, observed_end):
        issue('registered_range_mismatch')
    if (metadata.get('observed_start'), metadata.get('observed_end')) != (observed_start, observed_end):
        issue('sidecar_range_mismatch')
    expected_days = {start + timedelta(days=i) for i in range((end - start).days + 1)}
    for symbol, days in dates_by_symbol.items():
        if all_days != days:
            issue('instrument_alignment_gap', instrument=symbol, missing=len(all_days - days))
        if expected_days - days:
            issue('requested_calendar_gap', instrument=symbol, missing=len(expected_days - days),
                  first_missing=min(expected_days - days).isoformat())
        if days:
            missing = (max(days) - min(days)).days + 1 - len(days)
            if missing:
                issue('snapshot_calendar_gap', instrument=symbol, missing=missing)

    # No missing-day compression: N daily observations means N consecutive UTC days.
    required_bars = window.ma_window + window.slope_lookback
    first_indicator_day = start + timedelta(days=required_bars - 1)
    first_weekday = first_indicator_day + timedelta(days=(window.signal_weekday - first_indicator_day.weekday()) % 7)
    structural_ok = not issues
    can_compute_calendar = structural_ok and first_weekday < end
    if first_weekday >= end:
        issue('insufficient_history_for_signal_and_next_open')
    schedule = {
        'approved': False, 'bar_timestamp_semantics': 'proposed_start_of_UTC_day',
        'ma_window': window.ma_window, 'slope_lookback': window.slope_lookback,
        'required_observations_including_signal_bar': required_bars,
        'earlier_observations_required': required_bars - 1,
        'signal_weekday': window.signal_weekday,
        'first_indicator_bar': first_indicator_day.isoformat() if can_compute_calendar else None,
        'first_weekly_signal_bar': first_weekday.isoformat() if can_compute_calendar else None,
        'first_model_execution_boundary_utc': (
            (first_weekday + timedelta(days=1)).isoformat() + 'T00:00:00Z' if can_compute_calendar else None
        ),
        'execution_price_verified': False,
        'available_at_and_latency_verified': False,
        'in_sample': [start.isoformat(), is_end.isoformat()],
        'out_of_sample': [oos_start.isoformat(), end.isoformat()],
        'out_of_sample_untouched_verified': False,
        'aligned_days_in_sample': sum(start <= d <= is_end for d in common_days),
        'aligned_days_out_of_sample': sum(oos_start <= d <= end for d in common_days),
        'warmup_bars_before_oos': sum(oos_start - timedelta(days=required_bars - 1) <= d < oos_start for d in common_days),
    }
    blockers = ['human_rule_and_cost_decisions_missing', 'engine_protocol_review_required',
                'point_in_time_availability_unverified', 'not_a_frozen_experiment']
    if strategy.get('strategy_status') != 'ready':
        blockers.append('strategy_not_ready')
    if data.get('data_status') != 'ready':
        blockers.append('data_not_ready')
    if set(strategy.get('instruments', [])) != set(instruments):
        blockers.append('instrument_mismatch')
    if strategy.get('venue') != data.get('venue') or strategy.get('timeframe') != data.get('timeframe'):
        blockers.append('market_mismatch')
    if any(str(p.get('cost_model', '')).strip().lower() in ('', 'unknown', 'brak', '0', 'zero', 'nieznany')
           for p in (strategy, data)):
        blockers.append('unknown_cost_model')
    if strategy.get('cost_model') != data.get('cost_model'):
        blockers.append('cost_mismatch')
    if issues:
        blockers.append('data_integrity_or_calendar_findings')
    return {
        'format': 'astraljet-experiment-inputs-v1', 'status': 'DRAFT_BLOCKED',
        'generated_at': utc_now(), 'execution_authorized': False, 'can_freeze': False,
        'records_written': 0, 'experiment_id': None,
        'same_registry': strategy_database.config.database_path == data_database.config.database_path,
        'strategy_reference': {'scope': 'strategy_registry', **strat_ref},
        'data_reference': {'scope': 'data_registry', **data_ref},
        'registered_strategy_status': strategy.get('strategy_status'),
        'registered_data_status': data.get('data_status'),
        'snapshot': {
            'csv_sha256': digest, 'metadata_sha256': hashlib.sha256(metadata_bytes).hexdigest().upper(),
            'row_count': row_count, 'rows_per_instrument': dict(row_counts),
            'observed_start': observed_start, 'observed_end': observed_end,
            'structural_status': 'findings' if issues else 'checked_local_structure',
            'findings': [{'code': code, 'count': count, 'examples': examples.get(code, [])}
                         for code, count in sorted(issues.items())],
            'optional_missing': dict(optional_missing), 'zero_volume_rows': zero_volume,
            'prices_verified_with_provider': False,
        },
        'proposed_schedule': schedule, 'blockers': blockers,
        'limitations': [
            'Odczyt dwóch rejestrów jest osobny; nie scala baz ani nie tworzy relacji EXP.',
            'Hash porównuje odczytane bajty, nie potwierdza autora ani prawdziwości kwotowań.',
            'Kalendarz nie wylicza sygnałów, transakcji, rentowności ani kwalifikacji.',
            'Granica następnego dnia nie dowodzi dostępności finalnej świecy ani ceny realizacji.',
        ],
    }
