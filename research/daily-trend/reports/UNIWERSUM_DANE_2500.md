# Uniwersum CFD na danych dziennych przy kapitale 2 500 USD

Źródło: pliki D1 z `uniwersum/`, 61 symboli, ostatnia świeca 2026-11-19.
To nie jest test strategii ani zalecenie, czym handlować. Stawki swapu pochodzą z jednego odczytu.
Koszt trzymania to roczny ułamek wartości pozycji; „wpływ" oznacza, że broker dopisuje pieniądze.
Spread to większy z dwóch: z odczytu i mediana ze świec dziennych, w procentach ceny. Zmienność liczona z ostatnich 252 świec.

## Symbole

| Klasa | Rynek | Symbol | Historia od | Świece | Najmniejsza pozycja | Długa rocznie | Krótka rocznie | Spread | Zmienność roczna | Uwagi |
|---|---|---|---|---:|---|---|---|---:|---:|---|
| Akcje USA | QQQ | `QQQ` | 2022-08-23 | 1066 | 645 USD (25.8% kapitału) | koszt 6.0% | wpływ 2.0% | 0.047% | 21% |  |
| Akcje USA | S&P 500 | `SPY` | 2022-08-23 | 1066 | 716 USD (28.6% kapitału) | koszt 6.0% | wpływ 2.0% | 0.006% | 14% |  |
| Akcje USA | S&P 500 | `SP500.r` | 2009-09-17 | 2662 | 717 USD (28.7% kapitału) | koszt 8.3% | wpływ 1.6% | 0.008% | 14% |  |
| Akcje USA | S&P 500 | `SP500ft.r` | 2014-10-31 | 1833 | 718 USD (28.7% kapitału) | w cenie | w cenie | 0.014% | 14% | 1 luk ponad 5 dni od 2018 |
| Akcje USA | SMH | `SMH` | 2024-07-22 | 587 | 45 USD (1.8% kapitału) | koszt 6.5% | wpływ 0.5% | 0.407% | 42% |  |
| Akcje USA | USA małe spółki | `IWM` | 2022-08-23 | 1066 | 264 USD (10.6% kapitału) | koszt 6.0% | wpływ 2.0% | 0.042% | 19% |  |
| Akcje USA | USA małe spółki | `US2000.r` | 2020-04-09 | 1711 | 265 USD (10.6% kapitału) | koszt 8.5% | wpływ 1.7% | 0.017% | 19% |  |
| Akcje USA | XLF | `XLF` | 2022-08-23 | 1066 | 56 USD (2.2% kapitału) | koszt 6.0% | wpływ 2.0% | 0.018% | 15% |  |
| Akcje USA | XLK | `XLK` | 2022-08-23 | 1066 | 161 USD (6.4% kapitału) | koszt 6.0% | wpływ 2.0% | 0.162% | 29% |  |
| Akcje poza USA | CHINAH.r | `CHINAH.r` | 2024-11-21 | 491 | 98 USD (3.9% kapitału) | koszt 5.4% | wpływ 1.0% | 0.222% | 18% | krótka historia; 2 luk ponad 5 dni od 2018 |
| Akcje poza USA | EEM | `EEM` | 2022-02-16 | 1195 | 57 USD (2.3% kapitału) | koszt 6.0% | wpływ 2.0% | 0.035% | 27% |  |
| Akcje poza USA | EFA | `EFA` | 2022-02-16 | 1195 | 99 USD (4.0% kapitału) | koszt 6.0% | wpływ 2.0% | 0.010% | 17% |  |
| Akcje poza USA | EU50.r | `EU50.r` | 2017-11-09 | 2296 | 665 USD (26.6% kapitału) | koszt 6.0% | wpływ 0.6% | 0.125% | 17% | 2 luk ponad 5 dni od 2018; wycena z ticka daje 606 USD |
| Akcje poza USA | EWT | `EWT` | 2024-07-22 | 587 | 8 USD (0.3% kapitału) | koszt 6.5% | wpływ 0.5% | 0.596% | 37% |  |
| Akcje poza USA | EWY | `EWY` | 2026-04-30 | 142 | 13 USD (0.5% kapitału) | koszt 6.5% | wpływ 0.5% | 0.164% | 68% | krótka historia |
| Akcje poza USA | EWZ | `EWZ` | 2026-04-30 | 142 | 3 USD (0.1% kapitału) | koszt 6.5% | wpływ 0.5% | 0.544% | 40% | krótka historia |
| Akcje poza USA | FXI | `FXI` | 2022-08-23 | 1066 | 32 USD (1.3% kapitału) | koszt 6.0% | wpływ 2.0% | 0.031% | 19% |  |
| Akcje poza USA | Hongkong | `HK50.r` | 2017-06-28 | 2318 | 290 USD (11.6% kapitału) | koszt 6.1% | wpływ 0.7% | 0.066% | 17% | 4 luk ponad 5 dni od 2018 |
| Akcje poza USA | Hongkong | `HK50ft.r` | 2021-08-30 | 1284 | 290 USD (11.6% kapitału) | w cenie | w cenie | 0.031% | 17% | 3 luk ponad 5 dni od 2018 |
| Akcje poza USA | INDA | `INDA` | 2026-04-30 | 142 | 5 USD (0.2% kapitału) | koszt 6.5% | wpływ 0.5% | 0.676% | 15% | krótka historia |
| Akcje poza USA | Japonia | `EWJ` | 2026-04-30 | 142 | 9 USD (0.3% kapitału) | koszt 6.5% | wpływ 0.5% | 0.588% | 22% | krótka historia |
| Akcje poza USA | Japonia | `Nikkei225` | 2018-03-16 | 2244 | 363 USD (14.5% kapitału) | koszt 4.0% | koszt 0.5% | 0.040% | 30% |  |
| Akcje poza USA | Japonia | `JPN225ft` | 2022-12-08 | 1021 | 363 USD (14.5% kapitału) | w cenie | w cenie | 0.033% | 30% |  |
| Akcje poza USA | MCHI | `MCHI` | 2026-04-30 | 142 | 5 USD (0.2% kapitału) | koszt 6.5% | wpływ 0.5% | 0.533% | 19% | krótka historia |
| Akcje poza USA | SPI200.r | `SPI200.r` | 2007-04-17 | 3223 | 576 USD (23.0% kapitału) | koszt 9.4% | wpływ 2.1% | 0.114% | 13% |  |
| Akcje poza USA | Wielka Brytania | `UK100.r` | 2008-10-13 | 2925 | 1 369 USD (54.7% kapitału) | koszt 7.8% | wpływ 1.5% | 0.036% | 13% |  |
| Akcje poza USA | Wielka Brytania | `UK100ft.r` | 2020-03-19 | 1271 | 1 371 USD (54.8% kapitału) | w cenie | w cenie | 0.041% | 13% | 5 luk ponad 5 dni od 2018 |
| Obligacje | EUB10Y | `EUB10Y` | 2024-01-02 | 734 | 134 USD (5.4% kapitału) | w cenie | w cenie | 0.025% | 5% | 1 luk ponad 5 dni od 2018 |
| Obligacje | EUB2Y | `EUB2Y` | 2024-01-02 | 734 | 115 USD (4.6% kapitału) | w cenie | w cenie | 0.029% | 1% | 1 luk ponad 5 dni od 2018 |
| Obligacje | EUB30Y | `EUB30Y` | 2024-01-02 | 734 | 115 USD (4.6% kapitału) | w cenie | w cenie | 0.038% | 10% | 1 luk ponad 5 dni od 2018 |
| Obligacje | EUB5Y | `EUB5Y` | 2024-01-02 | 733 | 124 USD (5.0% kapitału) | w cenie | w cenie | 0.027% | 3% | 1 luk ponad 5 dni od 2018 |
| Obligacje | LongGilt | `LongGilt` | 2024-01-02 | 731 | 111 USD (4.4% kapitału) | w cenie | w cenie | 1.228% | 10% | 1 luk ponad 5 dni od 2018 |
| Obligacje | TLT | `TLT` | 2026-04-30 | 142 | 8 USD (0.3% kapitału) | koszt 6.5% | wpływ 0.5% | 0.199% | 10% | krótka historia |
| Obligacje | USNote10Y | `USNote10Y` | 2024-01-02 | 747 | 106 USD (4.2% kapitału) | w cenie | w cenie | 0.057% | 5% |  |
| Złoto i metale | GDX | `GDX` | 2022-08-23 | 1066 | 72 USD (2.9% kapitału) | koszt 6.0% | wpływ 2.0% | 0.042% | 52% |  |
| Złoto i metale | XAGUSD | `XAGUSD` | 2018-03-19 | 2240 | 2 145 USD (85.8% kapitału) | koszt 7.8% | wpływ 3.8% | 0.049% | 65% |  |
| Złoto i metale | XPTUSD.r | `XPTUSD.r` | 2022-02-28 | 1219 | 1 343 USD (53.7% kapitału) | koszt 14.4% | koszt 7.4% | 0.784% | 52% |  |
| Złoto i metale | Złoto | `GLD` | 2022-08-17 | 1070 | 335 USD (13.4% kapitału) | koszt 6.0% | wpływ 2.0% | 0.015% | 29% |  |
| Złoto i metale | Złoto | `XAUUSD+` | 2018-03-19 | 2240 | 3 625 USD (145.0% kapitału) | koszt 7.0% | wpływ 3.1% | 0.004% | 29% |  |
| Energia i surowce | DBC | `DBC` | 2022-02-15 | 1196 | 30 USD (1.2% kapitału) | koszt 6.0% | wpływ 2.0% | 0.270% | 22% |  |
| Energia i surowce | Ropa Brent | `BNO` | 2022-02-15 | 1196 | 59 USD (2.4% kapitału) | koszt 6.0% | wpływ 2.0% | 0.085% | 49% |  |
| Energia i surowce | Ropa Brent | `UKOUSDft` | 2021-12-21 | 1268 | 926 USD (37.0% kapitału) | w cenie | w cenie | 0.139% | 53% |  |
| Energia i surowce | Ropa Brent | `UKOUSD` | 2018-03-09 | 2245 | 937 USD (37.5% kapitału) | wpływ 48.0% | koszt 81.6% | 0.046% | 52% |  |
| Energia i surowce | Ropa WTI | `USO` | 2022-08-23 | 1066 | 138 USD (5.5% kapitału) | koszt 6.0% | wpływ 2.0% | 0.036% | 51% |  |
| Energia i surowce | Ropa WTI | `CL-OIL` | 2008-02-18 | 3068 | 831 USD (33.2% kapitału) | w cenie | w cenie | 0.149% | 56% |  |
| Energia i surowce | Ropa WTI | `USOUSD` | 2014-02-05 | 2355 | 844 USD (33.8% kapitału) | wpływ 12.5% | koszt 28.7% | 0.051% | 56% |  |
| Energia i surowce | Soybean-Cr | `Soybean-Cr` | 2022-01-24 | 1213 | 597 USD (23.9% kapitału) | koszt 9.3% | wpływ 3.2% | 0.193% | 17% |  |
| Energia i surowce | UNG | `UNG` | 2026-04-30 | 142 | 1 USD (0.0% kapitału) | koszt 6.5% | wpływ 0.5% | 1.570% | 40% | krótka historia |
| Energia i surowce | Wheat-Cr | `Wheat-Cr` | 2022-01-06 | 1222 | 578 USD (23.1% kapitału) | koszt 12.8% | wpływ 6.2% | 0.277% | 28% |  |
| Energia i surowce | XOP | `XOP` | 2022-08-23 | 1066 | 170 USD (6.8% kapitału) | koszt 6.0% | wpływ 2.0% | 0.106% | 30% |  |
| Krypto | BCHUSD | `BCHUSD` | 2017-08-19 | 2945 | 20 USD (0.8% kapitału) | koszt 8.3% | 0% | 1.643% | 80% |  |
| Krypto | Bitcoin | `IBIT` | 2024-02-01 | 704 | 35 USD (1.4% kapitału) | koszt 6.5% | wpływ 0.5% | 0.114% | 44% |  |
| Krypto | Bitcoin | `BTCUSD` | 2017-05-02 | 3012 | 615 USD (24.6% kapitału) | koszt 6.7% | 0% | 0.028% | 38% |  |
| Krypto | ETHUSD | `ETHUSD` | 2016-05-02 | 3419 | 17 USD (0.7% kapitału) | koszt 8.3% | 0% | 0.143% | 53% |  |
| Krypto | LTCUSD | `LTCUSD` | 2012-01-08 | 4897 | 41 USD (1.7% kapitału) | koszt 8.3% | 0% | 2.561% | 51% |  |
| Krypto | SOLUSD | `SOLUSD` | 2021-10-27 | 1823 | 7 USD (0.3% kapitału) | koszt 8.3% | 0% | 0.750% | 58% |  |
| Krypto | XRPUSD | `XRPUSD` | 2016-05-16 | 3325 | 95 USD (3.8% kapitału) | koszt 8.3% | 0% | 0.874% | 59% | 1 luk ponad 5 dni od 2018 |
| Waluty | AUDUSD+ | `AUDUSD+` | 2007-11-07 | 4937 | 666 USD (26.6% kapitału) | wpływ 0.4% | koszt 1.2% | 0.005% | 8% |  |
| Waluty | EURUSD+ | `EURUSD+` | 2007-11-07 | 4938 | 1 097 USD (43.9% kapitału) | koszt 2.0% | wpływ 0.6% | 0.001% | 6% |  |
| Waluty | GBPUSD+ | `GBPUSD+` | 2007-11-07 | 4937 | 1 309 USD (52.4% kapitału) | koszt 1.0% | koszt 1.0% | 0.002% | 6% |  |
| Waluty | USDJPY+ | `USDJPY+` | 2018-09-27 | 2113 | 1 003 USD (40.1% kapitału) | wpływ 1.7% | koszt 5.3% | 0.001% | 8% |  |

