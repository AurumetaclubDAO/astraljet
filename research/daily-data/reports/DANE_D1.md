# Dane D1 z terminala MT5

- Odczyt: 2026-11-18T05:51:39+00:00 UTC, skrypt `research/daily-data/scripts/collect_d1.py` (tylko odczyt).
- Pliki danych: `research/daily-data/data/` (pomijane przez Git).
- Limit świec terminala (maxbars): 100000.
- `symbol_select`: SP500.r, GER40.r.

## Rynki

| Rynek | Symbol | Od | Do | Świece | Luki > 5 dni | Spread teraz / mediana D1 [pkt] | Swap long / short (tryb, 3x dzień) |
|---|---|---|---|---:|---:|---|---|
| SP500 | `SP500.r` | 2009-09-17 | 2026-11-17 | 2660 | 1 | 60 / 54 | -1.6217 / 0.3178 (2, 5) |
| NAS100 | `NAS100.r` | 2018-03-16 | 2026-11-17 | 2242 | 0 | 187 / 150 | -5.9907 / 1.1741 (2, 5) |
| DAX | `GER40.r` | 2008-12-30 | 2026-11-17 | 2885 | 3 | 471 / 0 | -4.1573 / 0.4418 (2, 5) |
| GOLD | `XAUUSD+` | 2018-03-19 | 2026-11-17 | 2238 | 0 | 11 / 4 | -69.21 / 30.92 (1, 3) |
| BRENT | `UKOUSD` | 2018-03-09 | 2026-11-17 | 2243 | 0 | 27 / 30 | 123.368 / -209.503 (1, 5) |
| WTI | `USOUSD` | 2014-02-05 | 2026-11-17 | 2353 | 10 | 24 / 23 | 18.4543 / -54.7781 (1, 5) |
| EURUSD | `EURUSD+` | 2007-11-07 | 2026-11-17 | 4936 | 0 | 1 / 0 | -6.42 / 1.85 (1, 3) |
| BTCUSD | `BTCUSD` | 2017-05-02 | 2026-11-17 | 3010 | 0 | 1700 / 1594 | -20 / 0 (5, 5) |
| ETHUSD | `ETHUSD` | 2016-05-02 | 2026-11-17 | 3417 | 0 | 252 / 245 | -25 / 0 (5, 5) |

## Wybór symbolu

- SP500: `SP500.r` — S&P Index Cash CFD (USD); pozostali kandydaci: `SP500ft.r` (FULL, poza MW), `SPX` (FULL, poza MW), `SDS` (FULL, poza MW), `SPY` (FULL, poza MW), `SPYX` (LONGONLY, poza MW), `SPYUSD` (FULL, poza MW).
- NAS100: `NAS100.r` — NAS100 Cash; pozostali kandydaci: `NAS100ft.r` (FULL, poza MW).
- DAX: `GER40.r` — GER40 Cash; pozostali kandydaci: `GER40ft.r` (FULL, poza MW).
- GOLD: `XAUUSD+` — Gold US Dollar; pozostali kandydaci: `XAUUSD247` (FULL, MW, 177 świec), `XAUUSD.crp` (DISABLED, MW).
- BRENT: `UKOUSD` — Brent Crude Oil Cash; pozostali kandydaci: `UKOUSDft` (FULL, poza MW), `BNO` (FULL, poza MW).
- WTI: `USOUSD` — WTI Crude Oil Cash; jedyny kandydat.
- EURUSD: `EURUSD+` — Euro vs US Dollar; pozostali kandydaci: `EURUSD` (DISABLED, MW).
- BTCUSD: `BTCUSD` — Bitcoin; jedyny kandydat.
- ETHUSD: `ETHUSD` — Ethereum; jedyny kandydat.

## Luki dłuższe niż 5 dni kalendarzowych

