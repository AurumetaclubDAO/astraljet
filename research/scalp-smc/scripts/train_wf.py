# -*- coding: utf-8 -*-
"""Walk-forward (bez tasowania) z purge/embargo. XGBoost na GPU (device=cuda), fallback CPU.
Dla każdego (symbol, poziom, horyzont, strona): model P(TP przed SL), próg wybierany na walidacji
(ostatnie 20% okna treningowego), test na kolejnym bloku. Transakcje symulowane bez nakładania się.
Porównanie z baseline: losowe wejścia (ta sama liczba), momentum, prosta reguła SMC.
BADANIE — nie dowód skuteczności."""
import argparse, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd, xgboost as xgb

ROOT = Path(__file__).resolve().parents[1]; FEAT = ROOT / "features"; REP = ROOT / "reports"; MOD = ROOT / "models"
ENG = "fastparquet"
CONTRACT = {"ETHUSD": 1.0, "XAUUSD+": 100.0}; VMIN = 0.01

def sim(t, ex, pnl, take):
    """Bez nakładania: wejście tylko gdy poprzednia pozycja zamknięta."""
    nxt = -np.inf; out = []
    for i in np.flatnonzero(take):
        if t[i] >= nxt and not np.isnan(pnl[i]): out.append(pnl[i]); nxt = ex[i]
    return np.array(out)

def stats(p, spr):
    if len(p) == 0: return {"n": 0}
    eq = np.cumsum(p); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(p) else 0
    gw = p[p > 0].sum(); gl = -p[p < 0].sum()
    return {"n": int(len(p)), "win_rate": round(float((p > 0).mean()), 3), "exp_price": round(float(p.mean()), 4),
            "exp_in_spreads": round(float(p.mean() / spr), 3), "pf": round(float(gw / gl), 3) if gl > 0 else None,
            "total_price": round(float(p.sum()), 3), "max_dd_price": round(dd, 3)}

def run(df, feats, t, H, tag, spr, n_folds, embargo, dev, rules, imp_acc):
    res = []; n = len(df); order = np.arange(n)
    start = int(n * 0.4); bounds = np.linspace(start, n, n_folds + 1).astype(int)
    X = df[feats].values.astype(np.float32)
    for side in ("long", "short"):
        y = df[f"y_{side}_{tag}"].values; pnl = df[f"pnl_{side}_{tag}"].values; ex = df[f"exit_{side}_{tag}"].values.astype(float)
        ok = ~np.isnan(pnl)
        all_p = {"model": [], "random": [], "momentum": [], "smc_rule": [], "always": []}
        for f in range(n_folds):
            a, b = bounds[f], bounds[f + 1]
            tr_end_time = t[a] - embargo
            tr = (t < tr_end_time) & (ex < t[a]) & ok          # purge: etykieta musi się skończyć przed testem
            tri = np.flatnonzero(tr); nv = int(len(tri) * 0.2)
            fit_i, val_i = tri[:-nv], tri[-nv:]
            fit_i = fit_i[ex[fit_i] < t[val_i[0]] - embargo]     # purge między fit i walidacją
            te = np.arange(a, b); te = te[ok[te]]
            m = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                                  min_child_weight=20, max_bin=128, tree_method="hist", device=dev, n_jobs=6,
                                  eval_metric="logloss", early_stopping_rounds=30)
            m.fit(X[fit_i], y[fit_i], eval_set=[(X[val_i], y[val_i])], verbose=False)
            pv = m.predict_proba(X[val_i])[:, 1]; pt = m.predict_proba(X[te])[:, 1]
            best = None
            for q in (0.995, 0.99, 0.98, 0.95, 0.9, 0.8):
                thr = np.quantile(pv, q); tk = np.zeros(n, bool); tk[val_i[pv >= thr]] = True
                s = sim(t, ex, pnl, tk)
                if len(s) >= 30 and (best is None or s.mean() > best[1]): best = (thr, s.mean(), q)
            if best is None: best = (np.quantile(pv, 0.95), np.nan, 0.95)
            tk = np.zeros(n, bool); tk[te[pt >= best[0]]] = True
            pm = sim(t, ex, pnl, tk); all_p["model"].append(pm)
            rng = np.random.default_rng(f); k = max(int(tk.sum()), 1)
            rk = np.zeros(n, bool); rk[rng.choice(te, size=min(k, len(te)), replace=False)] = True
            all_p["random"].append(sim(t, ex, pnl, rk))
            mom = np.zeros(n, bool); mom[te] = rules["mom_" + side][te]; all_p["momentum"].append(sim(t, ex, pnl, mom))
            sr = np.zeros(n, bool); sr[te] = rules["smc_" + side][te]; all_p["smc_rule"].append(sim(t, ex, pnl, sr))
            al = np.zeros(n, bool); al[te] = True; all_p["always"].append(sim(t, ex, pnl, al))
            g = m.get_booster().get_score(importance_type="gain")
            for kf, v in g.items():
                nm = feats[int(kf[1:])] if kf.startswith("f") and kf[1:].isdigit() else kf
                imp_acc[nm] = imp_acc.get(nm, 0) + v
            prec = float(y[te][pt >= best[0]].mean()) if (pt >= best[0]).any() else None
            res.append({"side": side, "fold": f, "test_from_utc": int(t[a]), "test_to_utc": int(t[b - 1]),
                        "train_n": int(len(fit_i)), "val_q": best[2], "val_exp": None if np.isnan(best[1]) else round(float(best[1]), 4),
                        "oos_signal_precision_tp": None if prec is None else round(prec, 3), "oos": stats(pm, spr),
                        "base_rate_tp": round(float(y[te].mean()), 3), "best_iter": int(getattr(m, "best_iteration", -1))})
        agg = {k: stats(np.concatenate(v) if v else np.array([]), spr) for k, v in all_p.items()}
        res.append({"side": side, "fold": "ALL", "agg": agg})
    return res

