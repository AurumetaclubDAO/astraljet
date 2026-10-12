# Feature Specification: Bezpieczny MVP Astra JET

**Feature Branch**: `001-build-astra-jet` (katalog specyfikacji; gałąź Git nie została utworzona)

**Created**: 2026-09-19

**Status**: Gotowa do planowania — trzy decyzje zakresowe zatwierdzone 2026-09-19

**Input**: User description: "budowa bota Astra JET"

## Clarifications

### Session 2026-09-19

- Q: Jak mamy włączyć istniejącą Astrę do `D:\Astra Jet`? → A: Rozpocząć w `D:\Astra Jet` nową implementację niezależną od starego `astra_site`; ASTRA Pro jest modułem badawczo-oceniającym AstralJet i łączy się z resztą systemu przez wspólne rekordy oraz zdarzenia.
- Q: Jaki tryb ma obsługiwać pierwszy Wykonawca AstralJet? → A: Oba tryby: `PAPER_CONTINUOUS` i `BROKER_DEMO`; handel REAL pozostaje poza zakresem.
- Q: Jaka nowa strategia i rynek mają być pierwszym przypadkiem odbiorowym? → A: Wszystkie pięć strategii z przekazanego załącznika rejestrujemy do opracowania; pierwszy pełny przebieg obejmuje strategię #5 „BTC/ETH z kontrolą trendu i ryzyka” na dziennym rynku spot BTC i ETH w USD.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Odtwarzalne badanie jednej strategii (Priority: P1)

Karol przekazuje jedną strategię lub hipotezę wraz ze źródłami. ASTRA Pro Trading Lab
prowadzi ją przez rejestrację materiału, jednoznaczną specyfikację, kontrolę danych,
zamrożony plan eksperymentu, backtest, ocenę odporności i odtworzenie wyniku. Rezultatem
jest kompletny pakiet dowodów, również wtedy, gdy strategia zostaje odrzucona albo wynik
pozostaje nierozstrzygnięty.

**Why this priority**: Wiarygodny, odtwarzalny proces badawczy jest warunkiem wszystkich
dalszych decyzji i może dostarczyć wartość bez uruchamiania zleceń brokerskich.

**Independent Test**: Jedna uzgodniona strategia przechodzi LAB-01–LAB-12 bez ręcznego
dopowiadania wyników; drugi przebieg odtwarza wynik w zapisanej tolerancji, a raport prowadzi
do wszystkich wersji wejść i prób.

**Acceptance Scenarios**:

1. **Given** kompletna strategia, dopuszczone dane i kryteria zapisane przed wynikiem,
   **When** Karol uruchamia eksperyment, **Then** system tworzy powiązane artefakty STRAT,
   DATA, EXP, RUN i REVIEW oraz oddziela stan techniczny od oceny strategii.
2. **Given** strategia z brakującą regułą wyjścia, sizingiem lub źródłem kosztu,
   **When** system sprawdza kompletność, **Then** zatrzymuje badanie jako
   `ZABLOKOWANE + DO_UZUPEŁNIENIA`, wskazuje brak i właściciela decyzji, bez zgadywania.
3. **Given** poprawnie wykonany eksperyment z wynikiem niespełniającym wcześniej zapisanych
   kryteriów, **When** kończy się przegląd, **Then** wynik ma status
   `ZAKOŃCZONE + ODRZUCONA`, a wszystkie próby pozostają dostępne.

---

### User Story 2 - Niezależny przegląd i decyzja (Priority: P2)

Karol otrzymuje wynik, który został sprawdzony niezależnie od autora testu. Krytyk ocenia
metodę i kompletność dowodów, Ryzyko określa dopuszczalność następnego etapu, a decyzja
zawiera autora, datę, zakres i ograniczenia. Opinia modelu nie zastępuje obliczeń ani
potwierdzenia z danych.