- SP500: 2011-04-29 → 2018-03-16 (2513 dni).
- DAX: 2011-04-29 → 2017-11-08 (2385 dni), 2018-12-21 → 2018-12-27 (6 dni), 2025-12-23 → 2025-12-29 (6 dni).
- WTI: 2014-02-20 → 2014-02-27 (7 dni), 2014-02-27 → 2014-03-25 (26 dni), 2014-03-25 → 2014-03-31 (6 dni), 2014-04-02 → 2014-04-16 (14 dni), 2014-04-16 → 2014-04-28 (12 dni), 2014-04-29 → 2014-05-22 (23 dni), 2014-05-26 → 2014-06-10 (15 dni), 2014-06-11 → 2014-06-30 (19 dni), 2014-11-12 → 2014-12-01 (19 dni), 2014-12-02 → 2018-03-16 (1200 dni).

## Strefa czasu świec

Świeca D1 obejmuje dzień serwera MT5, a data w CSV to data początku świecy w czasie serwera.
Według `research/scalp-smc/scripts/srvtime.py` serwer działa w UTC+2 zimą i w UTC+3 w czasie letnim USA (dzień kończy się o 17:00 w Nowym Jorku).
Zmierzone dziś przesunięcie serwera względem UTC: +2 h.
Świeca bieżącego, niezamkniętego dnia jest pomijana (lista w polu `excluded_forming_bar_dates` pliku meta).

## Czego nie udało się pobrać

- Wszystkie rynki z listy zostały pobrane.

## Uwagi do danych (dopisane ręcznie po kontroli, 18.11.2026)

Kontrola po eksporcie: SHA-256 każdego CSV zgadza się z plikiem meta. Daty rosną i się nie powtarzają. W żadnej świecy nie ma sprzeczności OHLC. W każdym pliku pominięto trwającą świecę z 2026-11-18. Na danych niczego nie testowano.

1. **Ciągła historia zaczyna się praktycznie w marcu 2018.** SP500 i DAX mają przerwę od 2011-04-29 do 2018 (prawie 7 lat), a WTI przed 2018-03-16 ma tylko rzadkie świece z 2014 roku. Od 2018-03-19 do końca 2024 na każdym rynku jest 1725–2099 świec, czyli więcej niż wymagane w SPEC 1500 świec przed OOS. Starsze świece sprzed przerwy są w plikach, ale nie tworzą ciągłego szeregu. Silnik H2/H3 liczy świece przed 2025-01-01 łącznie, razem ze starszymi. Wspólny kalendarz koszyka zaczyna się od najpóźniejszego pierwszego dnia (XAUUSD+, 2018-03-19). O tym, czy wskaźniki z długim oknem mogą sięgać przez przerwę, rozstrzyga koordynator na podstawie SPEC, nie ta sesja.
2. **Kolumna `spread` w świecach często wynosi 0**, zwłaszcza w starszych danych: EURUSD+ ma tak 4383 z 4936 świec, GER40.r 2072 z 2885. Mediana spreadu z D1 jest więc dla części rynków zaniżona. Bieżący spread jest w polu `spread_points` w pliku meta.
3. **Kryptowaluty mają świece sobotnie i niedzielne** (BTCUSD 527, ETHUSD 673), pozostałe rynki nie mają. Kalendarz wspólny dla koszyka będzie więc miał dni bez świec rynków tradycyjnych.
4. **Wybór symbolu.** Dla SP500 i DAX nie było kandydata z pełnym handlem w Market Watch, więc dodano `SP500.r` i `GER40.r` (2 wywołania `symbol_select` w logu). Kontrakty `*ft` ani instrumenty ETF i akcyjne (`SPY`, `SDS`, `BNO`) nie były porównywane. Dla złota `XAUUSD247` miał tylko 177 świec, a `XAUUSD.crp` jest wyłączony z handlu.
5. **Swap.** Indeksy mają `swap_mode` 2 (kwota w walucie symbolu), złoto, ropa i EURUSD tryb 1 (punkty), a kryptowaluty tryb 5 (procent rocznie). Wartości odczytano 18.11.2026 i mogą się zmieniać w czasie.
