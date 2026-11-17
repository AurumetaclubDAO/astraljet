# -*- coding: utf-8 -*-
"""Deterministyczne detektory SMC + wskaźniki na M1 (bez patrzenia w przyszłość).
Każda cecha w wierszu j jest znana dopiero po ZAMKNIĘCIU świecy j.
Pivot (swing) o długości k jest potwierdzany dopiero na świecy i+k.
"""
import numpy as np, pandas as pd

def ema(x, n): return pd.Series(x).ewm(span=n, adjust=False).mean().values
def sma(x, n): return pd.Series(x).rolling(n, min_periods=n).mean().values

def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values

def pivots(h, l, k):
    """Zwraca maski pivotów high/low (na indeksie pivota i)."""
    n = len(h); ph = np.zeros(n, bool); pl = np.zeros(n, bool)
    hs = pd.Series(h); ls = pd.Series(l)
    mh = hs.rolling(2 * k + 1, center=True).max().values
    ml = ls.rolling(2 * k + 1, center=True).min().values
    ph[(h == mh)] = True; pl[(l == ml)] = True
    ph[:k] = ph[n - k:] = False; pl[:k] = pl[n - k:] = False
    return ph, pl

def structure(o, h, l, c, a, k, pref, max_fvg=30, max_ob=10):
    n = len(c); ph, pl = pivots(h, l, k)
    out = {x: np.full(n, np.nan) for x in [
        "trend", "bars_bos_up", "bars_bos_dn", "bars_choch_up", "bars_choch_dn", "dist_sh", "dist_sl",
        "dist_top", "dist_bot", "weak_high", "weak_low", "bars_sweep_bull", "bars_sweep_bear",
        "ob_bull_dist", "ob_bear_dist", "in_ob_bull", "in_ob_bear", "ob_bull_eq_touch", "ob_bear_eq_touch",
        "ob_bull_eq_dist", "ob_bear_eq_dist", "n_ob_bull", "n_ob_bear"]}
    trend = 0; sh = sl = None; shi = sli = -1; sh_brk = sl_brk = True
    last = {"bos_up": -10**9, "bos_dn": -10**9, "choch_up": -10**9, "choch_dn": -10**9, "sw_bull": -10**9, "sw_bear": -10**9}
    top = -np.inf; bot = np.inf
    obs_bull = []; obs_bear = []  # (lo, hi)
    for j in range(n):
        i = j - k
        if i >= 0 and ph[i]:
            sh, shi, sh_brk = h[i], i, False; top = h[i:j + 1].max()
        if i >= 0 and pl[i]:
            sl, sli, sl_brk = l[i], i, False; bot = l[i:j + 1].min()
        top = max(top, h[j]); bot = min(bot, l[j])
        # sweep: knot przez poziom, zamknięcie z powrotem
        if sh is not None and not sh_brk and h[j] > sh and c[j] <= sh: last["sw_bear"] = j
        if sl is not None and not sl_brk and l[j] < sl and c[j] >= sl: last["sw_bull"] = j
        if sh is not None and not sh_brk and c[j] > sh:
            last["choch_up" if trend <= 0 else "bos_up"] = j; trend = 1; sh_brk = True
            seg = slice(max(shi, 0), j)
            if seg.stop > seg.start:
                m = seg.start + int(np.argmin(l[seg])); obs_bull.append((l[m], h[m]))
                obs_bull = obs_bull[-max_ob:]
        if sl is not None and not sl_brk and c[j] < sl:
            last["choch_dn" if trend >= 0 else "bos_dn"] = j; trend = -1; sl_brk = True
            seg = slice(max(sli, 0), j)
            if seg.stop > seg.start:
                m = seg.start + int(np.argmax(h[seg])); obs_bear.append((l[m], h[m]))
                obs_bear = obs_bear[-max_ob:]
        # unieważnienie OB zamknięciem po drugiej stronie
        obs_bull = [z for z in obs_bull if c[j] >= z[0]]
        obs_bear = [z for z in obs_bear if c[j] <= z[1]]
        aj = a[j] if a[j] > 0 else np.nan
        r = out
        r["trend"][j] = trend
        for key, nm in (("bos_up", "bars_bos_up"), ("bos_dn", "bars_bos_dn"), ("choch_up", "bars_choch_up"),
                        ("choch_dn", "bars_choch_dn"), ("sw_bull", "bars_sweep_bull"), ("sw_bear", "bars_sweep_bear")):
            r[nm][j] = min(j - last[key], 500)
        if sh is not None: r["dist_sh"][j] = (sh - c[j]) / aj
        if sl is not None: r["dist_sl"][j] = (c[j] - sl) / aj
        r["dist_top"][j] = (top - c[j]) / aj; r["dist_bot"][j] = (c[j] - bot) / aj
        r["weak_high"][j] = 1.0 if trend > 0 else 0.0   # LuxAlgo: bias bycze => Weak High / Strong Low
        r["weak_low"][j] = 1.0 if trend < 0 else 0.0    # bias niedźwiedzie => Weak Low / Strong High
        r["n_ob_bull"][j] = len(obs_bull); r["n_ob_bear"][j] = len(obs_bear)
        if obs_bull:
            lo, hi = min(obs_bull, key=lambda z: abs(c[j] - z[1])); eq = (lo + hi) / 2
            r["ob_bull_dist"][j] = (c[j] - hi) / aj; r["in_ob_bull"][j] = float(l[j] <= hi and c[j] >= lo)
            r["ob_bull_eq_touch"][j] = float(l[j] <= eq <= h[j]); r["ob_bull_eq_dist"][j] = (c[j] - eq) / aj
        else:
            r["in_ob_bull"][j] = 0; r["ob_bull_eq_touch"][j] = 0
        if obs_bear:
            lo, hi = min(obs_bear, key=lambda z: abs(c[j] - z[0])); eq = (lo + hi) / 2
            r["ob_bear_dist"][j] = (lo - c[j]) / aj; r["in_ob_bear"][j] = float(h[j] >= lo and c[j] <= hi)
            r["ob_bear_eq_touch"][j] = float(l[j] <= eq <= h[j]); r["ob_bear_eq_dist"][j] = (eq - c[j]) / aj
        else:
            r["in_ob_bear"][j] = 0; r["ob_bear_eq_touch"][j] = 0
    return pd.DataFrame({f"{pref}_{x}": v for x, v in out.items()})