**Why this priority**: Oddzielenie badania od akceptacji ogranicza wybiórcze raportowanie,
dopasowanie do danych i awans strategii na podstawie jednego korzystnego przebiegu.

**Independent Test**: Dla pakietu RUN system wymusza drugi przebieg oraz osobny REVIEW;
brak dowodu, kosztu albo zgodności wersji kończy się werdyktem `unverified`, nie sukcesem.

**Acceptance Scenarios**:

1. **Given** kompletny RUN i wszystkie warianty, **When** Krytyk wykonuje przegląd,
   **Then** REVIEW wskazuje dowody, ograniczenia i werdykt `verified`, `unverified` albo
   `rejected`.
2. **Given** dwa raporty o różnych instrumentach, kosztach lub modelach wykonania,
   **When** użytkownik próbuje je porównać, **Then** system oznacza je jako
   `NIEPORÓWNYWALNE` i nie tworzy rankingu.
3. **Given** zmieniona reguła strategii po teście, **When** rozpoczyna się kolejny przebieg,
   **Then** powstają nowe wersje STRAT i EXP, a poprzedni RUN nie jest dowodem nowej wersji.

---

### User Story 3 - Kontrolowana inkubacja bez REAL (Priority: P3)

Po pozytywnym przeglądzie Karol może zatwierdzić mandat inkubacji dla jednej wersji
strategii. Oddzielny Wykonawca prowadzi ciągłą symulację lub brokerskie DEMO w granicach
mandatu, a Lab ma wyłącznie odczyt wyników. Każdy sygnał, zamiar, realizacja, błąd i stan
niepewny są rejestrowane.

**Why this priority**: Obserwacja na późniejszych danych jest potrzebna przed jakąkolwiek
przyszłą decyzją kapitałową, ale nie może rozszerzać uprawnień Laboratorium ani uruchamiać
handlu REAL.

**Independent Test**: Zatwierdzony mandat uruchamia jedną zamrożoną wersję w wybranym
trybie, restart nie dubluje działania, przekroczenie limitu blokuje nowe ryzyko, a brak
potwierdzenia zlecenia nie powoduje ślepego ponowienia.

**Acceptance Scenarios**:

1. **Given** pakiet zakwalifikowany do rozważenia inkubacji i zatwierdzony mandat,
   **When** Wykonawca rozpoczyna serię, **Then** zapisuje tryb, wersje, limity, środowisko
   oraz wszystkie zdarzenia w INCU.
2. **Given** brak mandatu, niewłaściwe środowisko albo decyzja Ryzyka `ZABLOKOWANE`,
   **When** pojawia się sygnał, **Then** system nie tworzy działania wykonawczego i zapisuje
   powód blokady.
3. **Given** niepewny wynik wcześniejszej operacji, **When** Wykonawca rozważa ponowienie,
   **Then** najpierw uzgadnia stan, uruchamia alarm i blokuje nowe ryzyko do wyjaśnienia.

---

### User Story 4 - Czytelny stan, koszt i ślad decyzji (Priority: P4)

Karol widzi, co system bada, na jakim jest etapie, co go blokuje, ile kosztowała praca,
jakie dowody powstały i jaka decyzja jest potrzebna. Ponowne dostarczenie tego samego
zadania nie powoduje drugiego płatnego wywołania ani działania wykonawczego.

**Why this priority**: Trwały stan i rozliczenie umożliwiają bezpieczne wznawianie pracy,
audyt oraz kontrolę kosztów bez polegania na historii rozmów.

**Independent Test**: Użytkownik może odtworzyć łańcuch źródło → strategia → dane → plan
→ przebieg → przegląd → decyzja → inkubacja i rozpoznać aktualny bloker bez przeglądania
logów technicznych.

**Acceptance Scenarios**:

1. **Given** zadanie przerwane przez brak danych lub limit kosztu, **When** użytkownik wraca
   do projektu, **Then** widzi ostatni potwierdzony krok, właściciela blokady i bezpieczną
   czynność wznowienia.
