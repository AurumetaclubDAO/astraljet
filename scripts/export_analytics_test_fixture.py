"""Export synthetic engine artifacts for the website parser's cross-language test.

No production registry, market download, AI, broker or strategy approval is used.
The existing model integration fixture is the producer, not hand-written returns.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from astraljet.application.weekly_experiment import inspect_weekly_experiment
from astraljet.infrastructure.snapshot_file import publish_snapshot
from tests.integration.test_weekly_experiment import WeeklyExperimentTest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    case = WeeklyExperimentTest()
    case.setUp()
    try:
        case.seed()
        reports = {
            'weekly-synthetic.json': case.run_model(),
            'weekly-inspection-synthetic.json': inspect_weekly_experiment(
                case.database, experiment_id=case.experiment.record_id, version=1, csv_path=case.csv),
        }
        for name, value in reports.items():
            result = publish_snapshot(value, args.output_dir / name)
            print(name, result['sha256'], result['bytes'])
    finally:
        case.doCleanups()


if __name__ == '__main__':
    main()