## Największy równy koszyk bez dźwigni

Liczę tylko symbole z pełnym trybem handlu i co najmniej 500 świecami. Z kilku symboli tego samego rynku biorę ten o najmniejszej pozycji. Równe wagi są tu miarą wykonalności, nie propozycją strategii.

**Rynków w koszyku: 20** z 41. Każdy ma wtedy 125 USD (5.0% kapitału) i dostaje choć najmniejszy lot. Klasy: Akcje USA, Akcje poza USA, Energia i surowce, Krypto, Obligacje, Złoto i metale.

| Rynek | Symbol | Najmniejsza pozycja | Klasa |
|---|---|---|---|
| SOLUSD | `SOLUSD` | 7 USD | Krypto |
| EWT | `EWT` | 8 USD | Akcje poza USA |
| ETHUSD | `ETHUSD` | 17 USD | Krypto |
| BCHUSD | `BCHUSD` | 20 USD | Krypto |
| DBC | `DBC` | 30 USD | Energia i surowce |
| FXI | `FXI` | 32 USD | Akcje poza USA |
| Bitcoin | `IBIT` | 35 USD | Krypto |
| LTCUSD | `LTCUSD` | 41 USD | Krypto |
| SMH | `SMH` | 45 USD | Akcje USA |
| XLF | `XLF` | 56 USD | Akcje USA |
| EEM | `EEM` | 57 USD | Akcje poza USA |
| Ropa Brent | `BNO` | 59 USD | Energia i surowce |
| GDX | `GDX` | 72 USD | Złoto i metale |
| XRPUSD | `XRPUSD` | 95 USD | Krypto |
| EFA | `EFA` | 99 USD | Akcje poza USA |
| USNote10Y | `USNote10Y` | 106 USD | Obligacje |
| LongGilt | `LongGilt` | 111 USD | Obligacje |
| EUB30Y | `EUB30Y` | 115 USD | Obligacje |
| EUB2Y | `EUB2Y` | 115 USD | Obligacje |
| EUB5Y | `EUB5Y` | 124 USD | Obligacje |

