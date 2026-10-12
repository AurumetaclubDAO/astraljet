# Plan po odbiorze MVP — pierwsza strategia BTC/ETH

- [x] P001 Zarejestrować rzeczywisty materiał i pięć CAND bez wykonywania instrukcji źródła.
- [x] P002 Wyodrębnić szkic BTC/ETH oraz oddzielić fakty źródłowe od hipotez i decyzji.
- [x] P003 Dodać test, który blokuje `READY` dla fraz „średnia rośnie”, „struktura trendu” i „2–3 transze”.
- [x] P004 Zapisać rzeczywisty szkic STRAT jako `needs_input` i pokazać siedem blokerów w statusie.
- [x] P005 Zapisywać odrzucenia i realizacje Wykonawcy jako trwałe EVENT.
- [ ] P006 Uzyskać od Karola decyzje parametrów wymienionych w `docs/strategies/BTC_ETH_STRAT_DRAFT_v0.1.md`.
- [ ] P007 Wskazać oraz zatwierdzić lokalny snapshot DATA z licencją/proweniencją i modelem kosztów.
  - [x] P007a Dodać bezpieczny adapter historycznych świec krypto Alpaca z paginacją i metadanymi.
  - [x] P007b Pobrać lokalny snapshot zamkniętych świec BTC/USD i ETH/USD oraz sprawdzić hash i kompletność.
  - [ ] P007c Zatwierdzić prywatne zastosowanie danych i konserwatywny model fee + spread + slippage.
- [ ] P008 Utworzyć nową, kompletną wersję STRAT i zamrozić EXP przed poznaniem wyniku.
- [ ] P009 Wykonać bazowy RUN, niezależną reprodukcję oraz pełny REVIEW.
- [ ] P010 Dopiero po `verified` REVIEW i `allowed` RISK-DECISION rozważyć osobny mandat PAPER.

Pozycje P006–P010 są celowo otwarte. Nie wolno ich zamykać na podstawie prognoz,
przykładów ani parametrów pochodzących wyłącznie z materiału źródłowego.

## Przyrost techniczny 06 — adapter zamrożonego modelu (20.09.2026)

To osobny zakres techniczny po etapie 05. Nie zamyka P006–P010 i nie stanowi
akceptacji propozycji BTC/ETH. Testy korzystają wyłącznie z tymczasowych rejestrów
i syntetycznych cen.

- [x] P011 Najpierw dodać testy wymagające dokładnych wersji, odrzucania podmiany planu/metadanych/kodu i braku zapisów.
- [x] P012 Zbudować jawny adapter `weekly_experiment.py`: pełne powiązanie STRAT/DATA, hash EXP, ograniczony profil reguł, wszystkie przypięte scenariusze.
- [x] P013 Dodać `experiment inspect-weekly` i `run weekly-offline`, bez inicjalizacji/migracji, RUN, REVIEW, brokera lub fallbacku do starego silnika.
- [x] P014 Domknąć regresję całego rdzenia, kontrakt CLI, instrukcję obsługi i raport etapu; potwierdzić brak zmian rzeczywistych baz i propozycji. Wynik: 136/136 testów Python 3.12; hashe dwóch baz, CSV i propozycji bez zmian.

## Naprawa operacyjna 07 — istniejąca witryna, bez zmiany wykonawców

Zakres zlecony 20.09.2026: usunąć usterki działania i pokazać faktyczne procesy.
Zmiany w istniejącym `astra_site`, bez migracji rejestrów, zgód strategii i budżetu.
Odczyty istniejących heartbeatów, telemetrii i blokad nie uruchamiają AI ani brokera.

- [x] P015 Odtworzyć błąd pochodzenia długiego ID i naprawić walidację bez skracania ID.
- [x] P016 Testy przed implementacją: stan procesu, wygasłe odczyty, właściciel, brak sekretów, przyczyny blokad.
- [x] P017 Podłączyć bieżące statusy do Command Center i ról AJ; automatyczny odczyt, bez pozorowania autonomii.
- [x] P018 Sprawdzić testy, kompilację, opublikować dokładnie przetestowany zakres w istniejącej prywatnej witrynie i odebrać widok. Wersja 52, 196/196 testów czystego wydania; odczyt heartbeat i 47 rekordów pochodzenia potwierdzony w przeglądarce.
- [x] P019 Zapisać wynik naprawy oraz pozostałe, konkretne blokady bez deklaracji ukończenia handlu. Raport `docs/operations/ETAP_07_2026-09-20.md`; P006–P010 nadal otwarte.

