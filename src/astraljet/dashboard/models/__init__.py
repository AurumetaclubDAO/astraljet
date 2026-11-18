from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict
from ..security import redact


def utcnow():
    return datetime.now(timezone.utc)


def parse_time(value):
    if isinstance(value, datetime):
        date = value
    else:
        date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('Czas bez strefy')
    return date.astimezone(timezone.utc)


class DataState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: Any = None
    state: Literal['CONFIRMED', 'UNCONFIRMED', 'MISSING']
    source: str
    as_of: str | None = None
    observed_at: str
    age_s: float | None = None
    error: str | None = None
    ttl_s: int = 90
    unit: str | None = None


def datum(value, source, as_of=None, ttl=90, error=None, uncertain=False, now=None, unit=None):
    now = now or utcnow()
    age = None
    stamp = None
    if as_of is not None:
        try:
            stamp = parse_time(as_of)
            age = round((now - stamp).total_seconds(), 1)
        except (ValueError, TypeError, OverflowError):
            uncertain = True
            error = error or 'Nieprawidłowy czas źródła'
    if value is None:
        state = 'MISSING'
    elif uncertain or age is None or age > ttl or age < -5:
        state = 'UNCONFIRMED'
        error = error or ('Dane poza progiem świeżości' if age is not None else 'Brak czasu pomiaru')
    else:
        state = 'CONFIRMED'
    return DataState(value=redact(value), state=state, source=source, as_of=stamp.isoformat() if stamp else None,
                     observed_at=now.isoformat(), age_s=age, error=redact(error), ttl_s=ttl, unit=unit).model_dump()


def missing(source, message='Brak danych'):
    return datum(None, source, error=message)


def age_tree(value, now=None):
    """Każda odpowiedź przelicza wiek; cache nigdy nie utrwala zielonego badge."""
    now = now or utcnow()
    if isinstance(value, list):
        return [age_tree(x, now) for x in value]
    if not isinstance(value, dict):
        return value
    result = {k: age_tree(v, now) for k, v in value.items()}
    if {'state', 'source', 'ttl_s', 'as_of'}.issubset(result) and result['as_of']:
        result['age_s'] = round((now - parse_time(result['as_of'])).total_seconds(), 1)
        if result['state'] == 'CONFIRMED' and not -5 <= result['age_s'] <= result['ttl_s']:
            result['state'] = 'UNCONFIRMED'
            result['error'] = 'Dane poza progiem świeżości'
    return result
