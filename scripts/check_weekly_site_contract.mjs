// Offline interoperability check. Uses only a temporary synthetic registry;
// no production API, browser, credential, database or network request.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {resolve, dirname} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
if (!process.argv[2]) throw new Error('Wskaż checkout istniejącej witryny.');
const site = resolve(process.argv[2]);
const {parseSyncEnvelope} = await import(pathToFileURL(resolve(site, 'lib/registry-sync.ts')).href);
const {parseAnalyticsReport} = await import(pathToFileURL(resolve(site, 'lib/analytics-report.ts')).href);
const python = process.env.ASTRALJET_PYTHON ?? resolve(root, '.venv/Scripts/python.exe');
const code = [
  'import json',
  'from tests.integration.test_weekly_recorded import WeeklyRecordedTest',
  'from astraljet.application.registry_sync import build_batch',
  'from astraljet.application.weekly_recorded import export_weekly_report',
  'case = WeeklyRecordedTest()',
  'case.setUp()',
  'try:',
  ' case.seed()',
  ' receipt = case.execute()',
  ' batch, body = build_batch(case.database, "weekly-contract-test")',
  ' report = export_weekly_report(case.database, idempotency_key="weekly-fixture-batch-1")',
  ' print(json.dumps({"batch": body.decode(), "report": report, "receipt": receipt}))',
  'finally:',
  ' case.doCleanups()',
].join('\n');
const values = JSON.parse(execFileSync(python, ['-c', code], {
  cwd: root, env: {...process.env, PYTHONPATH: resolve(root, 'src')},
  encoding: 'utf8', maxBuffer: 8 * 1024 * 1024, timeout: 30000,
}));
const batch = parseSyncEnvelope(values.batch);
const runs = batch.records.filter(item => item.kind === 'RUN');
assert.equal(runs.length, 2);
assert.ok(runs.every(item => item.status === 'inconclusive' && item.evidence_type === 'BACKTEST'));
assert.ok(runs.every(item => values.receipt.runs.some(ref => ref.record_id === item.id)));
assert.equal(batch.execution_authorized, false);
assert.doesNotMatch(values.batch, /weekly_result|equity_close|synthetic\.csv/);
const analytics = await parseAnalyticsReport(JSON.stringify(values.report));
assert.equal(analytics.kind, 'weekly');
assert.equal(analytics.value.results.length, 2);
assert.equal(analytics.value.report_hash, values.receipt.report_hash);
assert.equal(analytics.value.status, 'OFFLINE_UNQUALIFIED');
console.log(JSON.stringify({
  status: 'PASS', scope: 'offline_synthetic_contracts_only',
  recordedRuns: runs.length, syncMetadataAccepted: true,
  analyticsReportAccepted: true, networkRequests: 0, productionWrites: 0,
}));
