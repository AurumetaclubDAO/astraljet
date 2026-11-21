# -*- coding: utf-8 -*-
"""Próba drogi zleceń na koncie DEMO (MT5): łączność i blokady, nie test strategii.

Zgoda Karola z 21.11.2026: „Tak, testuj zlecenia”, „Tak, pisz próbę”, „go” (plan z uwagami koordynatora).
Skrypt uruchamia wyłącznie Karol. Bez flagi --wyslij-na-demo wykonuje tylko część bez brokera
(kroki 0–1). Z flagą wysyła najwyżej DWA zlecenia: kupno i zamknięcie najmniejszej pozycji ETHUSD.

Przebieg (zatrzymanie na pierwszym nieoczekiwanym wyniku, bez pętli ponowień):
  0. Start tylko przy czystym stanie: rachunek DEMO (numer i serwer z lokalnego pliku poza Git),
     Algo Trading włączone, ETHUSD w Market Watch, brak pozycji z magic próby, brak niedokończonych
     intencji i wyłącznika awaryjnego w bazie próby, ponad 15 min do startu kolektora ticków.
  1. Blokady bez wysyłania: wyłącznik awaryjny zatrzymuje zlecenie; zlecenie ponad limit jest
     odrzucane, a jego ponowienie przechodzi przez bramkę jeszcze raz (znowu odmowa).
  --- dalej tylko z flagą --wyslij-na-demo ---
  2. Kupno najmniejszego lota (1. zlecenie).
  3. Ta sama intencja drugi raz: odmowa (nowy klucz) albo DUPLICATE (ten sam klucz), bez wysyłania.
  4. Odczyt pozycji po tickecie z wyniku order_send i magic.
  5. Zamknięcie: sprzedaż z position=<ticket> (rachunek hedge) - 2. zlecenie.
  6. Uzgodnienie: brak pozycji o tym tickecie i brak jakiejkolwiek pozycji z magic próby.
  7. Przerwane uzgodnienie: symulowany błąd połączenia przy order_send (nic nie idzie do brokera)
     zostawia stan uncertain; nowe zlecenie jest blokowane; uzgodnienie stwierdza brak deala.
Baza próby (trwała, z wyłącznikiem awaryjnym): .runtime/demo-probe/state/
Raport bez numeru rachunku, salda i serwera: .runtime/demo-probe/<czas>/RAPORT_PROBY.md

Wykrycie rachunku innego niż DEMO: rozłączenie, wyłącznik awaryjny w bazie próby i trwały znacznik
.runtime/demo-probe/STOP_RACHUNEK_INNY_NIZ_DEMO.txt. Dopóki znacznik istnieje, skrypt odmawia jeszcze przed
połączeniem z terminalem; zdejmuje go tylko Karol, ręcznie (wraz z katalogiem state/).
Wszystkie odczyty skryptu idą przez twardą listę wywołań adaptera; pozycje i historia tylko po sprawdzeniu
rachunku.

Użycie (Algo Trading w terminalu DEMO włączone, terminal już działa):
    $env:MT5_TERMINAL = 'C:\\Program Files\\Vantage Markets MT5 Terminal\\terminal64.exe'
    research\\scalp-smc\\.venv\\Scripts\\python.exe scripts\\demo_order_probe.py                    (bez brokera)
    research\\scalp-smc\\.venv\\Scripts\\python.exe scripts\\demo_order_probe.py --wyslij-na-demo   (z brokerem)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from astraljet.application.mandates import MandateRequest, create_mandate  # noqa: E402
from astraljet.domain.enums import (  # noqa: E402
    ExecutionEnvironment, ExecutionResultState, RiskDecisionStatus, TechnicalStatus,
)
from astraljet.domain.errors import DomainBlockedError  # noqa: E402
from astraljet.domain.records import RiskDecisionRecord  # noqa: E402
from astraljet.executor.guard import ExecutorGuard  # noqa: E402
from astraljet.executor.mt5_demo import PROBE_MAGIC, DemoAccountRule, MT5DemoAdapter  # noqa: E402
from astraljet.executor.ports import FrozenContext, OrderIntent  # noqa: E402
from astraljet.infrastructure.database import Database  # noqa: E402

ACCOUNTS = ROOT / ".runtime" / "dashboard" / "accounts.toml"
PROBE_DIR = ROOT / ".runtime" / "demo-probe"
STATE_DIR = PROBE_DIR / "state"
KNOWN_TERMINALS = (
    r"C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe",
    r"E:\MT5-DEMO\Vantage\terminal64.exe",
)
COLLECTOR_TASK = "AstraJet-MT5-TickCollector"
SYMBOL = "ETHUSD"
LABEL = "DEMO-PROJEKT"
ENV, KILL_ENV = "demo-probe", "demo-probe-kill"
MAX_PROBE_NOTIONAL = Decimal("200")  # górna granica wartości jednej pozycji próby (USD)
SEND_FLAG = "--wyslij-na-demo"
# Trwały znacznik po wykryciu rachunku innego niż DEMO; dopóki istnieje, skrypt odmawia przed initialize().
LIVE_MARKER = PROBE_DIR / "STOP_RACHUNEK_INNY_NIZ_DEMO.txt"


def write_live_marker(path: Path | None, stage: str) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC: terminal byl zalogowany na rachunek inny niz "
                    f"DEMO ({stage}). Proba zablokowana. Usun ten plik recznie (tylko Karol) po sprawdzeniu terminala.\n",
                    encoding="utf-8")


class ProbeStop(Exception):
    pass


@dataclass
class Report:
    lines: list[str] = field(default_factory=list)
    open_ticket: int | None = None
    sent: int = 0
    closed: bool = False  # pozycja próby potwierdzona jako zamknięta (krok 6)
    warning: str | None = None  # ostrzeżenie po przerwanym przebiegu z wysłanym zleceniem
    partial: bool = False  # wynik order_send 10010 (wykonanie częściowe)

    def step(self, name: str, result: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        self.lines.append(f"| {stamp} | {name} | {result} |")
        try:  # błąd wydruku (strona kodowa konsoli) nie może przerwać próby
            print(f"{stamp} UTC  {name}: {result}", flush=True)
        except Exception:  # noqa: BLE001
            pass


class CountingSDK:
    """Liczy order_send; krok 7 symuluje błąd połączenia BEZ wywołania brokera. Nic więcej nie zmienia."""

    def __init__(self, sdk) -> None:
        self._sdk, self.sends, self.fail_next_send = sdk, 0, False

    def order_send(self, request):
        if self.fail_next_send:
            self.fail_next_send = False
            raise ConnectionError("symulowany błąd połączenia (próba; nic nie wysłano)")
        self.sends += 1
        return self._sdk.order_send(request)

    def __getattr__(self, name):
        return getattr(self._sdk, name)


# ---------- warunki startu ----------

def load_rule(path: Path = ACCOUNTS) -> DemoAccountRule:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    login, server = raw.get("demo_login"), raw.get("demo_server")
    if type(login) is not int or not isinstance(server, str) or not server:
        raise ProbeStop("Brak demo_login lub demo_server w lokalnym accounts.toml.")
    return DemoAccountRule(label=LABEL, login=login, server=server)


def check_terminal(path: str | None) -> None:
    norm = lambda p: os.path.normcase(os.path.abspath(p))  # noqa: E731
    if not path or norm(path) not in {norm(p) for p in KNOWN_TERMINALS}:
        raise ProbeStop("MT5_TERMINAL musi wskazywać znaną instalację terminala.")
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-Process terminal64 -ErrorAction SilentlyContinue | ForEach-Object { $_.Path }"],
                         capture_output=True, text=True, timeout=30)
    running = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    if sum(1 for p in running if norm(p) == norm(path)) != 1:
        raise ProbeStop("Terminal nie działa jako dokładnie jeden proces; skrypt go nie uruchamia.")


def collector_problem(now_local: datetime, next_run: datetime | None, state: str | None) -> str | None:
    """Odmowa, gdy kolektor ticków pracuje albo startuje za mniej niż 15 minut."""
    if state == "Running":
        return "kolektor ticków właśnie pracuje"
    if next_run is not None and timedelta(0) <= next_run - now_local < timedelta(minutes=15):
        return f"kolektor ticków startuje o {next_run:%H:%M} (mniej niż 15 min)"
    return None


def collector_status() -> tuple[datetime | None, str | None]:
    script = (f"$t = Get-ScheduledTask -TaskName '{COLLECTOR_TASK}' -ErrorAction Stop; "
              "$i = $t | Get-ScheduledTaskInfo; "
              "@{state=[string]$t.State; next=$i.NextRunTime.ToString('o')} | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    if out.returncode:
        raise ProbeStop("Nie udało się odczytać harmonogramu kolektora ticków.")
    data = json.loads(out.stdout)
    nxt = datetime.fromisoformat(data["next"]) if data.get("next") else None
    return (nxt.replace(tzinfo=None) if nxt else None), data.get("state")


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_mandate(env_id: str, now: datetime, limits: dict, code_hash: str):
    start, end = now - timedelta(minutes=1), now + timedelta(hours=1)
    risk = RiskDecisionRecord(
        record_id="RISK_DECISION-DEMOPROBE", version=1, owner="Karol", created_at=iso(now),
        technical_status=TechnicalStatus.COMPLETED, content_hash=code_hash, limitations=("Tylko próba DEMO.",),
        review_id="REVIEW-DEMOPROBE", scope="próba łączności i blokad na koncie DEMO",
        valid_from=iso(start), valid_until=iso(end + timedelta(minutes=1)), limits=limits,
        decision=RiskDecisionStatus.ALLOWED, rationale="Zgoda Karola z 21.11.2026: testuj zlecenia na DEMO.",
        permitted_next_step="jedna najmniejsza pozycja ETHUSD: kupno i zamknięcie", blockers=())
    mandate = create_mandate(risk_decision=risk, owner="Karol", request=MandateRequest(
        authorized_by="Karol", strategy_id="STRAT-DEMOPROBE", strategy_version=1, code_hash=code_hash,
        environment=ExecutionEnvironment.BROKER_DEMO, environment_id=env_id, account_id=LABEL,
        instruments=(SYMBOL,), limits=limits, starts_at=iso(start), expires_at=iso(end),
        stop_conditions=("kill switch", "nieoczekiwany wynik", "rachunek inny niż DEMO"), max_data_age_seconds=60))
    return risk, mandate


# ---------- próba ----------

def run_probe(sdk, rule: DemoAccountRule, state_dir: Path, *, send: bool = False,
              now_fn=lambda: datetime.now(timezone.utc), report: Report | None = None,
              live_marker: Path | None = None) -> Report:
    """Przebieg próby. Licznik wysłanych zleceń i ostrzeżenie o możliwej pozycji trafiają do raportu
    także wtedy, gdy przebieg przerwie wyjątek (np. odmowa bramki po order_send)."""
    report = report or Report()
    counting = CountingSDK(sdk)
    db = Database.from_state_dir(state_dir)
    db.initialize()
    guard = ExecutorGuard(db)
    adapter = MT5DemoAdapter(db, guard, counting, rule, symbols=(SYMBOL,))
    start = now_fn()
    run_id = start.strftime("%Y%m%d%H%M%S%f")
    keys = {"open": f"open-{run_id}", "close": f"close-{run_id}"}
    failed = True
    try:
        _steps(report, counting, guard, adapter, keys, run_id, start, send, now_fn, live_marker)
        failed = False
        return report
    finally:
        _settle(report, counting, adapter, keys, failed)


def _settle(report: Report, counting: CountingSDK, adapter: MT5DemoAdapter, keys: dict, failed: bool) -> None:
    report.sent = counting.sends
    responses = {}
    for name, key in keys.items():
        try:
            responses[name] = adapter.response(key)
        except Exception:  # noqa: BLE001 - raport musi powstać mimo błędu bazy
            responses[name] = {}
    report.partial = any(r.get("retcode") == 10010 for r in responses.values())
    if not report.closed and report.open_ticket is None and responses["open"].get("order"):
        report.open_ticket = int(responses["open"]["order"])
    if failed and counting.sends > 0 and not report.closed:
        order = report.open_ticket or "brak w bazie próby"
        report.warning = (f"Przebieg przerwany po wysłaniu {counting.sends} zlecenia(ń). Numer zlecenia kupna: {order}. "
                          f"Na koncie DEMO może być otwarta pozycja z magic {PROBE_MAGIC}: sprawdź i zamknij ją ręcznie; "
                          "skrypt nie próbuje ponownie."
                          + (" Wynik 10010: zlecenie mogło zostać wykonane częściowo." if report.partial else ""))


def _steps(report, counting, guard, adapter, keys, run_id, start, send, now_fn, live_marker) -> None:
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def expect(name: str, ok: bool, result: str) -> None:
        report.sent = counting.sends
        report.step(name, result)
        if not ok:
            raise ProbeStop(f"Nieoczekiwany wynik w kroku: {name}")

    def blocker(call) -> str:
        try:
            call()
        except DomainBlockedError as exc:
            return exc.blocker
        return "BRAK ODMOWY"

    ro = adapter.sdk  # własne odczyty skryptu także przez twardą listę wywołań (OrderSDK)

    def own_positions(stage: str):
        adapter.require_demo(ENV, "probe-worker", stage)  # rachunek przed każdym odczytem pozycji
        return [p for p in (ro.positions_get() or ()) if int(p.magic) == PROBE_MAGIC]

    # 0. czysty stan
    with adapter.database.connect() as connection:
        kill = connection.execute("SELECT active FROM kill_switches WHERE environment_id = ?", (ENV,)).fetchone()
        unfinished = connection.execute("SELECT COUNT(*) AS n FROM execution_intents WHERE environment_id = ? "
                                        "AND state = 'uncertain'", (ENV,)).fetchone()["n"]
    expect("0. wyłącznik awaryjny próby", not (kill and kill["active"]),
           "aktywny - zdejmuje go tylko Karol (usuń .runtime/demo-probe/state po sprawdzeniu)" if kill and kill["active"]
           else "nieaktywny")
    expect("0. niedokończone intencje w bazie próby", unfinished == 0, str(unfinished))
    problem = adapter._account_problem()
    if problem and problem[2]:  # rachunek inny niż DEMO: rozłączenie i trwały wyłącznik próby
        write_live_marker(live_marker, "krok 0")
        try:
            ro.shutdown()
        finally:
            guard.activate_kill_switch(ENV, reason="Rachunek inny niż DEMO wykryty przy starcie próby.",
                                       idempotency_key=f"probe-not-demo-{run_id}", now=now_fn())
        expect("0. rachunek DEMO", False, "terminal nie jest na rachunku DEMO - rozłączono, wyłącznik awaryjny włączony")
    health = adapter.health(type("M", (), {"environment": ExecutionEnvironment.BROKER_DEMO, "account_id": LABEL})())
    expect("0. rachunek DEMO i Algo Trading", health.state is ExecutionResultState.ACCEPTED, health.message)
    info, tick = ro.symbol_info(SYMBOL), ro.symbol_info_tick(SYMBOL)
    expect("0. symbol w Market Watch", info is not None and bool(info.visible) and tick is not None,
           "dostępny" if info is not None and info.visible else f"Dodaj {SYMBOL} ręcznie do Market Watch konta DEMO")
    leftover = own_positions("krok 0: pozycje z magic próby")
    expect("0. pozycje z magic próby", not leftover, str(len(leftover)))
    qty = Decimal(str(info.volume_min)) * Decimal(str(info.trade_contract_size))
    notional = qty * Decimal(str(tick.ask))
    expect("0. najmniejsza pozycja", notional <= MAX_PROBE_NOTIONAL,
           f"{qty.normalize()} {SYMBOL} (lot {info.volume_min}) ~ {notional:.2f} USD; spread {tick.ask - tick.bid:.2f}")
    adapter.require_demo(ENV, "probe-worker", "krok 0: wycena pozycji")
    existing = sum((Decimal(str(p.volume)) * Decimal(str(ro.symbol_info(p.symbol).trade_contract_size))
                    * Decimal(str(p.price_current)) for p in (ro.positions_get() or ())), Decimal("0"))
    cap = (notional * Decimal("1.5")).quantize(Decimal("0.01"))
    limits = {"max_notional": str(cap), "max_position_quantity": str(qty),
              "max_gross_exposure": str((existing + cap).quantize(Decimal("0.01")))}
    report.step("0. limity mandatu", f"max_notional {cap} USD, max_position_quantity {qty.normalize()}, "
                f"max_gross_exposure = inne pozycje na DEMO + {cap} USD")

    now = now_fn()
    risk, mandate = build_mandate(ENV, now, limits, code_hash)
    lease = guard.acquire_lease(ENV, "probe-worker", ttl_seconds=900, now=now)

    def ctx(m=mandate, r=risk, lease_id=lease.lease_id):
        return FrozenContext(mandate=m, risk_decision=r, strategy_id=m.strategy_id, strategy_version=m.strategy_version,
                             code_hash=m.code_hash, environment=m.environment, environment_id=m.environment_id,
                             worker_id="probe-worker", lease_id=lease_id, data_observed_at=iso(now_fn()))

    def intent(intent_id, side="buy", quantity=qty, signal=None):
        p = Decimal(str(ro.symbol_info_tick(SYMBOL).ask))
        return OrderIntent(intent_id=intent_id, instrument=SYMBOL, side=side, quantity=quantity, reference_price=p,
                           signal_id=signal or f"SIGNAL-{intent_id}")

    # 1a. wyłącznik awaryjny (osobne środowisko próby)
    k_risk, k_mandate = build_mandate(KILL_ENV, now, limits, code_hash)
    k_lease = guard.acquire_lease(KILL_ENV, "probe-worker", ttl_seconds=900, now=now)
    guard.activate_kill_switch(KILL_ENV, reason="próba: wyłącznik awaryjny", idempotency_key=f"kill-{run_id}",
                               now=now_fn())
    b = blocker(lambda: adapter.submit_intent(ctx(k_mandate, k_risk, k_lease.lease_id), intent(f"KILL-{run_id}"),
                                              idempotency_key=f"kill-intent-{run_id}", now=now_fn()))
    expect("1. wyłącznik awaryjny zatrzymuje zlecenie", b == "kill_switch_active" and counting.sends == 0, b)

    # 1b. odmowa ponad limit i ponowienie przez bramkę
    for attempt in (1, 2):
        b = blocker(lambda: adapter.submit_intent(ctx(), intent(f"BIG-{run_id}", quantity=qty * 100),
                                                  idempotency_key=f"big-{run_id}-{attempt}", now=now_fn()))
        expect(f"1. zlecenie ponad limit, próba {attempt}", b == "limit_exceeded" and counting.sends == 0, b)

    if not send:
        report.step("KONIEC (bez brokera)", f"wysłane zlecenia: {counting.sends}; do wysyłki potrzebna flaga {SEND_FLAG}")
        return

    # 2. kupno
    open_id, open_key = f"OPEN-{run_id}", keys["open"]
    t0 = time.perf_counter()
    receipt = adapter.submit_intent(ctx(), intent(open_id), idempotency_key=open_key, now=now_fn())
    ms = (time.perf_counter() - t0) * 1000
    resp = adapter.response(open_key)
    if resp.get("order"):
        report.open_ticket = int(resp["order"])
    expect("2. kupno (1. zlecenie)", receipt.state is ExecutionResultState.ACCEPTED and counting.sends == 1,
           f"{receipt.state.value}; cena żądana {resp.get('requested_price')}, wykonania {resp.get('fill_price')}, "
           f"różnica {_diff(resp)}; {ms:.0f} ms{_partial(resp)}")

    # 3. ta sama intencja drugi raz
    b = blocker(lambda: adapter.submit_intent(ctx(), intent(open_id, signal=f"SIGNAL-NEW-{run_id}"),
                                              idempotency_key=f"open-again-{run_id}", now=now_fn()))
    expect("3. ta sama intencja, nowy klucz", b == "duplicate_intent" and counting.sends == 1, b)
    again = adapter.submit_intent(ctx(), intent(open_id), idempotency_key=open_key, now=now_fn())
    expect("3. ta sama intencja, ten sam klucz", again.state is ExecutionResultState.DUPLICATE and counting.sends == 1,
           again.state.value)

    # 4. pozycja po tickecie z wyniku order_send (pierwszy klucz) i magic
    ticket = report.open_ticket
    adapter.ensure_demo(ctx(), "krok 4: odczyt pozycji")
    held = [p for p in (ro.positions_get(ticket=ticket) or ()) if int(p.magic) == PROBE_MAGIC]
    all_own = own_positions("krok 4: pozycje z magic próby")
    ok = (ticket is not None and len(held) == 1 and int(held[0].ticket) == int(ticket) and len(all_own) == 1
          and Decimal(str(held[0].volume)) == Decimal(str(info.volume_min)))
    expect("4. pozycja w terminalu", ok,
           f"ticket z wyniku {ticket}: {len(held)} pozycja, ticket pozycji {held[0].ticket if held else '-'}, "
           f"wolumen {held[0].volume if held else '-'}; pozycje z magic próby: {len(all_own)}")

    # 5. zamknięcie z position=<ticket> (rachunek hedge)
    close_key = keys["close"]
    t0 = time.perf_counter()
    receipt = adapter.submit_intent(ctx(), intent(f"CLOSE-{run_id}", side="sell"), idempotency_key=close_key,
                                    now=now_fn(), position_ticket=ticket)
    ms = (time.perf_counter() - t0) * 1000
    resp = adapter.response(close_key)
    expect("5. zamknięcie (2. zlecenie)", receipt.state is ExecutionResultState.ACCEPTED and counting.sends == 2,
           f"{receipt.state.value}; cena żądana {resp.get('requested_price')}, wykonania {resp.get('fill_price')}, "
           f"różnica {_diff(resp)}; {ms:.0f} ms{_partial(resp)}")

    # 6. uzgodnienie
    adapter.ensure_demo(ctx(), "krok 6: uzgodnienie")
    same = ro.positions_get(ticket=ticket) or ()
    left = own_positions("krok 6: pozycje z magic próby")
    if not same and not left:
        report.open_ticket, report.closed = None, True
    expect("6. uzgodnienie z terminalem", not same and not left,
           f"pozycja o tickecie {ticket}: {len(same)}; pozycje z magic próby: {len(left)}")

    # 7. przerwane uzgodnienie (błąd połączenia symulowany przed brokerem)
    counting.fail_next_send = True
    r = adapter.submit_intent(ctx(), intent(f"INT-{run_id}"), idempotency_key=f"int-{run_id}", now=now_fn())
    expect("7. błąd połączenia przy order_send", r.state is ExecutionResultState.UNCERTAIN and counting.sends == 2,
           f"{r.state.value}; nic nie wysłano")
    b = blocker(lambda: adapter.submit_intent(ctx(), intent(f"AFTER-{run_id}"), idempotency_key=f"after-{run_id}",
                                              now=now_fn()))
    expect("7. nowe zlecenie przy nierozstrzygniętej realizacji", b == "unresolved_execution" and counting.sends == 2, b)
    rec = adapter.reconcile(f"MT5D-INT-{run_id}", idempotency_key=f"rec-int-{run_id}", now=now_fn() + timedelta(hours=3),
                            since=start - timedelta(hours=3))
    expect("7. uzgodnienie przerwanej intencji", rec.state is ExecutionResultState.REJECTED and counting.sends == 2,
           f"{rec.state.value}: {rec.message}")
    report.step("KONIEC", f"wysłane zlecenia: {counting.sends} (oczekiwano 2)")


def _partial(resp: dict) -> str:
    return "; retcode 10010: zlecenie mogło zostać wykonane częściowo" if resp.get("retcode") == 10010 else ""


def _diff(resp: dict) -> str:
    try:
        return f"{float(resp['fill_price']) - float(resp['requested_price']):+.2f}"
    except (KeyError, TypeError, ValueError):
        return "-"


def write_report(report: Report, path: Path, error: str | None, send: bool) -> None:
    head = ["# Próba drogi zleceń na koncie DEMO", "",
            f"- Uruchomienie: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, `scripts/demo_order_probe.py`"
            + (f" {SEND_FLAG}." if send else " (bez brokera)."),
            "- Rachunek: DEMO (numer i serwer sprawdzone z lokalnym plikiem; nie są tu zapisane).",
            f"- Wysłane zlecenia: {report.sent}.",
            f"- Wynik: {'ZATRZYMANO - ' + error if error else 'wszystkie kroki zgodnie z oczekiwaniem'}."]
    if report.warning:
        head.append(f"- **UWAGA: {report.warning}**")
    elif report.open_ticket and not report.closed:
        head.append(f"- **UWAGA: na koncie DEMO została otwarta pozycja próby (ticket {report.open_ticket}, "
                    f"magic {PROBE_MAGIC}). Skrypt nie próbuje ponownie: zamknij ją ręcznie w terminalu.**")
    if report.partial and not report.warning:
        head.append("- Uwaga: wynik order_send 10010 - zlecenie mogło zostać wykonane częściowo.")
    body = ["", "| Czas UTC | Krok | Wynik |", "|---|---|---|", *report.lines]
    path.write_text("\n".join(head + body) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(SEND_FLAG, dest="send", action="store_true",
                    help="wyślij dwa zlecenia na konto DEMO (bez flagi: tylko część bez brokera)")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass
    out_dir = PROBE_DIR / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    report, error, sdk = Report(), None, None
    try:
        if LIVE_MARKER.exists():
            raise ProbeStop(f"Wcześniej wykryto rachunek inny niż DEMO: {LIVE_MARKER}. Zdejmuje go tylko Karol, ręcznie.")
        rule = load_rule()
        problem = collector_problem(datetime.now(), *collector_status())
        if problem:
            raise ProbeStop(f"Nie teraz: {problem}.")
        term = os.environ.get("MT5_TERMINAL")
        check_terminal(term)
        import MetaTrader5 as sdk_module
        sdk = sdk_module
        if not sdk.initialize(path=term):
            raise ProbeStop("initialize() nie powiodło się.")
        run_probe(sdk, rule, STATE_DIR, send=args.send, report=report, live_marker=LIVE_MARKER)
    except DomainBlockedError as exc:
        error = str(exc)
        if exc.blocker == "not_demo_account":
            write_live_marker(LIVE_MARKER, "w trakcie próby")
    except ProbeStop as exc:
        error = str(exc)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if sdk is not None:
            sdk.shutdown()
        write_report(report, out_dir / "RAPORT_PROBY.md", error, args.send)
        print(f"Raport: {out_dir / 'RAPORT_PROBY.md'}")
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
