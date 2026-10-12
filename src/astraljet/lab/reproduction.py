from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
from datetime import datetime
import re

from astraljet.domain.enums import TechnicalStatus
from astraljet.domain.records import RunRecord, record_content_hash


@dataclass(frozen=True, slots=True)
class ReproductionReport:
    verified: bool
    differences: tuple[str, ...]


def finite_number(value: object) -> Decimal:
    """Bound numerical evidence; never allow NaN/Infinity or huge exponents."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('invalid number')
    text = str(value)
    if not text or len(text) > 100:
        raise ValueError('invalid number')
    try:
        number = Decimal(text)
        if not number.is_finite() or abs(number.adjusted()) > 1000:
            raise ValueError('non-finite or out-of-range number')
        return number
    except DecimalException:
        raise ValueError('invalid number') from None


def compare_metrics(expected: dict, actual: dict, tolerance: dict) -> tuple[str, ...]:
    differences = []
    if not isinstance(tolerance, dict) or not tolerance or len(tolerance) > 100:
        return ('missing_metric_contract',)
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return ('invalid_metrics',)
    for metric, text in tolerance.items():
        if not isinstance(metric, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,80}', metric):
            differences.append('invalid_metric_name')
            continue
        try:
            allowed = finite_number(text)
            if allowed < 0:
                raise ValueError('negative tolerance')
        except ValueError:
            differences.append(f'invalid_tolerance_{metric}')
            continue
        if metric not in expected or metric not in actual:
            differences.append(f'missing_metric_{metric}')
            continue
        try:
            left = finite_number(expected[metric])
            right = finite_number(actual[metric])
            # Exact subtraction, including the least significant digit. The
            # default Decimal precision can round a failure down to tolerance.
            with localcontext() as context:
                context.prec = max(left.adjusted(), right.adjusted(), 0) - min(
                    left.as_tuple().exponent, right.as_tuple().exponent, 0
                ) + 2
                context.Emin = -10000
                context.Emax = 10000
                difference = (left - right).copy_abs()
            if difference > allowed:
                differences.append(f'metric_outside_tolerance_{metric}')
        except (ValueError, DecimalException):
            differences.append(f'non_numeric_metric_{metric}')
    return tuple(differences)


def trace_hash(run: RunRecord) -> str:
    return record_content_hash({key:getattr(run,key) for key in
                               ('trades','rejected_signals','exposure','equity_curve')})


def run_integrity_issues(run: RunRecord) -> tuple[str, ...]:
    issues = []
    if (run.engine_version.startswith('weekly-recorded-v1/')
            or isinstance(run.reproduction, dict) and run.reproduction.get('schema') == 'weekly-recorded-v1'
            or isinstance(run.metrics, dict) and 'weekly_result_hash' in run.metrics):
        from astraljet.lab.weekly_run import weekly_integrity_issues
        issues.extend(weekly_integrity_issues(run))
    if run.technical_status is not TechnicalStatus.COMPLETED:
        issues.append('run_not_completed')
    if run.errors:
        issues.append('run_contains_errors')
    if datetime.fromisoformat(run.started_at.replace('Z','+00:00')) > datetime.fromisoformat(run.completed_at.replace('Z','+00:00')):
        issues.append('run_time_order_invalid')
    try:
        if finite_number(run.total_cost) < 0:
            raise ValueError('negative cost')
    except ValueError:
        issues.append('invalid_total_cost')
    reproduction = run.reproduction if isinstance(run.reproduction, dict) else {}
    output_hash = reproduction.get('output_hash')
    if not isinstance(output_hash, str) or not re.fullmatch(r'[A-Fa-f0-9]{64}', output_hash):
        issues.append('missing_output_hash')
    else:
        # This is the existing immutable backtest output contract, not a claim
        # about market correctness. Future engines need explicit contracts.
        expected_hash = record_content_hash({
            'trades':run.trades, 'rejected_signals':run.rejected_signals,
            'exposure':run.exposure, 'equity_curve':run.equity_curve,
            'metrics':run.metrics, 'outcome':run.run_outcome.value,
        })
        if output_hash.upper() != expected_hash:
            issues.append('run_output_integrity_mismatch')
        content_hash = record_content_hash({'input_hash':run.input_hash,
            'output_hash':output_hash, 'outcome':run.run_outcome.value})
        if run.content_hash.upper() != content_hash:
            issues.append('run_content_integrity_mismatch')
    if reproduction.get('input_hash') != run.input_hash:
        issues.append('run_input_integrity_mismatch')
    return tuple(issues)


def compare_runs(
    expected: RunRecord,
    actual: RunRecord,
    tolerance: dict[str, str],
) -> ReproductionReport:
    differences: list[str] = list(run_integrity_issues(expected) + run_integrity_issues(actual))
    if expected.record_id == actual.record_id:
        differences.append('duplicate_run')
    if (expected.experiment_id, expected.experiment_version) != (actual.experiment_id, actual.experiment_version):
        differences.append('experiment_version_mismatch')
    if expected.evidence_type != actual.evidence_type:
        differences.append('evidence_type_mismatch')
    if expected.input_hash != actual.input_hash:
        differences.append("input_hash_mismatch")
    if expected.run_outcome != actual.run_outcome:
        differences.append("run_outcome_mismatch")

    differences.extend(compare_metrics(expected.metrics, actual.metrics, tolerance))
    try:
        if finite_number(expected.total_cost) != finite_number(actual.total_cost):
            differences.append('total_cost_mismatch')
    except ValueError:
        differences.append('invalid_total_cost')

    expected_hash = expected.reproduction.get('output_hash') if isinstance(expected.reproduction,dict) else None
    actual_hash = actual.reproduction.get('output_hash') if isinstance(actual.reproduction,dict) else None
    if expected_hash != actual_hash:
        differences.append("output_hash_mismatch")
    return ReproductionReport(verified=not differences, differences=tuple(dict.fromkeys(differences)))
