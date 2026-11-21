import math
import re
from pathlib import Path

_KEY = re.compile(r'(?i)(password|passwd|hasło|haslo|secret|api[_-]?key|authorization|bearer|token)')
_ASSIGN = re.compile(r'(?i)\b(password|passwd|hasło|haslo|secret|api[_-]?key|authorization|token)\b\s*[=:]\s*(?:"[^"]*"|\x27[^\x27]*\x27|[^\s,;]+)')
_TOKEN = re.compile(r'(?i)\b(?:sk-[A-Za-z0-9_-]{8,}|(?:PK|AK)[A-Za-z0-9]{12,}|Bearer\s+[^\s,;]+)')
_LONG = re.compile(r'(?<![\w])(?:[a-fA-F0-9]{32,}|[A-Za-z0-9+/=_-]{40,})(?![\w])')
_CREDENTIAL_URL = re.compile(r'(?i)(https?://)[^/\s@]+@')


def redact(value):
    if isinstance(value, dict):
        return {str(k): '[UKRYTO]' if _KEY.search(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        text = _ASSIGN.sub(lambda m: m.group(1) + '=[UKRYTO]', value)
        text = _TOKEN.sub('[UKRYTO]', text)
        text = _CREDENTIAL_URL.sub(r'\1[UKRYTO]@', text)
        return _LONG.sub('[UKRYTO]', text)[:1000]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def data_path(path: Path) -> Path:
    """Odrzuć sekrety również po rozwiązaniu symlinków; tylko formaty danych."""
    p = path.resolve()
    if any(part.lower().startswith('.env') or part.lower() in {'secrets', 'klucze.txt'} for part in p.parts):
        raise ValueError('Niedozwolone źródło')
    if p.suffix.lower() not in {'.json', '.csv', '.log'}:
        raise ValueError('Niedozwolony format danych')
    return p