## Przyrost 08 — raport lokalnego silnika w istniejącym Analytics

Odczyt pliku w pamięci przeglądarki, bez sieci dla zawartości raportu, scalenia baz,
sterowania procesami, płatnych wywołań i zmiany zatwierdzeń. Nie jest to automatyczna
synchronizacja rejestrów. Korzystamy z istniejących eksportów CLI, nie nowego silnika.

- [x] P020 Zdefiniować i przetestować kontrakt raportów `weekly-offline-report-v1` oraz `astraljet-experiment-inputs-v1`; błędny hash, obce pola i zgoda wykonawcza są odrzucane.
- [x] P021 Podłączyć Analytics do lokalnego raportu; IS/OOS, wszystkie warianty, benchmark, equity, DD, koszty i jawne braki metryk.
- [x] P022 Zweryfikować zgodność odczytu z eksportem rzeczywistego kodu Python na syntetycznym rejestrze oraz widok rzeczywistej blokady bez liczenia wyniku. 4174 wiersze / 8 blokad potwierdzone lokalnie i na wersji 53.
- [x] P023 Sprawdzić brak wysyłki/utrwalania, zmian baz i pozornej kwalifikacji; regresja, typy, kompilacja i odbiór UI. 207/207 testów czystej witryny, 136/136 rdzenia; hashe baz bez zmian.
- [x] P024 Opublikować wyłącznie przetestowany zakres w istniejącej prywatnej witrynie; dokumentacja ograniczeń i obsługi. Wersja 53, `a33de1787d84e0ee2a0e757d1bf87db909a3b4af`, raport etapu 08; P006–P010 pozostają otwarte.

## Przyrost 09 — lokalna kontrola materiałów bez uruchamiania AI

Wspólny parser procesu i inspektora, bez zmiany starej kolejki lub automatycznego
wznowienia. Inspektor nie importuje startu workera, nie czyta konfiguracji urządzeń,
nie odpytuje sieci/brokera i zapisuje tylko nowy, wskazany raport. To kontrola
odczytu źródeł, nie analiza strategii, OCR lub zgoda na koszty.

- [x] P025 Testami odtworzyć brak bezkosztowej inspekcji i ograniczenia wejścia/wyjścia parsera. Odtworzono też błąd przepuszczenia zmienionych bajtów pliku do parsera.
- [x] P026 Wydzielić wspólny parser i stronicowane fragmenty bez importu runtime; zachować interfejs istniejącego workera. Dodano zgodność SHA-256 przed parsowaniem przesłanego pliku.
- [x] P027 Dodać lokalny inspektor z hashami, metadanymi stron, limitem czasu, bez pełnej treści w raporcie i bez nadpisywania plików.
- [x] P028 Sprawdzić katalogowe PDF-y po zgodnym SHA-256, zachować jawne błędy/OCR i brak analizy AI; regresja. 22 wpisy / 21 plików, dwa wymagają przeglądu tekstu; 30/30 testów badań i 225/225 JS/TS roboczego checkout.
- [x] P029 Zapisać instrukcję i stan faktyczny; zachować niezwiązane zmiany, bazy, budżet, procesy i wersję opublikowanej witryny. Etap 09; lokalny commit 50d8ee1, publikacja i działający worker niezmienione przez ten przyrost.

## Naprawa 14 — rzeczywista ocena dowodów AJ-08

Zakres: lokalna ścieżka RUN → REVIEW, bez zmiany reguł strategii, kosztów,
aktywnego DEMO, harmonogramów i rejestrów produkcyjnych. Wykryta luka pozwalała
uznać duplikat RUN lub deklarację `ReproductionReport(True)` za weryfikację.
Kontrola niezależna wymaga jawnego, przypiętego raportu obserwacji; sam replay
tego samego silnika nie jest niezależną metodą. Nie zamyka P006–P010.

