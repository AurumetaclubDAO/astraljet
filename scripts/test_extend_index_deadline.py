from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from extend_index_deadline import extend, release_guard


class DeadlineTest(unittest.TestCase):
    def test_extension_and_guards(self):
        for field, value in [(None, None), ('mode', 'LIVE'), ('id', 'other'),
                             ('status', 'STOPPED'), ('scope', 'ALL'), ('endsAt', 'old')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                path, backup = Path(folder)/'round.sqlite3', Path(folder)/'backup.sqlite3'
                old = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
                new = (datetime.now(timezone.utc)+timedelta(days=3)).isoformat()
                round_id='00000000-0000-4000-8000-000000000001'
                row = dict(id=round_id, mode='DEMO', status='RUNNING', scope='ALL_INDICES',
                           endsAt=old, rules={'entryRiskPercent': 1.5}, books={'balance': 1500})
                if field:
                    row[field] = value
                with closing(sqlite3.connect(path)) as db, db:
                    db.executescript('CREATE TABLE state(key TEXT PRIMARY KEY,payload TEXT);'
                                     'CREATE TABLE journal(time TEXT,round_id TEXT,kind TEXT,payload TEXT);')
                    db.execute('INSERT INTO state VALUES (?,?)', ('round', json.dumps(row)))
                if field:
                    with self.assertRaises(ValueError):
                        extend(path, round_id, old, new, backup)
                else:
                    result = extend(path, round_id, old, new, backup)
                    self.assertEqual(result['changedFields'], ['endsAt'])
                with closing(sqlite3.connect(path)) as db:
                    saved = json.loads(db.execute('SELECT payload FROM state').fetchone()[0])
                    self.assertEqual(saved, row if field else dict(row, endsAt=new))
                    self.assertEqual(db.execute('SELECT count(*) FROM journal').fetchone()[0], 0 if field else 1)
                with closing(sqlite3.connect(backup)) as db:
                    self.assertEqual(json.loads(db.execute('SELECT payload FROM state').fetchone()[0]), row)
                if not field:
                    with closing(sqlite3.connect(path)) as db, db:
                        stale=dict(row, observedAt='2026-09-27T23:59:00Z', message='new cycle data')
                        db.execute('INSERT OR REPLACE INTO state VALUES (?,?)', ('round', json.dumps(stale)))
                        expected=dict(stale, endsAt=new)
                        self.assertEqual(json.loads(db.execute('SELECT payload FROM state').fetchone()[0]), expected)
                    release_guard(path, round_id, new, '2026-09-27T23:58:00Z')
                    with closing(sqlite3.connect(path)) as db:
                        self.assertEqual(db.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
