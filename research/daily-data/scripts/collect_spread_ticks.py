# -*- coding: utf-8 -*-
"""Pomiar spreadu z historii ticków dla kandydatów serii 2 — WYŁĄCZNIE ODCZYT.

Zlecenie koordynatora AURUQ-TRADING z 21.11.2026 (01:16, 01:42). Powód: w świecach D1 broker zapisuje
dla ETF-ów spread 0, więc koszt transakcji w regułach serii 2 stał na jednym odczycie bieżącym.

Konstrukcja jak collect_d1_universe.py:
- MT5_TERMINAL obowiązkowe, tylko znane instalacje (TERMINALS), terminal musi już działać;
- odmowa przy włączonym Algo Trading, chyba że podano --algo-trading-dozwolone (zgoda Karola z 21.11.2026);
  stan nieznany to zawsze odmowa; flaga nie zmienia listy dozwolonych wywołań;
- twarda lista dozwolonych wywołań: jak w D1 bez świec, plus copy_ticks_range;
- bez symbol_select, account_info, login, zleceń, pozycji i historii rachunku;
- symbol niewidoczny w Market Watch jest pomijany i trafia do raportu.

Okres: 30 dni kalendarzowych (UTC) kończących się o północy UTC po ostatniej zamkniętej sesji.
Czas ticków MT5 jest czasem serwera; przeliczenie na UTC opisuje server_offset_for().

Wynik:
    research/daily-data/data/spread_ticks/<SYMBOL>.parquet   (time_msc serwera, bid, ask; poza Git)
    research/daily-data/reports/SPREAD_TICKI_SERIA2.md
    research/daily-data/logs/collect_spread_ticks.log

Użycie:
    $env:MT5_TERMINAL = 'E:\\MT5-DEMO\\Vantage\\terminal64.exe'
    research\\scalp-smc\\.venv\\Scripts\\python.exe research\\daily-data\\scripts\\collect_spread_ticks.py [--algo-trading-dozwolone]
    research\\scalp-smc\\.venv\\Scripts\\python.exe research\\daily-data\\scripts\\collect_spread_ticks.py --selftest
    (bez terminala; także selftest wymaga numpy i pandas, więc działa w research\\scalp-smc\\.venv, nie w głównym .venv)
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_d1 import FORBIDDEN  # noqa: E402
from collect_d1_universe import (  # noqa: E402
    ALGO_FLAG, EXIT_ALGO_TRADING, TERMINALS, algo_text, algo_trading_refusal, check_terminal,
    running_terminal_paths,
)

ROOT = Path(__file__).resolve().parents[1]
OUT, LOGS, REPORTS = ROOT / "data" / "spread_ticks", ROOT / "logs", ROOT / "reports"
REPORT_NAME = "SPREAD_TICKI_SERIA2.md"
UTC = dt.timezone.utc
NY = ZoneInfo("America/New_York")
DAYS = 30

US_ETF = ("IWM", "XLF", "XLK", "EFA", "EEM", "FXI", "GDX", "USO", "DBC", "BNO", "GLD", "SPY", "QQQ")
WHOLE_DAY = ("Nikkei225", "BTCUSD", "ETHUSD", "AUDUSD+")
SYMBOLS = US_ETF + WHOLE_DAY

ALLOWED = frozenset({
    "initialize", "shutdown", "last_error", "version", "terminal_info",
    "symbols_get", "symbol_info", "symbol_info_tick", "copy_ticks_range",
})


def log(msg: str) -> None:
    line = f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "collect_spread_ticks.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


class StrictReadOnlyMT5:
    """Przepuszcza tylko ALLOWED i stałe (WIELKIE_LITERY)."""

    def __init__(self, module):
        self._m = module

    def __getattr__(self, name: str):
        if name in FORBIDDEN or name.startswith(("history_", "order", "position")) \
                or name in ("symbol_select", "account_info", "login", "copy_rates_from_pos", "copy_rates_range"):
            raise PermissionError(f"Zabronione wywołanie MetaTrader5.{name} (tylko odczyt)")
        if name.isupper():
            return getattr(self._m, name)
        if name not in ALLOWED:
            raise PermissionError(f"MetaTrader5.{name} nie jest na liście dozwolonych")
        return getattr(self._m, name)


# ---------- czas ----------

def ny_dst(t: dt.datetime) -> bool:
    return bool(t.astimezone(NY).dst())


def server_offset_for(t: dt.datetime, now_offset_h: int, now: dt.datetime) -> int:
    """Przesunięcie serwera MT5 względem UTC w chwili t.

    Mierzone teraz z ticka; dla wcześniejszych dat zakładamy, że serwer zmienia czas razem z Nowym Jorkiem
    (typowe GMT+2 zimą / GMT+3 latem). Założenie jest zapisane w raporcie.
    """
    return now_offset_h + (int(ny_dst(t)) - int(ny_dst(now)))


def window(now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    """30 dni UTC kończących się o północy UTC po ostatniej zamkniętej sesji (pon–pt)."""
    end = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    # sesja dnia D kończy się przed północą UTC; cofaj do dnia po ostatnim dniu roboczym
    while (end - dt.timedelta(days=1)).weekday() >= 5:
        end -= dt.timedelta(days=1)
    return end - dt.timedelta(days=DAYS), end


def in_us_session(ts_utc):
    """Maska: zwykła sesja USA 09:30–16:00 czasu Nowego Jorku, pon–pt (zimą = 14:30–21:00 UTC)."""
    import numpy as np
    import pandas as pd
    local = pd.to_datetime(ts_utc, unit="s", utc=True).tz_convert("America/New_York")
    minutes = np.asarray(local.hour) * 60 + np.asarray(local.minute)
    return (minutes >= 9 * 60 + 30) & (minutes < 16 * 60) & (np.asarray(local.day_of_week) < 5)


# ---------- statystyki ----------

def spread_stats(bid, ask) -> dict | None:
    import numpy as np
    bid, ask = np.asarray(bid, dtype=float), np.asarray(ask, dtype=float)
    ok = (bid > 0) & (ask > 0)
    if not ok.any():
        return None
    b, a = bid[ok], ask[ok]
    pct = (a - b) / ((a + b) / 2.0) * 100.0
    return {
        "n": int(ok.sum()), "invalid": int((~ok).sum()),
        "median": float(np.median(pct)), "p75": float(np.percentile(pct, 75)), "p95": float(np.percentile(pct, 95)),
        "zero_or_neg_share": float((a - b <= 0).mean()),
    }


def summarize(symbol: str, server_ms, bid, ask, offsets_h) -> dict:
    """offsets_h: przesunięcie serwera dla każdego ticka (h). Zwraca statystyki całości i podział sesji USA."""
    import numpy as np
    ts_utc = np.asarray(server_ms, dtype="int64") / 1000.0 - np.asarray(offsets_h, dtype=float) * 3600.0
    res = {"symbol": symbol, "ticks": int(len(ts_utc))}
    if len(ts_utc) == 0:
        return res
    first = dt.datetime.fromtimestamp(float(ts_utc.min()), UTC)
    last = dt.datetime.fromtimestamp(float(ts_utc.max()), UTC)
    days = np.unique((ts_utc // 86400).astype("int64"))
    res.update(first=first.isoformat(timespec="minutes"), last=last.isoformat(timespec="minutes"),
               days_with_ticks=int(len(days)), all=spread_stats(bid, ask))
    if symbol in US_ETF:
        mask = in_us_session(ts_utc)
        bid, ask = np.asarray(bid), np.asarray(ask)
        res["us"] = spread_stats(bid[mask], ask[mask])
        res["other"] = spread_stats(bid[~mask], ask[~mask])
        res["us_ticks"], res["other_ticks"] = int(mask.sum()), int((~mask).sum())
    return res


def fmt(s: dict | None) -> str:
    if not s:
        return "— | — | — | —"
    return f"{s['median']:.4f} | {s['p75']:.4f} | {s['p95']:.4f} | {s['zero_or_neg_share'] * 100:.1f}%"


def report(results, skipped, failures, start, end, read_at, terminal, algo_trading, offset_h, mw) -> str:
    L = ["# Spread z historii ticków — kandydaci serii 2", "",
         f"- Odczyt: {read_at} UTC, skrypt `research/daily-data/scripts/collect_spread_ticks.py` (tylko odczyt).",
         f"- Źródło: {terminal}.",
         f"- Handel automatyczny w terminalu (przycisk Algo Trading) w chwili odczytu: {algo_text(algo_trading)}.",
         f"- Okres: {start:%Y-%m-%d %H:%M} – {end:%Y-%m-%d %H:%M} UTC ({DAYS} dni kalendarzowych do ostatniej zamkniętej sesji).",
         f"- Ticki: `copy_ticks_range` z `COPY_TICKS_INFO` (zmiany bid/ask), po jednym dniu. Surowe dane: "
         "`research/daily-data/data/spread_ticks/` (pomijane przez Git).",
         "- Spread = (ask − bid) / ((ask + bid) / 2), w procentach ceny. Kolumny: mediana | 75. percentyl | "
         "95. percentyl | udział ticków ze spreadem ≤ 0.",
         "- Sesja USA = 09:30–16:00 czasu Nowego Jorku, pon–pt (zimą 14:30–21:00 UTC, przed 1.11 13:30–20:00 UTC). "
         "Liczymy ticki, nie czas: mediana waży okresy z częstymi kwotowaniami mocniej.",
         f"- Czas serwera: przesunięcie zmierzone przy odczycie {offset_h:+d} h względem UTC; dla dat sprzed zmiany "
         "czasu w USA (1.11.2026) przyjęto o 1 h więcej (serwer zmienia czas razem z Nowym Jorkiem)."
         if offset_h is not None else "- Czas serwera: przesunięcia nie udało się zmierzyć (przyjęto +2 h).",
         f"- Symbole w Market Watch przed odczytem: {mw[0]}, po odczycie: {mw[1]}"
         + (" (bez zmian)." if mw[0] == mw[1] else " — **ZMIANA, sprawdzić**."),
         "- `symbol_select`, `account_info`, zlecenia, pozycje i historia rachunku: zablokowane w skrypcie.",
         "", "## ETF-y z USA: sesja USA i pozostałe godziny", "",
         "| Symbol | Ticki | Od | Do | Dni | Sesja USA: ticki | mediana | p75 | p95 | ≤ 0 | Poza sesją: ticki | mediana | p75 | p95 | ≤ 0 |",
         "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        if r["symbol"] in US_ETF and r["ticks"]:
            L.append(f"| `{r['symbol']}` | {r['ticks']} | {r['first'][:10]} | {r['last'][:10]} | {r['days_with_ticks']} | "
                     f"{r['us_ticks']} | {fmt(r['us'])} | {r['other_ticks']} | {fmt(r['other'])} |")
    L += ["", "## Pozostałe (całość, bez podziału)", "",
          "| Symbol | Ticki | Od | Do | Dni | mediana | p75 | p95 | ≤ 0 |",
          "|---|---:|---|---|---:|---:|---:|---:|---:|"]
    for r in results:
        if r["symbol"] not in US_ETF and r["ticks"]:
            L.append(f"| `{r['symbol']}` | {r['ticks']} | {r['first'][:10]} | {r['last'][:10]} | {r['days_with_ticks']} | "
                     f"{fmt(r['all'])} |")
    empty = [r["symbol"] for r in results if not r["ticks"]]
    L += ["", "## Pominięte", ""]
    L += [f"- `{s}`: {why}." for s, why in skipped] + [f"- `{s}`: broker nie oddał ticków w tym okresie." for s in empty] \
        or ["- Brak."]
    L += ["", "## Błędy pobrania", ""]
    L += [f"- {f}" for f in failures] or ["- Brak."]
    return "\n".join(L) + "\n"


# ---------- praca z terminalem ----------

def server_offset_h(mt5) -> int | None:
    for s in ("BTCUSD", "ETHUSD"):
        t = mt5.symbol_info_tick(s)
        if t is not None and t.time and abs(t.time - time.time()) < 6 * 3600:
            return int(round((t.time - time.time()) / 3600.0))
    return None


def fetch_symbol(mt5, symbol, start, end, now_off, now):
    """Ticki [start, end) UTC po jednym dniu. Zwraca (time_msc serwera, bid, ask, przesunięcie dla ticka)."""
    import numpy as np
    parts, offs = [], []
    day = start
    while day < end:
        off = server_offset_for(day + dt.timedelta(hours=12), now_off, now)
        a, b = day + dt.timedelta(hours=off), day + dt.timedelta(days=1, hours=off)
        arr = mt5.copy_ticks_range(symbol, a, b, mt5.COPY_TICKS_INFO)
        if arr is not None and len(arr):
            parts.append(arr[["time_msc", "bid", "ask"]])
            offs.append(np.full(len(arr), off, dtype="int8"))
        day += dt.timedelta(days=1)
    if not parts:
        return np.array([], dtype="int64"), np.array([]), np.array([]), np.array([], dtype="int8")
    arr = np.concatenate(parts)
    off = np.concatenate(offs)
    return arr["time_msc"].astype("int64"), arr["bid"].astype(float), arr["ask"].astype(float), off


def save_raw(symbol, ms, bid, ask) -> None:
    import pandas as pd
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"time_msc_server": ms, "bid": bid, "ask": ask}).to_parquet(
        OUT / f"{symbol}.parquet", index=False, engine="fastparquet")


def run(symbols=SYMBOLS, allow_algo: bool = False) -> int:
    import MetaTrader5 as raw_mt5  # tylko w środowisku research/scalp-smc/.venv
    mt5 = StrictReadOnlyMT5(raw_mt5)
    term = os.environ.get("MT5_TERMINAL")
    try:
        label = check_terminal(term, running_terminal_paths())
    except Exception as exc:
        log(f"odmowa połączenia: {exc}")
        return 2
    log(f"terminal: {label}")
    if not mt5.initialize(path=term):
        log(f"initialize() nie powiodło się: {mt5.last_error()}")
        return 2
    try:
        ti = mt5.terminal_info()
        refusal = algo_trading_refusal(ti, allow_algo)
    except Exception as exc:
        ti, refusal = None, f"nie udało się odczytać terminal_info ({exc!r})"
    if refusal:
        log(f"odmowa odczytu: {refusal}")
        mt5.shutdown()
        return EXIT_ALGO_TRADING
    algo_trading = ti.trade_allowed
    log(f"Algo Trading: {algo_text(algo_trading)}")
    now = dt.datetime.now(UTC)
    read_at = now.isoformat(timespec="seconds")
    start, end = window(now)
    results, skipped, failures = [], [], []
    try:
        mw_before = sum(1 for s in (mt5.symbols_get() or []) if s.visible)
        off = server_offset_h(mt5)
        now_off = off if off is not None else 2
        log(f"okres {start:%Y-%m-%d}..{end:%Y-%m-%d} UTC, przesunięcie serwera {now_off:+d} h, MW={mw_before}")
        for symbol in symbols:
            try:
                si = mt5.symbol_info(symbol)
                if si is None:
                    skipped.append((symbol, "brak symbolu u brokera"))
                    continue
                if not si.visible:
                    skipped.append((symbol, "poza Market Watch"))
                    log(f"{symbol}: poza Market Watch — pominięty")
                    continue
                ms, bid, ask, offs = fetch_symbol(mt5, symbol, start, end, now_off, now)
                if len(ms):
                    save_raw(symbol, ms, bid, ask)
                r = summarize(symbol, ms, bid, ask, offs)
                results.append(r)
                med = (r.get("us") or r.get("all") or {}).get("median")
                log(f"{symbol}: {r['ticks']} ticków" + (f", mediana {med:.4f}%" if med is not None else ""))
            except Exception as exc:  # jeden symbol nie przerywa reszty
                failures.append(f"`{symbol}`: błąd {type(exc).__name__}: {exc}")
                log(f"{symbol}: błąd {exc!r}")
        mw_after = sum(1 for s in (mt5.symbols_get() or []) if s.visible)
    finally:
        mt5.shutdown()
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / REPORT_NAME).write_text(
        report(results, skipped, failures, start, end, read_at, label, algo_trading, off, (mw_before, mw_after)),
        encoding="utf-8")
    log(f"gotowe: {len(results)} symboli, pominięto {len(skipped)}, błędy {len(failures)}, MW {mw_before}->{mw_after}")
    if mw_before != mw_after:
        return 3
    return 0 if any(r["ticks"] for r in results) else 1


# ---------- autotest bez terminala ----------

def selftest() -> int:
    import numpy as np
    from types import SimpleNamespace as NS

    class Fake:
        def __getattr__(self, name):
            raise AssertionError(f"wrapper przepuścił {name} do modułu")

    ro = StrictReadOnlyMT5(Fake())
    for bad in ("symbol_select", "account_info", "login", "order_send", "order_check", "orders_get",
                "positions_get", "history_deals_get", "copy_rates_range", "copy_rates_from_pos", "market_book_add"):
        try:
            getattr(ro, bad)
            raise AssertionError(f"{bad} przepuszczone")
        except PermissionError:
            pass
    assert len(SYMBOLS) == 17 and len(set(SYMBOLS)) == 17

    # okno: sobota 21.11.2026 01:00 UTC -> 22.10..21.11; poniedziałek rano -> kończy się w sobotę 00:00
    s, e = window(dt.datetime(2026, 11, 21, 1, 0, tzinfo=UTC))
    assert (s, e) == (dt.datetime(2026, 10, 22, tzinfo=UTC), dt.datetime(2026, 11, 21, tzinfo=UTC)), (s, e)
    s, e = window(dt.datetime(2026, 11, 23, 8, 0, tzinfo=UTC))
    assert e == dt.datetime(2026, 11, 21, tzinfo=UTC), e

    now = dt.datetime(2026, 11, 21, 1, 0, tzinfo=UTC)
    assert server_offset_for(dt.datetime(2026, 11, 10, tzinfo=UTC), 2, now) == 2
    assert server_offset_for(dt.datetime(2026, 10, 25, tzinfo=UTC), 2, now) == 3

    st = spread_stats([100, 100, 100, 0], [100.1, 100.2, 100, 100])
    assert st["n"] == 3 and st["invalid"] == 1 and abs(st["zero_or_neg_share"] - 1 / 3) < 1e-9
    assert abs(st["median"] - 0.1 / 100.05 * 100) < 1e-9

    # SPY: 15:00 UTC 18.11 (sesja), 03:00 UTC 18.11 (poza); czas serwera = UTC + 2 h
    base = dt.datetime(2026, 11, 18, tzinfo=UTC).timestamp()
    ms = np.array([(base + 15 * 3600 + 7200) * 1000, (base + 3 * 3600 + 7200) * 1000], dtype="int64")
    r = summarize("SPY", ms, np.array([500.0, 500.0]), np.array([500.05, 501.0]), np.array([2, 2]))
    assert r["us_ticks"] == 1 and r["other_ticks"] == 1, r
    assert r["us"]["median"] < r["other"]["median"]
    r2 = summarize("BTCUSD", ms, np.array([1.0, 1.0]), np.array([1.01, 1.01]), np.array([2, 2]))
    assert "us" not in r2 and r2["all"]["n"] == 2

    txt = report([r, r2, {"symbol": "IWM", "ticks": 0}], [("FXI", "poza Market Watch")], [],
                 dt.datetime(2026, 10, 22, tzinfo=UTC), dt.datetime(2026, 11, 21, tzinfo=UTC), "x",
                 "terminal danych (test)", True, 2, (1419, 1419))
    assert "`FXI`: poza Market Watch" in txt and "`IWM`: broker nie oddał" in txt and "(bez zmian)" in txt
    assert "zgody Karola z 21.11.2026" in txt and ALGO_FLAG in txt and "| `SPY` |" in txt and "| `BTCUSD` |" in txt
    assert "wyłączony." in report([], [], [], s, e, "x", "t", False, None, (1, 1))
    assert set(TERMINALS)  # te same znane instalacje co D1
    print("selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="testy bez połączenia z terminalem")
    ap.add_argument(ALGO_FLAG, dest="allow_algo", action="store_true",
                    help="czytaj także przy włączonym Algo Trading (zgoda Karola z 21.11.2026); "
                         "lista dozwolonych wywołań bez zmian")
    a = ap.parse_args()
    return selftest() if a.selftest else run(allow_algo=a.allow_algo)


if __name__ == "__main__":
    sys.exit(main())
