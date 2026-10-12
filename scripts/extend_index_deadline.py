"""Narrow, audited maintenance of an existing DEMO index-round deadline.

No MT5 imports, orders, process control, code changes or round resets. The
operator must verify the new deadline through fresh executor cycles afterwards.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid


def guard_names(round_id):
    return ['astraljet_deadline_'+uuid.UUID(round_id).hex+'_'+kind for kind in ('insert', 'update')]


def release_guard(path, round_id, expected_end, observed_after):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=rw', uri=True, timeout=20)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        r = json.loads(db.execute("SELECT payload FROM state WHERE key='round'").fetchone()[0])
        if r['id'] != round_id or r['endsAt'] != expected_end or r.get('observedAt', '') <= observed_after:
            raise ValueError('No fresh executor confirmation; guard retained.')
        for name in guard_names(round_id):
            db.execute('DROP TRIGGER IF EXISTS '+name)
    return dict(roundId=round_id, endsAt=expected_end, guardReleased=True, observedAt=r['observedAt'])


def extend(path, round_id, expected_end, new_end, backup):
    names = guard_names(round_id)
    path, backup = Path(path).resolve(), Path(backup).resolve()
    if not path.is_file() or backup.exists() or path == backup:
        raise ValueError('Existing database and unused backup path required.')
    parse = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    if parse(new_end).tzinfo is None or parse(expected_end).tzinfo is None:
        raise ValueError('Explicit timezone required.')
    if not now < parse(expected_end) < parse(new_end):
        raise ValueError('Only extension of a still-active deadline is permitted.')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as source:
        backup.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(backup)) as target:
            source.backup(target)
    with closing(sqlite3.connect(path.as_uri()+'?mode=rw', uri=True, timeout=20)) as db, db:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        stored = db.execute("SELECT payload FROM state WHERE key='round'").fetchone()
        if not stored:
            raise ValueError('No existing round.')
        before = json.loads(stored[0])
        if (before.get('id') != round_id or before.get('mode') != 'DEMO'
                or before.get('status') != 'RUNNING' or before.get('scope') != 'ALL_INDICES'
                or before.get('endsAt') != expected_end):
            raise ValueError('Round identity, mode, state or expected deadline changed.')
        after = dict(before, endsAt=new_end)
        changed = [key for key in before if before[key] != after[key]]
        if changed != ['endsAt']:
            raise ValueError('Unexpected field change.')
        # The running engine stores its whole snapshot with INSERT OR REPLACE.
        # Guard only this exact stale deadline until fresh cycles acknowledge it.
        quote = lambda text: "'"+text.replace("'", "''")+"'"
        for name, action in zip(names, ('INSERT', 'UPDATE')):
            db.execute('CREATE TRIGGER '+name+' AFTER '+action+''' ON state
                WHEN NEW.key='round'
                 AND json_extract(NEW.payload,'$.id')='''+quote(round_id)+'''
                 AND json_extract(NEW.payload,'$.mode')='DEMO'
                 AND json_extract(NEW.payload,'$.endsAt')='''+quote(expected_end)+'''
                BEGIN UPDATE state SET payload=json_set(payload,'$.endsAt','''+quote(new_end)+''')
                 WHERE key='round'; END''')
        db.execute("UPDATE state SET payload=? WHERE key='round' AND payload=?",
                   (json.dumps(after, ensure_ascii=False, allow_nan=False), stored[0]))
        event = dict(previousEndsAt=expected_end, endsAt=new_end,
                     localDeadline='2026-10-02 23:00:00 Europe/Warsaw',
                     decisionNote='Karol: wydłużenie turnusu indeksowego do 02.10 godz. 23 Warszawa',
                     changes=['endsAt'], riskAndBooksUnchanged=True)
        db.execute('INSERT INTO journal(time,round_id,kind,payload) VALUES (?,?,?,?)',
                   (now.isoformat(), round_id, 'INDEX_DEADLINE_EXTENDED',
                    json.dumps(event, ensure_ascii=False, allow_nan=False)))
        saved = json.loads(db.execute("SELECT payload FROM state WHERE key='round'").fetchone()[0])
        if saved != after:
            raise ValueError('Write verification failed.')
    return dict(roundId=round_id, previousEndsAt=expected_end, endsAt=new_end,
                changedFields=changed, backup=str(backup), staleWriteGuard=names,
                committedAt=datetime.now(timezone.utc).isoformat())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for arg in ['db', 'round-id', 'expected-end', 'new-end', 'backup']:
        parser.add_argument('--'+arg, required=True)
    args = parser.parse_args()
    print(json.dumps(extend(args.db, args.round_id, args.expected_end, args.new_end, args.backup), ensure_ascii=False))
