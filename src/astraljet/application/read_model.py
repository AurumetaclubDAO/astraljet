"""Read models for the existing local registry, not a second source of truth.

Only metadata is exported. A graph is evidence of stored references, never an
authorization to execute or a claim that the referenced research is correct.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from astraljet.domain.enums import (
    CandidateStatus, DataStatus, EvidenceType, IncubationStatus, ReviewVerdict,
    RiskDecisionStatus, RunOutcome, StrategyStatus, TechnicalStatus, TrustStatus,
    RecordType,
)
from astraljet.domain.errors import ValidationError
from astraljet.domain.validation import utc_now
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.migrations import SCHEMA_VERSION


Key = tuple[str, int]
# child type: (payload field, target type, explicit version field, is a list)
REFERENCES = {
    'CAND': (('source_ids', 'SRC', None, True),),
    'STRAT': (('candidate_id', 'CAND', None, False),),
    'EXP': (('strategy_id', 'STRAT', 'strategy_version', False),
            ('data_id', 'DATA', 'data_version', False)),
    'RUN': (('experiment_id', 'EXP', 'experiment_version', False),),
    'REVIEW': (('run_ids', 'RUN', None, True),),
    'RISK_DECISION': (('review_id', 'REVIEW', None, False),),
    'MANDATE': (('risk_decision_id', 'RISK_DECISION', None, False),
                ('strategy_id', 'STRAT', 'strategy_version', False)),
    'INCU': (('mandate_id', 'MANDATE', None, False),),
}
DOMAIN_STATUSES = {
    'SRC': ('trust_status', TrustStatus), 'CAND': ('candidate_status', CandidateStatus),
    'STRAT': ('strategy_status', StrategyStatus), 'DATA': ('data_status', DataStatus),
    'RUN': ('run_outcome', RunOutcome), 'REVIEW': ('verdict', ReviewVerdict),
    'RISK_DECISION': ('decision', RiskDecisionStatus), 'INCU': ('incubation_status', IncubationStatus),
}
GUARDS = {'records_no_update', 'records_no_delete', 'records_no_replace',
          'events_no_update', 'events_no_delete', 'events_no_replace'}
REQUIRED_COLUMNS = {
    'schema_migrations': {'version'},
    'records': {'record_type', 'record_id', 'version', 'created_at', 'technical_status',
                'content_hash', 'payload_json'},
    'events': {'event_id', 'record_id', 'record_version'},
}


def ref(key: Key) -> dict[str, Any]:
    return {'record_id': key[0], 'version': key[1]}


def _enum_value(value: Any, enum: Any) -> str:
    try:
        return enum(value).value
    except (ValueError, TypeError):
        return 'unknown'


class _Snapshot:
    def __init__(self, connection: sqlite3.Connection) -> None:
        for table, columns in REQUIRED_COLUMNS.items():
            # Names come only from the fixed application allowlist above.
            actual = {row['name'] for row in connection.execute(f'PRAGMA table_info({table})')}
            if not columns <= actual:
                raise ValidationError('Nieobsługiwany schemat bazy.', blocker='schema_unsupported')
        versions = [row[0] for row in connection.execute('SELECT version FROM schema_migrations')]
        if not versions or any(type(v) is not int for v in versions) or not 1 <= max(versions) <= SCHEMA_VERSION:
            raise ValidationError('Nieobsługiwana wersja bazy.', blocker='schema_unsupported')
        self.storage_version = max(versions)
        self.nodes: dict[Key, dict[str, Any]] = {}
        self.payloads: dict[Key, dict[str, Any]] = {}
        self.by_id: dict[str, list[int]] = defaultdict(list)
        self.edges: list[dict[str, Any]] = []
        self.diagnostics: list[dict[str, Any]] = []
        existing_guards = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        self.missing_guards = sorted(GUARDS - existing_guards)
        if self.missing_guards:
            self.diagnostics.append({'code': 'history_guards_missing', 'guards': self.missing_guards})
        for row in connection.execute('SELECT record_type, record_id, version, created_at, technical_status, content_hash, payload_json FROM records ORDER BY record_id, version'):
            if row['record_type'] == 'SYSTEM':
                continue
            payload = json.loads(row['payload_json'])
            if not isinstance(payload, dict):
                raise ValidationError('Niepoprawny zapis rekordu.', blocker='invalid_record')
            key = (row['record_id'], row['version'])
            node = {name: row[name] for name in ('record_type', 'record_id', 'version', 'created_at', 'content_hash')}
            node['technical_status'] = _enum_value(row['technical_status'], TechnicalStatus)
            node['domain_status'] = 'unknown'
            if row['record_type'] in DOMAIN_STATUSES:
                field, enum = DOMAIN_STATUSES[row['record_type']]
                node['domain_status'] = _enum_value(payload.get(field), enum)
            if row['record_type'] == 'RUN':
                node['evidence_type'] = _enum_value(payload.get('evidence_type'), EvidenceType)
            self.nodes[key] = node
            self.payloads[key] = payload
            self.by_id[key[0]].append(key[1])
        for key, node in self.nodes.items():
            payload = self.payloads[key]
            for field, target_type, version_field, many in REFERENCES.get(node['record_type'], ()):
                value = payload.get(field)
                if many:
                    values = value if isinstance(value, list) and value else [None]
                else:
                    values = [value]
                for target in values:
                    version = payload.get(version_field) if version_field else None
                    self._add_edge(key, field, target_type, target, version, bool(version_field))
        self.event_count = connection.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        last_event = connection.execute('SELECT event_id FROM events ORDER BY rowid DESC LIMIT 1').fetchone()
        self.last_event_id = last_event[0] if last_event else None
        self.event_counts = {(row[0], row[1]): row[2] for row in connection.execute(
            'SELECT record_id, record_version, COUNT(*) FROM events GROUP BY record_id, record_version')}
        for key in self.nodes:
            if not self.event_counts.get(key):
                self.diagnostics.append({'code': 'audit_event_missing', 'record': ref(key)})

    def _add_edge(self, key: Key, field: str, target_type: str, target: Any,
                  version: Any, explicit: bool) -> None:
        valid = isinstance(target, str) and target.startswith(target_type + '-')
        valid = valid and (not explicit or type(version) is int and version >= 1)
        available = self.by_id.get(target, []) if isinstance(target, str) else []
        resolution = 'invalid'
        resolved = None
        if valid:
            if explicit:
                resolution = 'exact' if version in available else 'missing'
                resolved = version if resolution == 'exact' else None
            elif len(available) == 1:
                resolution, resolved = 'unversioned_single', available[0]
            else:
                resolution = 'ambiguous' if available else 'missing'
        edge = {
            'child': ref(key), 'parent': {'record_id': target if isinstance(target, str) else None,
                                        'version': version if explicit and type(version) is int else resolved},
            'relation': field, 'resolution': resolution, 'available_versions': list(available),
        }
        if resolved is not None and self.nodes[(target, resolved)]['record_type'] != target_type:
            edge['resolution'] = 'invalid'
        self.edges.append(edge)
        if edge['resolution'] != 'exact':
            self.diagnostics.append({'code': edge['resolution'] + '_reference', **edge})

    def strategy_key(self, record_id: str, version: int | None) -> Key:
        if version is not None and (type(version) is not int or version < 1):
            raise ValidationError('Wersja musi być dodatnią liczbą całkowitą.')
        available = self.by_id.get(record_id, [])
        key = (record_id, version if version is not None else max(available, default=0))
        if key not in self.nodes or self.nodes[key]['record_type'] != 'STRAT':
            raise ValidationError('Nie znaleziono wskazanej wersji STRAT.', blocker='strategy_missing')
        return key


@contextmanager
def _snapshot(database: Database) -> Iterator[_Snapshot]:
    try:
        with database.read_only() as connection:
            yield _Snapshot(connection)
    except (sqlite3.DatabaseError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        # Do not echo database payloads or connection paths to future API clients.
        raise ValidationError('Nie można odczytać spójnego stanu bazy.', blocker='snapshot_unavailable') from exc


def _base(snapshot: _Snapshot) -> dict[str, Any]:
    return {'schema_version': 1, 'generated_at': utc_now(), 'mode': 'READ_ONLY',
            'storage_schema_version': snapshot.storage_version, 'execution_authorized': False,
            'scope': 'selected_local_registry', 'broker_connection': 'not_checked'}


def inspect_system(database: Database) -> dict[str, Any]:
    with _snapshot(database) as snapshot:
        counts = Counter(node['record_type'] for node in snapshot.nodes.values())
        objects = Counter(snapshot.nodes[(record_id, max(versions))]['record_type']
                          for record_id, versions in snapshot.by_id.items())
        return {**_base(snapshot), 'record_versions': dict(sorted(counts.items())),
                'record_objects': dict(sorted(objects.items())), 'event_count': snapshot.event_count,
                'history_guard_names_present': not snapshot.missing_guards,
                'records': list(snapshot.nodes.values()), 'diagnostics': snapshot.diagnostics,
                'note': 'Obecność rekordów i triggerów nie potwierdza skuteczności strategii ani zgody na handel.'}


def list_strategies(database: Database) -> dict[str, Any]:
    with _snapshot(database) as snapshot:
        strategies = []
        for record_id, versions in snapshot.by_id.items():
            node = snapshot.nodes[(record_id, max(versions))]
            if node['record_type'] == 'STRAT':
                strategies.append({**node, 'available_versions': list(versions)})
        return {**_base(snapshot), 'strategies': strategies}


def registry_snapshot(database: Database, registry_id: str, *, include_cursor: bool = False) -> dict[str, Any]:
    """Portable, metadata-only view. The caller's label is not an authenticated ID.

    No strategy approval, raw payload, file locator or account data is exported.
    Limits match the browser contract; refuse rather than silently truncate.
    """
    token = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,47}', registry_id):
        raise ValidationError('Etykieta rejestru: 1–48 małych liter, cyfr lub myślników.')
    with _snapshot(database) as snapshot:
        if len(snapshot.nodes) > 5000 or len(snapshot.edges) > 20000:
            raise ValidationError('Rejestr przekracza limit widoku przeglądarki.', blocker='snapshot_too_large')
        nodes = []
        for node in snapshot.nodes.values():
            try:
                stamp = node['created_at']
                valid_time = isinstance(stamp, str) and bool(re.fullmatch(
                    r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', stamp))
                if valid_time:
                    datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            except ValueError:
                valid_time = False
            if (not isinstance(node['record_id'], str) or not token.fullmatch(node['record_id']) or
                    node['record_type'] not in {item.value for item in RecordType} or
                    not node['record_id'].startswith(node['record_type'] + '-') or
                    type(node['version']) is not int or not 1 <= node['version'] <= 9007199254740991 or
                    not isinstance(node['content_hash'], str) or
                    not re.fullmatch(r'[a-fA-F0-9]{64}', node['content_hash']) or not valid_time):
                raise ValidationError('Metadane rekordu nie spełniają kontraktu widoku.', blocker='invalid_metadata')
            nodes.append({'id': node['record_id'], 'version': node['version'],
                          'kind': node['record_type'], 'status': node['domain_status'],
                          'technical_status': node['technical_status'], 'created_at': node['created_at'],
                          'hash': node['content_hash'], 'evidence_type': node.get('evidence_type')})
        edges = []
        for edge in snapshot.edges:
            parent_id = edge['parent']['record_id']
            child = snapshot.nodes[(edge['child']['record_id'], edge['child']['version'])]
            target_type = next(r[1] for r in REFERENCES[child['record_type']] if r[0] == edge['relation'])
            valid_id = isinstance(parent_id, str) and bool(token.fullmatch(parent_id)) and parent_id.startswith(target_type + '-')
            version = edge['parent']['version']
            valid_version = type(version) is int and 1 <= version <= 9007199254740991
            edges.append({'child': {'id': edge['child']['record_id'], 'version': edge['child']['version']},
                          'parent': {'id': parent_id if valid_id else None,
                                     'version': version if valid_version else None},
                          'relation': edge['relation'],
                          'resolution': edge['resolution'] if valid_id else 'invalid'})
        warnings = set()
        if snapshot.missing_guards:
            warnings.add('history_guards_missing')
        if any(d['code'] == 'audit_event_missing' for d in snapshot.diagnostics):
            warnings.add('audit_event_missing')
        if any(e['resolution'] == 'unversioned_single' for e in edges):
            warnings.add('unversioned_references')
        if any(e['resolution'] in ('ambiguous', 'missing', 'invalid') for e in edges):
            warnings.add('unresolved_references')
        return {'format': 'astraljet-lineage-v1', 'origin': 'local_registry',
                'registry_id': 'local:' + registry_id, 'generated_at': utc_now(),
                'mode': 'READ_ONLY', 'execution_authorized': False, 'truncated': False,
                'nodes': nodes, 'edges': edges, 'warnings': sorted(warnings),
                **({'cursor': {'event_id': snapshot.last_event_id}} if include_cursor else {})}


def strategy_lineage(database: Database, record_id: str, *, version: int | None = None) -> dict[str, Any]:
    with _snapshot(database) as snapshot:
        root = snapshot.strategy_key(record_id, version)
        children: dict[Key, set[Key]] = defaultdict(set)
        parents: dict[Key, set[Key]] = defaultdict(set)
        for edge in snapshot.edges:
            if edge['resolution'] in ('exact', 'unversioned_single'):
                child = (edge['child']['record_id'], edge['child']['version'])
                parent = (edge['parent']['record_id'], edge['parent']['version'])
                children[parent].add(child)
                parents[child].add(parent)

        def expand(start: set[Key], graph: dict[Key, set[Key]]) -> set[Key]:
            seen, pending = set(start), list(start)
            while pending:
                for item in graph.get(pending.pop(), ()):
                    if item not in seen:
                        seen.add(item)
                        pending.append(item)
            return seen

        # Never expand descendants of shared ancestors: that would attach other
        # strategies merely because they use the same source or dataset.
        selected = expand(expand({root}, children), parents)
        nodes = [snapshot.nodes[key] for key in sorted(selected)]
        edges = [e for e in snapshot.edges if (e['child']['record_id'], e['child']['version']) in selected]
        incomplete = any(e['resolution'] in ('missing', 'ambiguous', 'invalid') for e in edges)
        status = 'incomplete' if incomplete else 'legacy_unversioned' if any(e['resolution'] == 'unversioned_single' for e in edges) else 'exact'
        return {**_base(snapshot), 'root': ref(root), 'provenance_status': status,
                'nodes': nodes, 'edges': edges,
                'evidence_counts': dict(sorted(Counter(n['evidence_type'] for n in nodes if n['record_type'] == 'RUN').items())),
                'audit_event_count': sum(snapshot.event_counts.get(key, 0) for key in selected),
                'limitations': ['Relacje bez zapisanej wersji nie są dowodem zamrożonego pochodzenia.',
                                'Graf nie weryfikuje zgód, rachunku, salda ani wykonania zleceń.',
                                'Nie obejmuje innych baz ani rekordów wykonania poza rejestrem.']}
