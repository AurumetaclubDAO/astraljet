from __future__ import annotations

from dataclasses import asdict, dataclass

from astraljet.application.independent_check import assess_independent_check, validate_independent_check
from astraljet.domain.enums import ReviewVerdict, TechnicalStatus, RunOutcome
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.domain.records import ExperimentRecord, ReviewRecord, RunRecord, record_content_hash
from astraljet.domain.validation import new_record_id, utc_now, validate_sha256
from astraljet.lab.reproduction import ReproductionReport, compare_runs, run_integrity_issues


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    reviewer: str
    evidence: tuple[str, ...]
    findings: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    conditions: tuple[str, ...]
    rejection_reasons: tuple[str, ...]


def comparability_issues(
    runs: tuple[RunRecord, ...],
    experiments: tuple[ExperimentRecord, ...],
) -> tuple[str, ...]:
    if len(runs) != len(experiments):
        return ("run_experiment_count_mismatch",)
    if not runs:
        return ("missing_runs",)
    first_run = runs[0]
    first_exp = experiments[0]
    issues: list[str] = []
    if len({r.record_id for r in runs}) != len(runs):
        issues.append('duplicate_run')
    for current_run, current_exp in zip(runs, experiments):
        if (current_run.experiment_id,current_run.experiment_version) != (current_exp.record_id,current_exp.version):
            issues.append('run_experiment_binding_mismatch')
        if not current_exp.metrics or set(current_exp.metrics) != set(current_exp.tolerance):
            issues.append('incomplete_metric_contract')
        if current_exp.technical_status is not TechnicalStatus.COMPLETED:
            issues.append('experiment_not_completed')
    for current_run, current_exp in zip(runs[1:], experiments[1:]):
        if (current_exp.record_id,current_exp.version,current_exp.plan_hash) != (first_exp.record_id,first_exp.version,first_exp.plan_hash):
            issues.append('experiment_plan_mismatch')
        if any(getattr(current_exp,key) != getattr(first_exp,key) for key in
               ('in_sample','out_of_sample','metrics','tolerance','criteria','allowed_variants','seed')):
            issues.append('experiment_protocol_mismatch')
        if (current_exp.strategy_id, current_exp.strategy_version) != (
            first_exp.strategy_id,
            first_exp.strategy_version,
        ):
            issues.append("strategy_version_mismatch")
        if (current_exp.data_id, current_exp.data_version) != (
            first_exp.data_id,
            first_exp.data_version,
        ):
            issues.append("data_version_mismatch")
        if current_exp.cost_model != first_exp.cost_model:
            issues.append("cost_model_mismatch")
        if current_exp.code_hash != first_exp.code_hash:
            issues.append("code_version_mismatch")
        if current_run.evidence_type != first_run.evidence_type:
            issues.append("evidence_type_mismatch")
        if current_run.input_hash != first_run.input_hash:
            issues.append("run_input_mismatch")
    return tuple(dict.fromkeys(issues))


def create_review(
    *,
    runs: tuple[RunRecord, ...],
    experiments: tuple[ExperimentRecord, ...],
    request: ReviewRequest,
    reproduction: ReproductionReport | None,
    owner: str,
    independent_checks: tuple[dict, ...] = (),
) -> ReviewRecord:
    if not runs or len(runs) > 100 or len(independent_checks) > 8:
        raise ValidationError('REVIEW wymaga 1–100 RUN i maksymalnie 8 niezależnych raportów.')
    if not request.reviewer.strip():
        raise ValidationError("REVIEW wymaga jawnego recenzenta.")
    if any(request.reviewer.strip().casefold() == run.owner.strip().casefold() for run in runs):
        raise DomainBlockedError(
            "Autor RUN nie może samodzielnie zweryfikować własnego wyniku.",
            blocker="reviewer_not_independent",
            owner="AJ-08",
            allowed_next_action="Wyznacz odrębnego recenzenta.",
        )
    issues = comparability_issues(runs, experiments)
    missing = list(request.missing_evidence)
    for run in runs:
        missing.extend(run_integrity_issues(run))
        if run.run_outcome is not RunOutcome.PASSED:
            missing.append('run_criteria_not_passed')
    if not request.evidence or any(not isinstance(e,str) or not e.strip() for e in request.evidence):
        missing.append('missing_review_evidence')
    if len(runs) < 2:
        missing.append("missing_independent_reproduction")
    if reproduction is None:
        missing.append("missing_reproduction_report")
    elif not reproduction.verified:
        missing.extend(reproduction.differences or ("reproduction_failed",))
    comparisons = [compare_runs(runs[0],run,experiments[0].tolerance)
                   for run in runs[1:]] if experiments and len(runs) == len(experiments) else []
    for comparison in comparisons:
        missing.extend(comparison.differences)
    reproduction_verified = (not issues and bool(comparisons)
        and all(c.verified for c in comparisons)
        and reproduction is not None and reproduction.verified is True and not reproduction.differences)
    checks = [assess_independent_check(value,runs,experiments) for value in independent_checks]
    independent_verified = bool(checks) and all(c['verified'] for c in checks)
    if not checks:
        missing.append('missing_independent_check')
    for check in checks:
        missing.extend(check['differences'])
    if not reproduction_verified:
        missing.append('reproduction_not_verified')
    missing.extend(issues)
    missing = list(dict.fromkeys(missing))

    if request.rejection_reasons:
        verdict = ReviewVerdict.REJECTED
    elif not missing and reproduction_verified and independent_verified:
        verdict = ReviewVerdict.VERIFIED
    else:
        verdict = ReviewVerdict.UNVERIFIED

    now = utc_now()
    findings = tuple(request.findings) + tuple(request.rejection_reasons) + issues
    comparability_status = "comparable" if not issues else "NIEPORÓWNYWALNE"
    verification_details = {'schema':'astraljet-review-verification-v1',
        'request_hash':record_content_hash({
            'schema':'astraljet-review-request-v1',
            'runs':[asdict(run) for run in runs],
            'experiments':[asdict(exp) for exp in experiments],
            'request':asdict(request), 'owner':owner,
            'reproduction':asdict(reproduction) if reproduction is not None else None,
            'independent_checks':independent_checks,
        }),
        'run_refs':[{'record_id':run.record_id,'version':run.version,
                     'record_hash':record_content_hash(asdict(run))} for run in runs],
        'experiment_refs':[{'record_id':exp.record_id,'version':exp.version,
                            'record_hash':record_content_hash(asdict(exp))} for exp in experiments],
        'reproduction_verified':reproduction_verified, 'independent_check_verified':independent_verified,
        'comparisons':[{'expected_run_id':runs[0].record_id,'actual_run_id':run.record_id,
                        'verified':comparison.verified,'differences':list(comparison.differences)}
                       for run,comparison in zip(runs[1:],comparisons)],
        'independent_checks':checks}
    payload = {
        "run_ids": tuple(run.record_id for run in runs),
        "reviewer": request.reviewer,
        "evidence": request.evidence,
        "findings": findings,
        "missing_evidence": tuple(missing),
        "verdict": verdict.value,
        "conditions": request.conditions,
        "comparability_status": comparability_status,
        "reproduction_verified": reproduction_verified,
        "verification_details":verification_details,
    }
    return ReviewRecord(
        record_id=new_record_id("REVIEW"),
        version=1,
        owner=owner,
        created_at=now,
        technical_status=TechnicalStatus.COMPLETED,
        content_hash=record_content_hash(payload),
        limitations=(
            "REVIEW ocenia dowody historyczne/testowe i nie jest gwarancją wyniku.",
            "Werdykt nie tworzy mandatu wykonawczego.",
            "Powtórzenie tego samego silnika sprawdza odtwarzalność, nie niezależność metody.",
            "Tożsamość autora i pochodzenie dostarczonego raportu są deklarowane lokalnie; hash nie uwierzytelnia autora ani rentowności.",
        ),
        run_ids=payload["run_ids"],
        reviewer=request.reviewer,
        evidence=request.evidence,
        findings=findings,
        missing_evidence=tuple(missing),
        verdict=verdict,
        conditions=request.conditions,
        comparability_status=comparability_status,
        reproduction_verified=reproduction_verified,
        verification_details=verification_details,
    )


