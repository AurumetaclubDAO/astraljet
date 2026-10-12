from __future__ import annotations

import csv
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from astraljet.domain.errors import TechnicalError, ValidationError
from astraljet.domain.validation import canonical_json, sha256_file, sha256_text, utc_now, validate_utc


DEFAULT_DATA_BASE_URL = "https://data.alpaca.markets/v1beta3"
CSV_COLUMNS = (
    "timestamp",
    "instrument",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "trade_count",
    "vwap",
)


@dataclass(frozen=True, slots=True)
class AlpacaCredentials:
    key_id: str = field(repr=False)
    secret_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.key_id.strip() or not self.secret_key.strip():
            raise ValidationError("Klucze Alpaca nie mogą być puste.")


@dataclass(frozen=True, slots=True)
class CryptoBarsRequest:
    symbols: tuple[str, ...]
    start: str
    end: str
    timeframe: str = "1Day"
    location: str = "us"
    limit: int = 10_000

    def __post_init__(self) -> None:
        if not self.symbols:
            raise ValidationError("Zapytanie Alpaca wymaga co najmniej jednego symbolu.")
        normalized = tuple(symbol.strip().upper() for symbol in self.symbols)
        if len(normalized) != len(set(normalized)):
            raise ValidationError("Symbole Alpaca nie mogą się powtarzać.")
        if any("/" not in symbol for symbol in normalized):
            raise ValidationError("Symbole Alpaca muszą mieć format BASE/QUOTE, np. BTC/USD.")
        if self.timeframe != "1Day":
            raise ValidationError("Pierwsza wersja AstralJet obsługuje z Alpaca tylko timeframe 1Day.")
        if self.location not in {"us", "us-1", "eu-1"}:
            raise ValidationError("Nieobsługiwana lokalizacja danych Alpaca.")
        if not 1 <= self.limit <= 10_000:
            raise ValidationError("Limit Alpaca musi mieścić się w zakresie 1-10000.")
        validate_utc(self.start)
        validate_utc(self.end)
        start = datetime.fromisoformat(self.start.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.end.replace("Z", "+00:00"))
        if start >= end:
            raise ValidationError("Początek zakresu DATA musi być wcześniejszy niż koniec.")
        object.__setattr__(self, "symbols", normalized)


@dataclass(frozen=True, slots=True)
class HttpJsonResponse:
    status: int
    payload: Mapping[str, Any]
    headers: Mapping[str, str]


class JsonTransport(Protocol):
    def get_json(self, url: str, headers: dict[str, str]) -> HttpJsonResponse: ...