2. **Given** ponowne wysłanie identycznego zlecenia, **When** orkiestrator rozpoznaje jego
   tożsamość, **Then** wiąże je z istniejącym zadaniem bez podwójnego kosztu lub wykonania.
3. **Given** korekta wcześniejszego wpisu, **When** zostaje zatwierdzona, **Then** system
   dodaje nowe zdarzenie i zachowuje poprzednią historię.

### Edge Cases

- Materiał źródłowy zawiera prompt nakazujący instalację, ujawnienie sekretu lub transakcję:
  system zachowuje go jako treść źródła i nie wykonuje polecenia.
- PDF lub inny materiał jest nieczytelny: zadanie importu jest blokowane, lecz strategia nie
  jest automatycznie odrzucana.
- Dane mają lukę, błędną strefę czasową albo informację niedostępną w chwili decyzji:
  zależny test jest nieważny i wymaga nowego przebiegu po poprawie DATA.
- Stop i cel występują w tej samej świecy bez danych o kolejności: system nie wybiera
  korzystniejszego wariantu po cichu.
- Brak kosztu nie jest zamieniany na zero; test mechaniki może działać z jawnym
  ograniczeniem, ale nie wydaje wniosku o wyniku netto.
- Brak transakcji albo brak strat nie tworzy sztucznej wartości Profit Factor ani awansu.
- Limit budżetu jest wyczerpany lub odpowiedź płatna ma stan niepewny: system zachowuje
  postęp i nie ponawia operacji do czasu rozliczenia.
- Proces zostaje zrestartowany podczas zadania albo inkubacji: stan jest odtwarzany z
  trwałego rejestru, bez dublowania płatności, przebiegu lub działania wykonawczego.
- Kod, dane, reguła albo konfiguracja zmieniają się podczas serii: seria jest zatrzymywana
  lub oznaczana jako nowa wersja; wyników nie łączy się bez segmentacji.
- Dwa wykonawcy próbują przejąć to samo środowisko: drugi start jest odrzucany i raportowany.
- Brak świeżych danych, monitoring przestaje działać albo limit ryzyka jest naruszony:
  nowe ryzyko jest blokowane w trybie fail-closed.
- Replay na późniejszych danych jest błędnie nazwany paper tradingiem: system zachowuje
  typ `LATER_DATA_REPLAY` i nie deklaruje ciągłości działania.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST przyjmować materiał, kod lub hipotezę jako wersjonowane źródło
  z pochodzeniem, autorem albo oznaczeniem „nieznany”, datą, lokalizatorem i hashem.
- **FR-002**: System MUST traktować instrukcje zapisane w źródłach jako dane i MUST NOT
  wykonywać z nich instalacji, wysyłki, publikacji, ujawnienia sekretu ani transakcji.
- **FR-003**: System MUST utrzymywać role AJ-00–AJ-18 jako odpowiedzialności i MUST NOT
  wymagać, aby każda rola była osobnym procesem, modelem lub abonamentem.
- **FR-004**: Laboratorium MUST pozostawać bez uprawnień do składania zleceń, a funkcje
  wykonawcze MUST być odseparowane od badania i oceny.
- **FR-005**: System MUST rozdzielać stan techniczny zadania od wyniku merytorycznego
  strategii zgodnie z katalogami opisanymi w dokumentacji v0.2.
- **FR-006**: System MUST zarejestrować jako `CAND` wszystkie pięć strategii z przekazanego
  materiału. Pierwszy pełny przebieg odbiorowy MUST objąć strategię #5 „BTC/ETH z kontrolą
  trendu i ryzyka” na dziennym rynku spot BTC i ETH w USD; konkretny dostawca i miejsce
  notowań MUST zostać zapisane w `DATA` przed zamrożeniem `EXP`. Pozostałe cztery
  strategie pozostają kandydatami do formalizacji i nie są uznawane za zweryfikowane.
