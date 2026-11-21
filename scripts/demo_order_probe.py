# -*- coding: utf-8 -*-
"""Próba drogi zleceń na koncie DEMO (MT5): łączność i blokady, nie test strategii.

Zgoda Karola z 21.11.2026: „Tak, testuj zlecenia” i „Tak, pisz próbę”. Skrypt uruchamia wyłącznie
Karol. Wysyła najwyżej DWA zlecenia: otwarcie i zamknięcie najmniejszej pozycji ETHUSD.

Przebieg (zatrzymanie na pierwszym nieoczekiwanym wyniku, bez pętli ponowień):
  0. Odczyt: rachunek DEMO (numer i serwer z lokalnego pliku poza Git), symbol, najmniejszy lot, cena.
  1. Blokady bez wysyłania: włączony wyłącznik awaryjny zatrzymuje zlecenie; zlecenie ponad limit
     jest odrzucane i jego ponowienie przechodzi przez bramkę jeszcze raz (znowu odmowa).
  2. Otwarcie najmniejszej pozycji (1. zlecenie).
  3. Ta sama intencja drugi raz: odmowa (nowy klucz) albo DUPLICATE (ten sam klucz), bez wysyłania.
  4. Odczyt pozycji z terminala.
  5. Zamknięcie pozycji (2. zlecenie).
  6. Uzgodnienie: brak pozycji wykonawcy, oba deale w historii.
  7. Przerwane uzgodnienie: symulowana przerwa przed wysłaniem zostawia stan uncertain; nowe zlecenie
     jest blokowane; uzgodnienie stwierdza brak deala. Nic nie zostaje wysłane.
Raport bez numeru rachunku, salda i serwera: .runtime/demo-probe/<czas>/RAPORT_PROBY.md

Użycie (Algo Trading w terminalu DEMO musi być włączone, terminal musi już działać):
    $env:MT5_TERMINAL = 'C:\\Program Files\\Vantage Markets MT5 Terminal\\terminal64.exe'
    research\\scalp-smc\\.venv\\Scripts\\python.exe scripts\\demo_order_probe.py
"""
from __future__ import annotations

import hashlib
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
from astraljet.executor.mt5_demo import PROBE_MAGIC, DemoAccountRule, MT5DemoAdapter, _comment  # noqa: E402
from astraljet.executor.ports import FrozenContext, OrderIntent  # noqa: E402
from astraljet.infrastructure.database import Database  # noqa: E402

ACCOUNTS = ROOT / ".runtime" / "dashboard" / "accounts.toml"
KNOWN_TERMINALS = (
    r"C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe",
    r"E:\MT5-DEMO\Vantage\terminal64.exe",
)
SYMBOL = "ETHUSD"
LABEL = "DEMO-PROJEKT"
MAX_PROBE_NOTIONAL = Decimal("200")  # górna granica wartości jednej pozycji próby (USD)


class ProbeStop(Exception):
    pass


@dataclass
class Report:
    lines: list[str] = field(default_factory=list)
    open_ticket: int | None = None

    def step(self, name: str, result: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        self.lines.append(f"| {stamp} | {name} | {result} |")
        print(f"{stamp} UTC  {name}: {result}", flush=True)


class CountingSDK:
    """Liczy order_send i pozwala zasymulować przerwę przed wysłaniem (krok 7). Nic nie przepuszcza dodatkowo."""

    def __init__(self, sdk) -> None:
        self._sdk, self.sends, self.interrupt_next = sdk, 0, False

    def order_send(self, request):
        if self.interrupt_next:
            self.interrupt_next = False
            raise RuntimeError("symulowana przerwa przed wysłaniem (próba)")
        self.sends += 1
        return self._sdk.order_send(request)

    def __getattr__(self, name):
        return getattr(self._sdk, name)


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
        permitted_next_step="jedna najmniejsza pozycja ETHUSD: otwarcie i zamknięcie", blockers=())
    mandate = create_mandate(risk_decision=risk, owner="Karol", request=MandateRequest(
        authorized_by="Karol", strategy_id="STRAT-DEMOPROBE", strategy_version=1, code_hash=code_hash,
        environment=ExecutionEnvironment.BROKER_DEMO, environment_id=env_id, account_id=LABEL,
        instruments=(SYMBOL,), limits=limits, starts_at=iso(start), expires_at=iso(end),
        stop_conditions=("kill switch", "nieoczekiwany wynik", "rachunek inny niż DEMO"), max_data_age_seconds=60))
    return risk, mandate


