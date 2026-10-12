from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from astraljet.application.experiments import ExperimentDefinition, freeze_experiment
from astraljet.application.weekly_experiment import (
    MODEL_ID, STOP_RULES, inspect_weekly_experiment, run_weekly_experiment,
    weekly_adapter_fingerprint, weekly_binding, weekly_strategy_definition,
)
from astraljet.cli import main
from astraljet.domain.enums import DataStatus, StrategyStatus
from astraljet.domain.errors import DomainBlockedError, ValidationError
from astraljet.infrastructure.database import Database
from astraljet.infrastructure.repositories import RecordRepository
from astraljet.lab.data_quality import DataImportSpec, import_market_data
from astraljet.lab.strategy import create_strategy


class WeeklyExperimentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.database = Database.from_state_dir(self.root / 'registry')
        self.database.initialize()
        self.csv = self.root / 'synthetic.csv'
        with self.csv.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(('timestamp', 'instrument', 'open', 'high', 'low', 'close'))
            for day in range(90):
                stamp = (date(2021, 1, 1) + timedelta(days=day)).isoformat() + 'T00:00:00Z'
                for symbol in ('BTCUSD', 'ETHUSD'):
                    price = 100 + day
                    writer.writerow((stamp, symbol, price, price + 1, price - 1, price))
        self.variants = tuple({
            'model_id': MODEL_ID, 'ma_window': 3, 'slope_lookback': 1,
            'initial_equity': '100', 'scenario_name': name,
            'cost_bps': cost, 'extra_delay_days': delay,
        } for name, cost, delay in (('base', '40', 0), ('stress_delay', '75', 1)))
        definition = weekly_strategy_definition(venue='synthetic', variants=self.variants,
                                                  source_adaptation='Wyłącznie fixture testowy.')
        self.strategy = create_strategy(candidate_id='CAND-fixture', definition=definition, owner='tester')
        self.data = import_market_data(self.csv, owner='tester', spec=DataImportSpec(
            'synthetic', 'synthetic', ('BTCUSD', 'ETHUSD'), '1d', 'UTC',
            'bar_close_utc_next_open_proxy', (), definition.cost_model,
        ))
        self.definition = ExperimentDefinition(
            code_hash=weekly_adapter_fingerprint(), hypothesis='Mechanika, nie rentowność.',
            in_sample=('2021-01-01T00:00:00Z', '2021-02-28T00:00:00Z'),
            out_of_sample=('2021-03-01T00:00:00Z', '2021-03-31T00:00:00Z'),
            allowed_variants=self.variants,
            criteria={'weekly_binding': weekly_binding(self.strategy, self.data),
                      'assessment': 'manual_review_required'},
            budget='0', seed=0, metrics=('net_return', 'max_drawdown'),
            tolerance={'net_return': '0', 'max_drawdown': '0'}, stop_rules=STOP_RULES,
        )
        self.experiment = freeze_experiment(strategy=self.strategy, data=self.data, definition=self.definition, owner='tester')

    def seed(self, *, experiment=None, strategy=None, data=None):
        for record in (strategy or self.strategy, data or self.data, experiment or self.experiment):
            RecordRepository(self.database).save(record, event_type='fixture', reason='test',
                outcome='test_only', actor='tester', idempotency_key=record.record_id + str(record.version))

    def run_model(self, **overrides):
        args = dict(experiment_id=self.experiment.record_id, version=1, csv_path=self.csv)
        args.update(overrides)
        return run_weekly_experiment(self.database, **args)

    def test_exact_frozen_inputs_run_all_variants_deterministically_without_writes(self):
        self.seed()
        paths = (self.database.config.database_path, self.csv)
        before = [p.read_bytes() for p in paths]
        with patch.object(Database, 'initialize', side_effect=AssertionError('migration')), \
                patch.object(RecordRepository, 'save', side_effect=AssertionError('write')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('network')):
            first, second = self.run_model(), self.run_model()
        self.assertEqual(first, second)
        self.assertEqual(before, [p.read_bytes() for p in paths])
        self.assertEqual('OFFLINE_UNQUALIFIED', first['status'])
        self.assertFalse(first['execution_authorized'])
        self.assertFalse(first['run_record_created'])
        self.assertEqual(0, first['records_written'])
        self.assertEqual(['base', 'stress_delay'], [v['scenario']['name'] for v in first['results']])
        self.assertEqual(self.experiment.plan_hash, first['experiment']['plan_hash'])
        self.assertNotIn(str(self.csv), json.dumps(first))
        self.assertEqual('not_evaluated', first['criteria_status'])

    def test_inspection_does_not_run_model(self):
        self.seed()
        with patch('astraljet.application.weekly_experiment.simulate_weekly', side_effect=AssertionError('run')):
            result = inspect_weekly_experiment(self.database, experiment_id=self.experiment.record_id,
                                               version=1, csv_path=self.csv)
        self.assertEqual('INPUTS_VERIFIED_ONLY', result['status'])
        self.assertNotIn('results', result)

    def test_newer_versions_never_replace_frozen_references(self):
        self.seed()
        newer = replace(self.strategy, version=2, strategy_status=StrategyStatus.NEEDS_INPUT)
        RecordRepository(self.database).save(newer, event_type='fixture', reason='test',
            outcome='test_only', actor='tester', idempotency_key='newer-version')
        self.assertEqual(1, self.run_model()['strategy']['version'])
        with self.assertRaises(ValidationError):
            self.run_model(version=2)
        with self.assertRaises(ValidationError):
            self.run_model(version=True)

    def test_missing_registry_is_not_created(self):
        missing = Database.from_state_dir(self.root / 'absent')
        with self.assertRaises(ValidationError):
            run_weekly_experiment(missing, experiment_id=self.experiment.record_id, version=1, csv_path=self.csv)
        self.assertFalse(missing.config.state_dir.exists())

    def test_tampered_plan_and_code_are_blocked_before_model(self):
        for field, value in (('hypothesis', 'changed'), ('budget', '1'), ('seed', 1),
                             ('code_hash', 'A' * 64), ('plan_hash', 'B' * 64)):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as directory:
                    db = Database.from_state_dir(directory)
                    db.initialize()
                    old, self.database = self.database, db
                    try:
                        self.seed(experiment=replace(self.experiment, **{field: value}))
                        with self.assertRaises(DomainBlockedError), \
                                patch('astraljet.application.weekly_experiment.simulate_weekly', side_effect=AssertionError('run')):
                            self.run_model()
                    finally:
                        self.database = old

    def test_metadata_change_with_identical_csv_hash_is_blocked(self):
        self.seed(data=replace(self.data, provider='changed', available_at_rule='future_information'))
        with self.assertRaises(DomainBlockedError) as error:
            self.run_model()
        self.assertEqual('weekly_binding_mismatch', error.exception.blocker)

    def test_strategy_payload_change_with_old_content_hash_is_blocked(self):
        self.seed(strategy=replace(self.strategy, exit_rule='Never sell'))
        with self.assertRaises(DomainBlockedError):
            self.run_model()

    def test_non_ready_records_remain_blocked_even_if_binding_was_rebuilt(self):
        self.seed(data=replace(self.data, data_status=DataStatus.GAPS))
        with self.assertRaises(DomainBlockedError):
            self.run_model()

    def test_changed_csv_and_wrong_path_are_blocked(self):
        self.seed()
        other = self.root / 'other.csv'
        other.write_bytes(self.csv.read_bytes())
        with self.assertRaises(DomainBlockedError):
            self.run_model(csv_path=other)
        self.csv.write_bytes(self.csv.read_bytes().replace(b'101', b'102', 1))
        with self.assertRaises(DomainBlockedError):
            self.run_model()

    def test_legacy_experiment_without_weekly_binding_is_not_routed(self):
        legacy = freeze_experiment(strategy=self.strategy, data=self.data,
            definition=replace(self.definition, criteria={'legacy': 'fixture'}), owner='tester')
        self.seed(experiment=legacy)
        with self.assertRaises(DomainBlockedError):
            self.run_model(experiment_id=legacy.record_id)

    def test_unsupported_metrics_and_criteria_do_not_silently_run(self):
        for overrides in ({'metrics': ('sharpe',), 'tolerance': {'sharpe': '0'}},
                          {'criteria': {**self.definition.criteria, 'profit_required': True}},
                          {'stop_rules': ('unknown_stop_rule',)}, {'budget': '1'}, {'seed': 42}):
            with self.subTest(overrides=overrides):
                exp = freeze_experiment(strategy=self.strategy, data=self.data,
                    definition=replace(self.definition, **overrides), owner='tester')
                self.seed(experiment=exp)
                with self.assertRaises(DomainBlockedError):
                    self.run_model(experiment_id=exp.record_id)

    def test_variants_are_explicit_bounded_and_no_rule_search_is_allowed(self):
        for variants in ((), self.variants * 9,
                         (self.variants[0], {**self.variants[1], 'ma_window': 4}),
                         ({**self.variants[0], 'extra_delay_days': True},),
                         ({**self.variants[0], 'cost_bps': 'NaN'},),
                         ({**self.variants[0], 'extra_field': 1},),
                         (self.variants[0], self.variants[0])):
            with self.subTest(variants=variants), self.assertRaises(ValidationError):
                weekly_strategy_definition(venue='synthetic', variants=variants, source_adaptation='fixture')

    def test_loaded_code_change_blocks_before_and_after_calculation(self):
        self.seed()
        target = 'astraljet.application.weekly_experiment._source_hash'
        with patch(target, return_value='A' * 64), self.assertRaises(DomainBlockedError):
            self.run_model()
        original = weekly_adapter_fingerprint()
        with patch(target, side_effect=[original, 'A' * 64]), self.assertRaises(DomainBlockedError):
            self.run_model()

    def test_inspection_rejects_period_without_in_sample_execution(self):
        short = freeze_experiment(strategy=self.strategy, data=self.data,
            definition=replace(self.definition,
                in_sample=('2021-01-01T00:00:00Z', '2021-01-02T00:00:00Z'),
                out_of_sample=('2021-01-03T00:00:00Z', '2021-03-31T00:00:00Z')), owner='tester')
        self.seed(experiment=short)
        with self.assertRaises(DomainBlockedError):
            inspect_weekly_experiment(self.database, experiment_id=short.record_id, version=1, csv_path=self.csv)

    def test_csv_is_read_once_and_hashed_bytes_are_the_model_input(self):
        self.seed()
        original = Path.open
        count = []

        def observe(path, *args, **kwargs):
            if path == self.csv:
                count.append(args)
            return original(path, *args, **kwargs)

        with patch.object(Path, 'open', observe):
            self.run_model()
        self.assertEqual([('rb',)], count)

    def test_rebuilt_bindings_cannot_route_different_strategy_rules(self):
        definition = weekly_strategy_definition(venue='synthetic', variants=self.variants, source_adaptation='fixture')
        changed = create_strategy(candidate_id='CAND-fixture', owner='tester',
                                  definition=replace(definition, sizing_rule='100 percent BTC'))
        experiment = freeze_experiment(strategy=changed, data=self.data,
            definition=replace(self.definition, criteria={**self.definition.criteria,
                'weekly_binding': weekly_binding(changed, self.data)}), owner='tester')
        self.seed(strategy=changed, experiment=experiment)
        with self.assertRaises(DomainBlockedError) as error:
            self.run_model(experiment_id=experiment.record_id)
        self.assertEqual('weekly_rule_mismatch', error.exception.blocker)

    def test_full_dataset_validation_catches_gap_outside_selected_period(self):
        content = self.csv.read_text(encoding='utf-8')
        self.csv.write_text('\n'.join(line for line in content.splitlines()
                           if not line.startswith('2021-01-02')) + '\n', encoding='utf-8')
        data = import_market_data(self.csv, owner='tester', spec=DataImportSpec(
            'synthetic', 'synthetic', ('BTCUSD', 'ETHUSD'), '1d', 'UTC',
            'bar_close_utc_next_open_proxy', (), self.strategy.cost_model))
        # A corrupt ready label must not substitute for a calendar check.
        data = replace(data, data_status=DataStatus.READY,
                       technical_status=self.data.technical_status, quality_findings=())
        experiment = freeze_experiment(strategy=self.strategy, data=data,
            definition=replace(self.definition,
                in_sample=('2021-01-03T00:00:00Z', '2021-02-28T00:00:00Z'),
                criteria={**self.definition.criteria, 'weekly_binding': weekly_binding(self.strategy, data)}), owner='tester')
        self.seed(data=data, experiment=experiment)
        with self.assertRaises(DomainBlockedError) as error:
            self.run_model(experiment_id=experiment.record_id)
        self.assertEqual('daily_calendar_gap', error.exception.blocker)

    def test_frozen_metadata_is_checked_against_csv_not_just_its_binding(self):
        for changes in ({'row_count': self.data.row_count + 1},
                        {'start': '2021-01-02T00:00:00Z'},
                        {'available_at_rule': 'unknown'}):
            with self.subTest(changes=changes):
                changed = replace(self.data, record_id='DATA-' + next(iter(changes)), **changes)
                experiment = freeze_experiment(strategy=self.strategy, data=changed,
                    definition=replace(self.definition, criteria={**self.definition.criteria,
                        'weekly_binding': weekly_binding(self.strategy, changed)}), owner='tester')
                self.seed(data=changed, experiment=experiment)
                with self.assertRaises(DomainBlockedError):
                    self.run_model(experiment_id=experiment.record_id)

    def test_export_limit_is_bounded_and_does_not_create_oversized_artifact(self):
        from astraljet.infrastructure.snapshot_file import publish_snapshot
        path = self.root / 'too-large.json'
        with self.assertRaises(ValidationError):
            publish_snapshot({'test': 'long enough'}, path, max_bytes=3)
        self.assertFalse(path.exists())
        for invalid in (0, True, 64 * 1024 * 1024 + 1):
            with self.assertRaises(ValidationError):
                publish_snapshot({}, path, max_bytes=invalid)

    def test_cli_blocked_result_is_structured_and_does_not_publish(self):
        self.seed()
        output = self.root / 'blocked.json'
        self.csv.write_bytes(b'changed')
        with redirect_stdout(io.StringIO()) as stream:
            code = main(['--state-dir', str(self.database.config.state_dir), 'run', 'weekly-offline',
                '--experiment-id', self.experiment.record_id, '--version', '1',
                '--csv', str(self.csv), '--output', str(output)])
        self.assertEqual(3, code)
        self.assertEqual('weekly_csv_hash_mismatch', json.loads(stream.getvalue())['error']['blocker'])
        self.assertFalse(output.exists())

    def test_cli_inspect_run_and_no_overwrite(self):
        self.seed()
        output = self.root / 'result.json'
        args = ['--state-dir', str(self.database.config.state_dir), 'run', 'weekly-offline',
                '--experiment-id', self.experiment.record_id, '--version', '1', '--csv', str(self.csv),
                '--output', str(output)]
        with redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(0, main(args))
        self.assertTrue(output.is_file())
        self.assertEqual('OFFLINE_UNQUALIFIED', json.loads(stream.getvalue())['status'])
        original = output.read_bytes()
        with redirect_stdout(io.StringIO()), \
                patch('astraljet.application.weekly_experiment.simulate_weekly', side_effect=AssertionError('run')):
            self.assertEqual(2, main(args))
        self.assertEqual(original, output.read_bytes())
        with redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(0, main(args[:2] + ['experiment', 'inspect-weekly'] + args[4:-2]))
        self.assertEqual('INPUTS_VERIFIED_ONLY', json.loads(stream.getvalue())['status'])