Poza koszykiem, bo najmniejsza pozycja jest za duża: EUB10Y (134 USD), Ropa WTI (138 USD), XLK (161 USD), XOP (170 USD), USA małe spółki (264 USD), Hongkong (290 USD), Złoto (335 USD), Japonia (363 USD), SPI200.r (576 USD), Wheat-Cr (578 USD), Soybean-Cr (597 USD), QQQ (645 USD), EU50.r (665 USD), AUDUSD+ (666 USD), S&P 500 (716 USD), USDJPY+ (1 003 USD), EURUSD+ (1 097 USD), GBPUSD+ (1 309 USD), XPTUSD.r (1 343 USD), Wielka Brytania (1 369 USD), XAGUSD (2 145 USD).

## Kontrakty oparte na futures a wersja kasowa

Baza to cena wersji futures do ceny kasowej minus 1. Między skokami rolowania baza schodzi do zera i tyle wersja
futures traci do kasowej. Zakładam, że skok ceny przy rolowaniu broker wyrównuje na rachunku; to trzeba potwierdzić
w specyfikacji brokera. Wersja kasowa ma osobno swap, a dywidend tu nie liczę.

| Rynek | Kasowy | Futures | Wspólne dni | Wykryte skoki | Spadek bazy rocznie (koszt długiej w cenie) | Swap długiej kasowej rocznie |
|---|---|---|---:|---:|---:|---|
| S&P 500 | `SP500.r` | `SP500ft.r` | 1831 | 39 | 2.0% | koszt 8.3% |
| Wielka Brytania | `UK100.r` | `UK100ft.r` | 1270 | 63 | 1.2% | koszt 7.8% |
| Hongkong | `HK50.r` | `HK50ft.r` | 1284 | 109 | 0.7% | koszt 6.1% |
| Japonia | `Nikkei225` | `JPN225ft` | 1021 | 35 | 0.2% | koszt 4.0% |
| Ropa WTI | `USOUSD` | `CL-OIL` | 2241 | 162 | -4.0% | wpływ 12.5% |
| Ropa Brent | `UKOUSD` | `UKOUSDft` | 1267 | 86 | -12.3% | wpływ 48.0% |

## Czego brakuje

- Dane są dla wszystkich kandydatów.
- Prowizja od CFD na akcje i ETF-y: nie ma jej w danych terminala, trzeba ją wziąć ze specyfikacji brokera.
- Kontrakty na obligacje nie mają wersji kasowej, więc ich kosztu rolowania nie da się zmierzyć tą metodą.