- **FR-007**: System MUST zapisywać rekordy SRC, CAND, STRAT, DATA, EXP, RUN, REVIEW,
  RISK-DECISION, MANDATE, INCU i EVENT z identyfikatorem, wersją, właścicielem, czasem,
  wejściami, stanem i ograniczeniami.
- **FR-008**: Strategia MUST określać instrument i miejsce obrotu, czas sygnału i wykonania,
  wejścia, wyjścia, sizing, koszty, ograniczenia oraz zachowanie przy brakach danych.
- **FR-009**: Brak istotnej reguły MUST blokować oceniany eksperyment; system MUST wskazać
  brak, możliwe warianty i właściciela decyzji bez wprowadzania domyślnej reguły handlowej.
- **FR-010**: DATA MUST zawierać dostawcę, zakres, strefę czasową, czas dostępności, hash,
  transformacje, model kosztów i wynik kontroli jakości.
- **FR-011**: System MUST odrzucać użycie informacji przyszłej oraz ujawniać wcześniejsze
  wykorzystanie danych do odkrywania, strojenia lub oceny.
- **FR-012**: EXP MUST przed wynikiem wiązać wersje STRAT i DATA, okresy, dozwolone
  warianty, kryteria, budżet, model kosztów, seed i tolerancję odtworzenia.
- **FR-013**: Zmiana STRAT, DATA, planu lub kodu po zamrożeniu MUST utworzyć nową wersję
  albo zatrzymać serię; wynik starej wersji MUST pozostać w historii.
- **FR-014**: System MUST sprawdzać mechanikę na małych przypadkach kontrolnych, w tym
  kolejność sygnału, sizing, księgowanie, koszty i niejednoznaczną realizację w świecy.
- **FR-015**: RUN MUST zachowywać wszystkie transakcje, realizacje, odrzucone sygnały,
  koszty, ekspozycję, krzywą kapitału, błędy, wersje i instrukcję odtworzenia.
- **FR-016**: System MUST rejestrować wszystkie dozwolone warianty, także przegrane,
  technicznie nieudane i odrzucone, bez selekcji wyłącznie najlepszego rezultatu.
- **FR-017**: Raport MUST rozróżniać BACKTEST, LATER_DATA_REPLAY, PAPER_CONTINUOUS i
  BROKER_DEMO oraz opisywać ograniczenia każdego rodzaju dowodu.
- **FR-018**: Raport MUST zawierać wynik netto, kapitał i walutę, okres, liczbę transakcji,
  koszty, ekspozycję, maksymalne obsunięcie, Profit Factor, win rate, punkt odniesienia,
  niepewność i liczbę badanych wariantów albo jawny powód braku każdej wartości.
- **FR-019**: Drugi przebieg MUST używać tych samych wersji i parametrów, a zgodność wyniku
  MUST być oceniana względem tolerancji zapisanej przed pierwszym ocenianym wynikiem.
- **FR-020**: REVIEW MUST być oddzielony od autora RUN i kończyć się werdyktem `verified`,
  `unverified` albo `rejected` z dowodami, brakami i warunkami następnego kroku.
- **FR-021**: System MUST NOT przedstawiać backtestu, DEMO, replay ani wyniku materiału
  źródłowego jako gwarancji, prognozy lub potwierdzonego wyniku LIVE.
- **FR-022**: Awans do inkubacji MUST wymagać kompletnego pakietu dowodów, oceny Ryzyka i
  jawnego, datowanego mandatu Karola dla konkretnej wersji, trybu i limitów.
- **FR-023**: Handel REAL, wybór brokera realnego i alokacja realnego kapitału MUST pozostać
  poza zakresem tej funkcji i nie mogą być uruchamiane przez żaden przepływ MVP.
- **FR-024**: Pierwszy Wykonawca MUST obsługiwać `PAPER_CONTINUOUS` i `BROKER_DEMO` jako
  odrębne tryby, z osobnymi mandatami, środowiskami i oznaczeniem rodzaju dowodu; żadna
  konfiguracja tych trybów nie może umożliwiać handlu REAL.
