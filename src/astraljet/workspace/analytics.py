"""Review Center i Analytics na podstawie deali.

Definicje (widoczne także w odpowiedzi API):
- transakcja = pozycja (position_id), której ostatni deal OUT mieści się w okresie i która
  po nim ma wolumen 0; częściowe zamknięcia pozycji wciąż otwartych NIE są transakcjami,
  ale ich wynik wchodzi do „zrealizowane w okresie” i jest pokazany osobno,
- wynik transakcji netto = profit + commission + swap + fee wszystkich jej deali (także IN
  sprzed okresu, jeśli są w danych; brak deala IN oznacza wynik niepełny),
- wpłaty/wypłaty nie są wynikiem handlowym; osobne opłaty brokera (FEE) są kosztem rachunku,
  nie przypisanym do transakcji,
- krzywa to SALDO (balance) po kolejnych dealach okresu — nie historyczne equity;
  floating jest pokazany tylko „teraz”, z otwartych pozycji, osobno,
- etykiety i dane wykresów pochodzą z tych samych struktur.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .instruments import D, Side
from .market import utc
from .model import Deal, DealEntry, DealType

DEFINITIONS = {
    "trade": "Pozycja w pełni zamknięta w okresie (ostatni deal OUT w okresie, wolumen końcowy 0).",
    "net": "profit + commission + swap + fee wszystkich deali transakcji.",
    "realized_period": ("Suma netto deali handlowych z okresu = część zamkniętych transakcji z okresu + częściowe "
                        "zamknięcia pozycji otwartych + koszty wejścia pozycji otwartych."),
    "balance_curve": "Saldo po kolejnych dealach okresu (z wpłatami/wypłatami). Nie jest to equity.",
    "floating": "Niezrealizowany wynik otwartych pozycji w chwili odczytu; brak historii floating.",
    "win_rate": "Odsetek transakcji z wynikiem netto > 0.",
    "expectancy": "Suma netto transakcji / liczba transakcji.",
    "profit_factor": "Suma zysków netto / |suma strat netto|; brak, gdy nie ma strat.",
    "max_drawdown": "Największy spadek krzywej salda od wcześniejszego szczytu w okresie (tylko zrealizowane).",
}


@dataclass(frozen=True, slots=True)
class ReviewFilter:
    start: datetime | None = None
    end: datetime | None = None   # wyłącznie
    symbol: str | None = None
    side: Side | None = None      # kierunek pozycji (strona deala IN)

    def in_period(self, t: datetime) -> bool:
        t = utc(t)
        if self.start is not None and t < utc(self.start):
            return False
        if self.end is not None and t >= utc(self.end):
            return False
        return True

    def to_dict(self) -> dict:
        return {"start": None if self.start is None else utc(self.start).isoformat(),
                "end": None if self.end is None else utc(self.end).isoformat(),
                "symbol": self.symbol, "side": None if self.side is None else self.side.value}


def s(v: Decimal | None) -> str | None:
    return None if v is None else str(v)


def review(
    deals: list[Deal],
    account_id: str,
    currency: str,
    flt: ReviewFilter,
    floating_now: Decimal | None,
    floating_note: str,
    source: str,
) -> dict:
    deals = sorted([d for d in deals if d.account_id == account_id], key=lambda d: (utc(d.time), d.deal_id))

    # Kierunek pozycji = strona pierwszego deala IN.
    position_side: dict[str, Side] = {}
    position_deals: dict[str, list[Deal]] = defaultdict(list)
    for d in deals:
        if d.type is DealType.TRADE and d.position_id:
            position_deals[d.position_id].append(d)
            if d.entry is DealEntry.IN and d.position_id not in position_side:
                position_side[d.position_id] = d.side

    def matches(d: Deal) -> bool:
        if flt.symbol and d.symbol != flt.symbol:
            return False
        if flt.side and position_side.get(d.position_id or "") is not flt.side:
            return False
        return True

    # Saldo początkowe = suma netto wszystkich deali przed okresem (jeżeli dane zaczynają się od zera).
    before = [d for d in deals if flt.start is not None and utc(d.time) < utc(flt.start)]
    start_balance = sum((d.net for d in before), Decimal(0))

    period = [d for d in deals if flt.in_period(d.time)]
    trade_deals = [d for d in period if d.type is DealType.TRADE and matches(d)]
    deposits = sum((d.amount for d in period if d.type is DealType.DEPOSIT), Decimal(0))
    withdrawals = sum((d.amount for d in period if d.type is DealType.WITHDRAWAL), Decimal(0))
    fees = sum((d.amount for d in period if d.type is DealType.FEE), Decimal(0))

    realized = sum((d.net for d in trade_deals), Decimal(0))
    gross_profit = sum((d.profit for d in trade_deals), Decimal(0))
    commission = sum((d.commission for d in trade_deals), Decimal(0))
    swap = sum((d.swap for d in trade_deals), Decimal(0))
    deal_fees = sum((d.fee for d in trade_deals), Decimal(0))

    trades = []
    partial_realized = Decimal(0)
    open_entry_costs = Decimal(0)
    closed_period_part = Decimal(0)
    incomplete = 0
    for pid, pdeals in position_deals.items():
        if not matches(pdeals[0]):
            continue
        volume_in = sum((d.volume for d in pdeals if d.entry is DealEntry.IN), Decimal(0))
        volume_out = sum((d.volume for d in pdeals if d.entry is DealEntry.OUT), Decimal(0))
        outs = [d for d in pdeals if d.entry is DealEntry.OUT]
        closed = volume_in > 0 and volume_in == volume_out
        has_in = any(d.entry is DealEntry.IN for d in pdeals)
        if closed and outs and flt.in_period(outs[-1].time):
            net = sum((d.net for d in pdeals), Decimal(0))
            trades.append({
                "position_id": pid,
                "symbol": pdeals[0].symbol,
                "side": position_side[pid].value,
                "volume": str(volume_in),
                "opened_at": utc(pdeals[0].time).isoformat(),
                "closed_at": utc(outs[-1].time).isoformat(),
                "exits": len(outs),
                "gross": str(sum((d.profit for d in pdeals), Decimal(0))),
                "costs": str(sum((d.commission + d.swap + d.fee for d in pdeals), Decimal(0))),
                "net": str(net),
                "complete": has_in,
            })
            if not has_in:
                incomplete += 1
            closed_period_part += sum((d.net for d in pdeals if flt.in_period(d.time)), Decimal(0))
        else:
            partial_realized += sum((d.net for d in pdeals if d.entry is DealEntry.OUT and flt.in_period(d.time)), Decimal(0))
            open_entry_costs += sum((d.net for d in pdeals if d.entry is DealEntry.IN and flt.in_period(d.time)), Decimal(0))

    nets = [D(t["net"]) for t in trades]
    wins = [n for n in nets if n > 0]
    losses = [n for n in nets if n < 0]
    n_trades = len(nets)
    total_trades_net = sum(nets, Decimal(0))

    # Krzywa salda: każdy deal okresu (z filtrem symbolu/strony tylko dla deali handlowych;
    # przy aktywnym filtrze wpłaty pomijamy i krzywa pokazuje wyłącznie wynik filtrowany).
    filtered = bool(flt.symbol or flt.side)
    curve = [{"t": utc(flt.start).isoformat() if flt.start else None, "balance": str(start_balance), "deal_id": None}]
    running = start_balance if not filtered else Decimal(0)
    if filtered:
        curve[0]["balance"] = "0"
    peak = running
    max_dd = Decimal(0)
    for d in period:
        if d.type is DealType.TRADE and not matches(d):
            continue
        if filtered and d.type is not DealType.TRADE:
            continue
        running += d.net
        curve.append({"t": utc(d.time).isoformat(), "balance": str(running), "deal_id": d.deal_id, "type": d.type.value})
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    by_side = {}
    for side in (Side.BUY, Side.SELL):
        sel = [t for t in trades if t["side"] == side.value]
        by_side[side.value] = {
            "trades": len(sel),
            "volume": str(sum((D(t["volume"]) for t in sel), Decimal(0))),
            "net": str(sum((D(t["net"]) for t in sel), Decimal(0))),
        }

    return {
        "account_id": account_id,
        "currency": currency,
        "source": source,
        "filter": flt.to_dict(),
        "definitions": DEFINITIONS,
        "balance": {
            "start": str(start_balance) if not filtered else None,
            "end": curve[-1]["balance"] if not filtered else None,
            "start_note": "Suma deali przed okresem w dostępnych danych." if flt.start else "Od początku dostępnych danych.",
        },
        "realized_period": str(realized),
        "realized_breakdown": {
            "gross_profit": str(gross_profit), "commission": str(commission), "swap": str(swap), "fee": str(deal_fees),
            # Trzy składniki sumują się dokładnie do realized_period (tylko deale z okresu).
            "from_closed_trades_in_period": str(closed_period_part),
            "from_partial_closes_of_open_positions": str(partial_realized),
            "entry_costs_of_open_positions": str(open_entry_costs),
            # Pełny wynik zamkniętych transakcji, także z deali wejścia sprzed okresu.
            "closed_trades_full_net": str(total_trades_net),
        },
        "cash_flows": {"deposits": str(deposits), "withdrawals": str(withdrawals), "account_fees": str(fees)},
        "floating_now": s(floating_now),
        "floating_note": floating_note,
        "stats": {
            "trades": n_trades,
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": n_trades - len(wins) - len(losses),
            "win_rate": None if n_trades == 0 else str(Decimal(len(wins)) / Decimal(n_trades)),
            "expectancy": None if n_trades == 0 else str(total_trades_net / Decimal(n_trades)),
            "profit_factor": None if not losses else str(sum(wins, Decimal(0)) / abs(sum(losses, Decimal(0)))),
            "max_drawdown": str(max_dd),
            "incomplete_trades": incomplete,
        },
        "by_side": by_side,
        "curve": curve,
        "trades": trades,
    }
