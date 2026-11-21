"""Plan transakcji (dane PLANOWANE) i jego ocena: odległości, pieniądze, R:R, koszty.

Plan nigdy nie jest wynikiem. Ocena zwraca błędy blokujące wysłanie oraz ostrzeżenia,
np. brak SL — który NIE oznacza zerowego ryzyka.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import StrEnum

from .instruments import D, FxTable, InstrumentSpec, Side
from .market import Freshness, Quote, QuoteStatus


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass(frozen=True, slots=True)
class CostModel:
    """Szacunek kosztów w walucie rachunku. None = koszt nieznany (nie zero)."""

    commission_per_lot_per_side: Decimal | None = None
    source: str = "brak danych o prowizji"

    @property
    def known(self) -> bool:
        return self.commission_per_lot_per_side is not None

    def round_turn(self, volume: Decimal) -> Decimal | None:
        if self.commission_per_lot_per_side is None:
            return None
        return D(self.commission_per_lot_per_side) * D(volume) * 2


@dataclass(frozen=True, slots=True)
class TradePlan:
    account_id: str
    symbol: str
    side: Side
    volume: Decimal
    order_type: OrderType = OrderType.MARKET
    entry: Decimal | None = None
    sl: Decimal | None = None
    tp: Decimal | None = None
    comment: str = ""

    def with_changes(self, **changes: object) -> "TradePlan":
        return replace(self, **changes)

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "volume": str(self.volume),
            "order_type": self.order_type.value,
            "entry": None if self.entry is None else str(self.entry),
            "sl": None if self.sl is None else str(self.sl),
            "tp": None if self.tp is None else str(self.tp),
            "comment": self.comment,
            "status": "PLANNED",
        }


@dataclass(slots=True)
class PlanEvaluation:
    status: str = "PLANNED"
    entry: Decimal | None = None
    entry_basis: str = ""
    sl_points: Decimal | None = None
    tp_points: Decimal | None = None
    sl_pips: Decimal | None = None
    tp_pips: Decimal | None = None
    risk_profit_ccy: Decimal | None = None
    reward_profit_ccy: Decimal | None = None
    risk_account: Decimal | None = None
    reward_account: Decimal | None = None
    reward_risk: Decimal | None = None
    breakeven_win_rate: Decimal | None = None
    costs_account: Decimal | None = None
    net_risk_account: Decimal | None = None
    net_reward_account: Decimal | None = None
    risk_to_equity: Decimal | None = None
    account_currency: str = ""
    profit_currency: str = ""
    fx_note: str = ""
    cost_note: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def can_send(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        def s(value: Decimal | None) -> str | None:
            return None if value is None else str(value)

        return {
            "status": self.status,
            "entry": s(self.entry),
            "entry_basis": self.entry_basis,
            "sl_points": s(self.sl_points),
            "tp_points": s(self.tp_points),
            "sl_pips": s(self.sl_pips),
            "tp_pips": s(self.tp_pips),
            "risk_profit_ccy": s(self.risk_profit_ccy),
            "reward_profit_ccy": s(self.reward_profit_ccy),
            "risk_account": s(self.risk_account),
            "reward_account": s(self.reward_account),
            "reward_risk": s(self.reward_risk),
            "breakeven_win_rate": s(self.breakeven_win_rate),
            "costs_account": s(self.costs_account),
            "net_risk_account": s(self.net_risk_account),
            "net_reward_account": s(self.net_reward_account),
            "risk_to_equity": s(self.risk_to_equity),
            "account_currency": self.account_currency,
            "profit_currency": self.profit_currency,
            "fx_note": self.fx_note,
            "cost_note": self.cost_note,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "can_send": self.can_send,
        }


def check_stop_levels(
    spec: InstrumentSpec,
    side: Side,
    reference: Decimal,
    sl: Decimal | None,
    tp: Decimal | None,
) -> list[str]:
    """Strona i minimalna odległość SL/TP od ceny odniesienia (zamknięcia pozycji
    albo ceny zlecenia oczekującego), wg stops level brokera."""
    errors: list[str] = []
    minimum = spec.from_points(spec.stops_level_points)
    ref = D(reference)
    if sl is not None:
        distance = (ref - D(sl)) * side.sign
        if distance <= 0:
            errors.append(f"SL {sl} jest po złej stronie ceny {ref} dla {side.value}.")
        elif distance < minimum:
            errors.append(f"SL {sl} bliżej niż stops level {spec.stops_level_points} pkt od {ref}.")
    if tp is not None:
        distance = (D(tp) - ref) * side.sign
        if distance <= 0:
            errors.append(f"TP {tp} jest po złej stronie ceny {ref} dla {side.value}.")
        elif distance < minimum:
            errors.append(f"TP {tp} bliżej niż stops level {spec.stops_level_points} pkt od {ref}.")
    return errors


def evaluate_plan(
    plan: TradePlan,
    spec: InstrumentSpec,
    account_currency: str,
    fx: FxTable,
    costs: CostModel = CostModel(),
    quote: Quote | None = None,
    quote_status: QuoteStatus | None = None,
    equity: Decimal | None = None,
) -> PlanEvaluation:
    ev = PlanEvaluation(account_currency=account_currency, profit_currency=spec.profit_currency)
    if plan.symbol != spec.symbol:
        ev.errors.append(f"Plan dotyczy {plan.symbol}, specyfikacja {spec.symbol}.")
        return ev

    volume = spec.check_volume(plan.volume)
    if not volume.ok:
        ev.errors.append(volume.reason)

    # Cena wejścia: rynkowa wynika z kwotowania (BUY po Ask, SELL po Bid), oczekująca z planu.
    if plan.order_type is OrderType.MARKET:
        if plan.entry is not None:
            ev.entry = D(plan.entry)
            ev.entry_basis = "cena podana w planie (rynek wykona po bieżącym kwotowaniu)"
        elif quote is not None:
            ev.entry = D(quote.ask) if plan.side is Side.BUY else D(quote.bid)
            ev.entry_basis = "Ask" if plan.side is Side.BUY else "Bid"
        else:
            ev.errors.append("Brak kwotowania: cena wejścia zlecenia rynkowego nieznana.")
    else:
        if plan.entry is None:
            ev.errors.append("Zlecenie oczekujące wymaga ceny wejścia.")
        else:
            ev.entry = D(plan.entry)
            ev.entry_basis = f"cena zlecenia {plan.order_type.value}"

    if quote_status is not None and quote_status.state is not Freshness.CONFIRMED:
        ev.warnings.append(f"Kwotowanie {quote_status.state.value}: {quote_status.reason}")

    for label, price in (("wejścia", ev.entry), ("SL", plan.sl), ("TP", plan.tp)):
        if price is not None and not spec.is_on_tick(D(price)):
            ev.errors.append(f"Cena {label} {price} nie leży na siatce ticka {spec.tick}.")

    if ev.entry is None:
        return ev

    entry = ev.entry
    if plan.order_type is OrderType.MARKET:
        if quote is not None:
            reference = D(quote.bid) if plan.side is Side.BUY else D(quote.ask)
        else:
            reference = entry
    else:
        reference = entry
        if quote is not None:
            market = D(quote.ask) if plan.side is Side.BUY else D(quote.bid)
            if plan.order_type is OrderType.LIMIT and (entry - market) * plan.side.sign >= 0:
                ev.errors.append("Zlecenie LIMIT musi leżeć po korzystniejszej stronie bieżącej ceny.")
            if plan.order_type is OrderType.STOP and (entry - market) * plan.side.sign <= 0:
                ev.errors.append("Zlecenie STOP musi leżeć za bieżącą ceną w kierunku transakcji.")
    ev.errors.extend(check_stop_levels(spec, plan.side, reference, plan.sl, plan.tp))

    if plan.sl is None:
        ev.warnings.append("Brak SL: strata do SL nieokreślona. To NIE jest 0% ryzyka.")
    else:
        ev.sl_points = spec.to_points((entry - D(plan.sl)) * plan.side.sign)
        ev.sl_pips = spec.to_pips((entry - D(plan.sl)) * plan.side.sign)
        ev.risk_profit_ccy = -spec.profit(plan.side, plan.volume, entry, plan.sl)
    if plan.tp is None:
        ev.warnings.append("Brak TP: potencjalny zysk nieokreślony.")
    else:
        ev.tp_points = spec.to_points((D(plan.tp) - entry) * plan.side.sign)
        ev.tp_pips = spec.to_pips((D(plan.tp) - entry) * plan.side.sign)
        ev.reward_profit_ccy = spec.profit(plan.side, plan.volume, entry, plan.tp)

    ev.risk_account, note_r = fx.convert(ev.risk_profit_ccy, spec.profit_currency, account_currency)
    ev.reward_account, note_w = fx.convert(ev.reward_profit_ccy, spec.profit_currency, account_currency)
    ev.fx_note = note_r if plan.sl is not None else note_w
    if (plan.sl is not None and ev.risk_account is None) or (plan.tp is not None and ev.reward_account is None):
        ev.warnings.append(ev.fx_note)

    if ev.sl_points is not None and ev.tp_points is not None and ev.sl_points > 0:
        ev.reward_risk = ev.tp_points / ev.sl_points
        ev.breakeven_win_rate = ev.sl_points / (ev.sl_points + ev.tp_points)

    ev.costs_account = costs.round_turn(D(plan.volume))
    if ev.costs_account is None:
        ev.cost_note = "Koszty prowizji nieznane: kwoty są brutto, przed kosztami."
        ev.warnings.append(ev.cost_note)
    else:
        ev.cost_note = f"Szacunek prowizji round-turn: {costs.source}. Spread zawarty w cenach Bid/Ask, swap pominięty."
        if ev.risk_account is not None:
            ev.net_risk_account = ev.risk_account + ev.costs_account
        if ev.reward_account is not None:
            ev.net_reward_account = ev.reward_account - ev.costs_account

    if equity is not None and ev.risk_account is not None and D(equity) > 0:
        ev.risk_to_equity = ev.risk_account / D(equity)
    return ev
