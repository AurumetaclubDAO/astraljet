"""Validate external observations; never execute a report or invent independence.

The local operator supplies the artifact. Hashes establish consistency, not
authentication of its author or proof that an independent program was executed.
"""
from dataclasses import asdict
from copy import deepcopy
import json
from pathlib import Path
import re

from astraljet.domain.errors import ValidationError
from astraljet.domain.records import record_content_hash
from astraljet.lab.reproduction import compare_metrics, finite_number, trace_hash

MAX_REPORT = 1024 * 1024
FIELDS = {'schema','method','verifier','implementation_hash','experiment_id',
          'experiment_version','plan_hash','observations','report_hash'}
OBS_FIELDS = {'run_id','run_version','record_hash','input_hash','trace_hash','metrics','total_cost'}


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r'[a-fA-F0-9]{64}', value) is not None


def validate_independent_check(value):
    try:
        if (not isinstance(value, dict) or set(value) != FIELDS
                or value['schema'] != 'astraljet-independent-check-v1'
                or value['method'] not in ('independent_engine','control_calculation')
                or not isinstance(value['verifier'], str) or not value['verifier'].strip()
                or len(value['verifier']) > 120
                or not _sha(value['implementation_hash']) or not _sha(value['plan_hash'])
                or not _sha(value['report_hash'])
                or not isinstance(value['experiment_id'], str)
                or not re.fullmatch(r'EXP-[A-Za-z0-9_.:-]{1,92}',value['experiment_id'])
                or type(value['experiment_version']) is not int or value['experiment_version'] < 1
                or not isinstance(value['observations'], list) or not 1 <= len(value['observations']) <= 100):
            raise ValueError('shape')
        for observation in value['observations']:
            if (not isinstance(observation, dict) or set(observation) != OBS_FIELDS
                    or not isinstance(observation['run_id'], str)
                    or not re.fullmatch(r'RUN-[A-Za-z0-9_.:-]{1,92}',observation['run_id'])
                    or type(observation['run_version']) is not int or observation['run_version'] < 1
                    or not all(_sha(observation[k]) for k in ('record_hash','input_hash','trace_hash'))
                    or not isinstance(observation['metrics'], dict) or not 1 <= len(observation['metrics']) <= 100
                    or any(not isinstance(k,str) or not re.fullmatch(r'[A-Za-z0-9_]{1,80}',k)
                           for k in observation['metrics'])
                    or finite_number(observation['total_cost']) < 0):
                raise ValueError('observation')
            for number in observation['metrics'].values():
                finite_number(number)
        body = {k:v for k,v in value.items() if k != 'report_hash'}
        if value['report_hash'].upper() != record_content_hash(body):
            raise ValueError('hash')
        return value
    except (KeyError, ValueError, TypeError, OverflowError):
        raise ValidationError('Nieprawidłowy raport niezależnego sprawdzenia; wymagany kompletny, powiązany artefakt.') from None


def load_independent_check(path: str):
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(MAX_REPORT+1)
        if len(raw) > MAX_REPORT:
            raise ValueError('size')
        def unique(pairs):
            result = {}
            for key,value in pairs:
                if key in result:
                    raise ValueError('duplicate')
                result[key] = value
            return result
        def reject_constant(value):
            raise ValueError('constant')
        return validate_independent_check(json.loads(raw,object_pairs_hook=unique,parse_constant=reject_constant))
    except (OSError, ValueError, TypeError, RecursionError):
        raise ValidationError('Nie można odczytać raportu niezależnego sprawdzenia (JSON, maks. 1 MiB).') from None


def assess_independent_check(value, runs, experiments):
    try:
        value = deepcopy(validate_independent_check(value))
    except ValidationError:
        return {'verified':False, 'differences':['invalid_independent_check']}
    differences = []
    if not runs or len(runs) != len(experiments):
        return {'verified':False, 'differences':['independent_check_scope_mismatch']}
    ref = (value['experiment_id'],value['experiment_version'],value['plan_hash'].upper())
    if any(ref != (e.record_id,e.version,e.plan_hash.upper()) for e in experiments):
        differences.append('independent_check_experiment_mismatch')
    if any(value['implementation_hash'].upper() == e.code_hash.upper() for e in experiments):
        differences.append('independent_check_implementation_not_distinct')
    if any(value['verifier'].strip().casefold() == r.owner.strip().casefold() for r in runs):
        differences.append('independent_check_author_not_distinct')
    observations = value['observations']
    by_ref = {(o['run_id'],o['run_version']):o for o in observations}
    if len(by_ref) != len(observations) or set(by_ref) != {(r.record_id,r.version) for r in runs}:
        differences.append('independent_check_scope_mismatch')
    for run,exp in zip(runs,experiments):
        observation = by_ref.get((run.record_id,run.version))
        if observation is None:
            continue
        if observation['record_hash'].upper() != record_content_hash(asdict(run)):
            differences.append('independent_check_record_mismatch')
        if observation['input_hash'].upper() != run.input_hash.upper():
            differences.append('independent_check_input_mismatch')
        if observation['trace_hash'].upper() != trace_hash(run):
            differences.append('independent_check_trace_mismatch')
        if set(observation['metrics']) != set(exp.metrics):
            differences.append('independent_check_metric_scope_mismatch')
        differences.extend(compare_metrics(run.metrics,observation['metrics'],exp.tolerance))
        try:
            if finite_number(observation['total_cost']) != finite_number(run.total_cost):
                differences.append('independent_check_cost_mismatch')
        except ValueError:
            differences.append('independent_check_cost_invalid')
    return {'verified':not differences, 'differences':list(dict.fromkeys(differences)),
            'report_hash':value['report_hash'], 'artifact':value}