def fvg(h, l, c, a, max_keep=30):
    n = len(c); res = {x: np.full(n, np.nan) for x in ["fvg_bull_new", "fvg_bear_new", "fvg_bull_n", "fvg_bear_n",
        "fvg_bull_dist", "fvg_bear_dist", "in_fvg_bull", "in_fvg_bear", "fvg_bull_partial", "fvg_bear_partial", "fvg_bull_size"]}
    bulls = []; bears = []  # [bottom, top, partially_filled]
    for j in range(n):
        nb = ns = 0.0
        if j >= 2 and l[j] > h[j - 2]: bulls.append([h[j - 2], l[j], False]); nb = 1.0
        if j >= 2 and h[j] < l[j - 2]: bears.append([h[j], l[j - 2], False]); ns = 1.0
        # wypełnienie (od świecy następnej po powstaniu)
        nbulls = []
        for z in bulls[:-1] if nb else bulls:
            if l[j] <= z[0]: continue          # pełne wypełnienie -> usuń
            if l[j] < z[1]: z[2] = True
            nbulls.append(z)
        bulls = (nbulls + ([bulls[-1]] if nb else []))[-max_keep:]
        nbears = []
        for z in bears[:-1] if ns else bears:
            if h[j] >= z[1]: continue
            if h[j] > z[0]: z[2] = True
            nbears.append(z)
        bears = (nbears + ([bears[-1]] if ns else []))[-max_keep:]
        aj = a[j] if a[j] > 0 else np.nan
        res["fvg_bull_new"][j] = nb; res["fvg_bear_new"][j] = ns
        res["fvg_bull_n"][j] = len(bulls); res["fvg_bear_n"][j] = len(bears)
        below = [z for z in bulls if z[0] <= c[j]]
        if below:
            z = max(below, key=lambda q: q[1]); res["fvg_bull_dist"][j] = (c[j] - z[1]) / aj
            res["in_fvg_bull"][j] = float(z[0] <= c[j] <= z[1]); res["fvg_bull_partial"][j] = float(z[2])
            res["fvg_bull_size"][j] = (z[1] - z[0]) / aj
        else: res["in_fvg_bull"][j] = 0
        above = [z for z in bears if z[1] >= c[j]]
        if above:
            z = min(above, key=lambda q: q[0]); res["fvg_bear_dist"][j] = (z[0] - c[j]) / aj
            res["in_fvg_bear"][j] = float(z[0] <= c[j] <= z[1]); res["fvg_bear_partial"][j] = float(z[2])
        else: res["in_fvg_bear"][j] = 0
    return pd.DataFrame(res)

