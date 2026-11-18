# -*- coding: utf-8 -*-
"""Eksport dziennych świec (D1) z terminala MT5 — WYŁĄCZNIE ODCZYT.

Zlecenie: D:\\CENTRUM\\01_PROJEKTY\\AURUQ-TRADING\\notatki\\ZLECENIE_SESJA_MT5_DANE_D1.md
Reguły badań, dla których są te dane: research/daily-trend/SPEC_H2_H3.md.

Zasady bezpieczeństwa (wzorzec: research/scalp-smc/scripts/collect_mt5.py):
- podpięcie do JUŻ DZIAŁAJĄCEGO terminala, bez loginu i hasła;
- moduł MetaTrader5 jest owinięty listą dozwolonych funkcji; każda inna
  (order_send, order_check, positions_get, orders_get, history_*, login, ...)
  kończy skrypt błędem, zanim cokolwiek zostanie wysłane;
- z account_info używana jest tylko nazwa serwera; numer rachunku nie jest
  ani zapisywany, ani wypisywany;
- jedyne wywołanie inne niż odczyt to symbol_select(symbol, True), gdy symbolu
  nie ma w Market Watch; każde takie wywołanie trafia do logu.

Wynik:
    research/daily-data/data/<SYMBOL>_D1.csv        (date,open,high,low,close,tick_volume,spread)
    research/daily-data/data/<SYMBOL>_D1.meta.json
    research/daily-data/reports/DANE_D1.md
    research/daily-data/logs/collect_d1.log

Użycie (środowisko z pakietem MetaTrader5):
    research\\scalp-smc\\.venv\\Scripts\\python.exe research\\daily-data\\scripts\\collect_d1.py
    python research/daily-data/scripts/collect_d1.py --selftest   (bez terminala)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, LOGS, REPORTS = ROOT / "data", ROOT / "logs", ROOT / "reports"
UTC = dt.timezone.utc
DAY = 86400
GAP_DAYS = 5

FORBIDDEN = ("order_send", "order_check", "order_calc_margin", "order_calc_profit",
             "positions_get", "positions_total", "orders_get", "orders_total", "login")
ALLOWED = frozenset({
    "initialize", "shutdown", "last_error", "version", "terminal_info", "account_info",
    "symbols_get", "symbol_info", "symbol_info_tick", "symbol_select",
    "copy_rates_from_pos", "copy_rates_range",
})

# Rynek -> wzorce nazwy symbolu i opisu (wielkie litery). Kolejność w NAME to priorytet.
MARKETS = {
    "SP500": {"name": [r"^US500", r"^SP500", r"^SPX500", r"^USA500", r"^SPX"], "desc": [r"S&P ?500", r"US ?500"]},
    "NAS100": {"name": [r"^NAS100", r"^US100", r"^USTEC", r"^NDX", r"^NASDAQ"], "desc": [r"NASDAQ ?100", r"US ?TECH ?100"]},
    "DAX": {"name": [r"^GER40", r"^DE40", r"^DAX40", r"^GER30", r"^DE30", r"^DAX"], "desc": [r"\bDAX\b", r"GERMAN(Y)? ?40"]},
    "GOLD": {"name": [r"^XAUUSD"], "desc": []},
    "BRENT": {"name": [r"^UKOUSD", r"^UKOIL", r"^BRENT", r"^XBRUSD"], "desc": [r"BRENT"]},
    "WTI": {"name": [r"^USOUSD", r"^USOIL", r"^WTI", r"^XTIUSD"], "desc": [r"\bWTI\b", r"WEST TEXAS"]},
    "EURUSD": {"name": [r"^EURUSD"], "desc": []},
    "BTCUSD": {"name": [r"^BTCUSD"], "desc": []},
    "ETHUSD": {"name": [r"^ETHUSD"], "desc": []},
}
SYMBOL_TRADE_MODE_FULL = 4
TRADE_MODES = {0: "DISABLED", 1: "LONGONLY", 2: "SHORTONLY", 3: "CLOSEONLY", 4: "FULL"}


def log(msg: str) -> None:
    line = f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "collect_d1.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


class ReadOnlyMT5:
    """Przepuszcza tylko funkcje z ALLOWED i stałe (WIELKIE_LITERY)."""

    def __init__(self, module):
        self._m = module
        self.select_calls: list[str] = []

    def __getattr__(self, name: str):
        if name in FORBIDDEN or name.startswith("history_") or name.startswith("order") \
                or name.startswith("position"):
            raise PermissionError(f"Zabronione wywołanie MetaTrader5.{name} (tylko odczyt)")
        if name.isupper():
            return getattr(self._m, name)
        if name not in ALLOWED:
            raise PermissionError(f"MetaTrader5.{name} nie jest na liście dozwolonych")
        if name == "symbol_select":
            return self._select
        if name == "account_info":
            return self._server_only
        return getattr(self._m, name)

    def _select(self, symbol: str, enable: bool = True):
        if enable is not True:
            raise PermissionError("symbol_select wolno wywołać tylko z enable=True")
        self.select_calls.append(symbol)
        log(f"symbol_select({symbol!r}, True) — dodanie do Market Watch (jedyne wywołanie inne niż odczyt)")
        ok = self._m.symbol_select(symbol, True)
        log(f"symbol_select({symbol!r}) -> {ok}")
        return ok

    def _server_only(self):
        ai = self._m.account_info()
        server = getattr(ai, "server", None) if ai is not None else None
        del ai  # numer rachunku nie wychodzi poza tę funkcję
        return server


# ---------- funkcje czyste (testowane w --selftest) ----------

def match_candidates(market: str, symbols) -> list:
    spec = MARKETS[market]
    out = []
    for s in symbols:
        name, desc = s.name.upper(), (getattr(s, "description", "") or "").upper()
        prio = next((i for i, p in enumerate(spec["name"]) if re.search(p, name)), None)
        if prio is None and any(re.search(p, desc) for p in spec["desc"]):
            prio = len(spec["name"])
        if prio is not None:
            out.append((prio, s))
    return out


def bars_to_rows(rates, digits: int, server_now: float) -> tuple[list[dict], list[str]]:
    """Zamienia świece na wiersze CSV; pomija świecę jeszcze trwającą. Zwraca (wiersze, pominięte daty)."""
    by_date: dict[str, dict] = {}
    skipped = []
    for r in rates:
        t = int(r["time"])
        d = dt.datetime.fromtimestamp(t, UTC).date().isoformat()  # czas serwera zapisany jako epoch
        if t + DAY > server_now:
            skipped.append(d)
            continue
        by_date[d] = {
            "date": d,
            "open": f"{float(r['open']):.{digits}f}",
            "high": f"{float(r['high']):.{digits}f}",
            "low": f"{float(r['low']):.{digits}f}",
            "close": f"{float(r['close']):.{digits}f}",
            "tick_volume": str(int(r["tick_volume"])),
            "spread": str(int(r["spread"])),
        }
    return [by_date[d] for d in sorted(by_date)], skipped


def csv_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["date", "open", "high", "low", "close", "tick_volume", "spread"],
                       lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def gaps(dates: list[str], limit: int = GAP_DAYS) -> list[dict]:
    out = []
    for a, b in zip(dates, dates[1:]):
        n = (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days
        if n > limit:
            out.append({"after": a, "before": b, "days": n})
    return out


# ---------- praca z terminalem ----------

def fetch_d1(mt5, symbol: str, maxbars: int):
    """Cała dostępna historia D1. Terminal może dociągać historię z serwera, więc powtarzamy do stabilizacji."""
    best, last_n = None, -1
    for attempt in range(6):
        count = maxbars
        rates = None
        while count >= 1000 and rates is None:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, count)
            if rates is None or len(rates) == 0:
                rates = None
                count //= 2
        n = 0 if rates is None else len(rates)
        if rates is not None and (best is None or n > len(best)):
            best = rates
        if n == last_n and n > 0:
            break
        last_n = n
        time.sleep(2 if attempt else 1)
    return best


def server_offset_h(mt5, symbols_24_7) -> int | None:
    for s in symbols_24_7:
        t = mt5.symbol_info_tick(s)
        if t is not None and t.time and abs(t.time - time.time()) < 6 * 3600:
            return int(round((t.time - time.time()) / 3600.0))
    return None


def choose(mt5, market: str, all_symbols, maxbars: int) -> tuple[object | None, list[dict], object]:
    cands = match_candidates(market, all_symbols)
    info = []
    for prio, s in sorted(cands, key=lambda x: (x[0], len(x[1].name), x[1].name)):
        info.append({"symbol": s.name, "description": s.description, "path": s.path,
                     "visible": bool(s.visible), "trade_mode": TRADE_MODES.get(s.trade_mode, s.trade_mode),
                     "priority": prio, "bars": None})
    if not info:
        return None, info, None
    full = [c for c in info if c["trade_mode"] == "FULL"] or info
    pool = [c for c in full if c["visible"]]
    if not pool:  # żaden kandydat nie jest w Market Watch: dodajemy tylko pierwszego wg priorytetu
        top = full[0]
        mt5.symbol_select(top["symbol"], True)
        pool = [top]
    best, best_rates = None, None
    for c in pool:
        rates = fetch_d1(mt5, c["symbol"], maxbars)
        c["bars"] = 0 if rates is None else int(len(rates))
        if rates is not None and (best is None or c["bars"] > best["bars"]):
            best, best_rates = c, rates
    return best, info, best_rates


def write_market(mt5, market: str, pick: dict, rates, server: str | None, server_now: float, read_at: str) -> dict:
    si = mt5.symbol_info(pick["symbol"])
    rows, skipped = bars_to_rows(rates, int(si.digits), server_now)
    if not rows:
        raise RuntimeError("brak zamkniętych świec")
    raw = csv_bytes(rows)
    DATA.mkdir(parents=True, exist_ok=True)
    stem = f"{pick['symbol']}_D1"
    (DATA / f"{stem}.csv").write_bytes(raw)
    dates = [r["date"] for r in rows]
    meta = {
        "market": market, "symbol": pick["symbol"], "description": si.description, "path": si.path,
        "digits": int(si.digits), "point": float(si.point), "trade_contract_size": float(si.trade_contract_size),
        "spread_points": int(si.spread), "spread_float": bool(si.spread_float),
        "spread_median_d1_points": statistics.median(int(r["spread"]) for r in rows),
        "swap_long": float(si.swap_long), "swap_short": float(si.swap_short),
        "swap_mode": int(si.swap_mode), "swap_rollover3days": int(si.swap_rollover3days),
        "currency_base": si.currency_base, "currency_profit": si.currency_profit,
        "trade_mode": TRADE_MODES.get(si.trade_mode, si.trade_mode),
        "bars": len(rows), "first_date": dates[0], "last_date": dates[-1],
        "excluded_forming_bar_dates": skipped,
        "gaps_over_5_days": gaps(dates),
        "csv_sha256": hashlib.sha256(raw).hexdigest(),
        "read_at_utc": read_at, "server": server,
        "candle_day": "dzień serwera MT5 (czas serwera zapisany jako epoch)",
    }
    (DATA / f"{stem}.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"{market}: {pick['symbol']} {len(rows)} świec {dates[0]}..{dates[-1]}, luki>5 dni: {len(meta['gaps_over_5_days'])}")
    return meta


def report(results: list[dict], failures: list[str], offset_h, select_calls, read_at: str, maxbars) -> str:
    L = ["# Dane D1 z terminala MT5", "",
         f"- Odczyt: {read_at} UTC, skrypt `research/daily-data/scripts/collect_d1.py` (tylko odczyt).",
         "- Pliki danych: `research/daily-data/data/` (pomijane przez Git).",
         f"- Limit świec terminala (maxbars): {maxbars}.",
         f"- `symbol_select`: {', '.join(select_calls) if select_calls else 'nie było wywołań'}.",
         "", "## Rynki", "",
         "| Rynek | Symbol | Od | Do | Świece | Luki > 5 dni | Spread teraz / mediana D1 [pkt] | Swap long / short (tryb, 3x dzień) |",
         "|---|---|---|---|---:|---:|---|---|"]
    for r in results:
        m = r["meta"]
        L.append(f"| {m['market']} | `{m['symbol']}` | {m['first_date']} | {m['last_date']} | {m['bars']} | "
                 f"{len(m['gaps_over_5_days'])} | {m['spread_points']} / {m['spread_median_d1_points']:g} | "
                 f"{m['swap_long']:g} / {m['swap_short']:g} ({m['swap_mode']}, {m['swap_rollover3days']}) |")
    L += ["", "## Wybór symbolu", ""]
    for r in results:
        others = [f"`{c['symbol']}` ({c['trade_mode']}, {'MW' if c['visible'] else 'poza MW'}"
                  + (f", {c['bars']} świec" if c["bars"] is not None else "") + ")"
                  for c in r["candidates"] if c["symbol"] != r["meta"]["symbol"]]
        L.append(f"- {r['meta']['market']}: `{r['meta']['symbol']}` — {r['meta']['description']}"
                 + (f"; pozostali kandydaci: {', '.join(others)}" if others else "; jedyny kandydat") + ".")
    L += ["", "## Luki dłuższe niż 5 dni kalendarzowych", ""]
    any_gap = False
    for r in results:
        g = r["meta"]["gaps_over_5_days"]
        if g:
            any_gap = True
            shown = ", ".join(f"{x['after']} → {x['before']} ({x['days']} dni)" for x in g[:10])
            more = f" i {len(g) - 10} kolejnych" if len(g) > 10 else ""
            L.append(f"- {r['meta']['market']}: {shown}{more}.")
    if not any_gap:
        L.append("- Brak.")
    L += ["", "## Strefa czasu świec", "",
          "Świeca D1 obejmuje dzień serwera MT5, a data w CSV to data początku świecy w czasie serwera.",
          "Według `research/scalp-smc/scripts/srvtime.py` serwer działa w UTC+2 zimą i w UTC+3 w czasie letnim USA "
          "(dzień kończy się o 17:00 w Nowym Jorku).",
          f"Zmierzone dziś przesunięcie serwera względem UTC: {('+' if offset_h >= 0 else '') + str(offset_h) + ' h' if offset_h is not None else 'nie udało się zmierzyć'}.",
          "Świeca bieżącego, niezamkniętego dnia jest pomijana (lista w polu `excluded_forming_bar_dates` pliku meta).",
          "", "## Czego nie udało się pobrać", ""]
    L += [f"- {f}" for f in failures] or ["- Wszystkie rynki z listy zostały pobrane."]
    return "\n".join(L) + "\n"


def run() -> int:
    import MetaTrader5 as raw_mt5  # tylko w środowisku research/scalp-smc/.venv
    mt5 = ReadOnlyMT5(raw_mt5)
    term = os.environ.get("MT5_TERMINAL", r"C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe")
    if not mt5.initialize(path=term):
        log(f"initialize() nie powiodło się: {mt5.last_error()}")
        return 2
    read_at = dt.datetime.now(UTC).isoformat(timespec="seconds")
    results, failures = [], []
    try:
        ti = mt5.terminal_info()
        server = mt5.account_info()
        maxbars = int(getattr(ti, "maxbars", 0) or 100000)
        log(f"terminal build={mt5.version()} connected={getattr(ti, 'connected', None)} maxbars={maxbars} server={server}")
        all_symbols = mt5.symbols_get() or []
        log(f"symboli w terminalu: {len(all_symbols)}")
        crypto = [s.name for s in all_symbols if re.match(r"^(BTCUSD|ETHUSD)", s.name.upper()) and s.visible]
        offset = server_offset_h(mt5, crypto)
        server_now = time.time() + (offset if offset is not None else 2) * 3600
        log(f"przesunięcie serwera względem UTC: {offset} h")
        for market in MARKETS:
            try:
                pick, cands, rates = choose(mt5, market, all_symbols, maxbars)
                if pick is None:
                    failures.append(f"{market}: brak pasującego symbolu u brokera.")
                    log(f"{market}: brak kandydatów")
                    continue
                if rates is None or len(rates) == 0:
                    failures.append(f"{market}: `{pick['symbol']}` nie zwrócił świec D1 ({mt5.last_error()}).")
                    continue
                meta = write_market(mt5, market, pick, rates, server, server_now, read_at)
                results.append({"meta": meta, "candidates": cands})
            except Exception as exc:  # jeden rynek nie przerywa reszty
                failures.append(f"{market}: błąd {type(exc).__name__}: {exc}")
                log(f"{market}: błąd {exc!r}")
    finally:
        mt5.shutdown()
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "DANE_D1.md").write_text(report(results, failures, offset, mt5.select_calls, read_at, maxbars),
                                        encoding="utf-8")
    log(f"gotowe: {len(results)} rynków, problemy: {len(failures)}")
    return 0 if results else 1


# ---------- autotest bez terminala ----------

def selftest() -> int:
    from types import SimpleNamespace as NS

    class Fake:
        TIMEFRAME_D1 = 16408

        def order_send(self, *a):
            raise AssertionError("nie powinno dojść do wywołania")

        def symbol_select(self, *a):
            return True

        def account_info(self):
            return NS(login=12345678, server="Test-Server")

    ro = ReadOnlyMT5(Fake())
    for bad in ("order_send", "order_check", "positions_get", "orders_get", "history_deals_get", "login"):
        try:
            getattr(ro, bad)
            raise AssertionError(f"{bad} przepuszczone")
        except PermissionError:
            pass
    assert ro.account_info() == "Test-Server"
    assert ro.TIMEFRAME_D1 == 16408
    try:
        ro.symbol_select("X", False)
        raise AssertionError("symbol_select(False) przepuszczone")
    except PermissionError:
        pass

    syms = [NS(name="US500", description="US 500 Index"), NS(name="SP500.r", description=""),
            NS(name="UKOUSD", description="Brent Crude Oil"), NS(name="XAUUSD+", description="Gold"),
            NS(name="EURUSD+", description="Euro vs US Dollar"), NS(name="GER40", description="Germany 40")]
    assert [s.name for _, s in match_candidates("SP500", syms)] == ["US500", "SP500.r"]
    assert [s.name for _, s in match_candidates("BRENT", syms)] == ["UKOUSD"]
    assert [s.name for _, s in match_candidates("DAX", syms)] == ["GER40"]
    assert match_candidates("WTI", syms) == []

    base = dt.datetime(2026, 11, 13, tzinfo=UTC).timestamp()  # piątek
    rates = [{"time": base + i * DAY, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15,
              "tick_volume": 10, "spread": 3} for i in (0, 3, 4, 5)]  # pt, pn, wt, śr (trwa)
    rates.append(dict(rates[1]))  # duplikat poniedziałku
    now = base + 5 * DAY + 3600
    rows, skipped = bars_to_rows(rates, 5, now)
    assert [r["date"] for r in rows] == ["2026-11-13", "2026-11-16", "2026-11-17"], rows
    assert skipped == ["2026-11-18"] and rows[0]["open"] == "1.10000"
    assert csv_bytes(rows).decode().splitlines()[0] == "date,open,high,low,close,tick_volume,spread"
    assert gaps(["2026-01-01", "2026-01-06", "2026-01-13"]) == [{"after": "2026-01-06", "before": "2026-01-13", "days": 7}]
    print("selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="testy bez połączenia z terminalem")
    a = ap.parse_args()
    return selftest() if a.selftest else run()


if __name__ == "__main__":
    sys.exit(main())
