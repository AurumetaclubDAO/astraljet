"""Compute and atomically register every frozen weekly scenario, without trading."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from astraljet.application.weekly_experiment import (
    MAX_CSV_BYTES, _records, run_weekly_experiment, weekly_adapter_fingerprint,
)
from astraljet.domain.enums import EvidenceType, RunOutcome, TechnicalStatus
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.records import RunRecord, record_content_hash
from astraljet.domain.validation import canonical_json, new_record_id, utc_now
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.event_store import Event, EventStore, event_from_row
from astraljet.infrastructure.migrations import SCHEMA_VERSION
from astraljet.infrastructure.repositories import RecordRepository
from astraljet.lab.reproduction import run_integrity_issues
from astraljet.lab.weekly_run import CONTRACT, weekly_projection, weekly_input_hash

_EVENT_TYPE = 'weekly_run.batch_completed'
_GUARDS = {'records_no_update', 'records_no_delete', 'records_no_replace',
           'events_no_update', 'events_no_delete', 'events_no_replace'}
MAX_BATCH_BYTES = 64 * 1024 * 1024


def _guard(connection):
    schema = connection.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]
    guards = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    if schema != SCHEMA_VERSION or not _GUARDS <= guards:
        raise ValidationError('Zapis RUN wymaga aktualnego schematu i ochrony historii; nie migruję bazy.',
                              blocker='weekly_registry_not_ready')


def _receipt(connection, repository, key, request_hash, *, report_output=False):
    row = connection.execute('SELECT * FROM events WHERE idempotency_key = ?', (key,)).fetchone()
    if row is None:
        return None
    event = event_from_row(row)
    if (event.event_type != _EVENT_TYPE
            or not re.fullmatch(r'[A-Fa-f0-9]{64}', str(event.payload.get('request_hash', '')))
            or request_hash is not None and event.payload.get('request_hash') != request_hash):
        raise ValidationError('Klucz został użyty przez inne żądanie; wcześniejszy zapis pozostaje niezmieniony.',
                              blocker='weekly_idempotency_conflict')
    manifest = event.payload.get('runs')
    if not isinstance(manifest, list) or not 1 <= len(manifest) <= 8:
        raise ValidationError('Brak kompletnego manifestu serii RUN.')
    runs = []
    for index, ref in enumerate(manifest):
        run = repository._get(connection, ref['record_id'], ref['version'])
        if (not isinstance(run, RunRecord) or record_content_hash(asdict(run)) != ref['record_hash']
                or run_integrity_issues(run) or run.reproduction['weekly_input']['scenario_index'] != index):
            raise ValidationError('Zapisany RUN nie odpowiada manifestowi serii.', blocker='weekly_batch_corrupt')
        runs.append(run)
    context = runs[0].reproduction['weekly_input']['report']
    if len(runs) != len(context['scenarios']) or any(r.reproduction['weekly_input']['report'] != context for r in runs):
        raise ValidationError('Seria RUN nie obejmuje dokładnie wszystkich scenariuszy.')
    reconstructed = {**context, 'results': [r.reproduction['weekly_result'] for r in runs]}
    report_hash = reconstructed.pop('report_hash')
    if record_content_hash(reconstructed) != report_hash or event.payload.get('report_hash') != report_hash:
        raise ValidationError('Hash serii nie odpowiada pełnemu raportowi.')
    if report_output:
        return {**reconstructed, 'report_hash': report_hash}
    return {'schema': CONTRACT, 'created': False, 'execution_authorized': False,
            'criteria_status': 'not_evaluated', 'report_hash': report_hash, 'runs': manifest}


def _make_runs(report, experiment, owner, started_at):
    unsigned = {key: value for key, value in report.items() if key != 'report_hash'}
    if (report.get('report_hash') != record_content_hash(unsigned)
            or not 1 <= len(report['results']) <= 8
            or len(report['results']) != len(experiment.allowed_variants)):
        raise ValidationError('Niekompletny albo zmieniony raport wszystkich scenariuszy.')
    context = {key: value for key, value in report.items() if key != 'results'}
    runs = []
    for index, result in enumerate(report['results']):
        inputs = {'report': context, 'scenario_index': index, 'metric_names': list(experiment.metrics),
                  'engine_input_hash': result['input_hash']}
        input_hash = weekly_input_hash(inputs)
        projection = weekly_projection(result, inputs['metric_names'])
        output_hash = record_content_hash({key: value for key, value in projection.items() if key != 'total_cost'}
                                         | {'outcome': RunOutcome.INCONCLUSIVE.value})
        completed_at = utc_now()
        run = RunRecord(
            record_id=new_record_id('RUN'), version=1, owner=owner, created_at=completed_at,
            technical_status=TechnicalStatus.COMPLETED,
            content_hash=record_content_hash({'input_hash': input_hash, 'output_hash': output_hash,
                                             'outcome': RunOutcome.INCONCLUSIVE.value}),
            limitations=(
                'Obliczenia ukończone; kryteria hipotezy i niezależny REVIEW nie są ocenione.',
                'Metryki główne: OOS strategii. total_cost: pełny okres jednego scenariusza, nie opłata AI/brokera.',
                'IS, benchmark i wszystkie obserwacje pozostają w weekly_result; bez selekcji wariantu.',
                'Next-open jest modelem; daty equity oznaczają dzień świecy, nie chwilę dostępności danych.',
                'Artefakt offline opisuje obliczenie; manifest EVENT potwierdza osobny zapis do rejestru.',
            ),
            experiment_id=experiment.record_id, experiment_version=experiment.version,
            evidence_type=EvidenceType.BACKTEST, started_at=started_at, completed_at=completed_at,
            engine_version=CONTRACT + '/' + result['engine_version'], input_hash=input_hash,
            run_outcome=RunOutcome.INCONCLUSIVE,
            reproduction={'schema': CONTRACT, 'input_hash': input_hash, 'output_hash': output_hash,
                          'weekly_input': inputs, 'weekly_result': result},
            **projection,
        )
        if run_integrity_issues(run):
            raise ValidationError('Niepoprawny artefakt modelu; nie zapisano serii RUN.')
        runs.append(run)
    return runs


def export_weekly_report(database: Database, *, idempotency_key: str) -> dict:
    """Reconstruct the original computation artifact from committed RUN records."""
    with database.read_only() as connection:
        _guard(connection)
        report = _receipt(connection, RecordRepository(database), idempotency_key, None, report_output=True)
    if report is None:
        raise ValidationError('Nie znaleziono zapisanej serii RUN dla tego klucza.')
    return report


def record_weekly_experiment(database: Database, *, experiment_id: str, version: int,
                             csv_path: str | Path, owner: str, idempotency_key: str) -> dict:
    if not isinstance(owner, str) or not owner.strip() or len(owner) > 120:
        raise ValidationError('Wymagany jawny autor RUN, maks. 120 znaków.')
    if not isinstance(idempotency_key, str) or not 8 <= len(idempotency_key) <= 200:
        raise ValidationError('Klucz serii RUN wymaga 8–200 znaków.')
    with database.read_only() as connection:
        _guard(connection)
    frozen = _records(database, experiment_id, version)
    experiment, strategy, data = frozen
    path = Path(csv_path).expanduser().resolve()
    if path != Path(data.locator).expanduser().resolve():
        raise DomainBlockedError('CSV nie wskazuje przypiętej lokalizacji DATA.', blocker='weekly_csv_locator_mismatch')
    hashes = [record_content_hash(asdict(record)) for record in frozen]
    request_hash = record_content_hash({'schema': CONTRACT, 'frozen_records': hashes,
                                        'csv_locator': str(path), 'owner': owner})
    repository = RecordRepository(database)
    with database.read_only() as connection:
        prior = _receipt(connection, repository, idempotency_key, request_hash)
        if prior:
            return prior
    started_at = utc_now()
    if datetime.fromisoformat(experiment.frozen_at.replace('Z', '+00:00')) > datetime.fromisoformat(started_at.replace('Z', '+00:00')):
        raise ValidationError('EXP musi być zamrożony przed rozpoczęciem RUN.')
    report = run_weekly_experiment(database, experiment_id=experiment_id, version=version, csv_path=path)
    runs = _make_runs(report, experiment, owner, started_at)
    if len(canonical_json([asdict(run) for run in runs]).encode('utf-8')) > MAX_BATCH_BYTES:
        raise ValidationError('Seria RUN przekracza 64 MiB; nie zapisano częściowego wyniku.')
    # Before committing, detect replacement of the file used for the calculation.
    # This is a second integrity read, not a second parse/calculation of prices.
    with path.open('rb') as stream:
        content = stream.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES or hashlib.sha256(content).hexdigest().upper() != data.sha256.upper():
        raise DomainBlockedError('CSV zmienił się podczas obliczeń; nie zapisano RUN.', blocker='weekly_csv_changed')
    if weekly_adapter_fingerprint() != report['adapter_hash']:
        raise DomainBlockedError('Kod zmienił się przed zapisem.', blocker='weekly_code_mismatch')
    manifest = [{'record_id': run.record_id, 'version': run.version,
                 'record_hash': record_content_hash(asdict(run)),
                 'scenario': run.reproduction['weekly_result']['scenario']['name']} for run in runs]
    with database.transaction() as connection:
        _guard(connection)
        prior = _receipt(connection, repository, idempotency_key, request_hash)
        if prior:  # another process won while we were calculating
            return prior
        for expected, digest in zip(frozen, hashes):
            actual = repository._get(connection, expected.record_id, expected.version)
            if record_content_hash(asdict(actual)) != digest:
                raise DomainBlockedError('Zamrożone rekordy zmieniły się przed zapisem.', blocker='weekly_frozen_records_changed')
        correlation = new_record_id('CORR')
        for index, run in enumerate(runs):
            repository.insert_record(connection, run)
            EventStore.insert(connection, Event.create(
                actor=owner, event_type='weekly_run.scenario_completed', record_type='RUN',
                record_id=run.record_id, record_version=run.version,
                reason='Obliczono przypięty scenariusz; kryteria nadal wymagają oceny.',
                outcome=run.run_outcome.value, payload={'record_hash': manifest[index]['record_hash']},
                correlation_id=correlation,
                idempotency_key='weekly-scenario:' + record_content_hash({'key': idempotency_key, 'index': index}),
            ))
        EventStore.insert(connection, Event.create(
            actor=owner, event_type=_EVENT_TYPE, record_type='RUN', record_id=runs[0].record_id,
            record_version=1, reason='Atomowy zapis wszystkich scenariuszy zamrożonego EXP.',
            outcome='inconclusive', payload={'request_hash': request_hash, 'report_hash': report['report_hash'], 'runs': manifest},
            correlation_id=correlation, idempotency_key=idempotency_key,
        ))
        receipt = _receipt(connection, repository, idempotency_key, request_hash)
    return {**receipt, 'created': True}
