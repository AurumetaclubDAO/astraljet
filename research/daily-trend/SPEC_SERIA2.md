# Seria 2 (H4 i H5) — reguły zapisane przed zobaczeniem danych

Data zapisu: 20.11.2026. Autor: Claude (koordynator). **Status: PROJEKT. Czeka na akceptację Karola; do tego czasu żaden test serii 2 nie rusza.**

Co było znane w chwili zapisu:

- lista symboli brokera z 19–20.11.2026 (wielkość lota, stawki swapu, tryb handlu);
- historia D1 dziesięciu symboli: `SP500.r`, `XAUUSD+`, `UKOUSD`, `USOUSD`, `BTCUSD`, `ETHUSD`, `SOLUSD`, `XRPUSD`, `EURUSD+`, `USDJPY+`;
- wyniki serii 1 (H1, H2, H3: wszystkie FAIL).

Historii D1 pozostałych 51 kandydatów w chwili zapisu nie ma w repozytorium. Reguł i progów nie zmieniamy po zobaczeniu wyników. Każda zmiana to nowa hipoteza z nowym numerem. Do pierwszego testu progi może zmienić tylko Karol.

Kapitał w całej serii: 2 500 USD. Instrumenty: CFD u obecnego brokera.

## 1. Kandydaci

61 symboli z listy `UNIVERSE` w `research/daily-data/scripts/collect_d1_universe.py`: 55 rynków w 7 klasach i 6 odpowiedników opartych na futures. Dane: `research/daily-data/data/uniwersum/<SYMBOL>_D1.csv` i `.meta.json`, kursy walut z `symbols_all.json` z tego samego dnia.

## 2. Dopuszczenie symbolu

Liczone na dniu odczytu danych. Symbol wchodzi dalej, gdy spełnia wszystko naraz:

1. Tryb handlu pełny (FULL).
2. Co najmniej 500 świec ciągłej historii przed 01.01.2025. Ciągła historia to świece po ostatniej przerwie dłuższej niż 10 dni kalendarzowych.
3. Najmniejsza pozycja nie większa niż kapitał × G / 8, czyli 312,50 USD przy G = 1. Najmniejsza pozycja = najmniejszy lot × wielkość kontraktu × ostatnie zamknięcie × kurs waluty zysku do USD. G to największa łączna ekspozycja (punkt 8).
4. Spread nie większy niż 0,50% ceny. Spread = większa z dwóch wartości (odczyt z pliku meta, mediana kolumny `spread` w CSV) × `point` / ostatnie zamknięcie.
5. Przynajmniej jedna strona pozycji (długa albo krótka) kosztuje w trzymaniu nie więcej niż 10% rocznie. Koszt liczony jak w punkcie 5; wpływ na rachunek liczymy jako zero.
6. Symbol oparty na futures (bez swapu, koszt siedzi w cenie i rolowaniu: kontrakty na obligacje, symbole z końcówką `ft`, `CL-OIL`) wchodzi dopiero po potwierdzeniu w specyfikacji brokera, jak rozliczany jest skok ceny przy rolowaniu. Do tego czasu jest poza koszykiem.

Każde odrzucenie trafia do raportu razem z powodem.

## 3. Wybór koszyka

- Jeden symbol na rynek. Gdy rynek ma kilka dopuszczonych symboli, wygrywa ten z najmniejszą sumą kosztu trzymania pozycji długiej i krótkiej; przy remisie ten z mniejszą najmniejszą pozycją.
- Najwyżej 3 rynki z jednej klasy, w kolejności z tabeli. Bierzemy pierwsze trzy rynki, które mają dopuszczony symbol.
- Koszyk jest ważny, gdy ma co najmniej 6 rynków z co najmniej 4 klas. Inaczej werdykt to BRAK DANYCH.
- Skład jest ustalany raz, na dniu odczytu użytym w teście, i nie zmienia się w trakcie testu.

