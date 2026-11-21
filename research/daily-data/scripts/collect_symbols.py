# -*- coding: utf-8 -*-
"""Lista wszystkich instrumentów brokera z parametrami wielkości i kosztu — WYŁĄCZNIE ODCZYT.

Zlecenie koordynatora z 19.11.2026: przy kapitale 2 500 USD potrzebna jest pełna lista symboli,
żeby sprawdzić, z czego da się zbudować koszyk o łącznej ekspozycji do 1x kapitału.

Zasady bezpieczeństwa (jak w collect_d1.py, ale ostrzej):
- podpięcie do JUŻ DZIAŁAJĄCEGO terminala, bez loginu i hasła;
- dozwolone są wyłącznie: initialize, shutdown, last_error, symbols_get, symbol_info, symbol_info_tick;
  wszystko inne (w tym symbol_select, account_info, funkcje zleceń, pozycji i historii) kończy skrypt błędem;
- symbol_info_tick jest wołane tylko dla symboli już widocznych w Market Watch;
  dla pozostałych cena pochodzi z danych symbols_get albo zostaje null;
- liczba symboli widocznych w Market Watch jest sprawdzana przed i po odczycie;
- skrypt nie odczytuje numeru rachunku ani nazwy serwera.

Wynik:
    research/daily-data/data/symbols_all.json      (pełna lista, katalog pomijany przez Git)
    research/daily-data/reports/SYMBOLE_BROKERA.md (raport)
    research/daily-data/logs/collect_symbols.log

Użycie (środowisko z pakietem MetaTrader5):
    research\\scalp-smc\\.venv\\Scripts\\python.exe research\\daily-data\\scripts\\collect_symbols.py
    python research/daily-data/scripts/collect_symbols.py --selftest   (bez terminala)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_d1 import FORBIDDEN, TRADE_MODES  # noqa: E402  (ta sama lista zakazów)

ROOT = Path(__file__).resolve().parents[1]
DATA, LOGS, REPORTS = ROOT / "data", ROOT / "logs", ROOT / "reports"
UTC = dt.timezone.utc
LOT_LIMIT_USD = 500.0

ALLOWED = frozenset({"initialize", "shutdown", "last_error", "symbols_get", "symbol_info", "symbol_info_tick"})
SWAP_MODES = {0: "DISABLED", 1: "POINTS", 2: "CURRENCY_SYMBOL", 3: "CURRENCY_MARGIN", 4: "CURRENCY_DEPOSIT",
              5: "INTEREST_CURRENT", 6: "INTEREST_OPEN", 7: "REOPEN_CURRENT", 8: "REOPEN_BID"}
CALC_MODES = {0: "FOREX", 1: "FUTURES", 2: "CFD", 3: "CFDINDEX", 4: "CFDLEVERAGE", 5: "FOREX_NO_LEVERAGE",
              32: "EXCH_STOCKS", 33: "EXCH_FUTURES", 34: "EXCH_FUTURES_FORTS", 35: "EXCH_BONDS",
              36: "EXCH_STOCKS_MOEX", 37: "EXCH_BONDS_MOEX", 64: "SERV_COLLATERAL"}
FIELDS = ("name", "description", "path", "currency_base", "currency_profit", "currency_margin",
          "trade_contract_size", "volume_min", "volume_step", "volume_max", "trade_mode", "trade_calc_mode",
          "digits", "point", "trade_tick_size", "trade_tick_value", "swap_mode", "swap_long", "swap_short",
          "swap_rollover3days", "spread", "visible")


def log(msg: str) -> None:
    line = f"{dt.datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "collect_symbols.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


class StrictReadOnlyMT5:
    """Przepuszcza tylko funkcje z ALLOWED i stałe (WIELKIE_LITERY). Bez symbol_select i account_info."""

    def __init__(self, module):
        self._m = module

    def __getattr__(self, name: str):
        if name in FORBIDDEN or name.startswith(("history_", "order", "position")):
            raise PermissionError(f"Zabronione wywołanie MetaTrader5.{name} (tylko odczyt)")
        if name.isupper():
            return getattr(self._m, name)
        if name not in ALLOWED:
            raise PermissionError(f"MetaTrader5.{name} nie jest na liście dozwolonych")
        return getattr(self._m, name)


# ---------- funkcje czyste (testowane w --selftest) ----------

def num(v):
    return v if isinstance(v, (str, bool)) or v is None else float(v)


def price_of(bid, ask, last) -> tuple[float | None, str | None]:
    """Cena środkowa z bid/ask, a gdy jej brak — last. Zera traktujemy jako brak."""
    bid, ask, last = (float(x) if x else 0.0 for x in (bid, ask, last))
    if bid > 0 and ask > 0:
        return (bid + ask) / 2, "mid"
    if last > 0:
        return last, "last"
    if bid > 0 or ask > 0:
        return bid or ask, "bid" if bid else "ask"
    return None, None


def record(s, tick=None) -> dict:
    r = {k: num(getattr(s, k, None)) for k in FIELDS}
    r["trade_mode_name"] = TRADE_MODES.get(int(r["trade_mode"]), r["trade_mode"])
    r["swap_mode_name"] = SWAP_MODES.get(int(r["swap_mode"]), r["swap_mode"])
    r["trade_calc_mode_name"] = CALC_MODES.get(int(r["trade_calc_mode"] or 0), r["trade_calc_mode"])
    src = tick if tick is not None else s
    bid, ask, last = getattr(src, "bid", 0), getattr(src, "ask", 0), getattr(src, "last", 0)
    p, how = price_of(bid, ask, last)
    r.update(bid=float(bid) if bid else None, ask=float(ask) if ask else None, last=float(last) if last else None,
             price=p, price_source=(("tick:" if tick is not None else "symbols_get:") + how) if how else None)
    r["category"] = (r["path"] or "").replace("/", "\\").split("\\")[0] or "(brak)"
    return r


def fx_rates(records: list[dict]) -> dict[str, float]:
    """Kurs waluty -> USD z par walutowych tej samej listy (najpierw pary w trybie FULL)."""
    rates: dict[str, float] = {"USD": 1.0}
    for prefer_full in (True, False):
        for r in records:
            b, q, p = r["currency_base"], r["currency_profit"], r["price"]
            if not p or not b or not q or len(b) != 3 or len(q) != 3 or b == q:
                continue
            if prefer_full and r["trade_mode_name"] != "FULL":
                continue
            if q == "USD" and b not in rates:
                rates[b] = p
            elif b == "USD" and q not in rates:
                rates[q] = 1.0 / p
    return rates


def lot_value_usd(r: dict, rates: dict[str, float]) -> tuple[float | None, str | None]:
    """Wartość nominalna najmniejszego lota w USD = volume_min * kontrakt * cena, w walucie zysku, przeliczona na USD."""
    if not r["price"]:
        return None, "brak ceny"
    if not r["trade_contract_size"] or not r["volume_min"]:
        return None, "brak wielkości kontraktu"
    rate = rates.get(r["currency_profit"])
    if rate is None:
        return None, f"brak kursu {r['currency_profit']}/USD"
    return r["volume_min"] * r["trade_contract_size"] * r["price"] * rate, None


def enrich(records: list[dict]) -> dict[str, float]:
    rates = fx_rates(records)
    for r in records:
        v, why = lot_value_usd(r, rates)
        r["min_lot_value_usd"] = round(v, 2) if v is not None else None
        r["min_lot_value_note"] = why
    return rates


def report(records: list[dict], rates: dict, read_at: str, visible_before: int, visible_after: int,
           ticks: int) -> str:
    cats = Counter(r["category"] for r in records)
    cheap = sorted((r for r in records if r["min_lot_value_usd"] is not None
                    and r["min_lot_value_usd"] <= LOT_LIMIT_USD), key=lambda r: (r["min_lot_value_usd"], r["name"]))
    missing = [r for r in records if r["min_lot_value_usd"] is None]
    why = Counter(r["min_lot_value_note"] for r in missing)
    L = ["# Symbole brokera — parametry wielkości i kosztu", "",
         f"- Odczyt: {read_at} UTC, skrypt `research/daily-data/scripts/collect_symbols.py` (tylko odczyt: "
         "`symbols_get`, `symbol_info_tick` dla symboli już widocznych w Market Watch).",
         "- Pełna lista: `research/daily-data/data/symbols_all.json` (pomijana przez Git).",
         f"- Symboli razem: {len(records)}; widocznych w Market Watch przed odczytem {visible_before}, po odczycie "
         f"{visible_after}; odczytanych ticków: {ticks}.",
         f"- Kursy walut do przeliczenia na USD (z tej samej listy): {', '.join(sorted(rates))}.",
         "", "## Symbole według kategorii", "", "| Kategoria | Symboli |", "|---|---:|"]
    L += [f"| {c} | {n} |" for c, n in sorted(cats.items(), key=lambda x: (-x[1], x[0]))]
    L += ["", f"## Najmniejszy lot wart najwyżej {LOT_LIMIT_USD:g} USD", "",
          "Wartość nominalna = `volume_min` × `trade_contract_size` × cena, w walucie zysku, przeliczona kursem "
          "z tej samej listy. Cena to środek bid/ask; dla symboli spoza Market Watch pochodzi z ostatnich danych "
          "terminala i może być nieświeża. Swap w jednostkach trybu (`swap_mode`).", "",
          f"Spełnia warunek: {len(cheap)} symboli.", "",
          "| Symbol | Opis | Kategoria | Najmniejszy lot [USD] | Lot min / krok | Swap long / short (tryb) | Tryb handlu | MW |",
          "|---|---|---|---:|---|---|---|---|"]
    for r in cheap:
        L.append(f"| `{r['name']}` | {(r['description'] or '').replace('|', '/')} | {r['category']} | "
                 f"{r['min_lot_value_usd']:,.2f} | {r['volume_min']:g} / {r['volume_step']:g} | "
                 f"{r['swap_long']:g} / {r['swap_short']:g} ({r['swap_mode_name']}) | {r['trade_mode_name']} | "
                 f"{'tak' if r['visible'] else 'nie'} |")
    L += ["", "## Czego nie udało się policzyć", "",
          f"Wartości najmniejszego lota nie da się policzyć dla {len(missing)} symboli."]
    L += [f"- {k}: {n}" for k, n in sorted(why.items(), key=lambda x: (-x[1], x[0]))]
    nop = Counter(r["category"] for r in missing if r["min_lot_value_note"] == "brak ceny")
    if nop:
        L += ["", "Symbole bez ceny według kategorii (z ceną / razem):", ""]
        L += [f"- {c}: {cats[c] - n} / {cats[c]}" for c, n in sorted(nop.items(), key=lambda x: (-x[1], x[0]))]
    L += ["", "Uwagi:",
          "- Symbole spoza Market Watch nie były do niego dodawane. Gdy terminal nie ma dla nich ceny, "
          "pole `price` w JSON jest puste, a wartość lota nieobliczona.",
          "- Dla trybów wyceny innych niż FOREX/CFD (`trade_calc_mode_name` w JSON) wzór nominalny może nie "
          "odpowiadać depozytowi u brokera; tabela pokazuje ekspozycję, nie wymagany depozyt."]
    return "\n".join(L) + "\n"


# ---------- praca z terminalem ----------

def run() -> int:
    import MetaTrader5 as raw_mt5  # tylko w środowisku research/scalp-smc/.venv
    mt5 = StrictReadOnlyMT5(raw_mt5)
    term = os.environ.get("MT5_TERMINAL", r"C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe")
    if not mt5.initialize(path=term):
        log(f"initialize() nie powiodło się: {mt5.last_error()}")
        return 2
    read_at = dt.datetime.now(UTC).isoformat(timespec="seconds")
    try:
        symbols = mt5.symbols_get() or []
        visible_before = sum(1 for s in symbols if s.visible)
        log(f"symboli: {len(symbols)}, widocznych w Market Watch: {visible_before}")
        records, ticks, tick_fail = [], 0, []
        for s in symbols:
            tick = None
            if s.visible:
                tick = mt5.symbol_info_tick(s.name)
                if tick is None:
                    tick_fail.append(s.name)
                else:
                    ticks += 1
            records.append(record(s, tick))
        after = mt5.symbols_get() or []
        visible_after = sum(1 for s in after if s.visible)
        log(f"widocznych w Market Watch po odczycie: {visible_after}; ticki: {ticks}, brak ticka: {len(tick_fail)}")
    finally:
        mt5.shutdown()
    rates = enrich(records)
    DATA.mkdir(parents=True, exist_ok=True)
    out = {"read_at_utc": read_at, "count": len(records), "visible_before": visible_before,
           "visible_after": visible_after, "tick_failures": tick_fail, "fx_to_usd": rates, "symbols": records}
    (DATA / "symbols_all.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "SYMBOLE_BROKERA.md").write_text(report(records, rates, read_at, visible_before, visible_after, ticks),
                                                encoding="utf-8")
    log(f"gotowe: {len(records)} symboli, lot <= {LOT_LIMIT_USD:g} USD: "
        f"{sum(1 for r in records if r['min_lot_value_usd'] is not None and r['min_lot_value_usd'] <= LOT_LIMIT_USD)}")
    if visible_after != visible_before:
        log("UWAGA: liczba symboli w Market Watch zmieniła się w trakcie odczytu")
        return 3
    return 0 if records else 1


# ---------- autotest bez terminala ----------

def selftest() -> int:
    from types import SimpleNamespace as NS

    class Fake:
        TIMEFRAME_D1 = 16408

        def symbols_get(self):
            return []

    ro = StrictReadOnlyMT5(Fake())
    for bad in ("order_send", "order_check", "positions_get", "orders_get", "history_deals_get", "login",
                "symbol_select", "account_info", "copy_rates_from_pos", "market_book_add"):
        try:
            getattr(ro, bad)
            raise AssertionError(f"{bad} przepuszczone")
        except PermissionError:
            pass
    assert ro.symbols_get() == [] and ro.TIMEFRAME_D1 == 16408

    def sym(name, base, profit, cs, vmin, bid, ask, path, visible=True, mode=4, last=0.0):
        return NS(name=name, description=name, path=path, currency_base=base, currency_profit=profit,
                  currency_margin=base, trade_contract_size=cs, volume_min=vmin, volume_step=vmin, volume_max=100,
                  trade_mode=mode, trade_calc_mode=0, digits=5, point=0.00001, trade_tick_size=0.00001,
                  trade_tick_value=1.0, swap_mode=1, swap_long=-5.0, swap_short=1.0, swap_rollover3days=3,
                  spread=10, visible=visible, bid=bid, ask=ask, last=last)

    syms = [sym("EURUSD+", "EUR", "USD", 100000, 0.01, 1.10, 1.10, "Forex\\Majors\\EURUSD+"),
            sym("USDJPY+", "USD", "JPY", 100000, 0.01, 150.0, 150.0, "Forex\\Majors\\USDJPY+"),
            sym("JP225", "JPY", "JPY", 1, 0.1, 40000.0, 40000.0, "Indices\\JP225"),
            sym("ETHUSD", "ETH", "USD", 1, 0.01, 2300.0, 2302.0, "Crypto\\ETHUSD"),
            sym("XYZCHF", "XYZ", "CHF", 1, 1, 10.0, 10.0, "Shares/XYZCHF", visible=False),
            sym("NOPRICE", "ABC", "USD", 1, 1, 0.0, 0.0, "Shares\\NOPRICE", visible=False)]
    recs = [record(s) for s in syms]
    rates = enrich(recs)
    by = {r["name"]: r for r in recs}
    assert abs(rates["EUR"] - 1.10) < 1e-12 and abs(rates["JPY"] - 1 / 150) < 1e-12 and "CHF" not in rates
    assert by["EURUSD+"]["min_lot_value_usd"] == 1100.0
    assert by["USDJPY+"]["min_lot_value_usd"] == 1000.0  # 0.01 * 100000 * 150 JPY / 150
    assert abs(by["JP225"]["min_lot_value_usd"] - 26.67) < 1e-9
    assert by["ETHUSD"]["min_lot_value_usd"] == 23.01 and by["ETHUSD"]["price_source"] == "symbols_get:mid"
    assert by["XYZCHF"]["min_lot_value_usd"] is None and by["XYZCHF"]["min_lot_value_note"] == "brak kursu CHF/USD"
    assert by["NOPRICE"]["price"] is None and by["NOPRICE"]["min_lot_value_note"] == "brak ceny"
    assert by["XYZCHF"]["category"] == "Shares" and by["EURUSD+"]["category"] == "Forex"
    assert price_of(0, 0, 5.0) == (5.0, "last") and price_of(0, 0, 0) == (None, None)
    t = record(syms[3], NS(bid=2400.0, ask=2402.0, last=0.0))
    assert t["price"] == 2401.0 and t["price_source"] == "tick:mid"
    txt = report(recs, rates, "2026-11-19T00:00:00+00:00", 4, 4, 0)
    assert "| `ETHUSD` |" in txt and "| `EURUSD+` |" not in txt and "brak kursu CHF/USD: 1" in txt, txt
    assert txt.index("`ETHUSD`") < txt.index("`JP225`")
    print("selftest OK")
    return 0


def rebuild_report() -> int:
    """Przebudowuje raport z zapisanego symbols_all.json, bez łączenia z terminalem."""
    d = json.loads((DATA / "symbols_all.json").read_text(encoding="utf-8"))
    ticks = sum(1 for r in d["symbols"] if (r.get("price_source") or "").startswith("tick:"))
    (REPORTS / "SYMBOLE_BROKERA.md").write_text(
        report(d["symbols"], d["fx_to_usd"], d["read_at_utc"], d["visible_before"], d["visible_after"], ticks),
        encoding="utf-8")
    print("raport przebudowany z symbols_all.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="testy bez połączenia z terminalem")
    ap.add_argument("--report-only", action="store_true", help="tylko raport z zapisanego JSON, bez terminala")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    return rebuild_report() if a.report_only else run()


if __name__ == "__main__":
    sys.exit(main())