- **FR-025**: Wykonawca MUST działać tylko w granicach mandatu, sprawdzać środowisko,
  strategię, instrument, limity i świeżość danych oraz blokować nowe ryzyko przy braku.
- **FR-026**: Każda intencja i próba wykonania MUST mieć stabilny identyfikator; ponowienie
  MUST być idempotentne, a stan niepewny MUST zostać uzgodniony przed kolejną próbą.
- **FR-027**: System MUST zapewniać pojedynczego aktywnego wykonawcę, trwały stan, ręczny
  kill switch, monitoring, alarm i odrębne traktowanie nowych wejść, zleceń oczekujących
  oraz istniejących pozycji.
- **FR-028**: EVENT MUST zapisywać czas, autora lub proces, wersję, przyczynę, wynik i
  powiązane artefakty; korekta MUST być nowym wpisem, nie nadpisaniem historii.
- **FR-029**: Orkiestrator MUST rozpoznawać duplikaty zadań i MUST NOT powtarzać płatnego
  wywołania, eksperymentu ani działania wykonawczego bez rozstrzygnięcia poprzedniej próby.
- **FR-030**: System MUST rozdzielać koszt rozliczony, aktywną rezerwację i koszt
  nieuzgodniony oraz MUST blokować kosztową operację po wyczerpaniu zatwierdzonego limitu.
- **FR-031**: Użytkownik MUST widzieć badany obiekt, etap, wynik, bloker, właściciela,
  powstałe artefakty, koszt i dozwolony następny krok bez odczytywania surowych logów.
- **FR-032**: System MUST umożliwiać audyt tylko do odczytu i eksport pełnego łańcucha
  źródło → reguła → test → przegląd → decyzja → inkubacja.

### Key Entities *(include if feature involves data)*

- **SRC**: Wersjonowane źródło lub materiał z pochodzeniem, lokalizatorem i hashem.
- **CAND**: Kandydat strategii lub hipotezy wraz z brakami i historią odkrycia.
- **STRAT**: Jednoznaczna wersja reguł strategii oraz jej ograniczeń.
- **DATA**: Konkretny, wersjonowany zbiór i raport jakości dla dopuszczonego zastosowania.
- **EXP**: Zamrożony przed wynikiem plan eksperymentu i jego kryteria.
- **RUN**: Pojedynczy przebieg z pełnymi wejściami, księgą, wynikiem i odtworzeniem.
- **REVIEW**: Niezależny przegląd jakości dowodów i ograniczeń.
- **RISK-DECISION**: Datowana decyzja o dopuszczalności określonego następnego kroku.
- **MANDATE**: Zgoda Karola określająca tryb, wersje, środowisko, limity i zatrzymanie.
- **INCU**: Seria ciągłej obserwacji ze zdarzeniami, realizacjami i lukami.
- **EVENT**: Niezmienny wpis audytowy wiążący działanie z autorem, czasem i artefaktami.
- **BUDGET-STATUS**: Limity, rezerwacje, koszty rozliczone i nierozstrzygnięte.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Jedna zatwierdzona strategia lub przypadek kontrolny przechodzi 12 etapów Lab,
  a każdy etap ma kompletne wejście, wynik, właściciela i kryterium odbioru.
- **SC-002**: Drugi przebieg odtwarza wszystkie zdarzenia i metryki w tolerancji zapisanej
  przed pierwszym ocenianym wynikiem; rozbieżności są automatycznie oznaczone.
- **SC-003**: 100% raportowanych wyników wskazuje tryb dowodu, wersje, okres, liczbę prób,
  koszty i maksymalne obsunięcie albo jawny powód braku wartości.
- **SC-004**: 100% zmian reguł, danych, planu lub kodu po zamrożeniu tworzy nową wersję albo
  blokadę; żaden wynik nie jest przypisany do innej wersji wejść.