| Klasa | Rynki w kolejności (symbole) |
|---|---|
| Akcje USA | S&P 500 (`SPY`, `SP500.r`, `SP500ft.r`); małe spółki (`IWM`, `US2000.r`); Nasdaq 100 (`QQQ`); finanse (`XLF`); technologia (`XLK`); półprzewodniki (`SMH`) |
| Akcje poza USA | rynki rozwinięte (`EFA`); rynki wschodzące (`EEM`); Japonia (`EWJ`, `Nikkei225`, `JPN225ft`); strefa euro (`EU50.r`); Wielka Brytania (`UK100.r`, `UK100ft.r`); Chiny (`FXI`, `MCHI`, `CHINAH.r`); Indie (`INDA`); Brazylia (`EWZ`); Korea (`EWY`); Tajwan (`EWT`); Hongkong (`HK50.r`, `HK50ft.r`); Australia (`SPI200.r`) |
| Obligacje | USA długie (`TLT`); USA 10 lat (`USNote10Y`); Niemcy 10 lat (`EUB10Y`); Wielka Brytania (`LongGilt`); Niemcy 5 lat (`EUB5Y`); Niemcy 30 lat (`EUB30Y`); Niemcy 2 lata (`EUB2Y`) |
| Złoto i metale | złoto (`GLD`, `XAUUSD+`); srebro (`XAGUSD`); platyna (`XPTUSD.r`); spółki złota (`GDX`) |
| Energia i surowce | ropa WTI (`USO`, `USOUSD`, `CL-OIL`); koszyk surowców (`DBC`); gaz ziemny (`UNG`); ropa Brent (`BNO`, `UKOUSD`, `UKOUSDft`); pszenica (`Wheat-Cr`); soja (`Soybean-Cr`); spółki naftowe (`XOP`) |
| Krypto | Bitcoin (`IBIT`, `BTCUSD`); Ethereum (`ETHUSD`); Solana (`SOLUSD`); Litecoin (`LTCUSD`); XRP (`XRPUSD`); Bitcoin Cash (`BCHUSD`) |
| Waluty | `EURUSD+`; `USDJPY+`; `GBPUSD+`; `AUDUSD+` |

## 4. Mechanika wspólna

Jak w serii 1 (`SPEC_H2_H3.md`), z poniższymi zmianami.

- Okres strojenia: do 31.12.2024. Próba poza strojeniem: od 01.01.2025 do ostatniej wspólnej daty. Reguł nie stroimy.
- Decyzja raz w miesiącu, na zamknięciu ostatniego dnia kalendarza koszyka w miesiącu. Wykonanie po cenie otwarcia pierwszej świecy rynku po dniu decyzji; wariant z opóźnieniem o jedną świecę później.
- Rynek bierze udział w decyzji, gdy ma co najmniej 320 świec ciągłej historii. Pierwsza decyzja zapada, gdy udział bierze co najmniej 6 rynków.
- Waga bazowa rynku: odwrotność zmienności dziennych zmian z ostatnich V = 60 świec, podzielona przez sumę odwrotności rynków biorących udział w decyzji.
- Pozycja docelowa = sygnał × waga bazowa × G. Suma wartości bezwzględnych pozycji nie przekracza G.
- Limit jednego rynku: 50% kapitału. Nadwyżka zostaje w gotówce.
- Wynik liczymy w dwóch widokach:
  - **model**: wagi ciągłe, jak w serii 1;
  - **rachunek 2 500 USD**: kapitał początkowy 2 500 USD, wartość pozycji = waga × bieżący kapitał, zaokrąglenie w dół do kroku lota, pozycja mniejsza od najmniejszego lota oznacza brak pozycji. Używamy tej samej funkcji wielkości pozycji co w paper (`astraljet.lab.position_sizing`).
- **Kryteria liczymy na widoku rachunku.** Widok modelu jest w raporcie dla porównania.
- W widoku modelu zmiana wagi mniejsza niż 2 punkty procentowe nie jest wykonywana (wyjątek: zejście do zera i zmiana strony).
- Rynki notowane w innej walucie niż USD: zwroty bez przeliczenia walut; wartość pozycji po kursie z dnia odczytu.

## 5. Koszty

- Koszt jednej strony transakcji. Bazowy: połowa spreadu + 1 pb. Stresowy: cały spread + 2 pb.
- Prowizja od CFD na akcje i ETF-y: stawka i kwota minimalna ze specyfikacji brokera (punkt 8). Bazowy: stawka. Stresowy: 1,5 × stawka.
- Finansowanie obu stron, naliczane za każdy dzień kalendarzowy od wartości pozycji, ze stawki swapu danej strony z dnia odczytu:
  - `swap_mode` 1 (punkty): |swap| × `point` × 365 / cena;
  - `swap_mode` 5 lub 6 (procent rocznie): |swap| %;
  - `swap_mode` 2, 3 lub 4 (kwota na lot): |swap| × kurs waluty swapu × 365 / (wielkość kontraktu × cena × kurs waluty zysku);
  - `swap_mode` 0: brak finansowania;
  - swap dodatni (wpływ) liczymy jako zero;
  - brak danych albo inny tryb: 7% rocznie.
