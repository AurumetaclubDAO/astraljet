# Protokół walidacji strategii — wersja 1

Obowiązuje dla pierwszej serii badań (H1, H2, H3). Kryteria ustalono 17.11.2026, przed pierwszym testem
(`PLAN_BUDOWY.md` w centrum projektu). Ten plik przenosi je do repozytorium i dopisuje, jak dokładnie są liczone.

Status każdego wyniku z tego protokołu: obliczenie modelu offline. To nie jest rekord RUN ani zgoda na handel.

## Po co ten protokół

Dotąd żadne podejście w projekcie nie pokazało przewagi po kosztach. Protokół ma jedno zadanie: nie przepuścić
strategii, która wygląda dobrze tylko dlatego, że dopasowano ją do danych albo pominięto koszty.

## Dane i podział

- Świece dzienne.
- Okres strojenia: do 31.12.2024.
- Próba poza strojeniem: od 01.01.2025 do końca danych. Na próbie niczego nie stroimy i niczego nie wybieramy.
- Każdy zbiór danych ma zapisaną sumę kontrolną SHA-256 w pliku wyniku.

## Koszty

Każdy wariant liczymy w dwóch scenariuszach: bazowym i stresowym.

- H1 (BTC i ETH): 40 i 75 punktów bazowych na transakcję (pakiet A z 20.09.2026).
- H2 i H3 (koszyk rynków): koszt z danych brokera, opisany w `research/daily-trend/SPEC_H2_H3.md`.
  Bazowy to połowa spreadu plus 1 punkt bazowy na stronę oraz finansowanie pozycji. Stresowy to pełny spread
  plus 2 punkty bazowe oraz finansowanie pomnożone przez 1,5 i powiększone o 1 punkt procentowy rocznie.

## Warianty

Najwyżej 12 wariantów na hipotezę i każdy trafia do rejestru prób (`research/REJESTR_PROB.md`):

- 4 warianty główne: koszt bazowy i stresowy, każdy bez opóźnienia i z opóźnieniem wykonania o jedną świecę;
- 8 sąsiadów: parametry przesunięte w dół i w górę o około 20% (parametr liczony w sztukach, np. liczba
  wybranych rynków, o jeden), koszt bazowy, bez opóźnienia.

Punkt odniesienia („kup i trzymaj" ten sam koszyk) nie jest wariantem strategii i nie liczy się do limitu.

## Kryteria PASS

Wszystkie liczone na próbie poza strojeniem. Wariant główny to parametry z reguł, bez opóźnienia.

| Nr | Kryterium | Jak liczone |
|---|---|---|
| 1 | Wynik po kosztach stresowych jest dodatni | Zwrot netto wariantu głównego w scenariuszu stresowym, większy od zera |
| 2 | Sharpe po kosztach bazowych wynosi co najmniej 0,7 | Średni dzienny zwrot podzielony przez odchylenie standardowe, przeliczony na rok. Stopa wolna od ryzyka przyjęta jako zero |
| 3 | Zysk do obsunięcia lepszy niż punkt odniesienia | Zwrot roczny podzielony przez największe obsunięcie, porównany z tą samą liczbą dla „kup i trzymaj" |
| 4 | Największe obsunięcie nie przekracza 25% | Największy spadek kapitału od szczytu, wariant główny, koszt bazowy |
| 5 | Co najmniej 60% okien jest dodatnich | Okna to kwartały kalendarzowe próby. Liczymy udział kwartałów ze zwrotem większym od zera |
| 6 | Sąsiednie parametry też są dodatnie | Wszystkich 8 sąsiadów ma zwrot netto większy od zera |

**PASS** wymaga spełnienia wszystkich sześciu naraz. Inaczej **FAIL**. Gdy danych jest za mało, żeby policzyć
któreś kryterium, werdykt to **BRAK DANYCH**.

Przeliczenie Sharpe'a na rok: H1 używa pierwiastka z 365, bo krypto ma notowania codziennie. H2 i H3 używają
faktycznej liczby sesji na rok w kalendarzu koszyka.

## Uwaga do kryterium 5

W planie z 17.11 kryterium nazywało się „walk-forward dodatni w co najmniej 60% okien". Reguły badanych
strategii nie są strojone, więc nie ma czego powtarzać w kolejnych oknach strojenia. Zostało samo sprawdzenie
stabilności: kwartały kalendarzowe próby. Tak policzono H1 i tak zapisano H2 i H3 przed zobaczeniem danych.
Dla strategii z parametrami strojonymi na danych trzeba będzie wrócić do pełnego walk-forward.

## Co oznacza werdykt

- **PASS** dopuszcza strategię do etapu paper (symulowane zlecenia na bieżących danych). Nie dopuszcza do demo
  u brokera ani do rachunku LIVE. O tych etapach decyduje Karol na podstawie osobnych kryteriów.
- **FAIL** zamyka hipotezę w tej postaci. Poprawiona wersja to nowa hipoteza z nowym wpisem w rejestrze.

## Czego ten protokół nie załatwia

- Próba jest krótka: niecałe dwa lata i 7 kwartałów. Jeden nietypowy kwartał zmienia wynik kryterium 5.
- Trzy hipotezy po 12 wariantów to 36 prób. Przy tylu próbach pojedynczy PASS może być przypadkiem,
  dlatego po nim idzie etap paper, a nie pieniądze.
- Warianty z opóźnieniem są raportowane, ale nie wchodzą do kryteriów.
- Koszty H2 i H3 pochodzą z jednego odczytu warunków brokera. Spread i swap zmieniają się w czasie.

## Zmiany protokołu

Progi może zmienić tylko Karol i tylko przed pierwszym testem danej serii. Każda zmiana dostaje nowy numer
wersji. Wyniki policzone według starej wersji zostają bez zmian i nie są przeliczane wstecz.

## Gdzie co leży

| Co | Plik |
|---|---|
| Reguły H1 i wynik | `research/btc-eth-weekly/scripts/run_offline.py`, `research/btc-eth-weekly/reports/` |
| Reguły H2 i H3 | `research/daily-trend/SPEC_H2_H3.md` |
| Silnik H2 i H3 | `research/daily-trend/scripts/run_h2_h3.py` |
| Rejestr prób | `research/REJESTR_PROB.md`, tworzony przez `research/tools/rejestr_prob.py` |
