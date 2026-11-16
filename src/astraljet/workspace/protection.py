"""Break-even, trailing i ręczna zmiana SL — jeden mechanizm rozstrzygania.

Definicje:
- BE: trigger (odległość zysku od wejścia) mówi KIEDY; cel SL = wejście ± bufor
  (BUY: wejście + bufor, SELL: wejście − bufor). BE jest cenowe — nie gwarantuje
  wyniku netto zero po prowizjach i swapach; szacunek netto jest liczony osobno.
- Trailing: po osiągnięciu progu aktywacji kandydat SL = cena zamknięcia ∓ odległość.
  Próg aktywacji to nie jest odległość stopa.
- Żadna automatyka ani zwykła ręczna zmiana nie pogarsza istniejącego (lepszego) SL.
  Pogorszenie wymaga jawnego potwierdzenia użytkownika i jest oznaczone w żądaniu.
- Status PROTECTED dopiero, gdy broker potwierdził SL na pozycji.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from .instruments import D, FxTable, InstrumentSpec, Side
from .model import Position


class RuleState(StrEnum):
    DISABLED = "DISABLED"            # reguła wyłączona
    WAITING = "WAITING"              # włączona, warunek niespełniony
    CONDITION_MET = "CONDITION_MET"  # warunek spełniony, zmiana jeszcze niewysłana (np. stops level)
    SENT = "SENT"                    # żądanie zmiany SL wysłane
    CONFIRMED = "CONFIRMED"          # broker potwierdził SL na pozycji
    SATISFIED = "SATISFIED"          # obecny SL już równy lub lepszy od celu reguły
    UNCERTAIN = "UNCERTAIN"          # brak odpowiedzi; czeka na uzgodnienie
    ERROR = "ERROR"                  # odrzucenie lub błąd konfiguracji


def better(side: Side, a: Decimal, b: Decimal) -> bool:
    """Czy stop `a` chroni lepiej niż `b` (BUY: wyżej, SELL: niżej)."""
    return (D(a) - D(b)) * side.sign > 0


def improves(side: Side, current: Decimal | None, candidate: Decimal, min_step: Decimal = Decimal(0)) -> bool:
    if current is None:
        return True
    return (D(candidate) - D(current)) * side.sign > 0 and abs(D(candidate) - D(current)) >= D(min_step)


def close_price(side: Side, bid: Decimal, ask: Decimal) -> Decimal:
    """Cena, po której pozycję da się zamknąć: BUY po Bid, SELL po Ask."""
    return D(bid) if side is Side.BUY else D(ask)


@dataclass(slots=True)
class BreakEvenRule:
    trigger_points: Decimal
    offset_points: Decimal = Decimal(0)
    enabled: bool = True

    def problems(self) -> list[str]:
        out = []
        if D(self.trigger_points) <= 0:
            out.append("Trigger BE musi być dodatni (odległość zysku od wejścia).")
        if D(self.offset_points) >= D(self.trigger_points):
            out.append("Bufor BE musi być mniejszy od triggera; inaczej cel SL leżałby za bieżącą ceną.")
        if D(self.offset_points) < 0:
            out.append("Ujemny bufor ustawia SL po stratnej stronie wejścia (to nie jest break-even).")
        return out

    def target(self, pos: Position, spec: InstrumentSpec) -> Decimal:
        return spec.normalize_price(D(pos.open_price) + pos.side.sign * spec.from_points(self.offset_points))

    def triggered(self, pos: Position, spec: InstrumentSpec, close: Decimal) -> bool:
        return (D(close) - D(pos.open_price)) * pos.side.sign >= spec.from_points(self.trigger_points)


@dataclass(slots=True)
class TrailingRule:
    activation_points: Decimal
    distance_points: Decimal
    step_points: Decimal = Decimal(1)
    enabled: bool = True

    def problems(self) -> list[str]:
        out = []
        if D(self.distance_points) <= 0:
            out.append("Odległość trailing musi być dodatnia.")
        if D(self.activation_points) < 0:
            out.append("Próg aktywacji nie może być ujemny.")
        if D(self.step_points) < 0:
            out.append("Krok trailing nie może być ujemny.")
        return out

    def candidate(self, pos: Position, spec: InstrumentSpec, close: Decimal) -> Decimal | None:
        profit_points = spec.to_points((D(close) - D(pos.open_price)) * pos.side.sign)
        if profit_points < D(self.activation_points):
            return None
        return spec.normalize_price(D(close) - pos.side.sign * spec.from_points(self.distance_points))


@dataclass(slots=True)
class RuleStatus:
    state: RuleState = RuleState.DISABLED
    reason: str = ""
    target: Decimal | None = None
    request_id: str | None = None
    rejected_target: Decimal | None = None

    def to_dict(self) -> dict:
        return {"state": self.state.value, "reason": self.reason,
                "target": None if self.target is None else str(self.target), "request_id": self.request_id}


@dataclass(frozen=True, slots=True)
class Proposal:
    source: str          # "be" / "trailing" / "manual"
    target: Decimal
    worsens: bool = False


@dataclass(slots=True)
class ProtectionState:
    position_id: str
    be: BreakEvenRule | None = None
    trailing: TrailingRule | None = None
    be_status: RuleStatus = field(default_factory=RuleStatus)
    trailing_status: RuleStatus = field(default_factory=RuleStatus)
    manual_status: RuleStatus = field(default_factory=RuleStatus)
    in_flight: Proposal | None = None
    in_flight_request: str | None = None
    revision: int = 0

    def status_for(self, source: str) -> RuleStatus:
        return {"be": self.be_status, "trailing": self.trailing_status, "manual": self.manual_status}[source]

    def evaluate(self, pos: Position, spec: InstrumentSpec, bid: Decimal, ask: Decimal, quote_ok: bool) -> Proposal | None:
        """Wyznacza najlepszą poprawę SL; nic nie wysyła. `pos.sl` to SL potwierdzony."""
        for rule, status, name in ((self.be, self.be_status, "BE"), (self.trailing, self.trailing_status, "Trailing")):
            if rule is None or not rule.enabled:
                status.state, status.reason, status.target = RuleState.DISABLED, f"{name} wyłączony.", None
        if self.in_flight is not None:
            return None
        if not quote_ok:
            for rule, status in ((self.be, self.be_status), (self.trailing, self.trailing_status)):
                if rule is not None and rule.enabled and status.state not in (RuleState.ERROR, RuleState.UNCERTAIN):
                    status.reason = "Kwotowanie nieświeże lub brak połączenia: ocena wstrzymana."
            return None
        close = close_price(pos.side, bid, ask)
        candidates: list[Proposal] = []
        if self.be is not None and self.be.enabled:
            problems = self.be.problems()
            st = self.be_status
            if problems:
                st.state, st.reason = RuleState.ERROR, " ".join(problems)
            elif st.state not in (RuleState.CONFIRMED, RuleState.SATISFIED):
                target = self.be.target(pos, spec)
                st.target = target
                if st.state is RuleState.ERROR and st.rejected_target == target:
                    pass  # ta sama, już odrzucona zmiana nie jest ponawiana automatycznie
                elif not self.be.triggered(pos, spec, close):
                    st.state = RuleState.WAITING
                    st.reason = f"Czekam na +{self.be.trigger_points} pkt od wejścia."
                elif not improves(pos.side, pos.sl, target):
                    st.state, st.reason = RuleState.SATISFIED, "Obecny SL jest równy lub lepszy od celu BE."
                else:
                    st.state, st.reason = RuleState.CONDITION_MET, "Warunek BE spełniony."
                    candidates.append(Proposal("be", target))
        if self.trailing is not None and self.trailing.enabled:
            problems = self.trailing.problems()
            st = self.trailing_status
            if problems:
                st.state, st.reason = RuleState.ERROR, " ".join(problems)
            else:
                cand = self.trailing.candidate(pos, spec, close)
                if cand is None:
                    if st.state not in (RuleState.CONFIRMED, RuleState.SATISFIED, RuleState.ERROR):
                        st.state = RuleState.WAITING
                        st.reason = f"Czekam na aktywację +{self.trailing.activation_points} pkt."
                elif st.state is RuleState.ERROR and st.rejected_target == cand:
                    pass  # nie ponawiamy identycznej, odrzuconej zmiany
                elif improves(pos.side, pos.sl, cand, spec.from_points(self.trailing.step_points)):
                    st.state, st.target, st.reason = RuleState.CONDITION_MET, cand, "Kandydat trailing poprawia SL."
                    candidates.append(Proposal("trailing", cand))
                elif st.state is not RuleState.CONFIRMED:
                    st.state, st.reason = RuleState.SATISFIED, "Obecny SL równy lub lepszy od kandydata trailing."
        if not candidates:
            return None
        best = candidates[0]
        for c in candidates[1:]:
            if better(pos.side, c.target, best.target):
                best = c
        minimum = spec.from_points(spec.stops_level_points)
        if (close - best.target) * pos.side.sign < minimum or (close - best.target) * pos.side.sign <= 0:
            self.status_for(best.source).reason = "Cel SL zbyt blisko ceny (stops level); czekam."
            return None
        return best

    def manual(self, pos: Position, new_sl: Decimal | None, acknowledge_worse: bool = False) -> Proposal:
        if new_sl is None:
            if pos.sl is not None and not acknowledge_worse:
                raise ValueError("Usunięcie SL pogarsza ochronę; wymaga jawnego potwierdzenia.")
            raise ValueError("Usuwanie SL nie jest obsługiwane w Workspace v0.1.")
        worse = pos.sl is not None and not improves(pos.side, pos.sl, new_sl) and D(new_sl) != D(pos.sl)
        if worse and not acknowledge_worse:
            raise ValueError("Nowy SL jest gorszy od obecnego; automatyka i zwykła zmiana nie pogarszają stopa.")
        return Proposal("manual", D(new_sl), worsens=worse)

    def mark_sent(self, proposal: Proposal, request_id: str) -> None:
        self.in_flight = proposal
        self.in_flight_request = request_id
        st = self.status_for(proposal.source)
        st.state, st.target, st.request_id = RuleState.SENT, proposal.target, request_id
        st.reason = "Żądanie zmiany SL wysłane; brak potwierdzenia."

    def mark_outcome(self, state: str, message: str, pos: Position | None) -> None:
        """state: FILLED / REJECTED / UNCERTAIN / NOT_SENT / NOT_FOUND (z RequestState)."""
        if self.in_flight is None:
            return
        st = self.status_for(self.in_flight.source)
        if state == "FILLED" and pos is not None and pos.sl is not None and D(pos.sl) == D(self.in_flight.target):
            st.state, st.reason = RuleState.CONFIRMED, "SL potwierdzony na pozycji."
            self.in_flight = None
            self.in_flight_request = None
        elif state == "UNCERTAIN":
            st.state, st.reason = RuleState.UNCERTAIN, message or "Brak odpowiedzi; uzgodnij stan."
        else:
            st.state = RuleState.ERROR
            st.rejected_target = self.in_flight.target
            st.reason = f"Zmiana SL nieprzyjęta ({state}): {message}"
            self.in_flight = None
            self.in_flight_request = None


@dataclass(frozen=True, slots=True)
class ProtectionView:
    status: str                 # PROTECTED / UNPROTECTED / CHANGE_PENDING
    confirmed_sl: Decimal | None
    pnl_at_sl_account: Decimal | None
    note: str

    def to_dict(self) -> dict:
        return {"status": self.status,
                "confirmed_sl": None if self.confirmed_sl is None else str(self.confirmed_sl),
                "pnl_at_sl_account": None if self.pnl_at_sl_account is None else str(self.pnl_at_sl_account),
                "note": self.note}


def protection_view(pos: Position, spec: InstrumentSpec, fx: FxTable, account_ccy: str, pending: bool) -> ProtectionView:
    if pos.sl is None:
        return ProtectionView("CHANGE_PENDING" if pending else "UNPROTECTED", None, None,
                              "Brak potwierdzonego SL: strata do SL nieokreślona.")
    gross = spec.profit(pos.side, pos.volume, pos.open_price, pos.sl)
    converted, note = fx.convert(gross, spec.profit_currency, account_ccy)
    return ProtectionView("CHANGE_PENDING" if pending else "PROTECTED", D(pos.sl), converted,
                          "Wynik przy SL to szacunek brutto, przed kosztami; luka cenowa i poślizg mogą go zmienić. " + note)
