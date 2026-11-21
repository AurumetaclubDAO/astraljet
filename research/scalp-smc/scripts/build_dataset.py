# -*- coding: utf-8 -*-
"""Buduje zbiory cech + etykiet triple-barrier (spread wliczony: long po ASK, wyjście po BID).
Poziom M1: decyzja na zamknięciu świecy j, wejście na otwarciu j+1, horyzonty 1/5/15 min.
Poziom tick (1 s siatka): decyzja co 5 s, opóźnienie wejścia 1 s, horyzonty 10/30/60 s.
TP=SL ustalane tylko z pierwszych 20% danych (bez przecieku skali z OOS).
Ta sama sekunda/świeca dotyka TP i SL => liczymy SL (konserwatywnie).
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from smc_features import m1_features
from srvtime import to_utc_s

ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT / "data"; FEAT = ROOT / "features"; REP = ROOT / "reports"
ENG = "fastparquet"

def load_m1(sym):
    fs = sorted((DATA / "m1" / sym).glob("*.parquet"))
    d = pd.concat([pd.read_parquet(p, engine=ENG) for p in fs])
    d = d[d["tick_volume"] > 0] if "tick_volume" in d else d
    return d.drop_duplicates("time").sort_values("time").reset_index(drop=True)

def barrier_m1(bars, spread, H, tp, sl):
    """Zwraca dla long/short: wynik (cena), wyjście (indeks świecy), kod (+1 TP, -1 SL, 0 czas)."""
    o, h, l, c = (bars[x].values for x in ("open", "high", "low", "close")); n = len(c)
    res = {}
    for side in ("long", "short"):
        pnl = np.full(n, np.nan); ex = np.full(n, -1); code = np.zeros(n, np.int8)
        for j in range(n - H - 1):
            e = o[j + 1] + spread if side == "long" else o[j + 1]  # ceny bid w świecach; ask=bid+spread
            done = False
            for k in range(j + 1, j + 1 + H):
                if side == "long":
                    hit_sl = l[k] <= e - sl; hit_tp = h[k] >= e + tp
                else:
                    hit_sl = h[k] + spread >= e + sl; hit_tp = l[k] + spread <= e - tp
                if hit_sl: pnl[j] = -sl; code[j] = -1; ex[j] = k; done = True; break
                if hit_tp: pnl[j] = tp; code[j] = 1; ex[j] = k; done = True; break
            if not done:
                k = j + H; pnl[j] = (c[k] - e) if side == "long" else (e - (c[k] + spread)); ex[j] = k
        res[side] = (pnl, ex, code)
    return res

def tick_grid(sym, days=None):
    fs = sorted((DATA / "ticks" / sym).glob("*.parquet"))
    if days: fs = fs[-days:]
    parts = []
    for p in fs:
        t = pd.read_parquet(p, columns=["time_msc", "bid", "ask"], engine=ENG)
        t = t[(t.bid > 0) & (t.ask > 0)]
        sec = (t["time_msc"].values // 1000).astype("int64")
        g = pd.DataFrame({"sec": sec, "bid": t.bid.values, "ask": t.ask.values})
        g["up"] = (g["bid"].diff() > 0).astype(np.int16); g["dn"] = (g["bid"].diff() < 0).astype(np.int16)
        a = g.groupby("sec").agg(bid=("bid", "last"), ask=("ask", "last"), bmax=("bid", "max"), bmin=("bid", "min"),
                                 amax=("ask", "max"), amin=("ask", "min"), n=("bid", "size"), up=("up", "sum"), dn=("dn", "sum"))
        parts.append(a)
    a = pd.concat(parts); a = a[~a.index.duplicated(keep="last")].sort_index()
    full = np.arange(a.index.min(), a.index.max() + 1)
    a = a.reindex(full)
    last_tick = pd.Series(np.where(a["n"].notna(), full, np.nan), index=full).ffill().values
    a["stale"] = full - last_tick
    for col in ("bid", "ask"): a[col] = a[col].ffill()
    for col, src in (("bmax", "bid"), ("bmin", "bid"), ("amax", "ask"), ("amin", "ask")): a[col] = a[col].fillna(a[src])
    for col in ("n", "up", "dn"): a[col] = a[col].fillna(0)
    a.index.name = "sec"
    return a

def barrier_tick(g, idx, H, tp, sl, lat=1):
    bid = g["bid"].values; ask = g["ask"].values; bmax = g["bmax"].values; bmin = g["bmin"].values
    amax = g["amax"].values; amin = g["amin"].values; n = len(bid)
    idx = idx[idx + lat + H < n]
    out = {}
    W = np.arange(lat + 1, lat + H + 1)
    for side in ("long", "short"):
        pnl = np.empty(len(idx)); ex = np.empty(len(idx), np.int64); code = np.zeros(len(idx), np.int8)
        for s in range(0, len(idx), 200000):
            ii = idx[s:s + 200000]; P = ii[:, None] + W[None, :]
            if side == "long":
                e = ask[ii + lat]; tpm = bmax[P] >= (e + tp)[:, None]; slm = bmin[P] <= (e - sl)[:, None]
                end = bid[ii + lat + H] - e
            else:
                e = bid[ii + lat]; tpm = amin[P] <= (e - tp)[:, None]; slm = amax[P] >= (e + sl)[:, None]
                end = e - ask[ii + lat + H]
            ft = np.where(tpm.any(1), tpm.argmax(1), 10**9); fs = np.where(slm.any(1), slm.argmax(1), 10**9)
            c = np.where((fs <= ft) & (fs < 10**9), -1, np.where(ft < 10**9, 1, 0))
            p = np.where(c == 1, tp, np.where(c == -1, -sl, end))
            off = np.where(c == 1, ft, np.where(c == -1, fs, H - 1)) + lat + 1
            pnl[s:s + len(ii)] = p; code[s:s + len(ii)] = c; ex[s:s + len(ii)] = ii + off
        out[side] = (pnl, ex, code)
    return idx, out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="ETHUSD,XAUUSD+")
    ap.add_argument("--tick-days", type=int, default=30)
    ap.add_argument("--tick-step", type=int, default=5)
    ap.add_argument("--tp-mult-m1", type=float, default=1.0, help="TP=SL = mult * mediana ATR14 * sqrt(H)")
    a = ap.parse_args(); FEAT.mkdir(exist_ok=True)
    meta = {}
    for sym in a.symbols.split(","):
        t0 = time.time(); m = load_m1(sym)
        f, bars = m1_features(m, 0.01)
        # spread z tików (realny), nie z pola spread świec
        g = tick_grid(sym, a.tick_days)
        spr = float(np.median((g["ask"] - g["bid"]).values[g["n"].values > 0]))
        n20 = int(len(bars) * 0.2); atr_med = float(np.nanmedian(bars["atr"].values[50:n20]))
        info = {"spread_med": spr, "atr14_med_first20pct": atr_med, "m1": {}, "tick": {}}
        lab = {}
        for H in (1, 5, 15):
            tp = max(a.tp_mult_m1 * atr_med * np.sqrt(H), 3 * spr)
            r = barrier_m1(bars, spr, H, tp, tp)
            for side, (pnl, ex, code) in r.items():
                lab[f"y_{side}_m{H}"] = (code == 1).astype(np.int8); lab[f"pnl_{side}_m{H}"] = pnl; lab[f"exit_{side}_m{H}"] = ex
            info["m1"][f"H{H}"] = {"tp": tp, "sl": tp, "spread_over_tp": spr / tp}
        fm = pd.concat([f, pd.DataFrame(lab)], axis=1)
        fm["utc_s"] = to_utc_s(fm["time"].values)
        fm.to_parquet(FEAT / f"{sym}_m1.parquet", index=False, engine=ENG)
        # ---- tick level
        sec = g.index.values
        dec = np.arange(0, len(g), a.tick_step); dec = dec[g["stale"].values[dec] <= 5]
        mid = ((g["bid"] + g["ask"]) / 2).values
        T = pd.DataFrame({"sec": sec[dec]})
        for w in (5, 15, 30, 60):
            prev = np.clip(dec - w, 0, None); T[f"ret_{w}s"] = (mid[dec] - mid[prev]) / spr
        cn = np.r_[0, np.cumsum(g["n"].values)]; cu = np.r_[0, np.cumsum(g["up"].values)]; cd = np.r_[0, np.cumsum(g["dn"].values)]
        for w in (5, 15, 30):
            lo = np.clip(dec + 1 - w, 0, None); nn = cn[dec + 1] - cn[lo]
            T[f"nticks_{w}s"] = nn
            T[f"imb_{w}s"] = ((cu[dec + 1] - cu[lo]) - (cd[dec + 1] - cd[lo])) / np.maximum(nn, 1)
        T["spread_now"] = (g["ask"] - g["bid"]).values[dec] / spr
        T["sec_in_min"] = sec[dec] % 60
        # aktualna (niezamknięta) świeca: ruch od otwarcia minuty
        mstart = sec[dec] - sec[dec] % 60; pos = np.searchsorted(sec, mstart); T["ret_from_min_open"] = (mid[dec] - mid[pos]) / spr
        # dołącz cechy ostatniej ZAMKNIĘTEJ M1 (open_time + 60 <= sec)
        fx = f.copy(); fx["avail"] = fx["time"] + 60
        T = pd.merge_asof(T.sort_values("sec"), fx.drop(columns=["time"]).sort_values("avail"), left_on="sec", right_on="avail",
                          direction="backward")
        T["m1_age_s"] = T["sec"] - T["avail"]; T = T.drop(columns=["avail"])
        rng = np.random.default_rng(0)
        n20 = int(len(dec) * 0.2)
        for H in (10, 30, 60):
            mv = np.abs(mid[np.clip(dec[:n20] + H, 0, len(mid) - 1)] - mid[dec[:n20]])
            tp = float(max(3 * spr, np.quantile(mv, 0.75)))
            idx, r = barrier_tick(g, dec, H, tp, tp)
            k = len(idx)
            for side, (pnl, ex, code) in r.items():
                T.loc[:k - 1, f"y_{side}_t{H}"] = (code == 1).astype(np.int8)
                T.loc[:k - 1, f"pnl_{side}_t{H}"] = pnl
                T.loc[:k - 1, f"exit_{side}_t{H}"] = sec[ex]
            info["tick"][f"H{H}"] = {"tp": tp, "sl": tp, "spread_over_tp": spr / tp}
        T["utc_s"] = to_utc_s(T["sec"].values)
        T.to_parquet(FEAT / f"{sym}_tick.parquet", index=False, engine=ENG)
        info["rows_m1"] = len(fm); info["rows_tick"] = len(T); info["tick_days"] = a.tick_days
        info["elapsed_s"] = round(time.time() - t0, 1); meta[sym] = info
        print(sym, json.dumps(info), flush=True)
    (REP / "dataset_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
