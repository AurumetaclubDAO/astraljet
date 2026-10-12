# Koszty MT5 / Vantage — BTCUSD i ETHUSD

**Wynik: potwierdzono bieżącą specyfikację i małą próbkę rozliczeń DEMO. Model kosztów pozostaje częściowo niezweryfikowany.**

Ostatni odczyt: **20.09.2026, 01:35:59 UTC / 03:35:59 Warszawa**.
Źródło: działający MetaTrader 5, `VantageMarkets-Demo`, firma zgłoszona przez terminal
`Vantage Markets (Pty) Ltd`, waluta USD. Zakres: BTC/ETH, zgodnie z bieżącym projektem
badania. To nie cennik wszystkich instrumentów, nie rachunek LIVE i nie rekomendacja transakcji.

## 1. Potwierdzone koszty i parametry

| Parametr | BTCUSD | ETHUSD |
|---|---:|---:|
| Bid / Ask w ostatniej obserwacji | 81 061,21 / 81 078,30 USD | 2 617,11 / 2 619,66 USD |
| Pełny spread Ask − Bid na jednostkę aktywa | 17,09 USD | 2,55 USD |
| Pełny spread względem mid | 2,1081 bps = 0,02108% | 9,7388 bps = 0,09739% |
| Minimalny lot / krok lota | 0,01 / 0,01 | 0,01 / 0,01 |
| Wielkość kontraktu: jednostki aktywa / lot | 1 | 1 |
| Koszt pełnego spreadu przy minimalnym locie | 0,1709 USD | 0,0255 USD |
| Minimalny krok ceny | 0,01 USD | 0,01 USD |
| Swap long w specyfikacji | −20% rocznie | −25% rocznie |
| Swap short w specyfikacji | 0 | 0 |
| `swap_mode` | 5 — INTEREST_CURRENT | 5 — INTEREST_CURRENT |
| Dzień wskazany w `swap_rollover3days` | 5 — piątek | 5 — piątek |

