# -*- coding: utf-8 -*-
"""
Kolektor danych MT5 (READ-ONLY) dla badań scalp-smc.
- Podpina się do JUŻ DZIAŁAJĄCEGO terminala (bez loginu/hasła).
- Używa wyłącznie: symbols_get, symbol_info, symbol_info_tick, copy_rates_range, copy_ticks_range.
- NIE wysyła zleceń, NIE zmienia SL/TP, NIE zamyka pozycji.
- Przyrostowy: tiki zapisywane per dzień (data/ticks/<SYM>/YYYY-MM-DD.parquet),
  M1 per miesiąc (data/m1/<SYM>/YYYY-MM.parquet). Ponowne uruchomienie dociąga
  brakujące dni/miesiące i nadpisuje tylko ostatni (niepełny) plik.
Użycie:  python collect_mt5.py [--days 120] [--m1-months 36] [--symbols ETHUSD,XAUUSD]
"""
import argparse, json, os, sys, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
import MetaTrader5 as mt5
sys.path.insert(0, str(Path(__file__).resolve().parent))
from srvtime import to_utc_s

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"; LOGS = ROOT / "logs"; REPORTS = ROOT / "reports"
UTC = dt.timezone.utc
FORBIDDEN = ("order_send", "order_check", "positions_get", "login")  # dokumentacyjnie: nie używamy

def log(msg):
    line = f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with open(LOGS / "collector.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")

def find_symbol(base):
    cands = [s.name for s in (mt5.symbols_get() or []) if base in s.name.upper()]
    if not cands:
        return None, []
    exact = [c for c in cands if c.upper() == base]
    pick = exact[0] if exact else sorted(cands, key=len)[0]
    return pick, cands

def server_offset_hours(sym):
    """MT5 zwraca czas serwera jako 'epoch'. Szacujemy przesunięcie serwer-UTC z ostatniego tiku."""
    t = mt5.symbol_info_tick(sym)
    if t is None or not t.time:
        return None
    diff = t.time - time.time()
    return int(round(diff / 3600.0))

def ticks_day(sym, day):
    a = dt.datetime(day.year, day.month, day.day, tzinfo=UTC)
    b = a + dt.timedelta(days=1)
    arr = mt5.copy_ticks_range(sym, a, b, mt5.COPY_TICKS_ALL)
    if arr is None or len(arr) <= 1:
        return None
    df = pd.DataFrame(arr)
    df = df[["time_msc", "bid", "ask", "last", "volume", "flags"]]
    df["time_msc"] = df["time_msc"].astype("int64")
    return df

def rates_range(sym, a, b):
    arr = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, a, b)
    if arr is None or len(arr) <= 1:  # terminal zwraca 1 świecę dla miesięcy spoza historii (limit maxbars)
        return None
    df = pd.DataFrame(arr)
    df["time"] = df["time"].astype("int64")
    return df

def collect_ticks(sym, max_days, empty_stop):
    d = DATA / "ticks" / sym; d.mkdir(parents=True, exist_ok=True)
    existing = sorted(p.stem for p in d.glob("*.parquet"))
    today = dt.datetime.utcnow().date() + dt.timedelta(days=1)  # czas serwera wyprzedza UTC
    days = []
    if existing:
        last = dt.date.fromisoformat(existing[-1])
        cur = last
        while cur <= today:
            days.append(cur); cur += dt.timedelta(days=1)
        # wstecz tylko jeśli poprosiono o więcej niż mamy
        first = dt.date.fromisoformat(existing[0])
        back = [first - dt.timedelta(days=i) for i in range(1, max_days + 1)
                if first - dt.timedelta(days=i) >= today - dt.timedelta(days=max_days)]
    else:
        back = [today - dt.timedelta(days=i) for i in range(0, max_days + 1)]
    n_new = 0
    for day in days:
        df = ticks_day(sym, day)
        if df is not None:
            df.to_parquet(d / f"{day.isoformat()}.parquet", index=False, engine="fastparquet"); n_new += len(df)
    empty = 0
    for day in back:
        if (d / f"{day.isoformat()}.parquet").exists():
            continue
        df = ticks_day(sym, day)
        if df is None:
            empty += 1
            if empty >= empty_stop:
                log(f"{sym} ticks: {empty_stop} pustych dni z rzędu — koniec historii przed {day}")
                break
            continue
        empty = 0
        df.to_parquet(d / f"{day.isoformat()}.parquet", index=False, engine="fastparquet"); n_new += len(df)
        log(f"{sym} ticks {day}: {len(df)}")
    log(f"{sym} ticks: nowe/odświeżone wiersze {n_new}")