def m1_features(df, point, server_off_h=2):
    """df: kolumny time(server epoch s), open, high, low, close, tick_volume, spread."""
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    o, h, l, c = (df[x].values.astype(float) for x in ("open", "high", "low", "close"))
    v = df["tick_volume"].values.astype(float)
    a = atr(h, l, c, 14)
    f = pd.DataFrame({"time": df["time"].values})
    f["atr_rel"] = a / c
    for n in (9, 20, 21, 50):  # ZAŁOŻENIE: okresy MA z wykresu nieznane — testujemy popularne
        e = ema(c, n); f[f"ema{n}_dist"] = (c - e) / a; f[f"ema{n}_slope"] = (e - np.r_[e[0], e[:-1]]) / a
    f["ema9_21"] = (ema(c, 9) - ema(c, 21)) / a; f["ema20_50"] = (ema(c, 20) - ema(c, 50)) / a
    m = ema(c, 12) - ema(c, 26); s = ema(m, 9)
    f["macd"] = m / a; f["macd_sig"] = s / a; f["macd_hist"] = (m - s) / a
    med = (h + l) / 2; ao = sma(med, 5) - sma(med, 34)
    f["ao"] = ao / a; f["ao_diff"] = (ao - np.r_[np.nan, ao[:-1]]) / a
    f["vol_ratio20"] = v / pd.Series(v).rolling(20, min_periods=5).mean().values
    f["range_atr"] = (h - l) / a; f["body_atr"] = (c - o) / a
    f["spread_pts"] = df["spread"].values.astype(float)
    # dzień serwera (Vantage ~UTC+2/+3) => PDH/PDL i VWAP sesyjny
    day = (df["time"].values // 86400)
    g = pd.DataFrame({"day": day, "h": h, "l": l, "pv": med * v, "v": v})
    dh = g.groupby("day")["h"].max(); dl = g.groupby("day")["l"].min()
    pdh = pd.Series(day).map(dh.shift(1)).values; pdl = pd.Series(day).map(dl.shift(1)).values
    f["pdh_dist"] = (pdh - c) / a; f["pdl_dist"] = (c - pdl) / a
    vw = g.groupby("day")["pv"].cumsum() / g.groupby("day")["v"].cumsum().replace(0, np.nan)
    f["vwap_dist"] = (c - vw.values) / a
    utc = pd.to_datetime(df["time"].values - server_off_h * 3600, unit="s", utc=True)
    hr = utc.hour + utc.minute / 60
    f["hour_sin"] = np.sin(2 * np.pi * hr / 24); f["hour_cos"] = np.cos(2 * np.pi * hr / 24); f["dow"] = utc.dayofweek
    st_i = structure(o, h, l, c, a, 3, "int"); st_s = structure(o, h, l, c, a, 15, "sw")
    fv = fvg(h, l, c, a)
    f = pd.concat([f, st_i, st_s, fv], axis=1)
    bars = df[["time", "open", "high", "low", "close", "spread"]].copy(); bars["atr"] = a
    return f, bars
