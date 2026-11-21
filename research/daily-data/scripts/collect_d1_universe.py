# -*- coding: utf-8 -*-
"""Eksport D1 dla jawnej listy symboli (uniwersum serii 2) — WYŁĄCZNIE ODCZYT.

Zlecenie koordynatora AURUQ-TRADING z 19–20.11.2026. Decyzja Karola: symbole do Market Watch
dodaje sam, skrypt niczego w terminalu nie zmienia.

Różnice względem collect_d1.py:
- dokładne nazwy symboli z listy, bez dopasowań wzorcem;
- symbol_select jest zabronione całkowicie (ani True, ani False), account_info także;
- symbol spoza Market Watch (visible == False) jest pomijany i wypisany w raporcie;
- wyjście do osobnego katalogu data/uniwersum/ (skrypty serii 1 czytają tylko data/*_D1.meta.json);
- meta bez nazwy serwera, z trade_calc_mode, path i liczbą prób pobrania historii.

Wynik:
    research/daily-data/data/uniwersum/<SYMBOL>_D1.csv        (date,open,high,low,close,tick_volume,spread)
    research/daily-data/data/uniwersum/<SYMBOL>_D1.meta.json
    research/daily-data/reports/DANE_D1_UNIWERSUM.md
    research/daily-data/logs/collect_d1_universe.log

Terminal trzeba wskazać jawnie w MT5_TERMINAL; dozwolone są tylko dwie znane instalacje (TERMINALS).
Skrypt podpina się wyłącznie do terminala, który już działa; nigdy go nie uruchamia.

Użycie (środowisko z pakietem MetaTrader5):
    $env:MT5_TERMINAL = 'E:\\MT5-DEMO\\Vantage\\terminal64.exe'   # terminal danych
    research\\scalp-smc\\.venv\\Scripts\\python.exe research\\daily-data\\scripts\\collect_d1_universe.py
    python research/daily-data/scripts/collect_d1_universe.py --selftest   (bez terminala)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_d1 import FORBIDDEN, TRADE_MODES, bars_to_rows, csv_bytes, gaps, sizing  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT, LOGS, REPORTS = ROOT / "data" / "uniwersum", ROOT / "logs", ROOT / "reports"
UTC = dt.timezone.utc
MIN_BARS = 500
CALC_MODES = {0: "FOREX", 1: "FUTURES", 2: "CFD", 3: "CFDINDEX", 4: "CFDLEVERAGE", 5: "FOREX_NO_LEVERAGE",
              32: "EXCH_STOCKS", 33: "EXCH_FUTURES", 34: "EXCH_FUTURES_FORTS", 35: "EXCH_OPTIONS",
              36: "EXCH_OPTIONS_MARGIN", 37: "EXCH_BONDS", 38: "EXCH_STOCKS_MOEX", 39: "EXCH_BONDS_MOEX",
              64: "SERV_COLLATERAL"}

# Lista Karola (51; ostatnie 6 opcjonalne) + 10 symboli pobranych 20.11 z terminala głównego.
# Symbol musi być widoczny w Market Watch terminala, z którego czytamy; skrypt go nie dodaje.
ADDED_BY_KAROL = (
    "SPY", "QQQ", "IWM", "XLF", "XLK", "SMH", "US2000.r", "EFA", "EEM", "EWJ", "FXI", "MCHI", "INDA", "EWZ",
    "EWY", "EWT", "EU50.r", "UK100.r", "Nikkei225", "HK50.r", "CHINAH.r", "SPI200.r", "TLT", "USNote10Y",
    "EUB10Y", "EUB5Y", "EUB2Y", "EUB30Y", "LongGilt", "GLD", "GDX", "XPTUSD.r", "XAGUSD", "USO", "BNO", "UNG",
    "DBC", "XOP", "Wheat-Cr", "Soybean-Cr", "LTCUSD", "BCHUSD", "IBIT", "GBPUSD+", "AUDUSD+",
    "SP500ft.r", "UK100ft.r", "HK50ft.r", "JPN225ft", "CL-OIL", "UKOUSDft",
)
READ_EARLIER = ("SP500.r", "XAUUSD+", "UKOUSD", "USOUSD", "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "EURUSD+", "USDJPY+")
UNIVERSE = ADDED_BY_KAROL + READ_EARLIER

# Znane instalacje na SOLYG-OMEN. Obie są zalogowane na rachunek LIVE; nazwa katalogu E:\MT5-DEMO jest historyczna.
TERMINALS = {
    r"C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe": r"terminal główny (C:\Program Files\Vantage Markets MT5 Terminal)",
    r"E:\MT5-DEMO\Vantage\terminal64.exe": r"terminal danych (E:\MT5-DEMO\Vantage)",
}


def norm_path(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


def terminal_label(path: str | None) -> str | None:
    """Etykieta znanej instalacji albo None (nieznana ścieżka lub brak MT5_TERMINAL)."""
    if not path:
        return None
    return next((label for p, label in TERMINALS.items() if norm_path(p) == norm_path(path)), None)


def running_terminal_paths() -> list[str]:
    """Ścieżki działających procesów terminal64.exe (bez psutil: przez PowerShell, tylko odczyt)."""
    import subprocess
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process terminal64 -ErrorAction SilentlyContinue | ForEach-Object { $_.Path }"],
        capture_output=True, text=True, timeout=30)
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


EXIT_ALGO_TRADING = 4  # handel automatyczny w terminalu nie jest na pewno wyłączony


ALGO_FLAG = "--algo-trading-dozwolone"
ALGO_CONSENT = "odczyt mimo włączonego Algo Trading na podstawie zgody Karola z 21.11.2026"


def algo_trading_refusal(terminal_info, allow_algo: bool = False) -> str | None:
    """None, gdy wolno czytać; inaczej powód odmowy.

    Domyślnie (warunek Karola z 20.11.2026) tylko przy trade_allowed dokładnie False.
    Z allow_algo (flaga --algo-trading-dozwolone, zgoda Karola z 21.11.2026) także przy True.
    Stan nieznany to zawsze odmowa. Flaga nie zmienia listy dozwolonych wywołań.
    """
    value = getattr(terminal_info, "trade_allowed", None)
    if value is False or (value is True and allow_algo):
        return None
    if value is True:
        return f"handel automatyczny (Algo Trading) jest włączony w terminalu (bez flagi {ALGO_FLAG})"
    return f"stan Algo Trading nieznany (trade_allowed={value!r})"


def algo_text(algo_trading) -> str:
    if algo_trading is True:
        return f"włączony — {ALGO_CONSENT} ({ALGO_FLAG})"
    return {False: "wyłączony"}.get(algo_trading, "nieznany")


def check_terminal(path: str | None, running: list[str]) -> str:
    """Zwraca etykietę terminala albo rzuca RuntimeError. Terminal musi już działać (dokładnie jeden proces)."""
    label = terminal_label(path)
    if label is None:
        raise RuntimeError("MT5_TERMINAL musi wskazywać jedną ze znanych instalacji (TERMINALS)")
    n = sum(1 for p in running if norm_path(p) == norm_path(path))
    if n != 1:
        raise RuntimeError(f"terminal {label} nie działa jako dokładnie jeden proces ({n}); skrypt go nie uruchamia")
    return label

ALLOWED = frozenset({
    "initialize", "shutdown", "last_error", "version", "terminal_info",
    "symbols_get", "symbol_info", "symbol_info_tick", "copy_rates_from_pos", "copy_rates_range",
})


def log(msg: str) -> None:
    line = f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "collect_d1_universe.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


class StrictReadOnlyMT5:
    """Przepuszcza tylko ALLOWED i stałe (WIELKIE_LITERY). symbol_select i account_info są zabronione."""

    def __init__(self, module):
        self._m = module

    def __getattr__(self, name: str):
        if name in FORBIDDEN or name.startswith(("history_", "order", "position")) \
                or name in ("symbol_select", "account_info", "login"):
            raise PermissionError(f"Zabronione wywołanie MetaTrader5.{name} (tylko odczyt)")
        if name.isupper():
            return getattr(self._m, name)
        if name not in ALLOWED:
            raise PermissionError(f"MetaTrader5.{name} nie jest na liście dozwolonych")
        return getattr(self._m, name)


def fetch_d1(mt5, symbol: str, maxbars: int, tries: int = 8):
    """Cała dostępna historia D1; powtarza do ustabilizowania liczby świec. Zwraca (świece, liczba prób)."""
    best, last_n = None, -1
    for attempt in range(1, tries + 1):
        count, rates = maxbars, None
        while count >= 1000 and rates is None:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, count)
            if rates is None or len(rates) == 0:
                rates = None
                count //= 2
        n = 0 if rates is None else len(rates)
        if rates is not None and (best is None or n > len(best)):
            best = rates
        if n == last_n and n > 0:
            return best, attempt
        last_n = n
        time.sleep(2 if attempt > 1 else 1)
    return best, tries


def server_offset_h(mt5) -> int | None:
    for s in ("BTCUSD", "ETHUSD"):
        t = mt5.symbol_info_tick(s)
        if t is not None and t.time and abs(t.time - time.time()) < 6 * 3600:
            return int(round((t.time - time.time()) / 3600.0))
    return None


def build_meta(symbol: str, si, tick, rows, skipped, raw: bytes, attempts: int, read_at: str,
               terminal: str | None = None) -> dict:
    dates = [r["date"] for r in rows]
    return {
        "market": symbol, "symbol": symbol, "description": si.description, "path": si.path,
        "terminal": terminal,
        "digits": int(si.digits), "point": float(si.point), "trade_contract_size": float(si.trade_contract_size),
        "spread_points": int(si.spread), "spread_float": bool(si.spread_float),
        "spread_median_d1_points": statistics.median(int(r["spread"]) for r in rows),
        "swap_long": float(si.swap_long), "swap_short": float(si.swap_short),
        "swap_mode": int(si.swap_mode), "swap_rollover3days": int(si.swap_rollover3days),
        "currency_base": si.currency_base, "currency_profit": si.currency_profit,
        "trade_mode": TRADE_MODES.get(si.trade_mode, si.trade_mode),
        "trade_calc_mode": CALC_MODES.get(int(si.trade_calc_mode), int(si.trade_calc_mode)),
        **sizing(si),
        "tick_bid": float(tick.bid) if tick is not None else None,
        "tick_ask": float(tick.ask) if tick is not None else None,
        "tick_time_utc_epoch_server": int(tick.time) if tick is not None else None,
        "bars": len(rows), "first_date": dates[0], "last_date": dates[-1],
        "excluded_forming_bar_dates": skipped,
        "gaps_over_5_days": gaps(dates),
        "history_fetch_attempts": attempts,
        "csv_sha256": hashlib.sha256(raw).hexdigest(),
        "read_at_utc": read_at,
        "candle_day": "dzień serwera MT5 (czas serwera zapisany jako epoch)",
    }


def unusual(meta: dict) -> list[str]:
    out = []
    if meta["bars"] < MIN_BARS:
        out.append(f"tylko {meta['bars']} świec")
    if meta["gaps_over_5_days"]:
        out.append(f"{len(meta['gaps_over_5_days'])} luk > 5 dni")
    if meta["tick_bid"] is None or not meta["tick_bid"]:
        out.append("brak ticka")
    if meta["trade_mode"] != "FULL":
        out.append(f"tryb {meta['trade_mode']}")
    return out


def parse_symbols(text: str) -> tuple[str, ...]:
    """Lista symboli z --symbole: tylko podzbiór UNIVERSE, bez powtórzeń, w kolejności podanej."""
    picked = tuple(dict.fromkeys(s.strip() for s in text.split(",") if s.strip()))
    unknown = [s for s in picked if s not in UNIVERSE]
    if not picked or unknown:
        raise ValueError(f"--symbole musi być niepustym podzbiorem listy UNIVERSE; spoza listy: {unknown}")
    return picked


PAPER_OUT = ROOT / "data" / "paper_seria2"


def resolve_out(symbols, wyjscie: str | None) -> Path:
    """Katalog wyjściowy. Odczyt częściowy nie może pisać do data/uniwersum/ (wejście testu serii 2)."""
    partial = tuple(symbols) != tuple(UNIVERSE)
    out = Path(wyjscie).resolve() if wyjscie else ROOT / "data" / "uniwersum"
    if partial and not wyjscie:
        raise ValueError("Odczyt częściowy (--symbole) wymaga --wyjscie, np. research/daily-data/data/paper_seria2.")
    if partial and out == (ROOT / "data" / "uniwersum").resolve():
        raise ValueError("Odczyt częściowy nie może nadpisać data/uniwersum/ (pliki testu serii 2).")
    return out


def report_path(symbols) -> Path:
    """Pełna lista: raport w reports/ (w Git). Odczyt częściowy (np. dzienny dla paper): obok danych, poza Git."""
    return REPORTS / "DANE_D1_UNIWERSUM.md" if tuple(symbols) == tuple(UNIVERSE) else OUT / "ODCZYT_CZESCIOWY.md"


def report(metas, skipped, failures, mw_before, mw_after, offset_h, maxbars, read_at, terminal="nieznany",
           algo_trading=None, listed: int | None = None) -> str:
    algo = algo_text(algo_trading)
    listed = len(UNIVERSE) if listed is None else listed
    L = ["# Dane D1 — uniwersum kandydatów do serii 2", "",
         f"- Odczyt: {read_at} UTC, skrypt `research/daily-data/scripts/collect_d1_universe.py` (tylko odczyt).",
         f"- Źródło: {terminal}.",
         f"- Handel automatyczny w terminalu (przycisk Algo Trading) w chwili odczytu: {algo}.",
         "- Pliki danych: `research/daily-data/data/uniwersum/` (pomijane przez Git).",
         f"- Symboli na liście: {listed}; pobrano: {len(metas)}; pominięto (poza Market Watch lub brak u brokera): {len(skipped)}; błędy: {len(failures)}.",
         f"- Symbole w Market Watch przed odczytem: {mw_before}, po odczycie: {mw_after}"
         + (" (bez zmian)." if mw_before == mw_after else " — **ZMIANA, sprawdzić**."),
         "- `symbol_select` nie było wywołane (skrypt blokuje je w każdej postaci), `account_info` także.",
         f"- Limit świec terminala (maxbars): {maxbars}. Przesunięcie serwera względem UTC: "
         + (f"{offset_h:+d} h." if offset_h is not None else "nie udało się zmierzyć."),
         "", "## Pobrane symbole", "",
         "| Symbol | Od | Do | Świece | Luki > 5 dni | Spread teraz / mediana D1 [pkt] | Swap long / short (tryb, 3x dzień) | Tryb | Próby |",
         "|---|---|---|---:|---:|---|---|---|---:|"]
    for m in metas:
        L.append(f"| `{m['symbol']}` | {m['first_date']} | {m['last_date']} | {m['bars']} | {len(m['gaps_over_5_days'])} | "
                 f"{m['spread_points']} / {m['spread_median_d1_points']:g} | "
                 f"{m['swap_long']:g} / {m['swap_short']:g} ({m['swap_mode']}, {m['swap_rollover3days']}) | "
                 f"{m['trade_mode']} | {m['history_fetch_attempts']} |")
    short = [m for m in metas if m["bars"] < MIN_BARS]
    L += ["", f"## Mniej niż {MIN_BARS} świec", ""]
    L += [f"- `{m['symbol']}`: {m['bars']} świec od {m['first_date']}." for m in short] or ["- Brak."]
    L += ["", "## Inne rzeczy nietypowe", ""]
    odd = [(m["symbol"], [u for u in unusual(m) if "świec" not in u]) for m in metas]
    L += [f"- `{s}`: {', '.join(u)}." for s, u in odd if u] or ["- Brak."]
    L += ["", "## Pominięte", ""]
    L += [f"- `{s}`: {why}." for s, why in skipped] or ["- Brak."]
    L += ["", "## Błędy pobrania", ""]
    L += [f"- {f}" for f in failures] or ["- Brak."]
    L += ["", "Świeca D1 obejmuje dzień serwera MT5; świeca bieżącego, niezamkniętego dnia jest pomijana."]
    return "\n".join(L) + "\n"


def run(symbols=UNIVERSE, allow_algo: bool = False) -> int:
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
    read_at = dt.datetime.now(UTC).isoformat(timespec="seconds")
    metas, skipped, failures = [], [], []
    try:
        maxbars = int(getattr(ti, "maxbars", 0) or 100000)
        mw_before = sum(1 for s in (mt5.symbols_get() or []) if s.visible)
        log(f"terminal build={mt5.version()} connected={getattr(ti, 'connected', None)} maxbars={maxbars} MW={mw_before}")
        offset = server_offset_h(mt5)
        server_now = time.time() + (offset if offset is not None else 2) * 3600
        OUT.mkdir(parents=True, exist_ok=True)
        for symbol in symbols:
            try:
                si = mt5.symbol_info(symbol)
                if si is None:
                    skipped.append((symbol, "brak symbolu u brokera"))
                    log(f"{symbol}: brak u brokera")
                    continue
                if not si.visible:
                    skipped.append((symbol, "poza Market Watch"))
                    log(f"{symbol}: poza Market Watch — pominięty")
                    continue
                tick = mt5.symbol_info_tick(symbol)
                rates, attempts = fetch_d1(mt5, symbol, maxbars)
                if rates is None or len(rates) == 0:
                    failures.append(f"`{symbol}`: brak świec D1 ({mt5.last_error()}).")
                    continue
                rows, forming = bars_to_rows(rates, int(si.digits), server_now)
                if not rows:
                    failures.append(f"`{symbol}`: brak zamkniętych świec.")
                    continue
                raw = csv_bytes(rows)
                (OUT / f"{symbol}_D1.csv").write_bytes(raw)
                meta = build_meta(symbol, si, tick, rows, forming, raw, attempts, read_at, label)
                (OUT / f"{symbol}_D1.meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                                                            encoding="utf-8")
                metas.append(meta)
                log(f"{symbol}: {meta['bars']} świec {meta['first_date']}..{meta['last_date']}, próby {attempts}"
                    + (f", uwagi: {', '.join(unusual(meta))}" if unusual(meta) else ""))
            except Exception as exc:  # jeden symbol nie przerywa reszty
                failures.append(f"`{symbol}`: błąd {type(exc).__name__}: {exc}")
                log(f"{symbol}: błąd {exc!r}")
        mw_after = sum(1 for s in (mt5.symbols_get() or []) if s.visible)
    finally:
        mt5.shutdown()
    target = report_path(symbols)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        report(metas, skipped, failures, mw_before, mw_after, offset, maxbars, read_at, label, algo_trading,
               listed=len(symbols)),
        encoding="utf-8")
    log(f"gotowe: pobrano {len(metas)}, pominięto {len(skipped)}, błędy {len(failures)}, MW {mw_before}->{mw_after}")
    if mw_before != mw_after:
        return 3
    return 0 if metas else 1


# ---------- autotest bez terminala ----------

def selftest() -> int:
    from types import SimpleNamespace as NS

    class Fake:
        TIMEFRAME_D1 = 16408

        def __getattr__(self, name):
            raise AssertionError(f"wrapper przepuścił {name} do modułu")

    ro = StrictReadOnlyMT5(Fake())
    for bad in ("symbol_select", "account_info", "login", "order_send", "order_check", "order_calc_margin",
                "orders_get", "orders_total", "positions_get", "positions_total", "history_deals_get",
                "history_orders_get", "symbols_total", "market_book_add"):
        try:
            getattr(ro, bad)
            raise AssertionError(f"{bad} przepuszczone")
        except PermissionError:
            pass
    assert ro.TIMEFRAME_D1 == 16408
    assert len(UNIVERSE) == 61 and len(set(UNIVERSE)) == 61

    rows = [{"date": d, "open": "1", "high": "1", "low": "1", "close": "1", "tick_volume": "1", "spread": s}
            for d, s in (("2026-01-01", "3"), ("2026-01-09", "5"), ("2026-01-12", "4"))]
    si = NS(description="Test", path="ETF\\TEST", digits=2, point=0.01, trade_contract_size=1.0, spread=6,
            spread_float=True, swap_long=-1.5, swap_short=0.2, swap_mode=1, swap_rollover3days=3,
            currency_base="USD", currency_profit="USD", currency_margin="USD", trade_mode=4, trade_calc_mode=32,
            volume_min=1.0, volume_step=1.0, volume_max=1000.0, trade_tick_size=0.01, trade_tick_value=0.01)
    meta = build_meta("SPY", si, None, rows, [], csv_bytes(rows), 3, "2026-11-20T00:00:00+00:00")
    assert meta["market"] == "SPY" and meta["trade_calc_mode"] == "EXCH_STOCKS" and meta["path"] == "ETF\\TEST"
    assert meta["history_fetch_attempts"] == 3 and meta["spread_median_d1_points"] == 4
    assert "server" not in meta and not any("login" in k for k in meta)
    assert unusual(meta) == ["tylko 3 świec", "1 luk > 5 dni", "brak ticka"]
    txt = report([meta], [("CL-OIL", "poza Market Watch")], [], 23, 23, 2, 100000, "2026-11-20T00:00:00+00:00")
    assert "`CL-OIL`: poza Market Watch" in txt and "(bez zmian)" in txt and "nie było wywołane" in txt
    assert "ZMIANA" in report([meta], [], [], 23, 24, None, 100000, "x")

    main_exe, data_exe = list(TERMINALS)
    assert terminal_label(None) is None and terminal_label(r"C:\inny\terminal64.exe") is None
    assert check_terminal(data_exe.upper(), [main_exe, data_exe]).startswith("terminal danych")
    for path, running in ((None, [main_exe]), (r"C:\inny\terminal64.exe", [r"C:\inny\terminal64.exe"]),
                          (data_exe, [main_exe]), (data_exe, [data_exe, data_exe])):
        try:
            check_terminal(path, running)
            raise AssertionError(f"check_terminal przepuścił {path} przy {running}")
        except RuntimeError:
            pass
    m2 = build_meta("SPY", si, None, rows, [], csv_bytes(rows), 1, "x", "terminal danych (test)")
    assert m2["terminal"] == "terminal danych (test)"
    assert "- Źródło: terminal danych (test)." in report([m2], [], [], 1, 1, 2, 100000, "x", m2["terminal"])
    assert "w chwili odczytu: włączony — odczyt mimo włączonego Algo Trading na podstawie zgody Karola z 21.11.2026" \
        in report([m2], [], [], 1, 1, 2, 100000, "x", "t", True)
    assert "w chwili odczytu: wyłączony." in report([m2], [], [], 1, 1, 2, 100000, "x", "t", False)
    assert "w chwili odczytu: nieznany." in report([m2], [], [], 1, 1, 2, 100000, "x", "t")

    assert algo_trading_refusal(NS(trade_allowed=False)) is None
    for ti in (NS(trade_allowed=True), NS(), None, NS(trade_allowed=0), NS(trade_allowed=None)):
        assert algo_trading_refusal(ti), f"algo_trading_refusal przepuścił {ti!r}"
    # Flaga --algo-trading-dozwolone: przepuszcza True, ale nie stan nieznany.
    assert algo_trading_refusal(NS(trade_allowed=True), True) is None
    assert algo_trading_refusal(NS(trade_allowed=False), True) is None
    for ti in (NS(), None, NS(trade_allowed=0), NS(trade_allowed=None), NS(trade_allowed=1)):
        assert algo_trading_refusal(ti, True), f"flaga przepuściła {ti!r}"

    class FakeTerminal:  # run(): odmowa przy włączonym Algo, shutdown i żadnego pobierania
        TIMEFRAME_D1 = 16408

        def __init__(self, allowed):
            self.allowed, self.calls = allowed, []

        def __getattr__(self, name):
            calls = self.__dict__["calls"]
            allowed = self.__dict__["allowed"]

            def f(*a, **k):
                calls.append(name)
                if name == "terminal_info":
                    return NS(trade_allowed=allowed, maxbars=1000)
                if name == "symbols_get":
                    return []
                return None if name in ("symbol_info_tick", "symbol_info") else True
            return f

    import tempfile
    import types
    _log, _out, _reports = globals()["log"], globals()["OUT"], globals()["REPORTS"]
    # (trade_allowed, flaga, oczekiwany kod, oczekiwane wywołania)
    cases = ((True, False, EXIT_ALGO_TRADING, ["initialize", "terminal_info", "shutdown"]),
             (None, False, EXIT_ALGO_TRADING, ["initialize", "terminal_info", "shutdown"]),
             (None, True, EXIT_ALGO_TRADING, ["initialize", "terminal_info", "shutdown"]),
             (True, True, 1, None))
    for allowed, flag, code, expected_calls in cases:
        fake = FakeTerminal(allowed)
        saved = (sys.modules.get("MetaTrader5"), os.environ.get("MT5_TERMINAL"), globals()["running_terminal_paths"])
        sys.modules["MetaTrader5"] = types.SimpleNamespace(**{n: getattr(fake, n) for n in ALLOWED},
                                                           TIMEFRAME_D1=16408)
        os.environ["MT5_TERMINAL"] = data_exe
        globals()["running_terminal_paths"] = lambda: [data_exe]
        globals()["log"] = lambda msg: None
        tmp = Path(tempfile.mkdtemp(prefix="d1_selftest_"))
        globals()["OUT"], globals()["REPORTS"] = tmp / "out", tmp / "reports"
        try:
            assert run(symbols=(), allow_algo=flag) == code, (allowed, flag)
            if code != EXIT_ALGO_TRADING:  # z flagą przy włączonym Algo: raport mówi o zgodzie
                txt = (tmp / "out" / "ODCZYT_CZESCIOWY.md").read_text(encoding="utf-8")  # symbols=() to odczyt częściowy
                assert ALGO_CONSENT in txt and ALGO_FLAG in txt
                assert "shutdown" in fake.calls and not any(c.startswith(("order", "position", "history"))
                                                            for c in fake.calls)
        finally:
            globals()["OUT"], globals()["REPORTS"] = _out, _reports
            if saved[0] is None:
                sys.modules.pop("MetaTrader5", None)
            else:
                sys.modules["MetaTrader5"] = saved[0]
            if saved[1] is None:
                os.environ.pop("MT5_TERMINAL", None)
            else:
                os.environ["MT5_TERMINAL"] = saved[1]
            globals()["running_terminal_paths"] = saved[2]
            globals()["log"] = _log
        if expected_calls is not None:
            assert fake.calls == expected_calls, fake.calls
    basket = parse_symbols("IWM, XLF,XLK,EFA,EEM,FXI,GDX,USO,DBC,BNO,ETHUSD,IWM")
    assert len(basket) == 11 and basket[0] == "IWM"
    for bad in ("", "IWM,NIE-MA", "SPY;QQQ"):
        try:
            parse_symbols(bad)
            raise AssertionError(f"parse_symbols przepuścił {bad!r}")
        except ValueError:
            pass
    for args in ((basket, None), (basket, str(ROOT / "data" / "uniwersum"))):
        try:
            resolve_out(*args)
            raise AssertionError(f"resolve_out przepuścił {args[1]!r} dla odczytu częściowego")
        except ValueError:
            pass
    assert resolve_out(basket, str(PAPER_OUT)) == PAPER_OUT.resolve()
    assert resolve_out(UNIVERSE, None) == ROOT / "data" / "uniwersum"
    assert report_path(UNIVERSE) == REPORTS / "DANE_D1_UNIWERSUM.md"
    assert report_path(basket).parent == OUT  # odczyt częściowy nie nadpisuje raportu w Git
    assert "- Symboli na liście: 11;" in report([], [], [], 1, 1, 2, 100000, "x", "t", False, listed=11)
    print("selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="testy bez połączenia z terminalem")
    ap.add_argument(ALGO_FLAG, dest="allow_algo", action="store_true",
                    help="czytaj także przy włączonym Algo Trading (zgoda Karola z 21.11.2026); "
                         "lista dozwolonych wywołań bez zmian")
    ap.add_argument("--symbole", help="tylko te symbole z UNIVERSE, po przecinku (np. koszyk paper serii 2); "
                                      "wymaga --wyjscie; raport częściowy w katalogu wyjściowym, poza Git")
    ap.add_argument("--wyjscie", help="katalog na pliki D1 (dla paper: research/daily-data/data/paper_seria2); "
                                      "odczyt częściowy nie może pisać do data/uniwersum/")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    global OUT
    symbols = parse_symbols(a.symbole) if a.symbole else UNIVERSE
    OUT = resolve_out(symbols, a.wyjscie)
    return run(symbols, allow_algo=a.allow_algo)


if __name__ == "__main__":
    sys.exit(main())
