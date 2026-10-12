"""Publish a new bounded JSON artifact without overwriting any existing path."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from astraljet.domain.errors import TechnicalError, ValidationError

MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024


def publish_snapshot(value: dict[str, Any], output: str | Path, *, max_bytes: int = MAX_SNAPSHOT_BYTES) -> dict[str, Any]:
    if type(max_bytes) is not int or not 1 <= max_bytes <= 64 * 1024 * 1024:
        raise ValidationError('Niepoprawny limit eksportu JSON (maks. 64 MiB).')
    content = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    if len(content) > max_bytes:
        raise ValidationError('Snapshot przekracza limit eksportu.', blocker='snapshot_too_large')
    path = Path(output).expanduser().absolute()
    if path.suffix.lower() != '.json':
        raise ValidationError('Snapshot wymaga rozszerzenia .json.')
    if os.path.lexists(path):
        raise ValidationError('Plik już istnieje. Wybierz nową nazwę.', blocker='snapshot_exists')
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.lineage-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Link publishes the complete file atomically and fails if the target
        # was created concurrently. No replace/rename fallback is safe here.
        os.link(temporary, path)
    except FileExistsError as exc:
        raise ValidationError('Plik już istnieje. Wybierz nową nazwę.', blocker='snapshot_exists') from exc
    except OSError as exc:
        raise TechnicalError('Nie udało się bezpiecznie opublikować snapshotu.') from exc
    finally:
        os.unlink(temporary)
    return {'status': 'exported', 'output': str(path), 'bytes': len(content),
            'sha256': hashlib.sha256(content).hexdigest(), 'execution_authorized': False}