class UrllibJsonTransport:
    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def get_json(self, url: str, headers: dict[str, str]) -> HttpJsonResponse:
        request = Request(url, headers=headers, method="GET")
        try:
            with build_opener(_NoRedirectHandler()).open(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                status = int(response.status)
                raw = response.read()
                response_headers = {key.lower(): value for key, value in response.headers.items()}
        except HTTPError as exc:
            raise TechnicalError(
                f"Alpaca Market Data zwróciła HTTP {exc.code}.",
                blocker="alpaca_http_error",
                owner="AJ-06 Dane i jakość danych",
                allowed_next_action="Sprawdź konfigurację PAPER, zakres dat i limity API.",
            ) from exc
        except URLError as exc:
            raise TechnicalError(
                "Nie udało się połączyć z Alpaca Market Data.",
                blocker="alpaca_connection_error",
                owner="AJ-06 Dane i jakość danych",
                allowed_next_action="Sprawdź połączenie sieciowe i ponów odczyt.",
            ) from exc
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TechnicalError("Alpaca zwróciła niepoprawny JSON.") from exc
        if not isinstance(payload, dict):
            raise TechnicalError("Odpowiedź Alpaca nie jest obiektem JSON.")
        return HttpJsonResponse(status=status, payload=payload, headers=response_headers)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


@dataclass(frozen=True, slots=True)
class NormalizedBar:
    timestamp: str
    source_symbol: str
    instrument: str
    open: str
    high: str
    low: str
    close: str
    volume: str
    trade_count: str
    vwap: str

    def csv_row(self) -> dict[str, str]:
        return {
            "timestamp": self.timestamp,
            "instrument": self.instrument,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "trade_count": self.trade_count,
            "vwap": self.vwap,
        }


@dataclass(frozen=True, slots=True)
class AlpacaSnapshotResult:
    csv_path: Path
    metadata_path: Path
    csv_sha256: str
    raw_payload_sha256: str
    row_count: int
    page_count: int
    start: str
    end: str
    retrieved_at: str


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ValidationError(f"Plik konfiguracji Alpaca nie istnieje: {path}")
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ValidationError("Nie można odczytać pliku konfiguracji Alpaca.") from exc
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValidationError(f"Niepoprawny wpis .env w wierszu {line_number}.")
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[name] = value
    return values


def load_alpaca_credentials(path_value: str | Path) -> tuple[AlpacaCredentials, str]:
    path = Path(path_value).expanduser().resolve()
    values = _read_env_file(path)
    missing = [
        name
        for name in ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY")
        if not values.get(name, "").strip()
    ]
    if missing:
        raise ValidationError(f"Brak wymaganych zmiennych Alpaca: {', '.join(missing)}.")
    base_url = values.get("ALPACA_DATA_BASE_URL", DEFAULT_DATA_BASE_URL).strip().rstrip("/")
    if not base_url.startswith("https://"):
        raise ValidationError("ALPACA_DATA_BASE_URL musi używać HTTPS.")
    parsed_base_url = urlsplit(base_url)
    if parsed_base_url.path in {"", "/"}:
        base_url = urlunsplit(
            (parsed_base_url.scheme, parsed_base_url.netloc, "/v1beta3", "", "")
        )
    _validate_data_base_url(base_url)
    return (
        AlpacaCredentials(
            key_id=values["ALPACA_API_KEY_ID"],
            secret_key=values["ALPACA_API_SECRET_KEY"],
        ),
        base_url,
    )


def _validate_data_base_url(base_url: str) -> None:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "data.alpaca.markets"
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") != "/v1beta3"
    ):
        raise ValidationError(
            "ALPACA_DATA_BASE_URL musi wskazywać https://data.alpaca.markets/v1beta3."
        )


def _decimal_text(value: Any, *, field_name: str, allow_zero: bool = False) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise TechnicalError(f"Alpaca zwróciła niepoprawne pole {field_name}.") from exc
    if not number.is_finite() or number < 0 or (number == 0 and not allow_zero):
        raise TechnicalError(f"Alpaca zwróciła niedozwoloną wartość pola {field_name}.")
    return format(number, "f")


def _canonical_timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise TechnicalError("Alpaca zwróciła świecę bez czasu UTC.")
    try:
        validate_utc(value)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValidationError as exc:
        raise TechnicalError("Alpaca zwróciła niepoprawny czas świecy.") from exc
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_bar(source_symbol: str, value: Any) -> NormalizedBar:
    if not isinstance(value, dict):
        raise TechnicalError("Alpaca zwróciła niepoprawny rekord świecy.")
    try:
        timestamp = _canonical_timestamp(value["t"])
        open_price = _decimal_text(value["o"], field_name="open")
        high = _decimal_text(value["h"], field_name="high")
        low = _decimal_text(value["l"], field_name="low")
        close = _decimal_text(value["c"], field_name="close")
        volume = _decimal_text(value["v"], field_name="volume", allow_zero=True) if "v" in value else ""
        trade_count = _decimal_text(value["n"], field_name="trade_count", allow_zero=True) if "n" in value else ""
        vwap = _decimal_text(value["vw"], field_name="vwap") if "vw" in value else ""
    except KeyError as exc:
        raise TechnicalError(f"Alpaca zwróciła świecę bez pola {exc.args[0]}.") from exc
    prices = tuple(Decimal(item) for item in (open_price, high, low, close))
    if Decimal(low) > min(Decimal(open_price), Decimal(close)):
        raise TechnicalError("Alpaca zwróciła low wyższe od open/close.")
    if Decimal(high) < max(Decimal(open_price), Decimal(close)):
        raise TechnicalError("Alpaca zwróciła high niższe od open/close.")
    if Decimal(high) < max(prices) or Decimal(low) > min(prices):
        raise TechnicalError("Alpaca zwróciła niespójny zakres OHLC.")
    return NormalizedBar(
        timestamp=timestamp,
        source_symbol=source_symbol,
        instrument=source_symbol.replace("/", ""),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        trade_count=trade_count,
        vwap=vwap,
    )