def rules_for(df, lvl):
    r = {}
    if lvl == "tick":
        r["mom_long"] = (df["ret_15s"] > 1).values; r["mom_short"] = (df["ret_15s"] < -1).values
    else:
        r["mom_long"] = (df["body_atr"] > 1).values; r["mom_short"] = (df["body_atr"] < -1).values
    # prosta reguła SMC: trend wewn. zgodny + dotknięcie EQ order blocka lub cena w FVG
    r["smc_long"] = ((df["int_trend"] > 0) & ((df["int_ob_bull_eq_touch"] > 0) | (df["in_fvg_bull"] > 0))).values
    r["smc_short"] = ((df["int_trend"] < 0) & ((df["int_ob_bear_eq_touch"] > 0) | (df["in_fvg_bear"] > 0))).values
    return r

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="ETHUSD,XAUUSD+"); ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--device", default="cuda"); a = ap.parse_args()
    meta = json.loads((REP / "dataset_meta.json").read_text(encoding="utf-8"))
    dev = a.device
    try:
        xgb.XGBClassifier(n_estimators=2, device=dev, tree_method="hist").fit(np.random.rand(100, 3), np.r_[np.zeros(50), np.ones(50)])
    except Exception as e:
        print("CUDA niedostępne dla XGBoost -> CPU:", e); dev = "cpu"
    out = {"device": dev, "results": {}}; t0 = time.time()
    for sym in a.symbols.split(","):
        spr = meta[sym]["spread_med"]
        for lvl, hs in (("m1", (1, 5, 15)), ("tick", (10, 30, 60))):
            df = pd.read_parquet(FEAT / f"{sym}_{lvl}.parquet", engine=ENG)
            t = df["utc_s"].values.astype(float)
            feats = [c for c in df.columns if not c.startswith(("y_", "pnl_", "exit_")) and c not in ("time", "sec", "utc_s")]
            rules = rules_for(df, lvl)
            for H in hs:
                tag = f"m{H}" if lvl == "m1" else f"t{H}"
                if f"y_long_{tag}" not in df: continue
                emb = (H * 60 if lvl == "m1" else H) + 3600
                if lvl == "tick":
                    for s in ("long", "short"): df[f"exit_{s}_{tag}"] = to_utc_exit(df, s, tag)
                else:
                    for s in ("long", "short"):
                        e = df[f"exit_{s}_{tag}"].values; df[f"exit_{s}_{tag}"] = np.where(e >= 0, t[np.clip(e, 0, len(t) - 1)] + 60, np.inf)
                imp = {}
                r = run(df, feats, t, H, tag, spr, a.folds, emb, dev, rules, imp)
                top = sorted(imp.items(), key=lambda x: -x[1])[:15]
                key = f"{sym}|{lvl}|{tag}"
                out["results"][key] = {"folds": r, "top_features_gain": [(k, round(v, 1)) for k, v in top],
                                       "tp_sl": meta[sym][lvl][f"H{H}"], "spread": spr, "rows": int(len(df))}
                aggs = [x for x in r if x["fold"] == "ALL"]
                print(key, json.dumps({x["side"]: {k: x["agg"][k] for k in ("model", "random", "smc_rule")} for x in aggs}), flush=True)
    out["elapsed_s"] = round(time.time() - t0, 1)
    (REP / "wf_results.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")

def to_utc_exit(df, s, tag):
    sys.path.insert(0, str(Path(__file__).resolve().parent)); from srvtime import to_utc_s
    e = df[f"exit_{s}_{tag}"].values.astype(float)
    return np.where(np.isnan(e), np.inf, to_utc_s(np.nan_to_num(e)))

if __name__ == "__main__":
    main()