def run_probe(sdk, rule: DemoAccountRule, state_dir: Path, now_fn=lambda: datetime.now(timezone.utc),
              report: Report | None = None) -> Report:
    report = report or Report()
    counting = CountingSDK(sdk)
    db = Database.from_state_dir(state_dir)
    db.initialize()
    guard = ExecutorGuard(db)
    adapter = MT5DemoAdapter(db, guard, counting, rule)
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    start = now_fn()

    def expect(name: str, ok: bool, result: str) -> None:
        report.step(name, result)
        if not ok:
            raise ProbeStop(f"Nieoczekiwany wynik w kroku: {name}")

    def blocker(call) -> str:
        try:
            call()
        except DomainBlockedError as exc:
            return exc.blocker
        return "BRAK ODMOWY"

    # 0. odczyt
    health = adapter.health(type("M", (), {"environment": ExecutionEnvironment.BROKER_DEMO, "account_id": LABEL})())
    expect("0. rachunek DEMO i Algo Trading", health.state is ExecutionResultState.ACCEPTED, health.message)
    info, tick = counting.symbol_info(SYMBOL), counting.symbol_info_tick(SYMBOL)
    if info is None or not info.visible or tick is None:
        expect("0. symbol", False, f"{SYMBOL} niedostępny w Market Watch albo bez ceny")
    qty = Decimal(str(info.volume_min)) * Decimal(str(info.trade_contract_size))
    price = Decimal(str(tick.ask))
    notional = qty * price
    expect("0. najmniejsza pozycja", notional <= MAX_PROBE_NOTIONAL,
           f"{qty.normalize()} {SYMBOL} (lot {info.volume_min}) ≈ {notional:.2f} USD; spread {tick.ask - tick.bid:.2f}")
    existing = sum((Decimal(str(p.volume)) * Decimal(str(counting.symbol_info(p.symbol).trade_contract_size))
                    * Decimal(str(p.price_current)) for p in (counting.positions_get() or ())), Decimal("0"))
    cap = (notional * Decimal("1.5")).quantize(Decimal("0.01"))
    limits = {"max_notional": str(cap), "max_position_quantity": str(qty),
              "max_gross_exposure": str((existing + cap).quantize(Decimal("0.01")))}
    report.step("0. limity mandatu", f"max_notional {cap} USD, max_position_quantity {qty.normalize()}, "
                f"max_gross_exposure = inne pozycje na DEMO + {cap} USD")

    now = now_fn()
    risk, mandate = build_mandate("demo-probe", now, limits, code_hash)
    lease = guard.acquire_lease("demo-probe", "probe-worker", ttl_seconds=900, now=now)

    def ctx(m=mandate, r=risk, lease_id=lease.lease_id):
        return FrozenContext(mandate=m, risk_decision=r, strategy_id=m.strategy_id, strategy_version=m.strategy_version,
                             code_hash=m.code_hash, environment=m.environment, environment_id=m.environment_id,
                             worker_id="probe-worker", lease_id=lease_id, data_observed_at=iso(now_fn()))

    def intent(intent_id, side="buy", quantity=qty, signal=None):
        p = Decimal(str((counting.symbol_info_tick(SYMBOL).ask)))
        return OrderIntent(intent_id=intent_id, instrument=SYMBOL, side=side, quantity=quantity, reference_price=p,
                           signal_id=signal or f"SIGNAL-{intent_id}")

    run_id = start.strftime("%Y%m%d%H%M%S")

    # 1a. wyłącznik awaryjny (osobne środowisko)
    k_risk, k_mandate = build_mandate("demo-probe-kill", now, limits, code_hash)
    k_lease = guard.acquire_lease("demo-probe-kill", "probe-worker", ttl_seconds=900, now=now)
    guard.activate_kill_switch("demo-probe-kill", reason="próba: wyłącznik awaryjny", idempotency_key=f"kill-{run_id}",
                               now=now_fn())
    b = blocker(lambda: adapter.submit_intent(ctx(k_mandate, k_risk, k_lease.lease_id), intent(f"KILL-{run_id}"),
                                              idempotency_key=f"kill-intent-{run_id}", now=now_fn()))
    expect("1. wyłącznik awaryjny zatrzymuje zlecenie", b == "kill_switch_active" and counting.sends == 0, b)

    # 1b. odmowa ponad limit i ponowienie przez bramkę
    big = qty * 100
    for attempt in (1, 2):
        b = blocker(lambda: adapter.submit_intent(ctx(), intent(f"BIG-{run_id}", quantity=big),
                                                  idempotency_key=f"big-{run_id}-{attempt}", now=now_fn()))
        expect(f"1. zlecenie ponad limit, próba {attempt}", b == "limit_exceeded" and counting.sends == 0, b)

    # 2. otwarcie
    open_id, open_key = f"OPEN-{run_id}", f"open-{run_id}"
    t0 = time.perf_counter()
    receipt = adapter.submit_intent(ctx(), intent(open_id), idempotency_key=open_key, now=now_fn())
    ms = (time.perf_counter() - t0) * 1000
    resp = adapter.response(open_key)
    if receipt.state is ExecutionResultState.ACCEPTED:
        report.open_ticket = int(resp.get("order", 0)) or None
    expect("2. otwarcie (1. zlecenie)", receipt.state is ExecutionResultState.ACCEPTED and counting.sends == 1,
           f"{receipt.state.value}; cena żądana {resp.get('requested_price')}, wykonania {resp.get('fill_price')}, "
           f"różnica {_diff(resp)}; {ms:.0f} ms")

    # 3. ta sama intencja drugi raz
    b = blocker(lambda: adapter.submit_intent(ctx(), intent(open_id, signal=f"SIGNAL-NEW-{run_id}"),
                                              idempotency_key=f"open-again-{run_id}", now=now_fn()))
    expect("3. ta sama intencja, nowy klucz", b == "duplicate_intent" and counting.sends == 1, b)
    again = adapter.submit_intent(ctx(), intent(open_id), idempotency_key=open_key, now=now_fn())
    expect("3. ta sama intencja, ten sam klucz", again.state is ExecutionResultState.DUPLICATE and counting.sends == 1,
           again.state.value)

    # 4. odczyt pozycji
    own = [p for p in (counting.positions_get() or ()) if int(p.magic) == PROBE_MAGIC
           and str(getattr(p, "comment", _comment(open_id))) in (_comment(open_id), "")]
    expect("4. pozycja w terminalu", len(own) == 1 and Decimal(str(own[0].volume)) == Decimal(str(info.volume_min)),
           f"{len(own)} pozycja wykonawcy, wolumen {own[0].volume if own else '—'}")
    ticket = int(own[0].ticket)
    report.open_ticket = ticket

    # 5. zamknięcie
    close_key = f"close-{run_id}"
    t0 = time.perf_counter()
    receipt = adapter.submit_intent(ctx(), intent(f"CLOSE-{run_id}", side="sell"), idempotency_key=close_key,
                                    now=now_fn(), position_ticket=ticket)
    ms = (time.perf_counter() - t0) * 1000
    resp = adapter.response(close_key)
    if receipt.state is ExecutionResultState.ACCEPTED:
        report.open_ticket = None
    expect("5. zamknięcie (2. zlecenie)", receipt.state is ExecutionResultState.ACCEPTED and counting.sends == 2,
           f"{receipt.state.value}; cena żądana {resp.get('requested_price')}, wykonania {resp.get('fill_price')}, "
           f"różnica {_diff(resp)}; {ms:.0f} ms")

    # 6. uzgodnienie
    left = [p for p in (counting.positions_get() or ()) if int(p.magic) == PROBE_MAGIC]
    deals = [d for d in (counting.history_deals_get(start - timedelta(hours=3), now_fn() + timedelta(hours=3)) or ())
             if int(d.magic) == PROBE_MAGIC]
    expect("6. uzgodnienie z terminalem", not left and len(deals) >= 2,
           f"pozycje wykonawcy: {len(left)}; deale z magic próby: {len(deals)}")

    # 7. przerwane uzgodnienie
    counting.interrupt_next = True
    try:
        adapter.submit_intent(ctx(), intent(f"INT-{run_id}"), idempotency_key=f"int-{run_id}", now=now_fn())
        expect("7. symulowana przerwa", False, "brak przerwy")
    except RuntimeError:
        report.step("7. symulowana przerwa przed wysłaniem", "intencja zapisana jako uncertain, nic nie wysłano")
    b = blocker(lambda: adapter.submit_intent(ctx(), intent(f"AFTER-{run_id}"), idempotency_key=f"after-{run_id}",
                                              now=now_fn()))
    expect("7. nowe zlecenie przy nierozstrzygniętej realizacji", b == "unresolved_execution" and counting.sends == 2, b)
    rec = adapter.reconcile(f"MT5D-INT-{run_id}", idempotency_key=f"rec-int-{run_id}", now=now_fn() + timedelta(hours=3),
                            since=start - timedelta(hours=3))
    expect("7. uzgodnienie przerwanej intencji", rec.state is ExecutionResultState.REJECTED and counting.sends == 2,
           f"{rec.state.value}: {rec.message}")
    report.step("KONIEC", f"wysłane zlecenia: {counting.sends} (oczekiwano 2)")
    return report


