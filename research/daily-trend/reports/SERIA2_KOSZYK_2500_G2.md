# Seria 2: koszyk według reguł z `SPEC_SERIA2.md` przy kapitale 2 500 USD

Źródło: pliki D1 z `uniwersum/`. Symboli z danymi: 61 z 61. Największa łączna ekspozycja G = 2.
To zastosowanie zapisanych wcześniej reguł doboru, nie test strategii ani zalecenie, czym handlować.
Stawki swapu pochodzą z jednego odczytu. Koszt trzymania to roczny ułamek wartości pozycji.

## Koszyk

**Koszyk ważny: 13 rynków z 5 klas.**

| Klasa | Rynek | Symbol | Ciągła historia od | Najmniejsza pozycja | Długa rocznie | Krótka rocznie | Spread | Zmienność roczna |
|---|---|---|---|---|---|---|---:|---:|
| Akcje USA | USA małe spółki | `IWM` | 2022-08-23 | 264 USD (10.6%) | koszt 6.0% | wpływ 2.0% | 0.042% | 19% |
| Akcje USA | USA finanse | `XLF` | 2022-08-23 | 56 USD (2.2%) | koszt 6.0% | wpływ 2.0% | 0.018% | 15% |
| Akcje USA | USA technologia | `XLK` | 2022-08-23 | 161 USD (6.4%) | koszt 6.0% | wpływ 2.0% | 0.162% | 29% |
| Akcje poza USA | Rynki rozwinięte | `EFA` | 2022-02-16 | 99 USD (4.0%) | koszt 6.0% | wpływ 2.0% | 0.010% | 17% |
| Akcje poza USA | Rynki wschodzące | `EEM` | 2022-02-16 | 57 USD (2.3%) | koszt 6.0% | wpływ 2.0% | 0.035% | 27% |
| Akcje poza USA | Japonia | `Nikkei225` | 2018-03-16 | 363 USD (14.5%) | koszt 4.0% | koszt 0.5% | 0.040% | 30% |
| Złoto i metale | Złoto | `GLD` | 2022-08-17 | 335 USD (13.4%) | koszt 6.0% | wpływ 2.0% | 0.015% | 29% |
| Złoto i metale | Spółki złota | `GDX` | 2022-08-23 | 72 USD (2.9%) | koszt 6.0% | wpływ 2.0% | 0.042% | 52% |
| Energia i surowce | Ropa WTI | `USO` | 2022-08-23 | 138 USD (5.5%) | koszt 6.0% | wpływ 2.0% | 0.036% | 51% |
| Energia i surowce | Koszyk surowców | `DBC` | 2022-02-15 | 30 USD (1.2%) | koszt 6.0% | wpływ 2.0% | 0.270% | 22% |
| Energia i surowce | Ropa Brent | `BNO` | 2022-02-15 | 59 USD (2.4%) | koszt 6.0% | wpływ 2.0% | 0.085% | 49% |
| Krypto | Bitcoin | `BTCUSD` | 2017-05-02 | 615 USD (24.6%) | koszt 6.7% | 0% | 0.028% | 38% |
| Krypto | Ethereum | `ETHUSD` | 2016-05-02 | 17 USD (0.7%) | koszt 8.3% | 0% | 0.143% | 53% |

Po jednym najmniejszym locie na każdym rynku: 2 266 USD, czyli 91% kapitału.

## Wszystkie symbole z danymi

