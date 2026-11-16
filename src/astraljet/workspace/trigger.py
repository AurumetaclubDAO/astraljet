"""Trend Trigger: jednorazowe wejście po przecięciu linii poziomej lub trendu.

Definicje (zapisane, żeby reguła była jednoznaczna):
- cena oceny: jawnie Bid albo Ask (`price_source`),
- strona: BELOW / ON / ABOVE względem ceny linii w chwili obserwacji,
- przecięcie w górę (UP): poprzednia obserwacja ściśle PONIŻEJ, bieżąca NA linii lub powyżej;
  przecięcie w dół (DOWN): poprzednia ściśle POWYŻEJ, bieżąca NA linii lub poniżej,
- uzbrojenie zapamiętuje stronę; jeśli cena już jest po stronie warunku (UP: ON/ABOVE),
  reguła przechodzi do WAITING_RESET i wyzwoli się dopiero po powrocie na stronę wyjściową
  i nowym przecięciu — nie wyzwala się natychmiast,
- pierwsza obserwacja po restarcie lub po przesunięciu linii tylko ustala stronę,
- nieświeże kwotowanie nie jest oceniane (stan i strona bez zmian),
- linia trendu poza swoim odcinkiem jest nieaktywna, chyba że `extend_right`,
- po wyzwoleniu reguła jest zakończona (jednorazowa): request_id jest deterministyczny,
  więc ponowna ocena nie może utworzyć drugiego żądania,
- przesunięcie linii po wyzwoleniu jest odrzucane; usunięcie linii anuluje regułę,
  ale nie cofa już wysłanego żądania,
- po `expires_at` reguła wygasa bez wyzwolenia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from .instruments import D, InstrumentSpec, Side
from .market import utc


class Cross(StrEnum):
    UP = "UP"
    DOWN = "DOWN"


class PriceSource(StrEnum):
    BID = "BID"
    ASK = "ASK"


class TriggerState(StrEnum):
    DRAFT = "DRAFT"                  # niekompletna konfiguracja; nie można uzbroić
    ARMED = "ARMED"
    WAITING_RESET = "WAITING_RESET"  # cena już po stronie warunku; czeka na powrót
    PAUSED = "PAUSED"
    FIRED = "FIRED"                  # żądanie utworzone; wynik w dzienniku żądań
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

    @property
    def finished(self) -> bool:
        return self in {TriggerState.FIRED, TriggerState.CANCELLED, TriggerState.EXPIRED}


@dataclass(frozen=True, slots=True)
class Line:
    """Pozioma: p1 bez t1/t2. Trendu: dwa punkty (t1, p1), (t2, p2)."""

    p1: Decimal
    t1: datetime | None = None
    p2: Decimal | None = None
    t2: datetime | None = None
    extend_right: bool = True

    @property
    def horizontal(self) -> bool:
        return self.t1 is None

    def __post_init__(self) -> None:
        if not self.horizontal:
            if self.t2 is None or self.p2 is None:
                raise ValueError("Linia trendu wymaga dwóch punktów")
            if utc(self.t2) <= utc(self.t1):
                raise ValueError("Drugi punkt linii musi być późniejszy")

    def price_at(self, at: datetime) -> Decimal | None:
        if self.horizontal:
            return D(self.p1)
        at, t1, t2 = utc(at), utc(self.t1), utc(self.t2)
        if at < t1 or (at > t2 and not self.extend_right):
            return None
        slope = (D(self.p2) - D(self.p1)) / Decimal(str((t2 - t1).total_seconds()))
        return D(self.p1) + slope * Decimal(str((at - t1).total_seconds()))

    def describe(self, spec: InstrumentSpec) -> str:
        if self.horizontal:
            return f"pozioma {spec.normalize_price(self.p1)}"
        return (f"trendu {spec.normalize_price(self.p1)} ({utc(self.t1):%Y-%m-%d %H:%M}) → "
                f"{spec.normalize_price(self.p2)} ({utc(self.t2):%Y-%m-%d %H:%M}){', przedłużona' if self.extend_right else ''}")

    def to_dict(self) -> dict:
        return {"p1": str(self.p1), "t1": None if self.t1 is None else utc(self.t1).isoformat(),
                "p2": None if self.p2 is None else str(self.p2),
                "t2": None if self.t2 is None else utc(self.t2).isoformat(), "extend_right": self.extend_right}

    @classmethod
    def from_dict(cls, d: dict) -> "Line":
        return cls(Decimal(d["p1"]), None if d.get("t1") is None else datetime.fromisoformat(d["t1"]),
                   None if d.get("p2") is None else Decimal(d["p2"]),
                   None if d.get("t2") is None else datetime.fromisoformat(d["t2"]), d.get("extend_right", True))


def side_of(price: Decimal, line_price: Decimal) -> int:
    diff = D(price) - D(line_price)
    return 0 if diff == 0 else (1 if diff > 0 else -1)


@dataclass(frozen=True, slots=True)
class FireOrder:
    request_id: str
    trigger_id: str
    symbol: str
    side: Side
    volume: Decimal
    sl_points: Decimal | None
    tp_points: Decimal | None
    observed_price: Decimal
    line_price: Decimal


@dataclass(slots=True)
class TrendTrigger:
    trigger_id: str
    symbol: str
    line: Line | None
    cross: Cross | None
    side: Side | None
    volume: Decimal | None
    price_source: PriceSource = PriceSource.BID
    sl_points: Decimal | None = None
    tp_points: Decimal | None = None
    expires_at: datetime | None = None
    state: TriggerState = TriggerState.DRAFT
    revision: int = 0
    last_side: int | None = None
    reason: str = ""
    fired_request_id: str | None = None
    history: list[dict] = field(default_factory=list)

    # --- konfiguracja i opis ------------------------------------------------
    def missing_fields(self) -> list[str]:
        missing = []
        if self.line is None:
            missing.append("linia")
        if self.cross is None:
            missing.append("kierunek przecięcia")
        if self.side is None:
            missing.append("BUY/SELL")
        if self.volume is None or D(self.volume) <= 0:
            missing.append("wolumen")
        return missing

    def warnings(self) -> list[str]:
        out = []
        if self.sl_points is None:
            out.append("UWAGA: brak SL — po wejściu strata nie będzie ograniczona stopem.")
        if self.tp_points is None:
            out.append("Brak TP — pozycja bez celu zysku.")
        if self.cross is not None and self.side is not None:
            if (self.cross is Cross.DOWN and self.side is Side.BUY) or (self.cross is Cross.UP and self.side is Side.SELL):
                out.append("Kierunek wejścia przeciwny do przecięcia (reguła kontrariańska) — sprawdź, czy to zamierzone.")
        return out

    def summary(self, spec: InstrumentSpec) -> str:
        if self.missing_fields():
            return "Reguła niekompletna: brakuje " + ", ".join(self.missing_fields()) + "."
        direction = "w górę" if self.cross is Cross.UP else "w dół"
        sl = f"SL {self.sl_points} pkt" if self.sl_points is not None else "SL BRAK"
        tp = f"TP {self.tp_points} pkt" if self.tp_points is not None else "TP brak"
        until = f"; ważne do {utc(self.expires_at):%Y-%m-%d %H:%M} UTC" if self.expires_at else "; bez terminu"
        return (f"{self.symbol}: gdy {self.price_source.value} przetnie linię {self.line.describe(spec)} {direction}, "
                f"wyślij jednorazowo {self.side.value} {self.volume} lota; {sl}; {tp}{until}.")

    def _log(self, at: datetime, message: str) -> None:
        self.reason = message
        self.history.append({"at": utc(at).isoformat(), "state": self.state.value, "rev": self.revision, "message": message})

    # --- cykl życia -------------------------------------------------------
    def arm(self, price: Decimal | None, at: datetime) -> None:
        if self.state.finished:
            raise ValueError("Reguła zakończona; utwórz nową.")
        missing = self.missing_fields()
        if missing:
            self.state = TriggerState.DRAFT
            self._log(at, "Nie można uzbroić: brakuje " + ", ".join(missing) + ".")
            return
        self.state = TriggerState.ARMED
        self.last_side = None
        self._log(at, "Uzbrojona; pierwsza świeża obserwacja ustali stronę ceny.")
        if price is not None:
            self._observe_side(price, at)

    def pause(self, at: datetime) -> None:
        if self.state in (TriggerState.ARMED, TriggerState.WAITING_RESET):
            self.state = TriggerState.PAUSED
            self.last_side = None
            self._log(at, "Wstrzymana przez użytkownika.")

    def cancel(self, at: datetime, reason: str = "Anulowana przez użytkownika.") -> None:
        if self.state is TriggerState.FIRED:
            self._log(at, "Reguła już wyzwolona; anulowanie nie cofa wysłanego żądania.")
            return
        if not self.state.finished:
            self.state = TriggerState.CANCELLED
            self._log(at, reason)

    def delete_line(self, at: datetime) -> None:
        self.cancel(at, "Linia usunięta; reguła anulowana.")
        if self.state is TriggerState.CANCELLED:
            self.line = None

    def move_line(self, line: Line, at: datetime) -> None:
        if self.state.finished:
            raise ValueError("Nie można przesunąć linii zakończonej reguły.")
        self.line = line
        self.revision += 1
        self.last_side = None
        if self.state is TriggerState.WAITING_RESET:
            self.state = TriggerState.ARMED
        self._log(at, f"Linia przesunięta (rewizja {self.revision}); następna obserwacja ustali stronę.")

    def restore_after_restart(self, at: datetime) -> None:
        """Po restarcie strona nie jest znana: następna obserwacja jej nie wyzwala."""
        self.last_side = None
        if not self.state.finished:
            self._log(at, "Odtworzona po restarcie; następna obserwacja tylko ustala stronę.")

    def _target_side(self, side: int) -> bool:
        return side >= 0 if self.cross is Cross.UP else side <= 0

    def _origin_side(self, side: int) -> bool:
        return side < 0 if self.cross is Cross.UP else side > 0

    def _observe_side(self, price: Decimal, at: datetime) -> int | None:
        line_price = self.line.price_at(at)
        if line_price is None:
            self.reason = "Linia trendu poza swoim zakresem czasu; brak oceny."
            return None
        side = side_of(price, line_price)
        self.last_side = side
        if self.state is TriggerState.ARMED and self._target_side(side):
            self.state = TriggerState.WAITING_RESET
            self._log(at, "Cena już po stronie warunku; czekam na powrót i nowe przecięcie.")
        return side

    def observe(self, bid: Decimal, ask: Decimal, at: datetime, fresh: bool) -> FireOrder | None:
        if self.state.finished or self.state in (TriggerState.DRAFT, TriggerState.PAUSED):
            return None
        if self.expires_at is not None and utc(at) >= utc(self.expires_at):
            self.state = TriggerState.EXPIRED
            self._log(at, "Termin minął bez wyzwolenia.")
            return None
        if not fresh:
            self.reason = "Kwotowanie nieświeże lub brak połączenia: brak oceny."
            return None
        price = D(bid) if self.price_source is PriceSource.BID else D(ask)
        previous = self.last_side
        line_price = self.line.price_at(at)
        if previous is None:
            self._observe_side(price, at)
            return None
        if line_price is None:
            self.reason = "Linia trendu poza swoim zakresem czasu; brak oceny."
            return None
        current = side_of(price, line_price)
        self.last_side = current
        if self.state is TriggerState.WAITING_RESET:
            if self._origin_side(current):
                self.state = TriggerState.ARMED
                self._log(at, "Cena wróciła na stronę wyjściową; reguła aktywna.")
            return None
        if self._origin_side(previous) and self._target_side(current):
            self.state = TriggerState.FIRED
            self.fired_request_id = f"trg-{self.trigger_id}-r{self.revision}"
            self._log(at, f"Przecięcie {self.cross.value} przy {self.price_source.value}={price}, linia={line_price}.")
            return FireOrder(self.fired_request_id, self.trigger_id, self.symbol, self.side, D(self.volume),
                             self.sl_points, self.tp_points, price, line_price)
        return None

    # --- trwałość ---------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "trigger_id": self.trigger_id, "symbol": self.symbol,
            "line": None if self.line is None else self.line.to_dict(),
            "cross": None if self.cross is None else self.cross.value,
            "side": None if self.side is None else self.side.value,
            "volume": None if self.volume is None else str(self.volume),
            "price_source": self.price_source.value,
            "sl_points": None if self.sl_points is None else str(self.sl_points),
            "tp_points": None if self.tp_points is None else str(self.tp_points),
            "expires_at": None if self.expires_at is None else utc(self.expires_at).isoformat(),
            "state": self.state.value, "revision": self.revision, "reason": self.reason,
            "fired_request_id": self.fired_request_id, "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrendTrigger":
        def dec(k: str) -> Decimal | None:
            return None if d.get(k) is None else Decimal(d[k])

        return cls(
            trigger_id=d["trigger_id"], symbol=d["symbol"],
            line=None if d.get("line") is None else Line.from_dict(d["line"]),
            cross=None if d.get("cross") is None else Cross(d["cross"]),
            side=None if d.get("side") is None else Side(d["side"]),
            volume=dec("volume"), price_source=PriceSource(d.get("price_source", "BID")),
            sl_points=dec("sl_points"), tp_points=dec("tp_points"),
            expires_at=None if d.get("expires_at") is None else datetime.fromisoformat(d["expires_at"]),
            state=TriggerState(d["state"]), revision=d.get("revision", 0), last_side=None,
            reason=d.get("reason", ""), fired_request_id=d.get("fired_request_id"),
            history=list(d.get("history", [])),
        )
