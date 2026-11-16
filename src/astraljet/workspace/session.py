"""Sesja Workspace: jedno źródło stanu i jeden snapshot dla wszystkich widoków.

Każda akcja zmienia stan, zwiększa wersję i zwraca nowy snapshot, z którego wykres,
plan, ryzyko, pozycje, triggery, przegląd i widgety są renderowane jednocześnie.
Rynek, rachunek i broker są SYMULOWANE.
"""

from __future__ import annotations

import random
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from . import __version__
from .analytics import ReviewFilter, review
from .execution import OrderService
from .instruments import (
    D, FxRate, FxTable, InstrumentSpec, Side, eurusd_example, index_example, usdjpy_example, xauusd_example,
)
from .market import Candle, CandleSeries, DataMode, Freshness, Quote, Timeframe, assess_quote, synthetic_series, utc
from .model import MarginMode, OrderRequest, RequestKind, RequestState
from .plan import CostModel, OrderType, TradePlan, evaluate_plan
from .protection import BreakEvenRule, ProtectionState, RuleState, TrailingRule, protection_view
from .settings import UISettings, apply_ui_settings
from .simulator import Behaviour, ScriptStep, SimulatedBroker
from .trigger import Cross, Line, PriceSource, TrendTrigger, TriggerState
from .widgets import candle_timer, indicators, margin_usage, risk_to_sl, spread

START_PRICES = {"EURUSD": Decimal("1.15438"), "USDJPY": Decimal("154.320"), "XAUUSD": Decimal("2650.00"),
                "US500": Decimal("5900.00")}
SPREAD_POINTS = {"EURUSD": 8, "USDJPY": 12, "XAUUSD": 25, "US500": 50}
VOLATILITY = {"EURUSD": 40, "USDJPY": 40, "XAUUSD": 120, "US500": 100}


@dataclass(slots=True)
class SimClock:
    current: datetime

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current = self.current + timedelta(seconds=seconds)


def chart_range(prices: list[Decimal], pad_ratio: Decimal = Decimal("0.06")) -> tuple[Decimal, Decimal]:
    """Zakres osi obejmujący świece ORAZ wszystkie poziomy planu i pozycji."""
    lo, hi = min(prices), max(prices)
    if hi == lo:
        hi = lo + Decimal(1)
    pad = (hi - lo) * pad_ratio
    return lo - pad, hi + pad


def price_to_y(price: Decimal, lo: Decimal, hi: Decimal, height: Decimal) -> Decimal:
    """Ta sama formuła jest używana w przeglądarce (app.js: yOf)."""
    return (D(hi) - D(price)) / (D(hi) - D(lo)) * D(height)