def collect_m1(sym, months, empty_stop=3):
    d = DATA / "m1" / sym; d.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(UTC) + dt.timedelta(days=1)
    existing = sorted(p.stem for p in d.glob("*.parquet"))
    def month_start(y, m): return dt.datetime(y, m, 1, tzinfo=UTC)
    def next_month(t): return month_start(t.year + (t.month == 12), 1 if t.month == 12 else t.month + 1)
    cur = month_start(now.year, now.month)
    mlist = []
    for _ in range(months):
        mlist.append(cur)
        prev = cur - dt.timedelta(days=1); cur = month_start(prev.year, prev.month)
    empty = 0
    for ms in mlist:
        key = ms.strftime("%Y-%m")
        is_recent = existing and key >= existing[-1]
        if (d / f"{key}.parquet").exists() and not is_recent:
            continue
        df = rates_range(sym, ms, next_month(ms))
        if df is None:
            empty += 1
            if empty >= empty_stop:
                log(f"{sym} M1: {empty_stop} pustych miesięcy — koniec historii przed {key}")
                break
            continue
        empty = 0
        df.to_parquet(d / f"{key}.parquet", index=False, engine="fastparquet")
        log(f"{sym} M1 {key}: {len(df)}")

def inventory(sym, off):
    inv = {"symbol": sym, "server_utc_offset_h_now": off}
    tz = "Europe/Warsaw"
    tf = sorted((DATA / "ticks" / sym).glob("*.parquet"))
    if tf:
        n = 0; gaps = []; first = last = None; spreads = []
        for p in tf:
            t = pd.read_parquet(p, columns=["time_msc", "bid", "ask"], engine="fastparquet")
            n += len(t)
            ts = t["time_msc"].values
            first = ts[0] if first is None else first; last = ts[-1]
            g = np.diff(ts) / 1000.0
            if len(g):
                i = int(np.argmax(g)); gaps.append((p.stem, float(g[i]), int(ts[i])))
            spreads.append((t["ask"] - t["bid"]).sample(min(len(t), 20000), random_state=0))
        sp = pd.concat(spreads)
        conv = lambda ms: pd.to_datetime(float(to_utc_s(ms / 1000.0)), unit="s", utc=True).tz_convert(tz).isoformat()
        big = sorted(gaps, key=lambda x: -x[1])[:5]
        inv["ticks"] = {"files_days": len(tf), "rows": int(n), "first_warsaw": conv(first), "last_warsaw": conv(last),
                        "largest_gaps_s": [{"day": a, "gap_s": round(b, 1), "at_warsaw": conv(c)} for a, b, c in big],
                        "spread_price_median": float(sp.median()), "spread_price_p90": float(sp.quantile(0.9))}
    mf = sorted((DATA / "m1" / sym).glob("*.parquet"))
    if mf:
        m = pd.concat([pd.read_parquet(p, engine="fastparquet") for p in mf]).drop_duplicates("time").sort_values("time")
        m = m.reset_index(drop=True)
        g = np.diff(m["time"].values)
        conv = lambda s: pd.to_datetime(float(to_utc_s(s)), unit="s", utc=True).tz_convert(tz).isoformat()
        idx = np.argsort(-g)[:5]
        inv["m1"] = {"rows": int(len(m)), "first_warsaw": conv(m["time"].iloc[0]), "last_warsaw": conv(m["time"].iloc[-1]),
                     "gaps_over_5min": int((g > 300).sum()), "gaps_over_1h": int((g > 3600).sum()),
                     "largest_gaps": [{"gap_min": int(g[i] // 60), "after_warsaw": conv(m["time"].iloc[i])} for i in idx]}
    return inv

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="ETHUSD,XAUUSD")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--m1-months", type=int, default=36)
    ap.add_argument("--empty-stop", type=int, default=6)
    a = ap.parse_args()
    LOGS.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True)
    # Podpięcie do działającego terminala, BEZ loginu/hasła.
    TERM = os.environ.get("MT5_TERMINAL", r"C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe")
    if not mt5.initialize(path=TERM):
        log(f"initialize() failed: {mt5.last_error()}"); sys.exit(2)
    ti = mt5.terminal_info(); ai = mt5.account_info()
    log(f"terminal: {ti.name if ti else '?'} build={mt5.version()} trade_allowed={getattr(ti,'trade_allowed',None)} "
        f"server={getattr(ai,'server','?')}")
    out = {"generated_local": dt.datetime.now().isoformat(timespec="seconds"),
           "server": getattr(ai, "server", None), "maxbars": getattr(ti, "maxbars", None), "symbols": []}
    for base in a.symbols.split(","):
        sym, cands = find_symbol(base.strip().upper())
        if not sym:
            log(f"brak symbolu {base}"); continue
        si = mt5.symbol_info(sym)
        if si is not None and not si.visible:
            mt5.symbol_select(sym, True)  # tylko widoczność w Market Watch (read-only)
        off = server_offset_hours(sym)
        log(f"{base}: wybrano {sym} (kandydaci {cands}) offset serwera ~{off}h")
        collect_m1(sym, a.m1_months)
        collect_ticks(sym, a.days, a.empty_stop)
        inv = inventory(sym, off)
        inv["candidates"] = cands
        inv["symbol_info"] = {k: getattr(si, k) for k in ("digits", "point", "spread", "spread_float",
                              "trade_contract_size", "volume_min", "volume_step", "trade_tick_value",
                              "trade_tick_size", "trade_stops_level", "currency_profit", "path")}
        out["symbols"].append(inv)
    mt5.shutdown()
    p = REPORTS / "data_inventory.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log(f"inventory -> {p}")

if __name__ == "__main__":
    main()