- [x] P030 Odtworzyć duplikat RUN, pomijanie trzeciego przebiegu, niezgodny EXP, brak hashy oraz NaN/Infinity w testach przed poprawką (`tests/contract/test_review_integrity.py`).
- [x] P031 Sprawdzać każdy RUN, zakres eksperymentu, integralność wyniku, koszty i wszystkie metryki; nie ufać przekazanemu booleanowi (`lab/reproduction.py`, `application/reviews.py`).
- [x] P032 Dodać ścisły, ograniczony raport `astraljet-independent-check-v1` z przypiętymi obserwacjami, metodą i hashem implementacji; zachować artefakt w REVIEW, odróżnić integralność od uwierzytelnienia autora (`application/independent_check.py`, `domain/records.py`).
- [x] P033 Podłączyć raport do CLI, zachować idempotencję i czytelne blokady w statusie; stary REVIEW bez dowodów nie może automatycznie uzyskać nowej decyzji allowed.
- [x] P034 Sprawdzić pozytywną i negatywną ścieżkę CLI → SQLite → REVIEW → RISK-DECISION na testowych artefaktach, bez zleceń i bez dopisywania ich do rejestru rzeczywistych badań.
- [x] P035 Uruchomić pełną regresję, zapisać dowody i ograniczenia; nie przedstawiać testowego raportu jako niezależnej walidacji rynku. 174/174 testy; `docs/operations/ETAP_14_2026-09-24.md`, brak nowych rekordów i zdarzeń w rejestrze rzeczywistym.

Założenie zaufania v1: raport jest dostarczany jawnie przez lokalnego operatora,
nie generowany automatycznie przez badany silnik. Hash spina jego treść z RUN/EXP,
ale nie uwierzytelnia tożsamości recenzenta ani sam nie dowodzi uruchomienia innego
programu. Obsługa drugiego źródła nie jest jeszcze uzyskaniem tego źródła dla
rzeczywistej strategii. Brak raportu pozostaje jawnym `unverified`.

## Przyrost 18 — trwałe wyniki modelu tygodniowego

Brakujące połączenie obliczeń z rejestrem: jawne `run weekly-recorded` dla
istniejącego, dokładnego EXP, bez inicjalizacji/migracji i bez dowolnego importu
raportu jako wyniku. Wszystkie warianty zapisujemy atomowo, po jednym RUN na
scenariusz. Metryki główne dotyczą OOS strategii; pełne IS/OOS, benchmark,
sygnały i scenariusz pozostają w przypiętym artefakcie. Kryteria nadal wymagają
oceny, więc wynik to `inconclusive`, nie automatyczne `passed`/`verified`.
Nie zmienia to P006–P010, strategii, zakresu `registry:sync` ani runtime.

- [x] P036 Najpierw testy trwałego zapisu, idempotencji, konfliktów, rollbacku, zmiany wejść i braku zapisu do nieistniejącej/starej bazy (`tests/integration/test_weekly_recorded.py`).
- [x] P037 Zbudować jawny kontrakt RUN scenariusza oraz kontrolę integralności pełnego artefaktu i projekcji (`lab/weekly_run.py`, `lab/reproduction.py`).
- [x] P038 Dodać atomowy zapis całej serii i CLI z dokładną wersją EXP, bez zleceń i automatycznej migracji (`application/weekly_recorded.py`, `cli.py`, `infrastructure/repositories.py`).
- [x] P039 Przetestować reprodukcję, niekwalifikujący REVIEW oraz kopię samych metadanych RUN w istniejącym formacie synchronizacji. Parsery v60 przyjmują metadane i odtworzony raport; test offline, nie nowe przyjęcie w D1.
- [x] P040 Pełna regresja, kontrakt CLI i raport; jawnie oddzielić sprawdzoną mechanikę od rzeczywistego eksperymentu i wdrożenia workera. 187/187 testów rdzenia, 34/34 na Python 3.12; `docs/operations/ETAP_18_2026-09-24.md`. P006–P010 nadal otwarte.

## Naprawa 19 — trwałe wyszukiwanie źródeł AJ-03

Rozszerzenie istniejącej ochrony operacji AI na `discover_search`. Nie zmienia
parametrów strategii ani uprawnień `registry:sync`, nie restartuje MT5/procesu
badań i nie wznawia zbiorczo zadań. Obecna ścieżka może ponownie zapłacić po
przerwaniu odpowiedzi; częściowy import zmienia również wejście ponowienia.
Zamrożenie żądania jest technicznym snapshotem wyszukiwania, nie EXP strategii.

