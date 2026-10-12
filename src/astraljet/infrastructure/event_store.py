from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from astraljet.domain.errors import ValidationError
from astraljet.domain.validation import canonical_json, new_record_id, utc_now, validate_utc

from .database import Database


@dataclass(frozen=True, slots=True)
class Event:
    event_id: str
    occurred_at: str
    recorded_at: str
    actor: str
    event_type: str
    record_type: str
    record_id: str
    record_version: int
    reason: str
    outcome: str
    payload: dict[str, Any]
    correlation_id: str
    causation_id: str | None
    idempotency_key: str

    def __post_init__(self) -> None:
        validate_utc(self.occurred_at)
        validate_utc(self.recorded_at)
        if self.record_version < 1:
            raise ValidationError("EVENT wymaga record_version >=1.")
        for name, value in (
            ("actor", self.actor),
            ("event_type", self.event_type),
            ("reason", self.reason),
            ("outcome", self.outcome),
        ):
            if not value.strip():
                raise ValidationError(f"EVENT wymaga niepustego pola {name}.")
        if len(self.correlation_id) < 8 or len(self.idempotency_key) < 8:
            raise ValidationError("Klucze EVENT muszą mieć co najmniej 8 znaków.")

    @classmethod
    def create(
        cls,
        *,
        actor: str,
        event_type: str,
        record_type: str,
        record_id: str,
        record_version: int,
        reason: str,
        outcome: str,
        payload: dict[str, Any],
        correlation_id: str,
        idempotency_key: str,
        causation_id: str | None = None,
        occurred_at: str | None = None,
    ) -> "Event":
        now = utc_now()
        return cls(
            event_id=new_record_id("EVT"),
            occurred_at=occurred_at or now,
            recorded_at=now,
            actor=actor,
            event_type=event_type,
            record_type=record_type,
            record_id=record_id,
            record_version=record_version,
            reason=reason,
            outcome=outcome,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=causation_id,
            idempotency_key=idempotency_key,
        )


def event_from_row(row: sqlite3.Row) -> Event:
    return Event(
        event_id=row["event_id"],
        occurred_at=row["occurred_at"],
        recorded_at=row["recorded_at"],
        actor=row["actor"],
        event_type=row["event_type"],
        record_type=row["record_type"],
        record_id=row["record_id"],
        record_version=row["record_version"],
        reason=row["reason"],
        outcome=row["outcome"],
        payload=json.loads(row["payload_json"]),
        correlation_id=row["correlation_id"],
        causation_id=row["causation_id"],
        idempotency_key=row["idempotency_key"],
    )


class EventStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_by_idempotency_key(self, key: str) -> Event | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
        return event_from_row(row) if row else None

    def list_for_record(self, record_id: str) -> list[Event]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE record_id = ? ORDER BY recorded_at, event_id",
                (record_id,),
            ).fetchall()
        return [event_from_row(row) for row in rows]

    @staticmethod
    def insert(connection: sqlite3.Connection, event: Event) -> None:
        connection.execute(
            """
            INSERT INTO events(
                event_id, occurred_at, recorded_at, actor, event_type, record_type,
                record_id, record_version, reason, outcome, payload_json,
                correlation_id, causation_id, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.occurred_at,
                event.recorded_at,
                event.actor,
                event.event_type,
                event.record_type,
                event.record_id,
                event.record_version,
                event.reason,
                event.outcome,
                canonical_json(event.payload),
                event.correlation_id,
                event.causation_id,
                event.idempotency_key,
            ),
        )
