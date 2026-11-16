"""Widgety: depozyt, ryzyko do SL, czas świecy, spread, RSI, MACD.

- Wykorzystanie depozytu = margin / equity. To NIE jest strata do SL.
- Ryzyko do SL sumuje tylko pozycje z potwierdzonym SL; pozycje bez SL powodują
  status INCOMPLETE i brak sumy całkowitej — nigdy 0%.
- Brak syntetycznego procentu „Health” — pokazujemy sprawdzalne składniki.
- Wskaźniki liczone tylko z zamkniętych świec, z symbolem, interwałem, źródłem i czasem.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from .instruments import D, FxTable, InstrumentSpec
from .market import CandleSeries, Quote, Timeframe, bar_start, utc
from .model import Position
from .protection import close_price


def margin_usage(margin: Decimal | None, equity: Decimal | None) -> dict:
    if margin is None or equity is None:
        return {"ratio": None, "free_margin": None, "state": "MISSING",
                "label": "Wykorzystanie depozytu (margin/equity): brak danych."}
    if D(equity) <= 0:
        return {"ratio": None, "free_margin": str(D(equity) - D(margin)), "state": "UNDEFINED",
                "label": "Equity ≤ 0: wskaźnik niezdefiniowany."}
    ratio = D(margin) / D(equity)
    return {"ratio": str(ratio), "free_margin": str(D(equity) - D(margin)), "state": "OK",
            "label": "Wykorzystanie depozytu (margin/equity). To nie jest strata przy SL."}


def risk_to_sl(
    positions: list[Position],
    specs: dict[str, InstrumentSpec],
    quotes: dict[str, Quote],
    fx: FxTable,
    account_ccy: str,
    equity: Decimal | None,
) -> dict:
    rows = []
    known_loss = Decimal(0)
    missing_sl = 0
    unknown_value = 0
    for pos in positions:
        spec = specs[pos.symbol]
        row = {"position_id": pos.position_id, "symbol": pos.symbol, "side": pos.side.value, "volume": str(pos.volume),
               "sl": None if pos.sl is None else str(pos.sl)}
        if pos.sl is None:
            missing_sl += 1
            row.update({"pnl_at_sl": None, "further_loss_to_sl": None, "note": "Brak SL: strata nieokreślona."})
            rows.append(row)
            continue
        at_sl, _ = fx.convert(spec.profit(pos.side, pos.volume, pos.open_price, pos.sl), spec.profit_currency, account_ccy)
        quote = quotes.get(pos.symbol)
        further = None
        if quote is not None:
            now_close = close_price(pos.side, quote.bid, quote.ask)
            further, _ = fx.convert(spec.profit(pos.side, pos.volume, now_close, pos.sl), spec.profit_currency, account_ccy)
        if at_sl is None or further is None:
            unknown_value += 1
        else:
            known_loss += min(further, Decimal(0))
        row.update({"pnl_at_sl": None if at_sl is None else str(at_sl),
                    "further_loss_to_sl": None if further is None else str(further),
                    "note": "Szacunek przy SL przed kosztami; poślizg możliwy."})
        rows.append(row)
    complete = missing_sl == 0 and unknown_value == 0
    total = known_loss if complete else None
    return {
        "state": "COMPLETE" if complete else "INCOMPLETE",
        "positions_without_sl": missing_sl,
        "positions_without_value": unknown_value,
        "loss_to_sl_from_now": None if total is None else str(total),
        "loss_to_sl_known_part": str(known_loss),
        "loss_to_sl_pct_equity": None if total is None or not equity or D(equity) <= 0 else str(-total / D(equity)),
        "label": ("Dalsza strata, gdyby wszystkie SL zadziałały po swoich cenach (od bieżącej ceny)."
                  if complete else
                  f"NIEPEŁNE: {missing_sl} poz. bez SL, {unknown_value} bez wyceny — suma nieznana, to nie jest 0%."),
        "positions": rows,
    }


def candle_timer(timeframe: Timeframe, now: datetime, last_tick: datetime | None) -> dict:
    start = bar_start(now, timeframe)
    end = start + timedelta(seconds=timeframe.seconds)
    remaining = (end - utc(now)).total_seconds()
    no_tick = last_tick is None or utc(last_tick) < start
    return {"timeframe": timeframe.value, "bar_start": start.isoformat(), "bar_end": end.isoformat(),
            "remaining_s": remaining,
            "note": ("Brak ticka w bieżącej świecy: czas liczony zegarem, świeca u brokera może się nie pojawić."
                     if no_tick else "Czas do końca świecy wg zegara UTC.")}


def spread(quote: Quote | None, spec: InstrumentSpec) -> dict:
    if quote is None:
        return {"points": None, "state": "MISSING"}
    return {"points": str(quote.spread_points(spec)), "bid": str(quote.bid), "ask": str(quote.ask),
            "as_of": utc(quote.time).isoformat(), "source": quote.source, "state": "OK"}


def rsi(closes: list[Decimal], period: int = 14) -> Decimal | None:
    """RSI Wildera. None, gdy za mało danych (period + 1 zamknięć)."""
    if len(closes) < period + 1:
        return None
    gains = Decimal(0)
    losses = Decimal(0)
    for prev, cur in zip(closes[:period], closes[1:period + 1]):
        change = D(cur) - D(prev)
        gains += max(change, Decimal(0))
        losses += max(-change, Decimal(0))
    avg_gain = gains / period
    avg_loss = losses / period
    for prev, cur in zip(closes[period:], closes[period + 1:]):
        change = D(cur) - D(prev)
        avg_gain = (avg_gain * (period - 1) + max(change, Decimal(0))) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, Decimal(0))) / period
    if avg_loss == 0:
        return Decimal(100) if avg_gain > 0 else Decimal(50)
    rs = avg_gain / avg_loss
    return Decimal(100) - Decimal(100) / (1 + rs)


def ema(values: list[Decimal], period: int) -> list[Decimal]:
    """EMA zainicjowana SMA z pierwszych `period` wartości."""
    if len(values) < period:
        return []
    k = Decimal(2) / Decimal(period + 1)
    out = [sum(values[:period], Decimal(0)) / period]
    for v in values[period:]:
        out.append((D(v) - out[-1]) * k + out[-1])
    return out


def macd(closes: list[Decimal], fast: int = 12, slow: int = 26, signal: int = 9) -> dict | None:
    """Konwencja: MACD = EMA(fast) − EMA(slow); sygnał = EMA(signal) z MACD; histogram = MACD − sygnał."""
    if len(closes) < slow + signal - 1:
        return None
    ef = ema(closes, fast)
    es = ema(closes, slow)
    offset = slow - fast
    line = [f - s_ for f, s_ in zip(ef[offset:], es)]
    sig = ema(line, signal)
    if not sig:
        return None
    return {"macd": line[-1], "signal": sig[-1], "histogram": line[-1] - sig[-1]}


def indicators(series: CandleSeries, now: datetime) -> dict:
    closed = series.closed(now)
    closes = [c.close for c in closed]
    as_of = None if not closed else utc(closed[-1].time).isoformat()
    r = rsi(closes)
    m = macd(closes)
    base = {"symbol": series.symbol, "timeframe": series.timeframe.value, "source": series.source,
            "mode": series.mode.value, "as_of_bar": as_of, "closed_bars": len(closes),
            "note": "Liczone wyłącznie z zamkniętych świec; to opis danych, nie sygnał ani prognoza."}
    return {
        "rsi14": {**base, "value": None if r is None else str(r.quantize(Decimal('0.01')))},
        "macd_12_26_9": {**base, "value": None if m is None else {k: str(v) for k, v in m.items()},
                         "convention": "histogram = MACD − sygnał"},
    }