Tryb 5 potwierdzono też stałą `SYMBOL_SWAP_MODE_INTEREST_CURRENT` w zainstalowanej
bibliotece MetaTrader5 **5.0.6180**. W tym trybie stawka dotyczy rocznych odsetek od
ceny instrumentu w chwili naliczenia, przy bazie 360 dni. To nie opłata 20/25 USD
za lot ani 20/25% dziennie. [Dokumentacja MetaQuotes](https://www.mql5.com/en/book/automation/symbols/symbols_swaps).

Przykładowe obliczenia przy **stałym nominale 1000 USD**, a nie depozycie 1000 USD:

| Naliczona jednostka finansowania | BTC long | ETH long |
|---|---:|---:|
| Jedna jednostka: nominał × stawka roczna / 360 | 0,5556 USD kosztu | 0,6944 USD kosztu |
| Trzy jednostki | 1,6667 USD | 2,0833 USD |
| 30 jednostek przy niezmiennym nominale i stawkach | 16,67 USD | 20,83 USD |

Nie utożsamiamy 30 jednostek z dowolnymi 30 dniami kalendarza: nie potwierdzono
wszystkich mnożników dni ani rzeczywistego naliczenia na tym rachunku. Pola
`swap_sunday` … `swap_saturday` nie są udostępnione w odczytanym Python namedtuple;
to **brak odczytu, nie zero**. Sama informacja o piątku nie dowodzi, jak rozliczane
są wszystkie dni rynku crypto działającego również w weekend.
[Znaczenie właściwości i mnożników](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants).

## 2. Spread — mała próbka, nie stała historyczna

Pobrano ostatnią godzinę kwotowań względem ostatniego surowego czasu ticka brokera.
Statystyki ważone zdarzeniami kwotowań, nie czasem utrzymywania spreadu:

| Statystyka pełnego spreadu | BTCUSD | ETHUSD |
|---|---:|---:|
| Liczba poprawnych ticków | 3074 | 7159 |
| Minimum | 2,0830 bps | 9,3126 bps |
| Mediana | 2,0968 bps | 9,5229 bps |
| P95 | 2,1073 bps | 9,6794 bps |
| Maksimum próbki | 2,1117 bps | 9,7399 bps |

To krótki wycinek weekendowy. Nie obejmuje całego tygodnia, publikacji danych,
rolloveru, luk ani okresów dużej zmienności. Nie nadaje się jeszcze do ustalenia
uniwersalnego kosztu lub P95 dla całego backtestu. Poprzednie dwa odczyty w tej sesji
miały nachodzące okna — nie dodawano ich do powyższej próbki.

Koszt Ask − Bid jest pełnym spreadem. Dla wejścia po Ask i wyjścia po Bid bez ruchu
rynku płaci się ekonomicznie jeden pełny spread. Przy cenie referencyjnej mid model
może używać połowy spreadu na każdą stronę. Przy świecach Bid potrzebna jest inna
korekta stron. Nie dodawać pełnego spreadu dwukrotnie ani ponownie do P&L już
opartego na rzeczywistych cenach realizacji.

## 3. Prowizja, opłaty i rzeczywiste naliczenia DEMO

Odczyt `history_deals_get`: zapytanie od 01.09.2026, z poszerzonym końcem w celu
uwzględnienia surowego zegara serwera. Nie wyświetlano identyfikatora rachunku,
numerów transakcji ani danych logowania.

| Zawartość odczytanej historii | BTCUSD | ETHUSD |
|---|---:|---:|
| Realizacje (deals, nie pełne transakcje) | 12 | 11 |
| Wejścia / wyjścia | 6 / 6 | 6 / 5 |
| Kompletnie zamknięte grupy pozycji | 6 | 5 |
| Suma `commission` | 0 USD | 0 USD |
| Suma `fee` | 0 USD | 0 USD |
| Suma `swap` w deals | 0 USD | 0 USD |
| Zamknięte long / short | 1 / 5 | 1 / 4 |
| Przekroczenia surowej północy serwera przez zamknięte long | 0 | 0 |

Nie znaleziono osobnych pozycji typu charge, correction, commission (w tym daily,
monthly, agent) lub interest w odczytanym zakresie rachunku. Nie ma w tej próbce
potwierdzonego obciążenia long przez rollover. Dlatego suma swap=0 **nie przeczy**
niezerowej stawce w specyfikacji. Nie było podstaw do otwierania pozycji testowej
lub przedłużania istniejącej pozycji w celu zmierzenia kosztu.

Wniosek: **zerowa prowizja została zaobserwowana w tej próbce DEMO**, ale nie
potwierdzono pełnej taryfy dla rachunku rzeczywistego, innych symboli lub przyszłych
okresów. Nie zmieniono `verifiedCommission=false` na `true`.
Pola commission/fee/swap to składniki osobne od cen realizacji i spreadu.
[Interfejs historii MetaQuotes](https://www.mql5.com/en/docs/python_metatrader5/mt5historydealsget_py).

## 4. Poślizg — obecna rezerwa nie obejmuje części obserwacji

Dotychczasowy `astra_crypto_cost_model.py` deklaruje:

- prowizja-rezerwa: **2 bps za pełny obrót**, `verifiedCommission=false`;
- poślizg-rezerwa: **2 ticki na stronę**, czyli obecnie 0,02 USD zmiany ceny;
- finansowanie: rezerwa trzech jednostek przy każdym możliwym rolloverze,
  `verifiedWeekdaySchedule=false` — to konserwatywne założenie, nie odtworzony kalendarz.

Zestawiono zapisane żądania z **rzeczywistymi deals odczytanymi z MT5**.
Lokalny dziennik otwarto w trybie SQLite `mode=ro`, `query_only=ON`, bez importowania
lub uruchamiania klas bota. Potwierdzono zgodność account pin. Dopasowanie wymagało
identycznego order ID, symbolu, strony, magic, wejścia/wyjścia i pełnego wolumenu;
numery nie trafiły do raportu. Kierunkowy poślizg = różnica ceny realizacji względem
ceny żądania, dodatnia oznacza pogorszenie. Nie jest to pomiar względem ceny sygnału
ani niezależnego rynku referencyjnego.

| Dopasowana próbka | Liczba żądań | Mediana w tickach | Największe pogorszenie | Pogorszenie ponad 2 ticki |
|---|---:|---:|---:|---:|
| BTC wejścia | 6 | 0 | **348 ticków = 3,48 USD ceny** | 1/6 |
| BTC wyjścia | 2 | 0 | 0 | 0/2 |
| ETH wejścia | 6 | −11,5 | **213 ticków = 2,13 USD ceny** | 1/6 |
| ETH wyjścia | 3 | 11 | **83 ticki = 0,83 USD ceny** | 2/3 |

Były także korzystniejsze realizacje: minimum dla wejść BTC −738 ticków, ETH
−80 ticków, dla wyjść ETH −16 ticków. Ujemnych odchyleń nie usunięto z mediany.
Brak dopasowanej ceny żądania dla czterech deals BTC i dwóch ETH; nie uznano ich
poślizgu za zero. Zestaw nie obejmuje pełnej analizy SL/TP ani rozkładu latencji.

Wniosek: **2 ticki nie są potwierdzonym ograniczeniem poślizgu i były przekroczone
w obserwacjach DEMO**. To ważna luka kalibracji istniejącego modelu. Nie wybrano
automatycznie nowej rezerwy na podstawie kilku skrajnych realizacji; potrzebna jest
większa próbka oraz osobne scenariusze normalny/stresowy. Nie zmieniono kodu ani
ryzyka działającego wykonawcy.

## 5. Zegar i ograniczenia danych

W ostatniej obserwacji surowy epoch ticków obu symboli był o 10 800 s większy od
bieżącego UTC. Zgadza się to z zastaną obsługą zegara Vantage w `astra_clock.py`,
ale nie stanowi potwierdzenia całego historycznego harmonogramu i zmian DST.
Dlatego godzinę próbki wyznaczono na surowej osi brokera, a dopasowania realizacji
wykonano po identyfikatorach, nie po naiwnym zrównaniu epoch z UTC. Nie przeliczano
całej historii przez stałe odjęcie trzech godzin.

## 6. Co to zmienia w planie AstralJet

1. **Nie można podstawić kosztów MT5 do obecnego modelu spot Alpaca.** To inny
   produkt, feed, kontrakt, finansowanie i minimalne wolumeny. Obecny model tygodniowy
   utrzymuje jednostki/cash i nie implementuje rachunku CFD, depozytu ani swapów.
2. Dla wielodniowego long BTC/ETH finansowanie może być istotniejsze niż sam spread.
   Przykład arytmetyczny, nie wynik strategii: dla niezatwierdzonego wariantu 70% BTC,
   20% ETH, 10% cash oraz stałego kapitału 1000 USD koszt 30 jednostek swapu przy
   odczytanych stawkach wynosi około **15,83 USD = 1,58% kapitału**, przed spreadem,
   prowizją i poślizgiem. Nominał, stawki i wagi w rzeczywistości mogą się zmieniać.
3. Prowizję opisać jako `zero_observed_demo_sample`, nie `zero_verified_live`.
   Rezerwę 2 bps zachować jako odrębne, niezweryfikowane założenie do decyzji.
4. Rezerwę poślizgu 2 ticki oznaczyć w badaniu jako niewystarczającą dla części
   zaobserwowanych realizacji. Przegląd/zmiana działającego wykonawcy wymaga osobnego
   uzgodnienia; badanie kosztów nie zmienia jego uprawnień.
5. Przed EXP MT5 potrzebne są: pełny harmonogram rolloveru, taryfa właściwego
   rachunku, dłuższe próbki spreadu/realizacji i odrębna specyfikacja modelu CFD.
   Nie zmieniać zamrożonego EXP spot po obejrzeniu wyniku.

Publiczny serwis australijski Vantage podaje dla crypto inne stawki (m.in. 7% rocznie).
Nie zastosowano ich do tego serwera DEMO — różnią się od bezpośrednio odczytanych
20/25%, a strona dotyczy innej oferty/jurysdykcji.
[Przykład informacji publicznej Vantage](https://www.vantagemarkets.com/en-au/cryptocurrency-trading/).

## Zakres wykonanych czynności i dowody lokalne

- Trzy krótkie sesje odczytu już uruchomionego terminala; brak login/account switch,
  wyboru nowych symboli, zleceń, kontroli zleceń, restartu i zmian konfiguracji.
- Połączenie i rachunek sprawdzono przed/po odczycie; sesję Python API odłączono,
  bez zamykania terminala. Nie wnioskowano o zatrzymaniu innych działających botów.
- Pomocniczy skrypt diagnostyczny: `D:\Astra Jet\.runtime\mt5_cost_readonly_20260920.py`.
  Nie jest modułem produkcyjnym ani automatyzacją; nie został podłączony do kolejki.
- Dziennik odczytu: `C:\Users\karol\AppData\Local\AstraMT5\crypto_round\round.sqlite3`.
- Zastany model kosztów: `C:\Users\karol\Documents\Claude\Projects\Trading\Astra_Lab_v2\mt5\astra_crypto_cost_model.py`,
  SHA-256 `5CF7BD3E94EBD6814FAE4AEA6D01E65C38E128D4C9723D5F0AA4A4B470983B2D`.
- Zastany kontrakt `crypto_contract.json`, SHA-256
  `548FC5622C3D2BD107B8BC49ABB25C42C1FA0DF46D82108C45705AEA4B778674`.
- Nie zmieniono obu plików runtime, propozycji v0.2, baz AstralJet, frontendów,
  kodu silnika, mandatów, budżetu lub limitów ryzyka. Nie wykonano backtestu cen,
  pełnej regresji ani niezależnego audytu bezpieczeństwa — zakres tej pracy to odczyt i analiza kosztów.
