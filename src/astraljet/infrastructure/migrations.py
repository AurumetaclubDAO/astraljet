from __future__ import annotations

import sqlite3


SCHEMA_VERSION = 7


MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
    record_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version >= 1),
    owner TEXT NOT NULL CHECK (length(owner) > 0),
    created_at TEXT NOT NULL,
    technical_status TEXT NOT NULL,
    content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
    limitations_json TEXT NOT NULL,
    supersedes TEXT,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (record_id, version)
);

CREATE INDEX IF NOT EXISTS idx_records_type ON records(record_type);
CREATE INDEX IF NOT EXISTS idx_records_latest ON records(record_id, version DESC);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    actor TEXT NOT NULL CHECK (length(actor) > 0),
    event_type TEXT NOT NULL CHECK (length(event_type) > 0),
    record_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    record_version INTEGER NOT NULL CHECK (record_version >= 1),
    reason TEXT NOT NULL CHECK (length(reason) > 0),
    outcome TEXT NOT NULL CHECK (length(outcome) > 0),
    payload_json TEXT NOT NULL,
    correlation_id TEXT NOT NULL CHECK (length(correlation_id) >= 8),
    causation_id TEXT,
    idempotency_key TEXT NOT NULL UNIQUE CHECK (length(idempotency_key) >= 8),
    FOREIGN KEY (record_id, record_version)
        REFERENCES records(record_id, version)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_events_record ON events(record_id, record_version);
CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id);

CREATE TRIGGER IF NOT EXISTS events_no_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'EVENT is append-only');
END;

CREATE TRIGGER IF NOT EXISTS events_no_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'EVENT is append-only');
END;
"""


MIGRATION_2 = """
CREATE TABLE IF NOT EXISTS executor_leases (
    environment_id TEXT PRIMARY KEY,
    lease_id TEXT NOT NULL UNIQUE,
    worker_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kill_switches (
    environment_id TEXT PRIMARY KEY,
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    reason TEXT NOT NULL,
    activated_at TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS execution_intents (
    idempotency_key TEXT PRIMARY KEY,
    intent_id TEXT NOT NULL,
    environment_id TEXT NOT NULL,
    mandate_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('accepted', 'rejected', 'uncertain')),
    external_reference TEXT,
    payload_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_intents_environment_state
ON execution_intents(environment_id, state);

CREATE TABLE IF NOT EXISTS paper_positions (
    environment_id TEXT NOT NULL,
    instrument TEXT NOT NULL,
    quantity_text TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (environment_id, instrument)
);

CREATE TABLE IF NOT EXISTS execution_reconciliations (
    idempotency_key TEXT PRIMARY KEY,
    external_reference TEXT NOT NULL,
    result_state TEXT NOT NULL CHECK (result_state IN ('accepted', 'rejected')),
    reconciled_at TEXT NOT NULL
);
"""


MIGRATION_4 = """
CREATE TABLE IF NOT EXISTS execution_signal_claims (
    environment_id TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    PRIMARY KEY (environment_id, signal_id),
    UNIQUE (environment_id, intent_id),
    UNIQUE (idempotency_key)
);
"""


MIGRATION_5 = """
CREATE TRIGGER IF NOT EXISTS records_no_update
BEFORE UPDATE ON records
BEGIN
    SELECT RAISE(ABORT, 'RECORD is append-only; insert a new version');
END;

CREATE TRIGGER IF NOT EXISTS records_no_delete
BEFORE DELETE ON records
BEGIN
    SELECT RAISE(ABORT, 'RECORD is append-only');
END;

-- REPLACE can bypass DELETE triggers when recursive_triggers is OFF.
CREATE TRIGGER IF NOT EXISTS records_no_replace
BEFORE INSERT ON records
WHEN EXISTS (SELECT 1 FROM records WHERE record_id=NEW.record_id AND version=NEW.version)
BEGIN
    SELECT RAISE(ABORT, 'RECORD version already exists');
END;

CREATE TRIGGER IF NOT EXISTS events_no_replace
BEFORE INSERT ON events
WHEN EXISTS (SELECT 1 FROM events
             WHERE event_id=NEW.event_id OR idempotency_key=NEW.idempotency_key)
BEGIN
    SELECT RAISE(ABORT, 'EVENT identity already exists');
END;
"""

MIGRATION_6 = """
CREATE TABLE IF NOT EXISTS registry_sync_installation (
    installation_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS registry_sync_batches (
    batch_id TEXT PRIMARY KEY,
    body_hash TEXT NOT NULL CHECK (length(body_hash)=64),
    cursor_event_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending','sending','acknowledged','retryable_failure','conflict','rejected')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_error TEXT,
    server_receipt_json TEXT
);
"""


MIGRATION_7 = """
ALTER TABLE registry_sync_batches ADD COLUMN body_json TEXT;
ALTER TABLE registry_sync_batches ADD COLUMN registry_id TEXT;
ALTER TABLE registry_sync_batches ADD COLUMN endpoint TEXT;
ALTER TABLE registry_sync_batches ADD COLUMN lease_until REAL;
CREATE TABLE registry_sync_cursors (
    registry_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES registry_sync_batches(batch_id),
    batch_seq INTEGER NOT NULL,
    event_id TEXT,
    acknowledged_at TEXT NOT NULL
);
CREATE TRIGGER registry_sync_body_immutable
BEFORE UPDATE OF body_json,body_hash,registry_id,endpoint,cursor_event_id ON registry_sync_batches
BEGIN
    SELECT RAISE(ABORT, 'SYNC envelope is immutable');
END;
"""


def migrate(connection: sqlite3.Connection, *, applied_at: str) -> None:
    connection.executescript(MIGRATION_1)
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (1, applied_at),
    )
    connection.executescript(MIGRATION_2)
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (2, applied_at),
    )
    connection.execute(
        """
        INSERT INTO records(
            record_type, record_id, version, owner, created_at, technical_status,
            content_hash, limitations_json, supersedes, payload_json
        ) SELECT 'SYSTEM', 'SYSTEM-EXECUTOR', 1, 'AstralJet', ?, 'completed', ?, '[]', NULL, '{}'
        WHERE NOT EXISTS (SELECT 1 FROM records WHERE record_id='SYSTEM-EXECUTOR' AND version=1)
        """,
        (applied_at, "0" * 64),
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (3, applied_at),
    )
    connection.executescript(MIGRATION_4)
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (4, applied_at),
    )
    connection.executescript(MIGRATION_5)
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (5, applied_at),
    )
    connection.executescript(MIGRATION_6)
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (6, applied_at),
    )
    if not connection.execute('SELECT 1 FROM schema_migrations WHERE version=7').fetchone():
        stamp = applied_at.replace("'", "''")
        connection.executescript("BEGIN IMMEDIATE;\n" + MIGRATION_7 +
                                 f"\nINSERT INTO schema_migrations VALUES (7, '{stamp}');\nCOMMIT;")
