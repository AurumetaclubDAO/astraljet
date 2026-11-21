# -*- coding: utf-8 -*-
"""Paper dla serii 2 (zlecenie E1, SPEC_SERIA2.md, punkt 9): H4 i H5 w dwóch niezależnych środowiskach PAPER.

NIE PRZESZŁA BADANIA: obie hipotezy mają werdykt FAIL. Paper sprawdza drogę (świeżość danych, decyzja,
wielkość pozycji, bramka, księga, hamulec, porównanie z backtestem). Nic z tego nie idzie do DEMO ani LIVE.

Ta sama logika co w badaniu, bez kopiowania: decyzje, koszty i ciągłość historii z
research/daily-trend/scripts/run_seria2.py, wielkość pozycji z astraljet.lab.position_sizing.
Krok dnia odtwarza pętlę run_seria2.simulate_account (test: na tych samych danych paper = backtest).

- Dzień jest księgowany, gdy w danych jest już następny dzień kalendarza koszyka (tak jak w backteście
  koniec miesiąca rozpoznaje się po następnym dniu). Decyzja na zamknięciu ostatniego dnia miesiąca,
  wykonanie na otwarciu następnej świecy danego rynku, po cenie z pliku D1.
- Zlecenia wyłącznie przez PaperExecutor (mandat PAPER: max_notional = 50% kapitału na rynek,
  max_gross_exposure = G × kapitał, marks dla wszystkich rynków). Klucz intencji = środowisko:dzień:rynek,
  więc ponowne uruchomienie po przerwie nie wykona zlecenia drugi raz.
- Księga gotówki i kosztów poza wykonawcą (koszt bazowy): spread według side_rate, prowizja 6 USD za stronę
  na ETF-ach, finansowanie za każdy dzień kalendarzowy według financing_rate.
- Hamulec obsunięcia astraljet.lab.drawdown_brake: próg to WYMAGANY parametr (ustala Karol).
- Świeżość astraljet.lab.data_freshness: przy nieświeżych danych brak księgowania i decyzji, zapis powodu.
- Po każdym pełnym miesiącu porównanie z backtestem simulate_account na tych samych plikach.

Uruchamianie ręcznie, raz dziennie po zamknięciu sesji USA (bez zadania w Harmonogramie):
    .venv\\Scripts\\python.exe scripts\\paper_seria2.py --prog-hamulca <ułamek> [--start 2026-11-01] [--dzien RRRR-MM-DD]
Stan i raport poza Git: .runtime/paper-seria2/
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "research" / "daily-trend" / "scripts"))

import run_seria2 as s2  # noqa: E402
from astraljet.application.mandates import MandateRequest, create_mandate  # noqa: E402
from astraljet.domain.enums import (  # noqa: E402
    ExecutionEnvironment, ExecutionResultState, RiskDecisionStatus, TechnicalStatus,
)
from astraljet.domain.errors import DomainBlockedError, ValidationError  # noqa: E402
from astraljet.domain.records import RiskDecisionRecord  # noqa: E402
from astraljet.executor.guard import ExecutorGuard  # noqa: E402
from astraljet.executor.paper import PaperExecutor  # noqa: E402
from astraljet.executor.ports import FrozenContext, OrderIntent  # noqa: E402
from astraljet.infrastructure.database import Database  # noqa: E402
from astraljet.lab import drawdown_brake as brake  # noqa: E402
from astraljet.lab.data_freshness import check_freshness  # noqa: E402
from astraljet.lab.position_sizing import SizingLimits, size_positions  # noqa: E402

RESULT_FILE = ROOT / "research" / "daily-trend" / "reports" / "wynik_seria2_2500.json"
DATA_DIR = ROOT / "research" / "daily-data" / "data" / "uniwersum"
OUT_DIR = ROOT / ".runtime" / "paper-seria2"
ENVIRONMENTS = {"H4": "paper-seria2-h4", "H5": "paper-seria2-h5"}
SERVER_OFFSET_H = 2  # dzień serwera MT5 (zimą UTC+2); --dzien nadpisuje
# Limit wieku ostatniej świecy w dniach (do potwierdzenia przez koordynatora): krypto handluje codziennie,
# ETF-y mają weekend i święta.
FRESHNESS_DAYS = {"ETHUSD": 2}
FRESHNESS_DEFAULT = 4
COMPARE_LIMIT_PP = 0.5
LABEL = "NIE PRZESZŁA BADANIA (werdykt FAIL); paper sprawdza tylko drogę, nic nie idzie do DEMO ani LIVE"


# ---------- stan ----------

@dataclass
class PaperState:
    hypothesis: str
    environment: str
    capital0: float
    gross: float
    start: str
    last_day: str | None = None
    cash: float = 0.0
    volume: dict[str, float] = field(default_factory=dict)
    targets: dict[str, float] = field(default_factory=dict)
    pending: dict[str, int] = field(default_factory=dict)
    rows: list[list] = field(default_factory=list)          # [dzień, kapitał na zamknięciu]
    costs: dict[str, float] = field(default_factory=lambda: {"spread": 0.0, "commission": 0.0, "financing": 0.0})
    trades: list[dict] = field(default_factory=list)
    refusals: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    brake_state: dict = field(default_factory=dict)

    @classmethod
    def new(cls, hypothesis: str, capital: float, gross: float, start: str) -> "PaperState":
        b = brake.start(capital)
        return cls(hypothesis=hypothesis, environment=ENVIRONMENTS[hypothesis], capital0=capital, gross=gross,
                   start=start, cash=capital, brake_state=_brake_dump(b))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.__dict__, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)  # zapis atomowy: przerwany przebieg nie zostawia połowy stanu

    @classmethod
    def load(cls, path: Path) -> "PaperState":
        return cls(**json.loads(path.read_text(encoding="utf-8")))


def _brake_dump(state: brake.BrakeState) -> dict:
    return {"peak": str(state.peak), "tripped": state.tripped, "tripped_at": state.tripped_at,
            "tripped_equity": None if state.tripped_equity is None else str(state.tripped_equity),
            "released_by": state.released_by, "released_at": state.released_at}


def _brake_load(data: dict) -> brake.BrakeState:
    return brake.BrakeState(peak=Decimal(data["peak"]), tripped=data["tripped"], tripped_at=data["tripped_at"],
                            tripped_equity=None if data["tripped_equity"] is None else Decimal(data["tripped_equity"]),
                            released_by=data["released_by"], released_at=data["released_at"])


# ---------- wykonawca PAPER ----------

def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cents_up(value: float) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_CEILING))


class PaperGate:
    """PaperExecutor + mandat odnawiany przy każdym wykonaniu (limity zależą od bieżącego kapitału)."""

    def __init__(self, database: Database, environment: str, hypothesis: str, now_fn) -> None:
        self.database, self.environment, self.hypothesis, self.now_fn = database, environment, hypothesis, now_fn
        self.guard = ExecutorGuard(database)
        self.executor = PaperExecutor(database, self.guard)
        self.lease = self.guard.acquire_lease(environment, "paper-seria2", ttl_seconds=3600, now=now_fn())

    def context(self, instruments: tuple[str, ...], equity: float, gross: float, marks: dict) -> FrozenContext:
        now = self.now_fn()
        limits = {"max_notional": _cents_up(s2.MARKET_CAP * equity), "max_position_quantity": "1000000000000",
                  "max_gross_exposure": _cents_up(gross * equity)}
        start, end = now - timedelta(minutes=1), now + timedelta(hours=1)
        risk = RiskDecisionRecord(
            record_id=f"RISK_DECISION-PAPER-{self.hypothesis}", version=1, owner="Karol", created_at=_iso(now),
            technical_status=TechnicalStatus.COMPLETED, content_hash="0" * 64, limitations=(LABEL,),
            review_id="REVIEW-SERIA2", scope=f"paper serii 2, {self.hypothesis}", valid_from=_iso(start),
            valid_until=_iso(end), limits=limits, decision=RiskDecisionStatus.ALLOWED,
            rationale="SPEC_SERIA2.md punkt 9: paper po akceptacji reguł, niezależnie od werdyktu.",
            permitted_next_step="tylko PAPER_CONTINUOUS", blockers=())
        mandate = create_mandate(risk_decision=risk, owner="Karol", request=MandateRequest(
            authorized_by="Karol", strategy_id=f"STRAT-SERIA2-{self.hypothesis}", strategy_version=1,
            code_hash="0" * 64, environment=ExecutionEnvironment.PAPER_CONTINUOUS, environment_id=self.environment,
            account_id=None, instruments=instruments, limits=limits, starts_at=_iso(start), expires_at=_iso(end),
            stop_conditions=("hamulec obsunięcia", "nieświeże dane", "kill switch"), max_data_age_seconds=3600))
        # Krótka pozycja tylko w H4; flaga logiczna poza porównaniem z RISK-DECISION (jak w testach limitu łącznego).
        mandate = replace(mandate, limits={**mandate.limits, "allow_short": self.hypothesis == "H4"})
        return FrozenContext(mandate=mandate, risk_decision=risk, strategy_id=mandate.strategy_id,
                             strategy_version=1, code_hash=mandate.code_hash, environment=mandate.environment,
                             environment_id=self.environment, worker_id="paper-seria2", lease_id=self.lease.lease_id,
                             data_observed_at=_iso(now),
                             marks={n: Decimal(str(p)) for n, p in marks.items()})

    def submit(self, ctx: FrozenContext, day: str, market: str, change_units: Decimal, price: float,
               *, leg: str = "zmiana") -> tuple[bool, str]:
        intent_id = f"{self.environment}:{day}:{market}:{leg}"
        intent = OrderIntent(intent_id=intent_id, instrument=market, side="buy" if change_units > 0 else "sell",
                             quantity=abs(Decimal(change_units)), reference_price=Decimal(repr(price)),
                             signal_id=f"SIGNAL-{intent_id}")
        try:
            receipt = self.executor.submit_intent(ctx, intent, idempotency_key=f"paper:{intent_id}", now=self.now_fn())
        except DomainBlockedError as exc:
            return False, exc.blocker
        if receipt.state is ExecutionResultState.ACCEPTED:
            return True, "accepted"
        if receipt.state is ExecutionResultState.DUPLICATE and receipt.previous_state is ExecutionResultState.ACCEPTED:
            return True, "duplicate (wykonane wcześniej)"
        return False, receipt.state.value

    def positions(self) -> dict[str, str]:
        return self.executor.positions(self.environment).quantities


# ---------- krok dnia ----------

def _index(market: s2.Market, day: str) -> int:
    return bisect.bisect_right(market.dates, day) - 1


def process_day(state: PaperState, markets: dict[str, s2.Market], calendar: list[str], k: int,
                gate: PaperGate | None, threshold: float) -> None:
    """Jeden dzień kalendarza koszyka; ta sama kolejność rachunku co w run_seria2.simulate_account."""
    day = calendar[k]
    names = list(markets)
    contract = {n: float(markets[n].spec.contract_size) for n in names}
    specs = {n: markets[n].spec for n in names}
    index = {n: _index(markets[n], day) for n in names}
    has_bar = {n for n in names if index[n] >= 0 and markets[n].dates[index[n]] == day}
    limits = SizingLimits(max_gross=Decimal(str(state.gross)), max_per_market=Decimal(str(s2.MARKET_CAP)))
    for n in names:
        state.volume.setdefault(n, 0.0)

    ready = []
    for n in list(state.pending):
        if n in has_bar:
            if state.pending[n] > 0:
                state.pending[n] -= 1
            else:
                ready.append(n)
                del state.pending[n]
    if ready:
        price = {n: (markets[n].opens[index[n]] if n in has_bar else markets[n].closes[index[n]])
                 for n in names if index[n] >= 0}
        equity = state.cash + sum(state.volume[n] * contract[n] * price[n] for n in price)
        sized = size_positions(state.targets, capital=equity, prices=price, specs=specs, limits=limits)
        changes = []
        for n in ready:
            wanted = sized.get(n)
            new_volume = float(wanted.volume) if wanted is not None else 0.0
            if wanted is not None and wanted.skipped:
                state.refusals.append({"day": day, "market": n, "reason": f"wielkość pozycji: {wanted.reasons[-1]}"})
            if abs(new_volume - state.volume[n]) > 1e-12:
                changes.append((new_volume - state.volume[n], n, new_volume))
        ctx = gate.context(tuple(names), equity, state.gross, price) if gate and changes else None
        # Najpierw zlecenia zmniejszające pozycję (także krótką), potem zwiększające: łączna ekspozycja
        # w wykonawcy nie przekracza limitu w trakcie przestawiania. Kolejność nie zmienia wyniku księgi.
        changes.sort(key=lambda c: (abs(c[2]) > abs(state.volume[c[1]]), c[0]))
        for change, n, new_volume in changes:
            unit = contract[n] * price[n]
            if gate is not None:
                # Zmiana strony (H4) idzie dwoma zleceniami: zamknięcie i otwarcie, bo limit max_notional dotyczy
                # też pojedynczego zlecenia. Księga liczy ją jak backtest: jedna prowizja za zmianę na rynku.
                # Ilości dla wykonawcy liczone dokładnie w Decimal z lotów (krok lota), bez błędów float,
                # żeby zamknięcie do zera nie zostawiało w wykonawcy resztki ani „krótkiej” pozycji.
                old = state.volume[n]
                d_old, d_new = Decimal(repr(old)), Decimal(repr(new_volume))
                legs = ([("zamkniecie", -d_old, 0.0), ("otwarcie", d_new, new_volume)] if old * new_volume < 0
                        else [("zmiana", d_new - d_old, new_volume)])
                booked = old
                d_contract = markets[n].spec.contract_size
                for leg, amount, after in legs:
                    ok, outcome = gate.submit(ctx, day, n, amount * Decimal(str(d_contract)), price[n], leg=leg)
                    if not ok:
                        state.refusals.append({"day": day, "market": n, "reason": f"bramka ({leg}): {outcome}"})
                        break
                    booked = after
                if booked == old:
                    continue  # nic nie wykonano: księga bez zmian, jak pozycja w wykonawcy
                change, new_volume = booked - old, booked
            spread_cost = abs(change) * unit * s2.side_rate(markets[n].costs, "base")
            commission = markets[n].costs.commission_side
            state.cash -= change * unit + spread_cost + commission
            state.volume[n] = new_volume
            state.costs["spread"] += spread_cost
            state.costs["commission"] += commission
            state.trades.append({"day": day, "market": n, "change": change, "volume_after": new_volume,
                                 "price": price[n], "spread_cost": spread_cost, "commission": commission})
    closing = {n: markets[n].closes[index[n]] for n in names if index[n] >= 0}
    previous = state.rows[-1][0] if state.rows else None
    if previous is not None:
        held_days = (date.fromisoformat(day) - date.fromisoformat(previous)).days
        financing = sum(abs(state.volume[n]) * contract[n] * closing[n]
                        * s2.financing_rate(markets[n].costs, "base", 1 if state.volume[n] > 0 else -1)
                        for n in closing if state.volume[n]) * held_days / 365
        state.cash -= financing
        state.costs["financing"] += financing
    equity = state.cash + sum(state.volume[n] * contract[n] * closing[n] for n in closing)
    state.rows.append([day, equity])
    state.last_day = day

    b = _brake_load(state.brake_state)
    was = b.tripped
    b = brake.observe(b, max(equity, 0.0), threshold=threshold, when=day)
    state.brake_state = _brake_dump(b)
    if b.tripped and not was:
        # Hamulec: wagi na zero, zamknięcie na otwarciu następnej świecy każdego rynku z pozycją.
        state.targets = {n: 0.0 for n in names if index[n] >= 0}
        state.pending = {n: 0 for n in state.targets}
        state.decisions.append({"day": day, "kind": "hamulec", "equity": equity})

    if k + 1 < len(calendar) and calendar[k + 1][:7] != day[:7]:
        histories = {}
        for n in names:
            if index[n] >= 0:
                bars = s2.continuous_bars(markets[n].dates, index[n])
                if bars >= s2.MIN_HISTORY:
                    histories[n] = markets[n].closes[index[n] + 1 - bars:index[n] + 1]
        if len(histories) >= s2.MIN_MARKETS:
            decided = s2.decide_targets(histories, hypothesis=state.hypothesis, gross=state.gross,
                                        lookback=s2.MAIN[0], vol_window=s2.MAIN[1])
            targets = {n: decided.get(n, 0.0) for n in names if index[n] >= 0}
            gated = brake.gate(b, targets)
            state.targets = {n: float(v) for n, v in gated.items()}
            state.pending = {n: 0 for n in state.targets}
            state.decisions.append({"day": day, "kind": "decyzja" if not b.tripped else "decyzja (hamulec: zera)",
                                    "targets": state.targets, "participants": len(histories)})
        else:
            state.decisions.append({"day": day, "kind": "brak decyzji",
                                    "reason": f"{len(histories)} rynków z pełną historią, potrzeba {s2.MIN_MARKETS}"})


def basket_calendar(markets: dict[str, s2.Market]) -> list[str]:
    last_common = min(m.dates[-1] for m in markets.values())
    return sorted({d for m in markets.values() for d in m.dates if d <= last_common})


def advance(state: PaperState, markets: dict[str, s2.Market], gate: PaperGate | None, threshold: float) -> int:
    """Księguje dni od startu (albo od ostatniego zaksięgowanego) do przedostatniego dnia kalendarza."""
    calendar = basket_calendar(markets)
    done = 0
    for k, day in enumerate(calendar):
        if day < state.start or (state.last_day is not None and day <= state.last_day):
            continue
        if k + 1 >= len(calendar):
            break  # ostatni dzień czeka na następny dzień danych (rozpoznanie końca miesiąca)
        process_day(state, markets, calendar, k, gate, threshold)
        done += 1
    return done


# ---------- świeżość i porównanie ----------

def freshness_problems(markets: dict[str, s2.Market], today: str) -> list[str]:
    report = check_freshness({n: m.dates[-1] if m.dates else None for n, m in markets.items()}, today=today,
                             max_age_days={n: FRESHNESS_DAYS.get(n, FRESHNESS_DEFAULT) for n in markets})
    return [f"{r.symbol}: {r.reason}" for r in report.values() if not r.fresh]


def monthly_returns(rows: list, capital0: float) -> dict[str, float]:
    out, prev, month_end = {}, capital0, {}
    for day, equity in rows:
        month_end[day[:7]] = equity
    for month in sorted(month_end):
        out[month] = month_end[month] / prev - 1
        prev = month_end[month]
    return out


def compare_with_backtest(state: PaperState, markets: dict[str, s2.Market]) -> list[dict]:
    """Miesiące zakończone w paper, porównane z simulate_account na tych samych plikach (koszt bazowy)."""
    if not state.rows:
        return []
    backtest = s2.simulate_account(markets, hypothesis=state.hypothesis, capital=state.capital0, gross=state.gross)
    bt_rows = [[d, e] for d, e in backtest.rows]
    bt_months = monthly_returns(bt_rows, state.capital0)
    paper = monthly_returns(state.rows, state.capital0)
    calendar = basket_calendar(markets)
    complete = {m for m in paper if any(d[:7] > m for d in calendar)}
    first_exec = min((t["day"][:7] for t in state.trades), default=None)
    same_start = state.start <= calendar[0]
    out = []
    for month in sorted(paper):
        if month not in complete or month not in bt_months:
            continue
        diff_pp = (paper[month] - bt_months[month]) * 100
        # Paper startuje bez pozycji: miesiące przed pierwszym wykonaniem nie mają odpowiednika w backteście.
        comparable = same_start or (first_exec is not None and month >= first_exec)
        out.append({"month": month, "paper": paper[month], "backtest": bt_months[month], "diff_pp": diff_pp,
                    "comparable": comparable,
                    "explain": comparable and abs(diff_pp) > COMPARE_LIMIT_PP})
    return out


# ---------- raport ----------

def write_report(path: Path, states: dict[str, PaperState], comparisons: dict[str, list], notes: list[str],
                 verdicts: dict[str, str]) -> None:
    L = ["# Paper serii 2", "", f"**{LABEL}.**", "",
         f"- Aktualizacja: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, `scripts/paper_seria2.py`.",
         "- Koszt bazowy: spread według pomiaru na tickach, prowizja 6 USD za stronę na ETF-ach, finansowanie dzienne.",
         *[f"- {n}" for n in notes]]
    for hyp, st in states.items():
        equity = st.rows[-1][1] if st.rows else st.capital0
        b = st.brake_state
        L += ["", f"## {hyp} (`{st.environment}`, werdykt badania: {verdicts.get(hyp, '?')})", "",
              f"- Start: {st.start}; ostatni zaksięgowany dzień: {st.last_day or '-'}.",
              f"- Kapitał: {equity:.2f} USD (start {st.capital0:.2f}); gotówka {st.cash:.2f} USD.",
              f"- Koszty: spread {st.costs['spread']:.2f}, prowizja {st.costs['commission']:.2f}, "
              f"finansowanie {st.costs['financing']:.2f} USD.",
              f"- Hamulec: {'ZACIĄGNIĘTY ' + str(b['tripped_at']) if b['tripped'] else 'nie zadziałał'} "
              f"(szczyt {float(b['peak']):.2f} USD).",
              "- Pozycje (loty): " + (", ".join(f"{n} {v:g}" for n, v in st.volume.items() if v) or "brak") + "."]
        if st.decisions:
            last = st.decisions[-1]
            L.append(f"- Ostatnia decyzja: {last['day']} ({last['kind']}).")
        if st.refusals:
            L += ["", "Odmowy (ostatnie 10):", *[f"- {r['day']} {r['market']}: {r['reason']}" for r in st.refusals[-10:]]]
        rows = comparisons.get(hyp) or []
        if rows:
            L += ["", "| Miesiąc | Paper | Backtest | Różnica [pp] | Uwagi |", "|---|---:|---:|---:|---|"]
            for r in rows:
                note = ("DO WYJAŚNIENIA" if r["explain"] else "") if r["comparable"] else \
                    "nieporównywalny (paper startuje bez pozycji)"
                L.append(f"| {r['month']} | {r['paper'] * 100:.2f}% | {r['backtest'] * 100:.2f}% | "
                         f"{r['diff_pp']:+.2f} | {note} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------- uruchomienie ----------

def load_markets(folder: Path, basket: list[str]) -> dict[str, s2.Market]:
    spreads = s2.load_spreads(s2.SPREAD_REPORT)
    return {n: s2.market_from_files(folder, n, spread=spreads.get(n)) for n in basket}


def server_today() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=SERVER_OFFSET_H)).date().isoformat()


def run(*, threshold: float, start: str | None, today: str, data_dir: Path = DATA_DIR, out_dir: Path = OUT_DIR,
        markets: dict[str, s2.Market] | None = None, now_fn=lambda: datetime.now(timezone.utc)) -> dict:
    result = json.loads(RESULT_FILE.read_text(encoding="utf-8"))
    basket, capital, gross = list(result["basket"]), float(result["capital"]), float(result["gross"])
    verdicts = {r["hypothesis"]: r["verdict"] for r in result["results"]}
    block = s2.acceptance_block(s2.SPEC_FILE.read_text(encoding="utf-8"))
    if block:
        raise ValidationError(block)
    markets = markets if markets is not None else load_markets(data_dir, basket)
    notes, states, comparisons = [], {}, {}
    stale = freshness_problems(markets, today)
    database = Database.from_state_dir(out_dir / "state")
    database.initialize()
    for hyp in ("H4", "H5"):
        path = out_dir / ENVIRONMENTS[hyp] / "state.json"
        if path.exists():
            st = PaperState.load(path)
        else:
            if start is None:
                raise ValidationError("Pierwsze uruchomienie wymaga --start (dzień startu paper).")
            st = PaperState.new(hyp, capital, gross, start)
        if stale:
            st.refusals.append({"day": today, "market": "*", "reason": "nieświeże dane: " + "; ".join(stale)})
        else:
            gate = PaperGate(database, st.environment, hyp, now_fn)
            booked = advance(st, markets, gate, threshold)
            held = {n: v for n, v in gate.positions().items() if Decimal(v) != 0}
            ledger = {n: v * float(markets[n].spec.contract_size) for n, v in st.volume.items() if v}
            mismatch = [n for n in set(held) | set(ledger)
                        if abs(float(held.get(n, "0")) - ledger.get(n, 0.0)) > 1e-6]
            if mismatch:
                st.refusals.append({"day": today, "market": ",".join(sorted(mismatch)),
                                    "reason": "księga różni się od pozycji wykonawcy"})
            notes.append(f"{hyp}: zaksięgowano {booked} dni" + (f"; ROZBIEŻNOŚĆ z wykonawcą: {mismatch}" if mismatch else ""))
        st.save(path)
        states[hyp] = st
        comparisons[hyp] = compare_with_backtest(st, markets)
    if stale:
        notes.append("Nieświeże dane, nic nie zaksięgowano: " + "; ".join(stale))
    write_report(out_dir / "RAPORT_PAPER_SERIA2.md", states, comparisons, notes, verdicts)
    return {"states": states, "comparisons": comparisons, "stale": stale}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prog-hamulca", dest="threshold", type=float, required=True,
                    help="próg hamulca obsunięcia jako ułamek (ustala Karol), np. 0.2")
    ap.add_argument("--start", help="dzień startu paper RRRR-MM-DD (tylko przy pierwszym uruchomieniu)")
    ap.add_argument("--dzien", help="dzień serwera dla kontroli świeżości (domyślnie bieżący, UTC+2)")
    ap.add_argument("--dane", type=Path, default=DATA_DIR)
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass
    try:
        out = run(threshold=a.threshold, start=a.start, today=a.dzien or server_today(), data_dir=a.dane)
    except ValidationError as exc:
        print(f"Odmowa: {exc}")
        return 2
    print(f"Raport: {OUT_DIR / 'RAPORT_PAPER_SERIA2.md'}")
    return 1 if out["stale"] else 0


if __name__ == "__main__":
    sys.exit(main())
