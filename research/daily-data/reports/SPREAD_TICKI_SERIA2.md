# Spread z historii ticków — kandydaci serii 2

- Odczyt: 2026-11-21T00:48:52+00:00 UTC, skrypt `research/daily-data/scripts/collect_spread_ticks.py` (tylko odczyt).
- Źródło: terminal danych (E:\MT5-DEMO\Vantage).
- Handel automatyczny w terminalu (przycisk Algo Trading) w chwili odczytu: wyłączony.
- Okres: 2026-10-22 00:00 – 2026-11-21 00:00 UTC (30 dni kalendarzowych do ostatniej zamkniętej sesji).
- Ticki: `copy_ticks_range` z `COPY_TICKS_INFO` (zmiany bid/ask), po jednym dniu. Surowe dane: `research/daily-data/data/spread_ticks/` (pomijane przez Git).
- Spread = (ask − bid) / ((ask + bid) / 2), w procentach ceny. Kolumny: mediana | 75. percentyl | 95. percentyl | udział ticków ze spreadem ≤ 0.
- Sesja USA = 09:30–16:00 czasu Nowego Jorku, pon–pt (zimą 14:30–21:00 UTC, przed 1.11 13:30–20:00 UTC). Liczymy ticki, nie czas: mediana waży okresy z częstymi kwotowaniami mocniej.
- Czas serwera: przesunięcie zmierzone przy odczycie +2 h względem UTC; dla dat sprzed zmiany czasu w USA (1.11.2026) przyjęto o 1 h więcej (serwer zmienia czas razem z Nowym Jorkiem).
- Symbole w Market Watch przed odczytem: 1419, po odczycie: 1419 (bez zmian).
- `symbol_select`, `account_info`, zlecenia, pozycje i historia rachunku: zablokowane w skrypcie.

## ETF-y z USA: sesja USA i pozostałe godziny

| Symbol | Ticki | Od | Do | Dni | Sesja USA: ticki | mediana | p75 | p95 | ≤ 0 | Poza sesją: ticki | mediana | p75 | p95 | ≤ 0 |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `IWM` | 360106 | 2026-10-22 | 2026-11-20 | 22 | 360106 | 0.0072 | 0.0106 | 0.0113 | 0.3% | 0 | — | — | — | — |
| `XLF` | 78062 | 2026-10-22 | 2026-11-20 | 22 | 78062 | 0.0176 | 0.0180 | 0.0356 | 1.1% | 0 | — | — | — | — |
| `XLK` | 377111 | 2026-10-22 | 2026-11-20 | 22 | 377111 | 0.0119 | 0.0167 | 0.0237 | 0.3% | 0 | — | — | — | — |
| `EFA` | 118969 | 2026-10-22 | 2026-11-20 | 22 | 118969 | 0.0097 | 0.0101 | 0.0196 | 1.2% | 0 | — | — | — | — |
| `EEM` | 127768 | 2026-10-22 | 2026-11-20 | 22 | 127768 | 0.0169 | 0.0179 | 0.0342 | 0.8% | 0 | — | — | — | — |
| `FXI` | 25109 | 2026-10-22 | 2026-11-20 | 22 | 25109 | 0.0302 | 0.0308 | 0.0581 | 0.9% | 0 | — | — | — | — |
| `GDX` | 287915 | 2026-10-22 | 2026-11-20 | 22 | 287915 | 0.0249 | 0.0349 | 0.0463 | 0.2% | 0 | — | — | — | — |
| `USO` | 246660 | 2026-10-22 | 2026-11-20 | 22 | 246660 | 0.0292 | 0.0369 | 0.0539 | 0.0% | 0 | — | — | — | — |
| `DBC` | 45155 | 2026-10-22 | 2026-11-20 | 22 | 45155 | 0.0323 | 0.0342 | 0.0676 | 1.6% | 0 | — | — | — | — |
| `BNO` | 203731 | 2026-10-22 | 2026-11-20 | 22 | 203731 | 0.0422 | 0.0505 | 0.0679 | 0.2% | 0 | — | — | — | — |
| `GLD` | 332221 | 2026-10-22 | 2026-11-20 | 22 | 332221 | 0.0106 | 0.0135 | 0.0197 | 0.1% | 0 | — | — | — | — |
| `SPY` | 432354 | 2026-10-22 | 2026-11-20 | 22 | 432354 | 0.0040 | 0.0053 | 0.0081 | 0.3% | 0 | — | — | — | — |
| `QQQ` | 453525 | 2026-10-22 | 2026-11-20 | 22 | 453525 | 0.0044 | 0.0059 | 0.0081 | 0.2% | 0 | — | — | — | — |

## Pozostałe (całość, bez podziału)

| Symbol | Ticki | Od | Do | Dni | mediana | p75 | p95 | ≤ 0 |
|---|---:|---|---|---:|---:|---:|---:|---:|
| `Nikkei225` | 3335690 | 2026-10-22 | 2026-11-20 | 26 | 0.0210 | 0.0225 | 0.0313 | 0.0% |
| `BTCUSD` | 12471632 | 2026-10-22 | 2026-11-20 | 30 | 0.0225 | 0.0248 | 0.0273 | 0.0% |
| `ETHUSD` | 7700677 | 2026-10-22 | 2026-11-20 | 30 | 0.1178 | 0.1371 | 0.1438 | 0.0% |
| `AUDUSD+` | 2299260 | 2026-10-22 | 2026-11-20 | 26 | 0.0044 | 0.0045 | 0.0058 | 0.0% |

## Pominięte

- Brak.

## Błędy pobrania

- Brak.
