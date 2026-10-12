from __future__ import annotations

import json
import sqlite3
from typing import Any

from astraljet.domain.enums import (
    CandidateStatus,
    DataStatus,
    EvidenceType,
    ExecutionEnvironment,
    IncubationStatus,
    ReviewVerdict,
    RiskDecisionStatus,
    RunOutcome,
    StrategyStatus,
    TechnicalStatus,
    TrustStatus,
)
from astraljet.domain.errors import ValidationError
from astraljet.domain.records import (
    BaseRecord,
    BudgetStatusRecord,
    CandidateRecord,
    DataRecord,
    ExperimentRecord,
    IncubationRecord,
    MandateRecord,
    ReviewRecord,
    RiskDecisionRecord,
    RunRecord,
    SourceRecord,
    StrategyRecord,
)
from astraljet.domain.validation import canonical_json, new_record_id

from .database import Database
from .event_store import Event, EventStore, event_from_row


class RecordRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(
        self,
        record: BaseRecord,
        *,
        event_type: str,
        reason: str,
        outcome: str,
        actor: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> tuple[BaseRecord, Event, bool]:
        with self.database.transaction() as connection:
            duplicate = connection.execute(
                "SELECT * FROM events WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if duplicate:
                event = event_from_row(duplicate)
                existing = self._get(connection, event.record_id, event.record_version)
                return existing, event, False

            self.insert_record(connection, record)
            event = Event.create(
                actor=actor,
                event_type=event_type,
                record_type=record.record_type,
                record_id=record.record_id,
                record_version=record.version,
                reason=reason,
                outcome=outcome,
                payload={"content_hash": record.content_hash},
                correlation_id=correlation_id or new_record_id("CORR"),
                idempotency_key=idempotency_key,
            )
            EventStore.insert(connection, event)
            return record, event, True

    @staticmethod
    def insert_record(connection: sqlite3.Connection, record: BaseRecord) -> None:
        """Insert within caller's transaction; the caller must also append EVENT."""
        connection.execute(
            """
            INSERT INTO records(
                record_type, record_id, version, owner, created_at,
                technical_status, content_hash, limitations_json, supersedes,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.record_type,
                record.record_id,
                record.version,
                record.owner,
                record.created_at,
                record.technical_status.value,
                record.content_hash,
                canonical_json(record.limitations),
                record.supersedes,
                canonical_json(record.payload()),
            ),
        )

    def get_latest(self, record_id: str) -> BaseRecord:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM records WHERE record_id = ? ORDER BY version DESC LIMIT 1",
                (record_id,),
            ).fetchone()
            if not row:
                raise ValidationError(f"Nie znaleziono rekordu {record_id}.")
            return self._record_from_row(row)

    def get(self, record_id: str, version: int) -> BaseRecord:
        with self.database.connect() as connection:
            return self._get(connection, record_id, version)

    def list_by_type(self, record_type: str) -> list[BaseRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT r.* FROM records r
                JOIN (
                    SELECT record_id, MAX(version) AS version
                    FROM records WHERE record_type = ? GROUP BY record_id
                ) latest ON latest.record_id = r.record_id AND latest.version = r.version
                ORDER BY r.created_at, r.record_id
                """,
                (record_type,),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def count_by_type(self, record_type: str) -> int:
        with self.database.connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(DISTINCT record_id) FROM records WHERE record_type = ?",
                    (record_type,),
                ).fetchone()[0]
            )

    def _get(self, connection: sqlite3.Connection, record_id: str, version: int) -> BaseRecord:
        row = connection.execute(
            "SELECT * FROM records WHERE record_id = ? AND version = ?",
            (record_id, version),
        ).fetchone()
        if not row:
            raise ValidationError(f"Brak rekordu {record_id} v{version} dla EVENT.")
        return self._record_from_row(row)

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> BaseRecord:
        common: dict[str, Any] = {
            "record_id": row["record_id"],
            "version": row["version"],
            "owner": row["owner"],
            "created_at": row["created_at"],
            "technical_status": TechnicalStatus(row["technical_status"]),
            "content_hash": row["content_hash"],
            "limitations": tuple(json.loads(row["limitations_json"])),
            "supersedes": row["supersedes"],
        }
        payload = json.loads(row["payload_json"])
        if row["record_type"] == "SRC":
            payload["trust_status"] = TrustStatus(payload["trust_status"])
            return SourceRecord(**common, **payload)
        if row["record_type"] == "CAND":
            payload["source_ids"] = tuple(payload["source_ids"])
            payload["missing_decisions"] = tuple(payload["missing_decisions"])
            payload["candidate_status"] = CandidateStatus(payload["candidate_status"])
            return CandidateRecord(**common, **payload)
        if row["record_type"] == "STRAT":
            payload["instruments"] = tuple(payload["instruments"])
            payload["constraints"] = tuple(payload["constraints"])
            payload["strategy_status"] = StrategyStatus(payload["strategy_status"])
            return StrategyRecord(**common, **payload)
        if row["record_type"] == "DATA":
            payload["instruments"] = tuple(payload["instruments"])
            payload["transformations"] = tuple(payload["transformations"])
            payload["quality_findings"] = tuple(payload["quality_findings"])
            payload["data_status"] = DataStatus(payload["data_status"])
            return DataRecord(**common, **payload)
        if row["record_type"] == "EXP":
            payload["in_sample"] = tuple(payload["in_sample"])
            payload["out_of_sample"] = tuple(payload["out_of_sample"])
            payload["allowed_variants"] = tuple(payload["allowed_variants"])
            payload["metrics"] = tuple(payload["metrics"])
            payload["stop_rules"] = tuple(payload["stop_rules"])
            return ExperimentRecord(**common, **payload)
        if row["record_type"] == "RUN":
            payload["evidence_type"] = EvidenceType(payload["evidence_type"])
            payload["run_outcome"] = RunOutcome(payload["run_outcome"])
            for name in ("trades", "rejected_signals", "exposure", "equity_curve", "errors"):
                payload[name] = tuple(payload[name])
            return RunRecord(**common, **payload)
        if row["record_type"] == "REVIEW":
            for name in ("run_ids", "evidence", "findings", "missing_evidence", "conditions"):
                payload[name] = tuple(payload[name])
            payload["verdict"] = ReviewVerdict(payload["verdict"])
            return ReviewRecord(**common, **payload)
        if row["record_type"] == "RISK_DECISION":
            payload["decision"] = RiskDecisionStatus(payload["decision"])
            payload["blockers"] = tuple(payload["blockers"])
            return RiskDecisionRecord(**common, **payload)
        if row["record_type"] == "MANDATE":
            payload["environment"] = ExecutionEnvironment(payload["environment"])
            payload["instruments"] = tuple(payload["instruments"])
            payload["stop_conditions"] = tuple(payload["stop_conditions"])
            return MandateRecord(**common, **payload)
        if row["record_type"] == "INCU":
            payload["environment"] = ExecutionEnvironment(payload["environment"])
            payload["incubation_status"] = IncubationStatus(payload["incubation_status"])
            payload["alerts"] = tuple(payload["alerts"])
            return IncubationRecord(**common, **payload)
        if row["record_type"] == "BUDGET_STATUS":
            return BudgetStatusRecord(**common, **payload)
        raise ValidationError(f"Nieobsługiwany typ rekordu: {row['record_type']}.")