def _diff(resp: dict) -> str:
    try:
        return f"{float(resp['fill_price']) - float(resp['requested_price']):+.2f}"
    except (KeyError, TypeError, ValueError):
        return "—"


def write_report(report: Report, path: Path, error: str | None) -> None:
    head = ["# Próba drogi zleceń na koncie DEMO", "",
            f"- Uruchomienie: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, `scripts/demo_order_probe.py`.",
            "- Rachunek: DEMO (numer i serwer sprawdzone z lokalnym plikiem; nie są tu zapisane).",
            f"- Wynik: {'ZATRZYMANO — ' + error if error else 'wszystkie kroki zgodnie z oczekiwaniem'}."]
    if report.open_ticket:
        head.append(f"- **UWAGA: w terminalu DEMO może zostać otwarta pozycja próby (ticket {report.open_ticket}, "
                    f"magic {PROBE_MAGIC}). Zamknij ją ręcznie.**")
    body = ["", "| Czas UTC | Krok | Wynik |", "|---|---|---|", *report.lines]
    path.write_text("\n".join(head + body) + "\n", encoding="utf-8")


def main() -> int:
    state_dir = ROOT / ".runtime" / "demo-probe" / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    state_dir.mkdir(parents=True, exist_ok=True)
    report, error = Report(), None
    sdk = None
    try:
        rule = load_rule()
        term = os.environ.get("MT5_TERMINAL")
        check_terminal(term)
        import MetaTrader5 as sdk_module
        sdk = sdk_module
        if not sdk.initialize(path=term):
            raise ProbeStop("initialize() nie powiodło się.")
        run_probe(sdk, rule, state_dir, report=report)
    except (ProbeStop, DomainBlockedError) as exc:
        error = str(exc)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if sdk is not None:
            sdk.shutdown()
        write_report(report, state_dir / "RAPORT_PROBY.md", error)
        print(f"Raport: {state_dir / 'RAPORT_PROBY.md'}")
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