@dataclass
class WorkspaceSession:
    seed: int = 7
    clock: SimClock = field(default_factory=lambda: SimClock(datetime.now(timezone.utc).replace(microsecond=0)))
    quote_ttl_s: float = 30
    version: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.specs: dict[str, InstrumentSpec] = {
            s.symbol: s for s in (eurusd_example(stops_level_points=10), usdjpy_example(), xauusd_example(), index_example())
        }
        self.fx = FxTable()
        self.broker = SimulatedBroker(
            account_id="SIM-001", currency="USD", margin_mode=MarginMode.HEDGING, specs=self.specs, fx=self.fx,
            now=self.clock, commission_per_lot_side=Decimal("3.50"),
        )
        self.costs = CostModel(Decimal("3.50"), "SIMULATED: prowizja symulatora 3,50 USD/lot/strona")
        self.orders = OrderService(self.broker, now=self.clock)
        self.broker.deposit(Decimal("10000"), self.clock() - timedelta(days=1))
        self.market_price = dict(START_PRICES)
        self.last_quote: dict[str, Quote] = {}
        self.symbol = "EURUSD"
        self.timeframe = Timeframe.M15
        self.series: dict[tuple[str, Timeframe], CandleSeries] = {}
        self.plan = TradePlan("SIM-001", "EURUSD", Side.BUY, Decimal("0.01"), OrderType.MARKET,
                              entry=None, sl=Decimal("1.13949"), tp=Decimal("1.16505"))
        self.protections: dict[str, ProtectionState] = {}
        self.triggers: dict[str, TrendTrigger] = {}
        self.ui = UISettings()
        self.review_filter = ReviewFilter()
        self.events: list[dict] = []
        self._mod_counter = 0
        for symbol in self.specs:
            self._publish_quote(symbol)
        self._ensure_series(self.symbol, self.timeframe)

    # --- rynek symulowany ---------------------------------------------------
    def _quote_for(self, symbol: str) -> Quote:
        spec = self.specs[symbol]
        mid = spec.normalize_price(self.market_price[symbol])
        half = spec.from_points(SPREAD_POINTS[symbol]) / 2
        bid = spec.normalize_price(mid - half)
        ask = spec.normalize_price(bid + spec.from_points(SPREAD_POINTS[symbol]))
        return Quote(symbol, bid, ask, self.clock(), "SIMULATED: generator sesji", DataMode.SIMULATED)

    def _publish_quote(self, symbol: str) -> None:
        quote = self._quote_for(symbol)
        closed = self.broker.set_quote(quote)  # broker widzi rynek nawet bez połączenia Workspace
        for deal in closed:
            self._event("broker", f"Pozycja {deal.position_id} zamknięta przez SL/TP po {deal.price}.")
        if symbol == "USDJPY":
            mid = (quote.bid + quote.ask) / 2
            self.fx.add(FxRate("USD", "JPY", mid, "SIMULATED: mid USDJPY", utc(quote.time).isoformat()))
        if self.broker.connected:
            self.last_quote[symbol] = quote
        for key, series in self.series.items():
            if key[0] == symbol:
                series.update_with_price((quote.bid + quote.ask) / 2, quote.time)

    def _ensure_series(self, symbol: str, timeframe: Timeframe) -> CandleSeries:
        key = (symbol, timeframe)
        if key not in self.series:
            spec = self.specs[symbol]
            series = synthetic_series(spec, timeframe, self.clock(), 120, self.market_price[symbol],
                                      seed=self.seed * 1000 + list(self.specs).index(symbol) * 10 + list(Timeframe).index(timeframe),
                                      volatility_points=VOLATILITY[symbol])
            shift = spec.normalize_price(self.market_price[symbol]) - series.candles[-1].close

            series.candles = [Candle(c.time, c.open + shift, c.high + shift, c.low + shift, c.close + shift)
                              for c in series.candles]
            self.series[key] = series
        return self.series[key]

    def _event(self, kind: str, message: str) -> None:
        self.events.append({"at": utc(self.clock()).isoformat(), "kind": kind, "message": message})
        del self.events[:-80]

    def _fresh(self, symbol: str) -> bool:
        status = assess_quote(self.last_quote.get(symbol), self.clock(), self.quote_ttl_s, self.broker.connected)
        return status.state is Freshness.CONFIRMED

    # --- pętla kroku --------------------------------------------------------
    def step(self, n: int = 1, seconds: int = 20, drift_points: dict[str, int] | None = None) -> None:
        for _ in range(max(1, min(int(n), 500))):
            self.clock.advance(seconds)
            for symbol, spec in self.specs.items():
                move = (drift_points or {}).get(symbol)
                if move is None:
                    move = self.rng.randint(-VOLATILITY[symbol], VOLATILITY[symbol])
                self.market_price[symbol] = spec.normalize_price(self.market_price[symbol] + spec.from_points(move))
                self._publish_quote(symbol)
            self._after_market()

    def _after_market(self) -> None:
        if not self.broker.connected:
            return
        self._reconcile_pending()
        self._run_triggers()
        self._run_protection()

    def _reconcile_pending(self) -> None:
        for record in self.orders.reconcile_all():
            self._sync_protection_outcome(record.request.request_id)

    def _run_triggers(self) -> None:
        for trg in self.triggers.values():
            quote = self.last_quote.get(trg.symbol)
            if quote is None:
                continue
            fire = trg.observe(quote.bid, quote.ask, self.clock(), self._fresh(trg.symbol))
            if fire is None:
                continue
            spec = self.specs[fire.symbol]
            ref = quote.ask if fire.side is Side.BUY else quote.bid
            sl = None if fire.sl_points is None else spec.normalize_price(ref - fire.side.sign * spec.from_points(fire.sl_points))
            tp = None if fire.tp_points is None else spec.normalize_price(ref + fire.side.sign * spec.from_points(fire.tp_points))
            req = OrderRequest(fire.request_id, "SIM-001", RequestKind.OPEN, fire.symbol, fire.side, fire.volume,
                               sl=sl, tp=tp, origin=f"trigger:{fire.trigger_id}", created_at=utc(self.clock()).isoformat())
            rec = self.orders.submit(req)
            self._event("trigger", f"Trigger {fire.trigger_id} wyzwolony; żądanie {req.request_id}: {rec.state.value}.")

    def _run_protection(self) -> None:
        positions = {p.position_id: p for p in self.broker.positions()}
        for pid in list(self.protections):
            if pid not in positions:
                del self.protections[pid]
        for pid, state in self.protections.items():
            pos = positions[pid]
            quote = self.last_quote.get(pos.symbol)
            if quote is None:
                continue
            proposal = state.evaluate(pos, self.specs[pos.symbol], quote.bid, quote.ask, self._fresh(pos.symbol))
            if proposal is not None:
                self._send_sl(pos, proposal, state)

    def _send_sl(self, pos, proposal, state: ProtectionState) -> None:
        self._mod_counter += 1
        req = OrderRequest(f"prot-{pos.position_id}-{proposal.source}-{self._mod_counter}", "SIM-001",
                           RequestKind.MODIFY_SLTP, pos.symbol, sl=proposal.target, tp=pos.tp,
                           position_id=pos.position_id,
                           origin=f"protection:{proposal.source}{':POGORSZENIE' if proposal.worsens else ''}",
                           created_at=utc(self.clock()).isoformat())
        state.mark_sent(proposal, req.request_id)
        self.orders.submit(req)
        self._sync_protection_outcome(req.request_id)

    def _sync_protection_outcome(self, request_id: str) -> None:
        record = self.orders.records.get(request_id)
        if record is None or record.request.kind is not RequestKind.MODIFY_SLTP:
            return
        state = self.protections.get(record.request.position_id or "")
        if state is None or state.in_flight_request != request_id:
            return
        if record.state in (RequestState.SENT,):
            return
        try:
            positions = {p.position_id: p for p in self.broker.positions()}
        except Exception:  # noqa: BLE001 - brak połączenia: zostaw stan niepewny
            return
        state.mark_outcome(record.state.value, record.message, positions.get(record.request.position_id))
        self._event("protection", f"{record.request.origin}: {record.state.value} — {record.message}")

    # --- akcje użytkownika --------------------------------------------------
    def act(self, action: str, params: dict) -> dict:
        with self.lock:
            handler = getattr(self, f"_a_{action}", None)
            if handler is None:
                raise ValueError(f"Nieznana akcja: {action}")
            result = handler(**params) or {}
            self.version += 1
            return result

    def _a_step(self, n: int = 1, drift_points: int | None = None) -> dict:
        drift = None if drift_points is None else {self.symbol: int(drift_points)}
        self.step(int(n), drift_points=drift)
        return {}

    def _a_set_symbol(self, symbol: str) -> None:
        if symbol not in self.specs:
            raise ValueError("Nieznany symbol")
        self.symbol = symbol
        self._ensure_series(symbol, self.timeframe)
        spec = self.specs[symbol]
        quote = self.last_quote.get(symbol) or self._quote_for(symbol)
        sl_d = spec.from_points(VOLATILITY[symbol] * 25)
        tp_d = spec.from_points(VOLATILITY[symbol] * 40)
        self.plan = TradePlan("SIM-001", symbol, self.plan.side, spec.volume_min, OrderType.MARKET, None,
                              spec.normalize_price(quote.ask - sl_d), spec.normalize_price(quote.ask + tp_d))

    def _a_set_timeframe(self, timeframe: str) -> None:
        self.timeframe = Timeframe(timeframe)
        self._ensure_series(self.symbol, self.timeframe)

    def _a_set_plan(self, **fields) -> None:
        changes: dict = {}
        for key in ("entry", "sl", "tp", "volume"):
            if key in fields:
                value = fields[key]
                changes[key] = None if value in (None, "") else D(str(value))
        if "side" in fields:
            changes["side"] = Side(fields["side"])
        if "order_type" in fields:
            changes["order_type"] = OrderType(fields["order_type"])
            if changes["order_type"] is OrderType.MARKET and "entry" not in fields:
                changes["entry"] = None
        spec = self.specs[self.plan.symbol]
        for key in ("entry", "sl", "tp"):
            if changes.get(key) is not None and fields.get("snap", True):
                changes[key] = spec.normalize_price(changes[key])
        self.plan = self.plan.with_changes(**changes)

    def _a_send_plan(self, client_request_id: str) -> dict:
        if not client_request_id or len(client_request_id) < 8:
            raise ValueError("Wymagany client_request_id (min. 8 znaków)")
        quote = self.last_quote.get(self.plan.symbol)
        ev = evaluate_plan(self.plan, self.specs[self.plan.symbol], "USD", self.fx, self.costs, quote,
                           assess_quote(quote, self.clock(), self.quote_ttl_s, self.broker.connected))
        if not ev.can_send:
            raise ValueError("Plan ma błędy blokujące: " + " ".join(ev.errors))
        if self.plan.order_type is not OrderType.MARKET:
            raise ValueError("Symulator v0.1 obsługuje wyłącznie zlecenia rynkowe.")
        req = OrderRequest(f"plan-{client_request_id}", "SIM-001", RequestKind.OPEN, self.plan.symbol, self.plan.side,
                           self.plan.volume, sl=self.plan.sl, tp=self.plan.tp, origin="manual:plan",
                           created_at=utc(self.clock()).isoformat())
        rec = self.orders.submit(req)
        self._event("order", f"Żądanie {req.request_id}: {rec.state.value} — {rec.message}")
        return {"request": rec.to_dict()}

    def _a_close_position(self, position_id: str, client_request_id: str, volume: str | None = None) -> dict:
        pos = {p.position_id: p for p in self.broker.positions()}.get(position_id)
        if pos is None:
            raise ValueError("Pozycja nie istnieje")
        req = OrderRequest(f"close-{client_request_id}", "SIM-001", RequestKind.CLOSE, pos.symbol, pos.side.opposite,
                           D(volume) if volume else pos.volume, position_id=position_id, origin="manual:close",
                           created_at=utc(self.clock()).isoformat())
        rec = self.orders.submit(req)
        self._event("order", f"Zamknięcie {position_id}: {rec.state.value} — {rec.message}")
        return {"request": rec.to_dict()}

    def _state_for(self, position_id: str) -> ProtectionState:
        if position_id not in {p.position_id for p in self.broker.positions()}:
            raise ValueError("Pozycja nie istnieje")
        return self.protections.setdefault(position_id, ProtectionState(position_id))

    def _a_set_be(self, position_id: str, trigger_points, offset_points, enabled: bool = True) -> None:
        st = self._state_for(position_id)
        st.be = BreakEvenRule(D(str(trigger_points)), D(str(offset_points)), bool(enabled))
        st.be_status.state = RuleState.WAITING if enabled else RuleState.DISABLED
        st.be_status.rejected_target = None
        self._after_market()

    def _a_set_trailing(self, position_id: str, activation_points, distance_points, step_points=1,
                        enabled: bool = True) -> None:
        st = self._state_for(position_id)
        st.trailing = TrailingRule(D(str(activation_points)), D(str(distance_points)), D(str(step_points)), bool(enabled))
        st.trailing_status.rejected_target = None
        st.trailing_status.state = RuleState.WAITING if enabled else RuleState.DISABLED
        self._after_market()

    def _a_manual_sl(self, position_id: str, sl, acknowledge_worse: bool = False) -> None:
        st = self._state_for(position_id)
        if st.in_flight is not None:
            raise ValueError("Poprzednia zmiana SL nie jest jeszcze rozstrzygnięta.")
        pos = {p.position_id: p for p in self.broker.positions()}[position_id]
        spec = self.specs[pos.symbol]
        proposal = st.manual(pos, spec.normalize_price(D(str(sl))), bool(acknowledge_worse))
        self._send_sl(pos, proposal, st)

    def _a_trigger_create(self, symbol: str | None = None, line_price=None, line=None, cross=None, side=None,
                          volume=None, price_source: str = "BID", sl_points=None, tp_points=None,
                          expires_minutes=None) -> dict:
        tid = uuid.uuid4().hex[:8]
        symbol = symbol or self.symbol
        built = None
        if line is not None:
            built = Line(D(str(line["p1"])), datetime.fromisoformat(line["t1"]), D(str(line["p2"])),
                         datetime.fromisoformat(line["t2"]), bool(line.get("extend_right", True)))
        elif line_price not in (None, ""):
            built = Line(self.specs[symbol].normalize_price(D(str(line_price))))
        trg = TrendTrigger(
            tid, symbol, built, None if not cross else Cross(cross), None if not side else Side(side),
            None if volume in (None, "") else D(str(volume)), PriceSource(price_source),
            None if sl_points in (None, "") else D(str(sl_points)),
            None if tp_points in (None, "") else D(str(tp_points)),
            None if not expires_minutes else self.clock() + timedelta(minutes=int(expires_minutes)),
        )
        self.triggers[tid] = trg
        return {"trigger_id": tid}

    def _trg(self, trigger_id: str) -> TrendTrigger:
        return self.triggers[trigger_id]

    def _a_trigger_arm(self, trigger_id: str) -> None:
        trg = self._trg(trigger_id)
        quote = self.last_quote.get(trg.symbol)
        price = None
        if quote is not None and self._fresh(trg.symbol):
            price = quote.bid if trg.price_source is PriceSource.BID else quote.ask
        trg.arm(price, self.clock())

    def _a_trigger_pause(self, trigger_id: str) -> None:
        self._trg(trigger_id).pause(self.clock())

    def _a_trigger_cancel(self, trigger_id: str) -> None:
        self._trg(trigger_id).cancel(self.clock())

    def _a_trigger_move(self, trigger_id: str, line_price) -> None:
        trg = self._trg(trigger_id)
        trg.move_line(Line(self.specs[trg.symbol].normalize_price(D(str(line_price)))), self.clock())

    def _a_trigger_delete_line(self, trigger_id: str) -> None:
        self._trg(trigger_id).delete_line(self.clock())

    def _a_set_connected(self, connected: bool) -> None:
        self.broker.connected = bool(connected)
        self._event("connection", "Połączenie przywrócone." if connected else "Połączenie z symulatorem przerwane.")
        if connected:
            for symbol in self.specs:
                self.last_quote[symbol] = self._quote_for(symbol)
            self._after_market()

    def _a_script_next(self, behaviour: str, reason: str = "") -> None:
        self.broker.script.append(ScriptStep(Behaviour(behaviour), reason))
        self._event("simulator", f"Następne żądanie: scenariusz {behaviour}.")

    def _a_reconcile(self, request_id: str) -> dict:
        rec = self.orders.reconcile(request_id)
        self._sync_protection_outcome(request_id)
        return {"request": rec.to_dict()}

    def _a_kill_switch(self, active: bool, reason: str = "ręcznie w Workspace") -> None:
        self.orders.set_kill_switch(bool(active), reason)
        self._event("kill_switch", f"Kill switch Workspace: {'AKTYWNY' if active else 'wyłączony'} ({reason}).")

    def _a_deposit(self, amount) -> None:
        self.broker.deposit(D(str(amount)), self.clock())

    def _a_set_margin_mode(self, margin_mode: str) -> None:
        if self.broker.book.positions:
            raise ValueError("Zmiana trybu rachunku możliwa tylko bez otwartych pozycji.")
        self.broker.margin_mode = MarginMode(margin_mode)
        self.broker.book.margin_mode = MarginMode(margin_mode)

    def _a_review_filter(self, symbol: str | None = None, side: str | None = None, hours: int | None = None) -> None:
        start = None if not hours else self.clock() - timedelta(hours=int(hours))
        self.review_filter = ReviewFilter(start=start, end=None, symbol=symbol or None, side=Side(side) if side else None)

    def _a_ui_settings(self, **patch) -> None:
        self.ui = apply_ui_settings(self.ui, patch)

    # --- snapshot ---------------------------------------------------------
    def snapshot(self) -> dict:
        with self.lock:
            return self._snapshot()

    def _snapshot(self) -> dict:
        now = self.clock()
        spec = self.specs[self.symbol]
        quote = self.last_quote.get(self.symbol)
        qstatus = assess_quote(quote, now, self.quote_ttl_s, self.broker.connected)
        connected = self.broker.connected
        account = self.broker.account() if connected else None
        positions = self.broker.positions() if connected else []
        deals = self.broker.history() if connected else []
        plan_spec = self.specs[self.plan.symbol]
        plan_quote = self.last_quote.get(self.plan.symbol)
        ev = evaluate_plan(self.plan, plan_spec, "USD", self.fx, self.costs, plan_quote,
                           assess_quote(plan_quote, now, self.quote_ttl_s, connected),
                           equity=None if account is None else account.equity)
        series = self._ensure_series(self.symbol, self.timeframe)
        candles = series.candles[-120:]
        levels: list[Decimal] = []
        if self.plan.symbol == self.symbol:
            levels += [x for x in (ev.entry, self.plan.sl, self.plan.tp) if x is not None]
        for p in positions:
            if p.symbol == self.symbol:
                levels += [x for x in (p.open_price, p.sl, p.tp) if x is not None]
        for t in self.triggers.values():
            if t.symbol == self.symbol and t.line is not None and not t.state.finished:
                lp = t.line.price_at(now)
                if lp is not None:
                    levels.append(lp)
        lo, hi = chart_range([c.low for c in candles] + [c.high for c in candles] + levels)

        pos_rows = []
        for p in positions:
            pspec = self.specs[p.symbol]
            pq = self.last_quote.get(p.symbol)
            st = self.protections.get(p.position_id)
            floating = None
            if pq is not None:
                close = pq.bid if p.side is Side.BUY else pq.ask
                floating, _ = self.fx.convert(pspec.profit(p.side, p.volume, p.open_price, close), pspec.profit_currency, "USD")
                profit_points = pspec.to_points((close - p.open_price) * p.side.sign)
            else:
                profit_points = None
            pos_rows.append({
                **p.to_dict(),
                "floating": None if floating is None else str(floating),
                "profit_points": None if profit_points is None else str(profit_points),
                "protection": protection_view(p, pspec, self.fx, "USD", bool(st and st.in_flight)).to_dict(),
                "rules": None if st is None else {
                    "be": None if st.be is None else {"trigger_points": str(st.be.trigger_points),
                                                      "offset_points": str(st.be.offset_points), "enabled": st.be.enabled},
                    "trailing": None if st.trailing is None else {
                        "activation_points": str(st.trailing.activation_points),
                        "distance_points": str(st.trailing.distance_points),
                        "step_points": str(st.trailing.step_points), "enabled": st.trailing.enabled},
                    "be_status": st.be_status.to_dict(),
                    "trailing_status": st.trailing_status.to_dict(),
                    "manual_status": st.manual_status.to_dict(),
                },
            })

        floating_total = None
        if account is not None and account.equity is not None and account.balance is not None:
            floating_total = account.equity - account.balance

        return {
            "version": self.version,
            "workspace_version": __version__,
            "generated_at": utc(now).isoformat(),
            "mode": DataMode.SIMULATED.value,
            "mode_note": "Wszystko w tym widoku jest SYMULOWANE: rynek, rachunek i broker. Brak połączenia z MT5/DEMO/LIVE.",
            "connection": {"connected": connected, "state": "OK" if connected else "DISCONNECTED"},
            "kill_switch": {"active": self.orders.kill_switch, "reason": self.orders.kill_reason},
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "symbols": list(self.specs),
            "timeframes": [t.value for t in Timeframe],
            "instrument": spec.to_dict(),
            "quote": None if quote is None else quote.to_dict(),
            "quote_status": {"state": qstatus.state.value, "age_s": qstatus.age_s, "reason": qstatus.reason},
            "account": None if account is None else account.to_dict(),
            "chart": {
                "lo": str(lo), "hi": str(hi), "source": series.source, "mode": series.mode.value,
                "candles": [c.to_dict() for c in candles],
                "formula": "y = (hi - cena) / (hi - lo) * wysokość",
            },
            "plan": {**self.plan.to_dict(), "evaluation": ev.to_dict()},
            "positions": pos_rows,
            "requests": [r.to_dict() for r in list(self.orders.records.values())[-40:]][::-1],
            "triggers": [{**t.to_dict(), "summary": t.summary(self.specs[t.symbol]), "warnings": t.warnings(),
                          "missing": t.missing_fields(),
                          "line_price_now": None if t.line is None or t.line.price_at(now) is None else str(t.line.price_at(now))}
                         for t in self.triggers.values()],
            "review": review(deals, "SIM-001", "USD", self.review_filter, floating_total,
                             "Floating teraz = equity − balance z symulatora.", "SIMULATED: historia deali symulatora")
                      if connected else None,
            "widgets": {
                "margin": margin_usage(None if account is None else account.margin, None if account is None else account.equity),
                "risk_to_sl": risk_to_sl(positions, self.specs, self.last_quote, self.fx, "USD",
                                         None if account is None else account.equity),
                "candle_timer": candle_timer(self.timeframe, now, None if quote is None else quote.time),
                "spread": spread(quote, spec),
                "indicators": indicators(series, now),
            },
            "ui": self.ui.to_dict(),
            "events": self.events[::-1][:30],
        }
