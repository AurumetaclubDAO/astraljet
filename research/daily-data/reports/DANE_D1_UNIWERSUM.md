# Dane D1 — uniwersum kandydatów do serii 2

- Odczyt: 2026-11-20T06:30:03+00:00 UTC, skrypt `research/daily-data/scripts/collect_d1_universe.py` (tylko odczyt).
- Pliki danych: `research/daily-data/data/uniwersum/` (pomijane przez Git).
- Symboli na liście: 61; pobrano: 10; pominięto (poza Market Watch lub brak u brokera): 51; błędy: 0.
- Symbole w Market Watch przed odczytem: 23, po odczycie: 23 (bez zmian).
- `symbol_select` nie było wywołane (skrypt blokuje je w każdej postaci), `account_info` także.
- Limit świec terminala (maxbars): 100000. Przesunięcie serwera względem UTC: +2 h.

## Pobrane symbole

| Symbol | Od | Do | Świece | Luki > 5 dni | Spread teraz / mediana D1 [pkt] | Swap long / short (tryb, 3x dzień) | Tryb | Próby |
|---|---|---|---:|---:|---|---|---|---:|
| `SP500.r` | 2009-09-17 | 2026-11-19 | 2662 | 1 | 60 / 54.5 | -1.6217 / 0.3178 (2, 5) | FULL | 3 |
| `XAUUSD+` | 2018-03-19 | 2026-11-19 | 2240 | 0 | 10 / 4 | -69.21 / 30.92 (1, 3) | FULL | 2 |
| `UKOUSD` | 2018-03-09 | 2026-11-19 | 2245 | 0 | 34 / 30 | 123.368 / -209.503 (1, 5) | FULL | 3 |
| `USOUSD` | 2014-02-05 | 2026-11-19 | 2355 | 10 | 34 / 23 | 28.9036 / -66.3285 (1, 5) | FULL | 3 |
| `BTCUSD` | 2017-05-02 | 2026-11-19 | 3012 | 0 | 1708 / 1594 | -20 / 0 (5, 5) | FULL | 3 |
| `ETHUSD` | 2016-05-02 | 2026-11-19 | 3419 | 0 | 247 / 245 | -25 / 0 (5, 5) | FULL | 2 |
| `SOLUSD` | 2021-10-27 | 2026-11-19 | 1823 | 0 | 54 / 51 | -25 / 0 (5, 5) | FULL | 2 |
| `XRPUSD` | 2016-05-16 | 2026-11-19 | 3325 | 1 | 84 / 79 | -25 / 0 (5, 5) | FULL | 2 |
| `EURUSD+` | 2007-11-07 | 2026-11-19 | 4938 | 0 | 1 / 0 | -6.09 / 1.68 (1, 3) | FULL | 3 |
| `USDJPY+` | 2018-09-27 | 2026-11-19 | 2113 | 0 | 3 / 0 | 7.4 / -23.12 (1, 3) | FULL | 2 |

## Mniej niż 500 świec

- Brak.

## Inne rzeczy nietypowe

- `SP500.r`: 1 luk > 5 dni.
- `USOUSD`: 10 luk > 5 dni.
- `XRPUSD`: 1 luk > 5 dni.

## Pominięte

- `SPY`: poza Market Watch.
- `QQQ`: poza Market Watch.
- `IWM`: poza Market Watch.
- `XLF`: poza Market Watch.
- `XLK`: poza Market Watch.
- `SMH`: poza Market Watch.
- `US2000.r`: poza Market Watch.
- `EFA`: poza Market Watch.
- `EEM`: poza Market Watch.
- `EWJ`: poza Market Watch.
- `FXI`: poza Market Watch.
- `MCHI`: poza Market Watch.
- `INDA`: poza Market Watch.
- `EWZ`: poza Market Watch.
- `EWY`: poza Market Watch.
- `EWT`: poza Market Watch.
- `EU50.r`: poza Market Watch.
- `UK100.r`: poza Market Watch.
- `Nikkei225`: poza Market Watch.
- `HK50.r`: poza Market Watch.
- `CHINAH.r`: poza Market Watch.
- `SPI200.r`: poza Market Watch.
- `TLT`: poza Market Watch.
- `USNote10Y`: poza Market Watch.
- `EUB10Y`: poza Market Watch.
- `EUB5Y`: poza Market Watch.
- `EUB2Y`: poza Market Watch.
- `EUB30Y`: poza Market Watch.
- `LongGilt`: poza Market Watch.
- `GLD`: poza Market Watch.
- `GDX`: poza Market Watch.
- `XPTUSD.r`: poza Market Watch.
- `XAGUSD`: poza Market Watch.
- `USO`: poza Market Watch.
- `BNO`: poza Market Watch.
- `UNG`: poza Market Watch.
- `DBC`: poza Market Watch.
- `XOP`: poza Market Watch.
- `Wheat-Cr`: poza Market Watch.
- `Soybean-Cr`: poza Market Watch.
- `LTCUSD`: poza Market Watch.
- `BCHUSD`: poza Market Watch.
- `IBIT`: poza Market Watch.
- `GBPUSD+`: poza Market Watch.
- `AUDUSD+`: poza Market Watch.
- `SP500ft.r`: poza Market Watch.
- `UK100ft.r`: poza Market Watch.
- `HK50ft.r`: poza Market Watch.
- `JPN225ft`: poza Market Watch.
- `CL-OIL`: poza Market Watch.
- `UKOUSDft`: poza Market Watch.

## Błędy pobrania

- Brak.

Świeca D1 obejmuje dzień serwera MT5; świeca bieżącego, niezamkniętego dnia jest pomijana.