| Klasa | Rynek | Symbol | Wynik | Powód |
|---|---|---|---|---|
| Akcje USA | S&P 500 | `SPY` | odrzucony | najmniejsza pozycja 716 USD, limit 625 USD |
| Akcje USA | S&P 500 | `SP500.r` | odrzucony | najmniejsza pozycja 717 USD, limit 625 USD |
| Akcje USA | S&P 500 | `SP500ft.r` | odrzucony | najmniejsza pozycja 718 USD, limit 625 USD; oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Akcje USA | USA małe spółki | `IWM` | w koszyku |  |
| Akcje USA | USA małe spółki | `US2000.r` | dopuszczony, poza koszykiem | na tym rynku wygrał `IWM` |
| Akcje USA | Nasdaq 100 | `QQQ` | odrzucony | najmniejsza pozycja 645 USD, limit 625 USD |
| Akcje USA | USA finanse | `XLF` | w koszyku |  |
| Akcje USA | USA technologia | `XLK` | w koszyku |  |
| Akcje USA | USA półprzewodniki | `SMH` | odrzucony | 114 świec ciągłej historii przed 2025-01-01, wymagane 500 |
| Akcje poza USA | Rynki rozwinięte | `EFA` | w koszyku |  |
| Akcje poza USA | Rynki wschodzące | `EEM` | w koszyku |  |
| Akcje poza USA | Japonia | `EWJ` | odrzucony | 0 świec ciągłej historii przed 2025-01-01, wymagane 500; spread 0.59% ceny, limit 0.50% |
| Akcje poza USA | Japonia | `Nikkei225` | w koszyku |  |
| Akcje poza USA | Japonia | `JPN225ft` | odrzucony | oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Akcje poza USA | Strefa euro | `EU50.r` | odrzucony | najmniejsza pozycja 665 USD, limit 625 USD |
| Akcje poza USA | Wielka Brytania | `UK100.r` | odrzucony | najmniejsza pozycja 1 369 USD, limit 625 USD |
| Akcje poza USA | Wielka Brytania | `UK100ft.r` | odrzucony | najmniejsza pozycja 1 371 USD, limit 625 USD; oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Akcje poza USA | Chiny | `FXI` | dopuszczony, poza koszykiem | klasa ma już 3 rynki |
| Akcje poza USA | Chiny | `MCHI` | odrzucony | 0 świec ciągłej historii przed 2025-01-01, wymagane 500; spread 0.53% ceny, limit 0.50% |
| Akcje poza USA | Chiny | `CHINAH.r` | odrzucony | 27 świec ciągłej historii przed 2025-01-01, wymagane 500 |
| Akcje poza USA | Indie | `INDA` | odrzucony | 0 świec ciągłej historii przed 2025-01-01, wymagane 500; spread 0.68% ceny, limit 0.50% |
| Akcje poza USA | Brazylia | `EWZ` | odrzucony | 0 świec ciągłej historii przed 2025-01-01, wymagane 500; spread 0.54% ceny, limit 0.50% |
| Akcje poza USA | Korea | `EWY` | odrzucony | 0 świec ciągłej historii przed 2025-01-01, wymagane 500 |
| Akcje poza USA | Tajwan | `EWT` | odrzucony | 114 świec ciągłej historii przed 2025-01-01, wymagane 500; spread 0.60% ceny, limit 0.50% |
| Akcje poza USA | Hongkong | `HK50.r` | dopuszczony, poza koszykiem | klasa ma już 3 rynki |
| Akcje poza USA | Hongkong | `HK50ft.r` | odrzucony | oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Akcje poza USA | Australia | `SPI200.r` | dopuszczony, poza koszykiem | klasa ma już 3 rynki |
| Obligacje | USA długie | `TLT` | odrzucony | 0 świec ciągłej historii przed 2025-01-01, wymagane 500 |
| Obligacje | USA 10 lat | `USNote10Y` | odrzucony | 259 świec ciągłej historii przed 2025-01-01, wymagane 500; oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Obligacje | Niemcy 10 lat | `EUB10Y` | odrzucony | 254 świec ciągłej historii przed 2025-01-01, wymagane 500; oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Obligacje | Wielka Brytania, obligacje | `LongGilt` | odrzucony | 253 świec ciągłej historii przed 2025-01-01, wymagane 500; spread 1.23% ceny, limit 0.50%; oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Obligacje | Niemcy 5 lat | `EUB5Y` | odrzucony | 253 świec ciągłej historii przed 2025-01-01, wymagane 500; oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Obligacje | Niemcy 30 lat | `EUB30Y` | odrzucony | 254 świec ciągłej historii przed 2025-01-01, wymagane 500; oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Obligacje | Niemcy 2 lata | `EUB2Y` | odrzucony | 254 świec ciągłej historii przed 2025-01-01, wymagane 500; oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Złoto i metale | Złoto | `GLD` | w koszyku |  |
| Złoto i metale | Złoto | `XAUUSD+` | odrzucony | najmniejsza pozycja 3 625 USD, limit 625 USD |
| Złoto i metale | Srebro | `XAGUSD` | odrzucony | najmniejsza pozycja 2 145 USD, limit 625 USD |
| Złoto i metale | Platyna | `XPTUSD.r` | odrzucony | najmniejsza pozycja 1 343 USD, limit 625 USD; spread 0.78% ceny, limit 0.50% |
| Złoto i metale | Spółki złota | `GDX` | w koszyku |  |
| Energia i surowce | Ropa WTI | `USO` | w koszyku |  |
| Energia i surowce | Ropa WTI | `USOUSD` | odrzucony | najmniejsza pozycja 844 USD, limit 625 USD |
| Energia i surowce | Ropa WTI | `CL-OIL` | odrzucony | najmniejsza pozycja 831 USD, limit 625 USD; oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Energia i surowce | Koszyk surowców | `DBC` | w koszyku |  |
| Energia i surowce | Gaz ziemny | `UNG` | odrzucony | 0 świec ciągłej historii przed 2025-01-01, wymagane 500; spread 1.57% ceny, limit 0.50% |
| Energia i surowce | Ropa Brent | `BNO` | w koszyku |  |
| Energia i surowce | Ropa Brent | `UKOUSD` | odrzucony | najmniejsza pozycja 937 USD, limit 625 USD |
| Energia i surowce | Ropa Brent | `UKOUSDft` | odrzucony | najmniejsza pozycja 926 USD, limit 625 USD; oparty na futures: czeka na potwierdzenie, jak broker rozlicza rolowanie |
| Energia i surowce | Pszenica | `Wheat-Cr` | dopuszczony, poza koszykiem | klasa ma już 3 rynki |
| Energia i surowce | Soja | `Soybean-Cr` | dopuszczony, poza koszykiem | klasa ma już 3 rynki |
| Energia i surowce | Spółki naftowe | `XOP` | dopuszczony, poza koszykiem | klasa ma już 3 rynki |
| Krypto | Bitcoin | `IBIT` | odrzucony | 231 świec ciągłej historii przed 2025-01-01, wymagane 500 |
| Krypto | Bitcoin | `BTCUSD` | w koszyku |  |
| Krypto | Ethereum | `ETHUSD` | w koszyku |  |
| Krypto | Solana | `SOLUSD` | odrzucony | spread 0.75% ceny, limit 0.50% |
| Krypto | Litecoin | `LTCUSD` | odrzucony | spread 2.56% ceny, limit 0.50% |
| Krypto | XRP | `XRPUSD` | odrzucony | spread 0.87% ceny, limit 0.50% |
| Krypto | Bitcoin Cash | `BCHUSD` | odrzucony | spread 1.64% ceny, limit 0.50% |
| Waluty | EURUSD | `EURUSD+` | odrzucony | najmniejsza pozycja 1 097 USD, limit 625 USD |
| Waluty | USDJPY | `USDJPY+` | odrzucony | najmniejsza pozycja 1 003 USD, limit 625 USD |
| Waluty | GBPUSD | `GBPUSD+` | odrzucony | najmniejsza pozycja 1 309 USD, limit 625 USD |
| Waluty | AUDUSD | `AUDUSD+` | odrzucony | najmniejsza pozycja 666 USD, limit 625 USD |

## Czego brakuje

- Dane są dla wszystkich 61 symboli.
- Prowizja od CFD na akcje i ETF-y: bez niej test serii 2 nie rusza dla koszyka z ETF-ami.
- Rozliczenie rolowania kontraktów opartych na futures: do potwierdzenia te symbole są poza koszykiem.
- Wypłaty na CFD (dywidendy, odsetki): do potwierdzenia zostaje szacunek ze specyfikacji.