def validate_review_replay(existing: object, requested: ReviewRecord) -> None:
    """A duplicate key may replay only the same pinned input and assessment."""
    if (not isinstance(existing, ReviewRecord)
            or not isinstance(existing.verification_details, dict)
            or existing.verification_details.get('request_hash') != requested.verification_details['request_hash']
            or existing.content_hash != record_content_hash(existing.payload())):
        raise ValidationError(
            'Klucz idempotencji był użyty z innym lub starszym zakresem. '
            'Nowa ocena wymaga nowego klucza; istniejący REVIEW nie został zmieniony.'
        )


def review_evidence_verified(review: ReviewRecord) -> bool:
    """Validate stored evidence consistency, not author identity or profit."""
    details = review.verification_details
    if (review.technical_status is not TechnicalStatus.COMPLETED
            or review.verdict is not ReviewVerdict.VERIFIED
            or review.reproduction_verified is not True or review.missing_evidence
            or review.content_hash.upper() != record_content_hash(review.payload())
            or not isinstance(details, dict)
            or details.get('schema') != 'astraljet-review-verification-v1'
            or details.get('reproduction_verified') is not True
            or details.get('independent_check_verified') is not True):
        return False
    comparisons = details.get('comparisons')
    checks = details.get('independent_checks')
    refs = details.get('run_refs')
    if (not 2 <= len(review.run_ids) <= 100 or len(set(review.run_ids)) != len(review.run_ids)
            or not isinstance(comparisons, list) or len(comparisons) != len(review.run_ids) - 1
            or not isinstance(checks, list) or not 1 <= len(checks) <= 8
            or not isinstance(refs, list) or len(refs) != len(review.run_ids)):
        return False
    try:
        validate_sha256(details.get('request_hash', ''))
        for index, ref in enumerate(refs):
            if (not isinstance(ref, dict) or ref.get('record_id') != review.run_ids[index]
                    or type(ref.get('version')) is not int or ref['version'] < 1):
                return False
            validate_sha256(ref.get('record_hash', ''))
        for index, comparison in enumerate(comparisons, start=1):
            if (not isinstance(comparison, dict) or comparison.get('verified') is not True
                    or comparison.get('differences') != []
                    or comparison.get('expected_run_id') != review.run_ids[0]
                    or comparison.get('actual_run_id') != review.run_ids[index]):
                return False
        by_ref = {(ref['record_id'], ref['version']):ref['record_hash'].upper() for ref in refs}
        for check in checks:
            if (not isinstance(check, dict) or check.get('verified') is not True
                    or check.get('differences') != []):
                return False
            artifact = validate_independent_check(check.get('artifact'))
            if check.get('report_hash') != artifact['report_hash']:
                return False
            observations = artifact['observations']
            observed = {(o['run_id'], o['run_version']):o['record_hash'].upper() for o in observations}
            if len(observed) != len(observations) or observed != by_ref:
                return False
    except (ValidationError, TypeError, KeyError, AttributeError):
        return False
    return True
