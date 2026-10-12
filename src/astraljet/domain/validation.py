from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from .errors import ValidationError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_utc(value: str) -> None:
    if not value.endswith("Z") and not value.endswith("+00:00"):
        raise ValidationError("Czas musi zawierać jawną strefę UTC.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("Niepoprawny czas ISO-8601.") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValidationError("Czas musi być zapisany w UTC.")


def new_record_id(prefix: str) -> str:
    if not prefix or any(char.isspace() for char in prefix):
        raise ValidationError("Prefiks identyfikatora jest niepoprawny.")
    return f"{prefix}-{uuid4().hex}"


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Nieobsługiwany typ kanoniczny: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def validate_sha256(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789ABCDEFabcdef" for char in value):
        raise ValidationError("SHA-256 musi mieć 64 znaki szesnastkowe.")
