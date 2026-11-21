# Badania H2 i H3 — reguły zapisane przed zobaczeniem danych

Data zapisu: 18.11.2026. Autor: Claude (koordynator). W chwili zapisu w repozytorium nie ma jeszcze dziennych danych z MT5 dla koszyka; są tylko dane BTC/ETH z Alpaca użyte w H1. Reguł i progów nie zmieniamy po zobaczeniu wyników. Każda zmiana to nowa hipoteza z nowym numerem.

## Dane

- Źródło: historia D1 z terminala MT5 Karola, pliki `research/daily-data/data/<SYMBOL>_D1.csv` i `.meta.json`.
- Koszyk (pole `market` w pliku meta): `SP500`, `NAS100`, `DAX`, `GOLD`, `BRENT`, `EURUSD`, `BTCUSD`. `WTI` i `ETHUSD` są pobierane, ale nie wchodzą do koszyka, bo niemal powielają `BRENT` i `BTCUSD`.
- Rynek z mniej niż 1500 świecami przed 01.01.2025 wypada z koszyka. Fakt ten trafia do raportu.
- Okres strojenia: do 31.12.2024. Próba poza strojeniem: od 01.01.2025 do ostatniej wspólnej daty.

## Mechanika wspólna

- Kalendarz to suma dat wszystkich rynków koszyka, od dnia, w którym każdy rynek ma już notowania, do ostatniej wspólnej daty.
- Decyzja zapada raz w miesiącu, na zamknięciu ostatniego dnia kalendarza w miesiącu. Każdy rynek używa swoich świec do tego dnia włącznie.
- Wykonanie: po cenie otwarcia pierwszej świecy danego rynku po dniu decyzji. Wariant z opóźnieniem: o jedną świecę później.
- Pierwsza decyzja zapada, gdy każdy rynek ma co najmniej 320 świec.
- Tylko pozycje długie, bez dźwigni: suma wag nie przekracza 1, reszta to gotówka bez odsetek.
- Zmiana wagi mniejsza niż 2 punkty procentowe nie jest wykonywana (wyjątek: zejście do zera).
- Wycena codziennie po cenie zamknięcia; rynek bez świecy w danym dniu zachowuje ostatnie zamknięcie.

## Koszty

- Spread względny = największa z wartości (spread z pliku meta, mediana kolumny `spread` w CSV) × `point` / ostatnie zamknięcie. Gdy brak danych: 0,10%.
- Koszt jednej strony transakcji. Bazowy: połowa spreadu + 1 pb. Stresowy: cały spread + 2 pb.
- Finansowanie pozycji długiej, naliczane za każdy dzień kalendarzowy od wartości pozycji:
  - `swap_mode` 1 (punkty): |swap_long| × `point` × 365 / cena, gdy swap jest ujemny;
  - `swap_mode` 5 lub 6 (procent rocznie): |swap_long| %, gdy swap jest ujemny;
  - `swap_mode` 2, 3 lub 4 (kwota na lot): |swap_long| × 365 / (`trade_contract_size` × cena), gdy swap jest ujemny; przybliżenie bez przeliczenia walut;
  - `swap_mode` 0: brak finansowania;
  - swap dodatni liczymy jako zero (ostrożnie);
  - brak danych lub inny tryb: 7% rocznie.
- Wariant stresowy finansowania: 1,5 × stawka bazowa + 1 punkt procentowy.

## H2 — podążanie za trendem

- Sygnał rynku: zamknięcie wyższe niż zamknięcie sprzed L = 252 świec.
- Waga bazowa rynku: odwrotność zmienności dziennych zmian z ostatnich V = 60 świec, podzielona przez sumę odwrotności dla całego koszyka.
- Waga docelowa: waga bazowa, gdy sygnał jest dodatni, inaczej zero.
- Punkt odniesienia: wagi bazowe trzymane stale, z tym samym miesięcznym równoważeniem i kosztami.
- Warianty (12): główny (252, 60) w czterech scenariuszach (koszt bazowy i stresowy, z opóźnieniem i bez) oraz 8 sąsiadów przy koszcie bazowym: L z {202, 252, 302} × V z {48, 60, 72} bez wariantu głównego.

## H3 — rotacja momentum

- Ranking rynków według zmiany ceny z ostatnich L = 126 świec.
- Trzymamy N = 3 najlepsze, każdy z wagą 1/N. Rynek ze zmianą niedodatnią nie jest kupowany, a jego część zostaje w gotówce.
- Punkt odniesienia: wszystkie rynki koszyka w równych wagach, z miesięcznym równoważeniem i tymi samymi kosztami.
- Warianty (12): główny (126, 3) w czterech scenariuszach oraz 8 sąsiadów przy koszcie bazowym: L z {101, 126, 151} × N z {2, 3, 4} bez wariantu głównego.

## Kryteria (te same co w H1, z `PLAN_BUDOWY.md` z 17.11.2026)

PASS, gdy na próbie poza strojeniem spełnione jest wszystko naraz:

1. wynik po kosztach stresowych jest dodatni;
2. Sharpe po kosztach bazowych wynosi co najmniej 0,7;
3. relacja rocznego zysku do największego obsunięcia jest lepsza niż dla punktu odniesienia;
4. największe obsunięcie nie przekracza 25%;
5. co najmniej 60% kwartałów jest dodatnich;
6. wszyscy sąsiedzi dają wynik dodatni.

Inaczej FAIL. Gdy koszyk ma mniej niż 4 rynki: BRAK DANYCH.

## Uruchomienie

    python research/daily-trend/scripts/run_h2_h3.py --selftest
    python research/daily-trend/scripts/run_h2_h3.py

Wynik to obliczenie modelu. Nie jest rekordem RUN ani zgodą na handel.