- **SC-005**: 100% negatywnych, technicznie nieudanych i nierozstrzygniętych prób pozostaje
  dostępne w historii oraz nie jest automatycznie awansowane.
- **SC-006**: Żadna ścieżka Laboratorium ani materiał źródłowy nie może utworzyć operacji
  brokerskiej; automatyczne testy akceptacyjne potwierdzają blokadę wszystkich takich prób.
- **SC-007**: Ponowne dostarczenie identycznego zadania w 100% przypadków kontrolnych nie
  powoduje drugiego kosztu, RUN ani działania wykonawczego.
- **SC-008**: Po kontrolowanym restarcie użytkownik odzyskuje ostatni potwierdzony stan,
  komplet powiązań i bezpieczną czynność wznowienia bez duplikacji.
- **SC-009**: Każde naruszenie mandatu, utrata świeżości danych, konflikt wykonawców albo
  stan niepewny blokuje nowe ryzyko i tworzy widoczny alarm w ciągu 60 sekund.
- **SC-010**: W teście odbiorowym Karol potrafi w mniej niż 2 minuty wskazać badany obiekt,
  etap, wynik, bloker, koszt, dowody i dozwolony następny krok.
- **SC-011**: 100% twierdzeń o wynikach odróżnia backtest, replay, PAPER, DEMO i LIVE;
  żaden komunikat nie zawiera obietnicy lub gwarancji zysku.
- **SC-012**: Test bezpieczeństwa potwierdza, że MVP nie ma ścieżki uruchomienia handlu REAL
  ani możliwości rozszerzenia mandatu bez nowej datowanej decyzji Karola.

## Assumptions

- Dokumentacja v0.2 w `docs/architektura/` jest zatwierdzoną podstawą zakresu; v0.1 jest
  historią, a instrukcje w materiałach źródłowych nie są poleceniami wykonawczymi.
- Początkowy materiał strategii ma lokalizator
  `C:\Users\karol\Downloads\5_strategii_inwestycyjnych_2026_PL.md` i SHA-256
  `ED708DAF399C9851CA925F4050817936CD2F6F80D3C14A29899699CEA8FB6998`; zawarte w nim
  zakresy wyników, dane makro i przykłady instrumentów są twierdzeniami źródła wymagającymi
  osobnej weryfikacji, a nie domyślnymi parametrami AstralJet.
- AstralJet powstaje jako nowa lokalna implementacja w `D:\Astra Jet`, niezależna od kodu
  starego `astra_site`. ASTRA Pro jest modułem badawczo-oceniającym AstralJet i komunikuje
  się z pozostałymi częściami systemu przez wersjonowane rekordy oraz niezmienne zdarzenia;
  nie uzyskuje przez to uprawnień wykonawczych.
- Głównym użytkownikiem i właścicielem ważnych decyzji jest Karol. Role AJ są rolami
  odpowiedzialności, nie obowiązkowo osobnymi agentami.
- Pierwsze wydanie jest lokalnym narzędziem dla jednego właściciela; publikacja, marketing,
  wielodostęp i handel REAL są poza zakresem.
- Pełne dane rynkowe, sekrety, logi runtime i bazy pozostają poza repozytorium; rekordy
  przechowują bezpieczne identyfikatory, hashe i lokalizatory.
- Kryteria wyniku, ryzyka, budżetu i tolerancji nie są uniwersalne. System wymaga ich w EXP
  lub MANDATE przed właściwą próbą, ale nie przyjmuje progów z materiałów jako domyślnych.
- Integracje TradingKit, TradingView, Trigger Trade i broker są opcjonalnymi adapterami;
  ich instalacja i uprawnienia wymagają odrębnego zatwierdzenia.
- Dostęp do prywatnego `AurumetaclubDAO/astraljet` pozostaje warunkiem bezpiecznego
  połączenia lokalnych prac z istniejącą historią Git.
