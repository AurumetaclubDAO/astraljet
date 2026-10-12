"""Stored weekly scenario contract; integrity is not economic qualification."""
from __future__ import annotations

from astraljet.domain.enums import EvidenceType, RunOutcome
from astraljet.domain.records import RunRecord, record_content_hash
from astraljet.domain.validation import canonical_json

CONTRACT = 'weekly-recorded-v1'


def weekly_input_hash(inputs: dict) -> str:
    # The full report hash describes an OUTPUT, not an input. Keep it in the
    # artifact/manifest, but do not let it redefine input identity on replay.
    context = {key: value for key, value in inputs['report'].items() if key != 'report_hash'}
    return record_content_hash({**inputs, 'report': context})


def weekly_projection(result: dict, metric_names: list[str]) -> dict:
    history = result['daily']['strategy']
    metrics = {name: result['metrics']['strategy']['out_of_sample'][name] for name in metric_names}
    # Bind the complete scenario, including the benchmark and IS, into the
    # existing RUN output hash. Never discard the non-selected observations.
    metrics['weekly_result_hash'] = record_content_hash(result)
    return {
        'trades': tuple(order for order in result['orders'] if order['portfolio'] == 'strategy'),
        'rejected_signals': tuple(item for item in result['unfilled'] if item['portfolio'] == 'strategy'),
        'exposure': tuple({key: row[key] for key in
                          ('date', 'cash', 'btc_units', 'eth_units', 'gross_exposure')} for row in history),
        'equity_curve': tuple({'date': row['date'], 'equity': row['equity_close']} for row in history),
        'metrics': metrics,
        'total_cost': result['metrics']['strategy']['full']['total_cost'],
    }


def weekly_integrity_issues(run: RunRecord) -> tuple[str, ...]:
    """Also validate fields the legacy RUN contract does not cover."""
    try:
        evidence = run.reproduction
        if evidence['schema'] != CONTRACT or not run.engine_version.startswith(CONTRACT + '/'):
            raise ValueError('contract')
        if run.evidence_type is not EvidenceType.BACKTEST or run.run_outcome is not RunOutcome.INCONCLUSIVE:
            raise ValueError('unqualified research only')
        inputs, result = evidence['weekly_input'], evidence['weekly_result']
        if weekly_input_hash(inputs) != run.input_hash or inputs['engine_input_hash'] != result['input_hash']:
            raise ValueError('input hash')
        context, index = inputs['report'], inputs['scenario_index']
        if type(index) is not int or index < 0 or index >= len(context['scenarios']):
            raise ValueError('scenario index')
        if (context['experiment']['record_id'], context['experiment']['version']) != (run.experiment_id, run.experiment_version):
            raise ValueError('experiment')
        if (context['schema'] != 'weekly-offline-report-v1' or context['status'] != 'OFFLINE_UNQUALIFIED'
                or context['execution_authorized'] is not False
                or context['criteria_status'] != 'not_evaluated'
                or context['reproduction_status'] != 'not_independently_verified'):
            raise ValueError('qualification')
        if (result['status'] != 'OFFLINE_UNQUALIFIED' or result['execution_authorized'] is not False
                or result['scenario'] != context['scenarios'][index]
                or result['protocol'] != context['protocol']
                or result['engine_hash'] != context['binding']['engine_hash']):
            raise ValueError('scenario binding')
        output = {key: result[key] for key in ('signals', 'orders', 'unfilled', 'daily', 'metrics')}
        if record_content_hash(output) != result['output_hash']:
            raise ValueError('engine output')
        projection = weekly_projection(result, inputs['metric_names'])
        for key, value in projection.items():
            if canonical_json(value) != canonical_json(getattr(run, key)):
                raise ValueError('projection')
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        return ('weekly_artifact_integrity_mismatch',)
    return ()
