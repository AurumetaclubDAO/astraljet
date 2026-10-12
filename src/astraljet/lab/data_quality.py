from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from astraljet.domain.enums import DataStatus, TechnicalStatus
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.records import DataRecord
from astraljet.domain.validation import new_record_id, sha256_file, utc_now, validate_utc


REQUIRED_COLUMNS = ("timestamp", "instrument", "open", "high", "low", "close")


@dataclass(frozen=True, slots=True)
class MarketBar:
    timestamp: str
    instrument: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True, slots=True)
class DataImportSpec:
    provider: str
    venue: str
    instruments: tuple[str, ...]
    timeframe: str
    timezone: str
    available_at_rule: str
    transformations: tuple[str, ...]
    cost_model: str
    schema_version: str = "ohlcv-v1"


def _parse_timestamp(value: str) -> datetime:
    validate_utc(value)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _read_bars(path: Path) -> list[MarketBar]:
    bars: list[MarketBar] = []
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing_columns = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or ())]
        if missing_columns:
            raise ValidationError(
                f"CSV nie zawiera wymaganych kolumn: {', '.join(missing_columns)}."
            )
        for line_number, row in enumerate(reader, start=2):
            try:
                timestamp = str(row["timestamp"]).strip()
                _parse_timestamp(timestamp)
                instrument = str(row["instrument"]).strip()
                prices = {
                    name: Decimal(str(row[name]).strip())
                    for name in ("open", "high", "low", "close")
                }
            except (InvalidOperation, TypeError, ValueError, ValidationError) as exc:
                raise ValidationError(f"Niepoprawny wiersz CSV {line_number}: {exc}") from exc
            if not instrument:
                raise ValidationError(f"Brak instrumentu w wierszu {line_number}.")
            if any(value <= 0 for value in prices.values()):
                raise ValidationError(f"Cena <=0 w wierszu {line_number}.")
            if prices["low"] > min(prices["open"], prices["close"]):
                raise ValidationError(f"Low jest wyższe od open/close w wierszu {line_number}.")
            if prices["high"] < max(prices["open"], prices["close"]):
                raise ValidationError(f"High jest niższe od open/close w wierszu {line_number}.")
            bars.append(MarketBar(timestamp=timestamp, instrument=instrument, **prices))
    if not bars:
        raise ValidationError("CSV nie zawiera żadnych danych.")
    return sorted(bars, key=lambda bar: (bar.timestamp, bar.instrument))


def _quality_findings(bars: list[MarketBar], spec: DataImportSpec) -> tuple[str, ...]:
    findings: list[str] = []
    seen: set[tuple[str, str]] = set()
    by_instrument: dict[str, list[str]] = {instrument: [] for instrument in spec.instruments}
    allowed = set(spec.instruments)
    for bar in bars:
        key = (bar.timestamp, bar.instrument)
        if key in seen:
            findings.append(f"duplicate_{bar.instrument}_{bar.timestamp}")
        seen.add(key)
        if bar.instrument not in allowed:
            findings.append(f"unexpected_instrument_{bar.instrument}")
            continue
        by_instrument[bar.instrument].append(bar.timestamp)

    all_timestamps = set().union(*(set(values) for values in by_instrument.values()))
    for instrument, timestamps in by_instrument.items():
        timestamp_set = set(timestamps)
        for missing in sorted(all_timestamps - timestamp_set):
            findings.append(f"missing_{instrument}_{missing}")
        ordered = sorted(timestamp_set)
        if spec.timeframe == "1d":
            for previous, current in zip(ordered, ordered[1:]):
                delta = _parse_timestamp(current) - _parse_timestamp(previous)
                if delta.days != 1 or delta.seconds != 0:
                    findings.append(f"gap_{instrument}_{previous}_{current}")

    normalized_cost = spec.cost_model.strip().lower()
    if normalized_cost in {"", "unknown", "nieznany", "brak", "0", "zero"}:
        findings.append("unknown_cost_model")
    if spec.timezone != "UTC":
        findings.append("timezone_not_utc")
    if not spec.provider.strip():
        findings.append("missing_provider")
    if not spec.venue.strip():
        findings.append("missing_venue")
    if not spec.available_at_rule.strip():
        findings.append("missing_available_at_rule")
    return tuple(dict.fromkeys(findings))


def import_market_data(
    file_path: str | Path,
    *,
    spec: DataImportSpec,
    owner: str,
) -> DataRecord:
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise ValidationError(f"Plik DATA nie istnieje: {path}")
    if not spec.instruments:
        raise ValidationError("DATA wymaga co najmniej jednego instrumentu.")
    bars = _read_bars(path)
    findings = _quality_findings(bars, spec)
    data_status = DataStatus.GAPS if findings else DataStatus.READY
    timestamps = [bar.timestamp for bar in bars]
    file_hash = sha256_file(path)
    return DataRecord(
        record_id=new_record_id("DATA"),
        version=1,
        owner=owner,
        created_at=utc_now(),
        technical_status=(
            TechnicalStatus.COMPLETED if data_status is DataStatus.READY else TechnicalStatus.BLOCKED
        ),
        content_hash=file_hash,
        limitations=(
            "Lokalny snapshot danych; hash nie potwierdza prawdziwości kwotowań.",
            "DATA może służyć tylko do zastosowania opisanego w EXP.",
        ),
        provider=spec.provider,
        venue=spec.venue,
        instruments=spec.instruments,
        timeframe=spec.timeframe,
        timezone=spec.timezone,
        start=min(timestamps),
        end=max(timestamps),
        available_at_rule=spec.available_at_rule,
        locator=str(path),
        sha256=file_hash,
        schema_version=spec.schema_version,
        transformations=spec.transformations,
        cost_model=spec.cost_model,
        quality_findings=findings,
        row_count=len(bars),
        data_status=data_status,
    )


def load_market_data(record: DataRecord) -> list[MarketBar]:
    if record.data_status is not DataStatus.READY:
        raise DomainBlockedError(
            "DATA nie ma statusu ready.",
            blocker="data_not_ready",
            owner=record.owner,
            allowed_next_action="Popraw DATA i utwórz nową wersję.",
        )
    path = Path(record.locator)
    if not path.is_file() or sha256_file(path) != record.sha256:
        raise DomainBlockedError(
            "Plik DATA zniknął albo jego hash się zmienił.",
            blocker="data_hash_mismatch",
            owner=record.owner,
            allowed_next_action="Ponownie zaimportuj DATA jako nową wersję.",
        )
    return _read_bars(path)