- Wariant stresowy finansowania: 1,5 × stawka bazowa + 1 punkt procentowy.
- Wypłaty (dywidendy, odsetki). Ceny CFD nie są o nie korygowane, a terminal nie podaje ich historii.
  - Pozycja długa: dopisanych wypłat nie liczymy.
  - Pozycja krótka na ETF-ie akcyjnym albo indeksie kasowym: dopłata 3% rocznie (stres 5%).
  - Pozycja krótka na ETF-ie obligacji (`TLT`): dopłata 5% rocznie (stres 7%).
  - Pozostałe rynki: bez dopłaty.
  - To szacunek, nie dane. Zastąpią go rzeczywiste wypłaty, gdy będzie ich źródło (punkt 8).

## 6. Hipotezy

### H4 — trend w obie strony

- Sygnał rynku: +1, gdy zamknięcie jest wyższe niż zamknięcie sprzed L = 252 świec; −1, gdy niższe; 0, gdy równe.

### H5 — trend tylko po stronie długiej, nowy koszyk

- Sygnał rynku: +1, gdy zamknięcie jest wyższe niż zamknięcie sprzed L = 252 świec; inaczej 0.
- To reguła H2 na nowych instrumentach i w lotach. Pokazuje, ile wnosi strona krótka z H4.

### Wspólne dla H4 i H5

- Punkt odniesienia: wszystkie rynki koszyka po stronie długiej w wagach bazowych × G, z tym samym miesięcznym równoważeniem, kosztami i lotami.
- Warianty (12 na hipotezę, razem 24): główny (252, 60) w czterech scenariuszach (koszt bazowy i stresowy, z opóźnieniem i bez) oraz 8 sąsiadów przy koszcie bazowym: L z {202, 252, 302} × V z {48, 60, 72} bez wariantu głównego. Po serii 2 rejestr prób będzie miał 60 wariantów.

## 7. Kryteria

Protokół walidacji w wersji 1 bez zmian (`docs/research/PROTOKOL_WALIDACJI.md`): sześć kryteriów na próbie poza strojeniem, wszystkie naraz. Gdy koszyk jest nieważny (punkt 3) albo brakuje danych z punktu 8: BRAK DANYCH.

Raport podaje dodatkowo, bez wpływu na werdykt: wynik do 31.12.2024, udział strony długiej i krótkiej, liczbę pozycji pominiętych przez najmniejszy lot, rozbicie kosztów i różnicę między widokiem modelu a rachunku.

Okres 2025–2026 był już oglądany 36 razy na innych hipotezach. PASS dopuszcza więc tylko do etapu paper. O każdym dalszym etapie decyduje Karol na podstawie wyniku na nowych danych.

## 8. Dane, których brakuje przed pierwszym testem

| Czego brakuje | Kto ustala | Co się dzieje bez tego |
|---|---|---|
| G: największa łączna ekspozycja (bez dźwigni albo z dźwignią do limitu) | Karol | Test nie rusza |
| Prowizja od CFD na akcje i ETF-y: stawka i kwota minimalna | specyfikacja brokera | Test nie rusza dla koszyka z ETF-ami |
| Wypłaty na CFD: czy i jak broker koryguje pozycje długie i krótkie | specyfikacja brokera | Zostaje szacunek z punktu 5, opisany w raporcie jako ograniczenie |
| Rozliczenie skoku ceny przy rolowaniu kontraktów opartych na futures | specyfikacja brokera | Te symbole są poza koszykiem (punkt 2.6) |

## 9. Etap paper

- Paper buduje i sprawdza wykonanie. Rusza po akceptacji reguł, niezależnie od werdyktu; strategia z FAIL jest oznaczona „nie przeszła badania".
- Codziennie: kontrola świeżości danych, decyzja, zapis. Hamulec obsunięcia jest aktywny.
- Po każdym miesiącu porównanie z backtestem na tych samych danych. Różnica miesięcznego wyniku większa niż 0,5 punktu procentowego wymaga wyjaśnienia.
- Paper nie potwierdza przewagi w krótkim czasie: przy decyzji raz w miesiącu trzy miesiące to trzy decyzje.

Wynik to obliczenie modelu. Nie jest rekordem RUN ani zgodą na handel.
