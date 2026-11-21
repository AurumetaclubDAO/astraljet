# -*- coding: utf-8 -*-
"""Opcjonalnie: lokalny model Ollama pisze po polsku prosty opis wykrytych setupów i wyników.
NIE służy do predykcji. Model dostaje tylko liczby wyliczone deterministycznie.
Użycie: python ollama_describe.py [--model SpeakLeash/bielik-minitron-7B-v3.0-instruct:Q4_K_M]"""
import argparse, json, urllib.request
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]; FEAT = ROOT / "features"; REP = ROOT / "reports"

def last_setups(sym):
    f = pd.read_parquet(FEAT / f"{sym}_m1.parquet", engine="fastparquet").tail(1).iloc[0]
    keys = ["int_trend", "sw_trend", "int_bars_bos_up", "int_bars_bos_dn", "int_bars_choch_up", "int_bars_choch_dn",
            "int_weak_low", "int_weak_high", "in_fvg_bull", "in_fvg_bear", "fvg_bull_n", "fvg_bear_n", "int_in_ob_bull",
            "int_in_ob_bear", "int_ob_bull_eq_touch", "int_ob_bear_eq_touch", "pdh_dist", "pdl_dist", "ema9_21", "macd_hist", "ao", "vol_ratio20"]
    return {k: (round(float(f[k]), 2) if pd.notna(f[k]) else None) for k in keys}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="SpeakLeash/bielik-minitron-7B-v3.0-instruct:Q4_K_M")
    ap.add_argument("--host", default="http://127.0.0.1:11434"); a = ap.parse_args()
    wf = json.loads((REP / "wf_results.json").read_text(encoding="utf-8"))
    summ = {}
    for k, v in wf["results"].items():
        summ[k] = {x["side"]: x["agg"]["model"] for x in v["folds"] if x["fold"] == "ALL"}
    facts = {"setupy_ostatniej_swiecy_M1": {s: last_setups(s) for s in ("ETHUSD", "XAUUSD+")}, "wyniki_OOS_model": summ}
    prompt = ("Jesteś asystentem, który tłumaczy liczby na prosty polski. Nie przewiduj cen, nie dawaj rekomendacji "
              "kupna/sprzedaży. Opisz w 8-12 zdaniach: (1) jaki układ Smart Money Concepts widać na ostatniej świecy M1 "
              "(trend wewnętrzny 1/-1, ile świec temu BOS/CHoCH, czy cena jest w FVG lub order blocku, odległości w ATR), "
              "(2) co mówią wyniki testu poza próbką (exp_price = średni wynik na transakcję po spreadzie, pf = profit factor). "
              "Słownik (używaj dokładnie): FVG = Fair Value Gap (luka wartości godziwej); OB = order block; BOS = wybicie struktury; "
              "CHoCH = zmiana charakteru trendu; trend 1 = wzrostowy, -1 = spadkowy. pf < 1 oraz exp_price < 0 oznaczają STRATĘ, "
              "a nie przewagę; przewaga byłaby dopiero przy pf > 1 stabilnie we wszystkich foldach. "
              "Podkreśl, że to badanie, nie dowód. Dane JSON:\n" + json.dumps(facts, ensure_ascii=False))
    body = json.dumps({"model": a.model, "prompt": prompt, "stream": False, "keep_alive": "2m",
                       "options": {"temperature": 0.2, "num_ctx": 8192}}).encode()
    req = urllib.request.Request(a.host + "/api/generate", data=body, headers={"Content-Type": "application/json"})
    txt = json.loads(urllib.request.urlopen(req, timeout=600).read())["response"]
    (REP / "ollama_opis.md").write_text(f"# Opis (model lokalny {a.model}) — tylko wyjaśnienie, nie predykcja\n\n{txt}\n", encoding="utf-8")
    print(txt)

if __name__ == "__main__":
    main()