def _publish_new_file(temporary_name: str, path: Path) -> None:
    """Publish a complete file without replacing a concurrently created version.

    The temporary file is on the same filesystem. If hard links are unsupported,
    fail rather than fall back to a non-atomic check-then-overwrite.
    """
    try:
        os.link(temporary_name, path)
    except FileExistsError as exc:
        raise ValidationError(
            "Snapshot już istnieje; zapisz nową wersję pod nową nazwą.",
            blocker="snapshot_exists",
        ) from exc
    except OSError as exc:
        raise TechnicalError(
            "Nie udało się opublikować snapshotu bez nadpisania. Wymagany system plików obsługujący hard link.",
            blocker="snapshot_publication_failed",
        ) from exc
    os.unlink(temporary_name)


def _atomic_write_csv(path: Path, bars: list[NormalizedBar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(bar.csv_row() for bar in bars)
            stream.flush()
            os.fsync(stream.fileno())
        _publish_new_file(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _publish_new_file(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


class AlpacaCryptoDataClient:
    def __init__(
        self,
        credentials: AlpacaCredentials,
        *,
        base_url: str = DEFAULT_DATA_BASE_URL,
        transport: JsonTransport | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.credentials = credentials
        self.base_url = base_url.rstrip("/")
        _validate_data_base_url(self.base_url)
        self.transport = transport or UrllibJsonTransport()
        self.clock = clock

    def fetch_to_csv(
        self,
        request: CryptoBarsRequest,
        output_path: str | Path,
    ) -> AlpacaSnapshotResult:
        output = Path(output_path).expanduser().resolve()
        if output.suffix.lower() != ".csv":
            raise ValidationError("Snapshot Alpaca musi mieć rozszerzenie .csv.")
        metadata_path = output.with_suffix(output.suffix + ".metadata.json")
        if os.path.lexists(output) or os.path.lexists(metadata_path):
            raise ValidationError(
                "Snapshot lub jego metadane już istnieje; podaj nową nazwę --output.",
                blocker="snapshot_exists",
                allowed_next_action="Zachowaj wcześniejsze pliki i wybierz nazwę nowej wersji.",
            )
        headers = {
            "Accept": "application/json",
            "APCA-API-KEY-ID": self.credentials.key_id,
            "APCA-API-SECRET-KEY": self.credentials.secret_key,
        }
        pages: list[Mapping[str, Any]] = []
        request_ids: list[str] = []
        bars: list[NormalizedBar] = []
        seen_bars: set[tuple[str, str]] = set()
        page_token: str | None = None
        seen_tokens: set[str] = set()

        for _page_number in range(1, 1001):
            query: dict[str, str | int] = {
                "symbols": ",".join(request.symbols),
                "timeframe": request.timeframe,
                "start": request.start,
                "end": request.end,
                "limit": request.limit,
                "sort": "asc",
            }
            if page_token:
                query["page_token"] = page_token
            url = f"{self.base_url}/crypto/{request.location}/bars?{urlencode(query)}"
            response = self.transport.get_json(url, headers)
            if response.status != 200:
                raise TechnicalError(f"Alpaca Market Data zwróciła HTTP {response.status}.")
            payload = response.payload
            pages.append(payload)
            request_id = response.headers.get("x-request-id") or response.headers.get("apca-request-id")
            if request_id:
                request_ids.append(request_id)
            payload_bars = payload.get("bars")
            if not isinstance(payload_bars, dict):
                raise TechnicalError("Odpowiedź Alpaca nie zawiera obiektu bars.")
            for source_symbol, raw_bars in payload_bars.items():
                if source_symbol not in request.symbols:
                    raise TechnicalError(f"Alpaca zwróciła nieoczekiwany symbol {source_symbol}.")
                if not isinstance(raw_bars, list):
                    raise TechnicalError(f"Alpaca zwróciła niepoprawną listę świec {source_symbol}.")
                for raw_bar in raw_bars:
                    bar = _normalize_bar(source_symbol, raw_bar)
                    identity = (bar.source_symbol, bar.timestamp)
                    if identity in seen_bars:
                        raise TechnicalError(
                            f"Alpaca zwróciła duplikat świecy {bar.source_symbol} {bar.timestamp}."
                        )
                    seen_bars.add(identity)
                    bars.append(bar)
            token_value = payload.get("next_page_token")
            if token_value in (None, ""):
                break
            if not isinstance(token_value, str):
                raise TechnicalError("Alpaca zwróciła niepoprawny next_page_token.")
            if token_value in seen_tokens:
                raise TechnicalError("Alpaca powtórzyła next_page_token; przerwano pętlę.")
            seen_tokens.add(token_value)
            page_token = token_value
        else:
            raise TechnicalError("Przekroczono bezpieczny limit 1000 stron Alpaca.")

        present_symbols = {bar.source_symbol for bar in bars}
        missing_symbols = [symbol for symbol in request.symbols if symbol not in present_symbols]
        if missing_symbols:
            raise TechnicalError(f"Alpaca nie zwróciła danych dla: {', '.join(missing_symbols)}.")
        bars.sort(key=lambda bar: (bar.timestamp, bar.instrument))
        retrieved_at = self.clock()
        validate_utc(retrieved_at)
        retrieved_time = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        if request.timeframe == "1Day":
            unclosed = [
                bar
                for bar in bars
                if datetime.fromisoformat(bar.timestamp.replace("Z", "+00:00"))
                + timedelta(days=1)
                > retrieved_time
            ]
            if unclosed:
                raise TechnicalError(
                    "Alpaca zwróciła potencjalnie niezamkniętą świecę dzienną; snapshot odrzucono.",
                    blocker="unclosed_market_bar",
                    owner="AJ-06 Dane i jakość danych",
                    allowed_next_action="Ustaw --end przed początkiem bieżącego dnia UTC i pobierz ponownie.",
                )
        _atomic_write_csv(output, bars)
        csv_hash = sha256_file(output)
        raw_hash = sha256_text(canonical_json(pages))
        metadata = {
            "schema_version": "astraljet-alpaca-crypto-bars-v2",
            "provider": "Alpaca Market Data",
            "venue": "Alpaca US" if request.location == "us" else request.location,
            "source_endpoint": f"{self.base_url}/crypto/{request.location}/bars",
            "request": {
                "symbols": list(request.symbols),
                "normalized_instruments": [symbol.replace("/", "") for symbol in request.symbols],
                "timeframe": request.timeframe,
                "start": request.start,
                "end": request.end,
                "limit": request.limit,
                "sort": "asc",
            },
            "retrieved_at": retrieved_at,
            "request_ids": request_ids,
            "page_count": len(pages),
            "row_count": len(bars),
            "observed_start": bars[0].timestamp,
            "observed_end": bars[-1].timestamp,
            "csv_path": str(output),
            "csv_sha256": csv_hash,
            "raw_payload_sha256": raw_hash,
            "missing_optional_fields": {
                field: sum(getattr(bar, field) == "" for bar in bars)
                for field in ("volume", "trade_count", "vwap")
            },
            "transformations": [
                "symbole BASE/QUOTE zapisano jako BASEQUOTE",
                "wartości liczbowe zapisano dziesiętnie bez notacji wykładniczej",
                "wiersze posortowano po timestamp i instrument",
                "brak volume/trade_count/vwap pozostaje pustym polem, nie zerem ani ceną close",
            ],
            "limitations": [
                "Snapshot służy wyłącznie do lokalnych badań AstralJet.",
                "Prawo do redystrybucji danych nie zostało potwierdzone.",
                "Alpaca może tworzyć świece z midpointu kwotowań przy braku transakcji; taka świeca może mieć volume=0.",
                "Dane OHLCV nie definiują fee, spreadu ani slippage dla backtestu.",
            ],
        }
        _atomic_write_json(metadata_path, metadata)
        return AlpacaSnapshotResult(
            csv_path=output,
            metadata_path=metadata_path,
            csv_sha256=csv_hash,
            raw_payload_sha256=raw_hash,
            row_count=len(bars),
            page_count=len(pages),
            start=bars[0].timestamp,
            end=bars[-1].timestamp,
            retrieved_at=retrieved_at,
        )
