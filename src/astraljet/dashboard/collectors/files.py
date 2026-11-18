import csv
import io
import json
import math
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from ..models import datum, missing, parse_time, utcnow
from ..security import data_path

MAX_BYTES = 8 * 1024 * 1024


def read_text(path, limit=MAX_BYTES):
    p = data_path(Path(path))
    for _ in range(2):
        before = p.stat()
        if before.st_size > limit:
            raise ValueError('Przekroczony limit źródła')
        with p.open('rb') as stream:
            raw = stream.read(limit + 1)
        after = p.stat()
        if len(raw) > limit:
            raise ValueError('Przekroczony limit źródła')
        if (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns):
            return raw.decode('utf-8-sig')
    raise ValueError('Źródło zmienia się podczas odczytu')


def read_json(path):
    return json.loads(read_text(path))


def rows(path):
    return list(csv.DictReader(io.StringIO(read_text(path))))


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Nieprawidłowa liczba')
    return result


def signal(folder, ttl, shadow=False):
    path = folder / ('journal_vb.csv' if shadow else 'signals.csv')
    try:
        data = rows(path)
        key = 'run_at_utc' if shadow else 'eval_time'
        if not data:
            return missing(str(path), 'Brak ewaluacji')
        latest = max(data, key=lambda x: parse_time(x[key]))
        fields = ('decision', 'market', 'blocked_by') if shadow else ('symbol', 'signal', 'action', 'reason')
        value = {k: latest.get(k) for k in fields}
        if not shadow:
            batch = [r for r in data if r.get(key) == latest[key]][-12:]
            value['last_batch'] = [{k: r.get(k) for k in ('symbol', 'signal', 'action')} for r in batch]
        return datum(value, str(path), latest[key], ttl)
    except (OSError, ValueError, KeyError, csv.Error, TypeError):
        return missing(str(path), 'Brak poprawnego sygnału lub czasu ze strefą')


def runner_state(folder, ttl):
    path = folder / 'state.json'
    try:
        raw = read_json(path)
        if not isinstance(raw, dict) or not raw:
            return missing(str(path), 'Pusty stan nie potwierdza braku pozycji')
        value = {'keys_count': len(raw)}
        if 'kill_stats' in raw or 'paused' in raw:
            ks = raw.get('kill_stats') if isinstance(raw.get('kill_stats'), dict) else {}
            value.update(paused=bool(raw.get('paused')), paused_reason=raw.get('paused_reason'), paused_at=raw.get('paused_at'),
                         kill_stats={k: ks.get(k) for k in ('trades', 'dd_usd', 'loss_streak', 'pf')},
                         status='PAUSED DEMO' if raw.get('paused') else 'RUNNING DEMO')
        return datum(value, str(path), utcnow(), ttl, uncertain=True,
                     error='Stan runnera bez zatwierdzonego schematu; nie używany do PnL')
    except (OSError, ValueError, TypeError):
        return missing(str(path))


def log_errors(path, now=None):
    now = now or utcnow()
    try:
        p = data_path(path)
        size = p.stat().st_size
        with p.open('rb') as stream:
            stream.seek(max(0, size - 256 * 1024))
            lines = stream.read(256 * 1024).decode('utf-8-sig', errors='replace').splitlines()
        truncated = size > 256 * 1024 or len(lines) > 2000
        lines = lines[-2000:]
        count, undated = 0, False
        for line in lines:
            if not re.search(r'\bERROR\b|Traceback', line):
                continue
            match = re.search(r'\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:[.,]\d+)?(?:Z|[+-]\d\d:\d\d)?', line)
            if not match:
                undated = True
                continue
            stamp = datetime.fromisoformat(match.group().replace(',', '.').replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=ZoneInfo('Europe/Warsaw'))
            if now - timedelta(hours=24) <= stamp <= now + timedelta(seconds=5):
                count += 1
        return datum({'count': count, 'partial': truncated or undated, 'lines_scanned': len(lines)},
                     str(path), now, 90, uncertain=truncated or undated,
                     error='Co najmniej wskazana liczba; niepełne datowanie lub fragment logu' if truncated or undated else None)
    except (OSError, ValueError):
        return missing(str(path), 'Nie można odczytać licznika błędów')