- [x] P041 Odtworzyć utratę odpowiedzi, zmienną bibliotekę/X, równoległość, utratę dzierżawy i błąd atomowego zapisu w testach. 18 nowych testów.
- [x] P042 Zapisać pełne wejście wyszukiwania w istniejącym zadaniu przed wywołaniem AI, zachować hashe i użyć trwałej operacji rozliczeniowej.
- [x] P043 Zapisać materiały, ich zadania importu, raport i zakończenie wyszukiwania atomowo, z kontrolą właściciela i bieżącej dzierżawy. Nowy token podjęcia chroni także po wyzerowaniu prób na tym samym urządzeniu.
- [x] P044 Wykonać regresję, TypeScript i build; opublikować przetestowaną zmianę prywatnej witryny i sprawdzić działający odbiornik. 287/287 testów, wersja 61; jedno rzeczywiste wyszukiwanie i import zakończone. Dalsza ekstrakcja zablokowana przez cytat, bez nowej karty.
- [x] P045 Zapisać dowody i pozostałe ograniczenia, osobno od gotowości wszystkich ról i nieuzgodnionej tożsamości runtime. `docs/operations/ETAP_19_2026-09-24.md`; P006–P010 nadal otwarte.

## Przyrost 20 — wyjaśnienie blokad ekstrakcji bez nowego kosztu

Zapisana odpowiedź AI jest niedostępna w podglądzie materiału, a błąd cytatu
nie wskazuje reguły lub fragmentu. Dodajemy odczyt diagnostyczny konkretnej
rewizji i zapisanej operacji. Nie naprawiamy cytatów domysłem, nie publikujemy
kart ani nie wywołujemy modelu z tego podglądu. Źródła pozostają niezaufaną treścią.

- [x] P046 Testami określić diagnostykę poprawnych/błędnych cytatów, błędnego ID, brakującej odpowiedzi, wersji, limitów i izolacji właścicieli. 11 nowych testów.
- [x] P047 Zbudować ograniczony odczyt zapisanej operacji i raport błędów powiązany z aktualną rewizją źródła; bez zapisu i płatnego transportu.
- [x] P048 Dodać uwierzytelniony odczyt API i podgląd przy materiale; jawnie oddzielić wskazówkę od zatwierdzonej poprawki.
- [x] P049 Pełna regresja, TypeScript, lint/build i prywatna publikacja; sprawdzić diagnozę rzeczywistego zablokowanego materiału w panelu. 298/298 testów, wersja 62; zastane 3 błędy lint starszego komponentu bez zmiany, nowe pliki czyste.
- [x] P050 Zapisać konkretną przyczynę i dalszą ścieżkę; nie zamknąć P006–P010 ani odbioru całego systemu na podstawie samej diagnostyki. 23/31 poprawnych cytatów, 8 skrótów/zmian typografii, `docs/operations/ETAP_20_2026-09-24.md`.

## Naprawa 21 — cytaty wybierane z oryginału

Rzeczywisty materiał blokują skróty i zmiany zapisu cytatów. Korekta wybiera
wyłącznie ID dosłownych fragmentów już odczytanego źródła. Nie zmienia tytułu,
reguł, parametrów ani braków strategii. Zachowuje oryginalną odpowiedź,
oddzielny koszt korekty i jej ślad; najwyżej jedna nowa opłacona odpowiedź
korygująca dla tego samego wejścia. Niepewna lub nieużyteczna odpowiedź nie
tworzy pętli wywołań. Karty pozostają do przeglądu.

- [ ] P051 Testy niezmiennych fragmentów, mapowania, odmowy/braku dowodu, błędnych ID i zachowania reguł.
- [ ] P052 Podłączyć ograniczoną korektę do ekstrakcji, z trwałą operacją AI, audytem oraz ścisłą końcową walidacją cytatów.
- [ ] P053 Testy integracyjne utraty zapisu, ponowień, kosztów i starej odpowiedzi; pełna regresja.
- [ ] P054 Prywatna publikacja i jedno kontrolowane wznowienie zablokowanej analizy; odebrać faktyczny wynik bez zmiany handlu.
- [ ] P055 Dokumentacja wyników, kosztów, niepewności oraz zakresu gotowości ról.
