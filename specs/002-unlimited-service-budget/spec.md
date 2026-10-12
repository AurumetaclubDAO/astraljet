# Feature Specification: Wydatki AI i X bez stałego pułapu

**Feature Branch**: `codex/unlimited-service-budget`, izolowany checkout wydania
**Created**: 2026-09-20
**Status**: Wdrożono prywatnie jako wersję 54; odbiór i granice w raporcie etapu 10
**Input**: Karol: „1 no limit wszędzie. 2 demo i live”, następnie „Działaj”.

Pierwszy niezależny przyrost po konstytucji 2.0.0 usuwa pułapy wydatków usług
istniejącej Astry. Nie jest kompletnym wdrożeniem wszystkich zasad 2.0.0.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Analiza bez sztucznej blokady kwotowej (Priority: P1)

Karol korzysta z AI także po przekroczeniu historycznych 25 USD/miesiąc i 20 USD
automatycznych analiz. Nie potwierdza każdego kosztu przekraczającego szacunek.

**Why this priority**: Usuwa rzeczywistą przeszkodę pracy badań przy zachowaniu historii.
**Independent Test**: Testy przed implementacją, na danych testowych i bez płatnych wywołań.

**Acceptance Scenarios**:
1. **Given** koszt miesiąca ponad dawne pułapy, **When** nowe zadanie AI,
   **Then** przechodzi do dostawcy, a koszt zostaje zapisany raz.
2. **Given** koszt odpowiedzi większy niż rezerwacja, **When** wiarygodne rozliczenie,
   **Then** użytkownik dostaje odpowiedź, koszt zostaje zapisany bez blokady kolejnych zadań.
3. **Given** stary zapis przekroczenia szacunku, **When** nowe zadanie,
   **Then** stare rozliczenie pozostaje widoczne, ale nie blokuje nowego zadania.
4. **Given** błąd dostawcy lub nieznany koszt, **When** odczyt stanu,
   **Then** brak nie staje się kosztem zerowym ani automatycznym ponowieniem.

### User Story 2 - Źródła X bez pułapu miesięcznego (Priority: P2)

Odczyt X nie zatrzymuje się po historycznych 5 USD. Jedna partia pozostaje jednym
zadaniem, z tym samym identyfikatorem przy ponowieniu.

**Why this priority**: „Wszędzie” obejmuje także drugą obecną usługę płatną.
**Independent Test**: Odczyty symulowane, również po przekroczeniu 5 USD.

**Acceptance Scenarios**:
1. **Given** wydatek ponad 5 USD, **When** nowa partia, **Then** wydatek nie blokuje odczytu.
2. **Given** niepewna poprzednia partia, **When** ta sama partia ponownie,
   **Then** dostawca nie otrzymuje drugiego żądania; inna partia nie ma blokady kwotowej.
3. **Given** brak kredytów, uprawnień lub ograniczenie tempa dostawcy,
   **When** odczyt, **Then** pojawia się właściwa przyczyna, bez automatycznego doładowania.

### User Story 3 - Prawdziwy stan kosztów w panelu (Priority: P2)

Karol widzi „bez pułapu”, koszt i kwoty wymagające uzgodnienia, zamiast fałszywego
zera pozostałego budżetu, nieskończoności lub dawnego limitu 25/5/30 USD.

**Why this priority**: Interfejs ma odpowiadać działającemu rozliczeniu.
**Independent Test**: Widoki budżetu, czatu i X z tymi samymi danymi testowymi.

**Acceptance Scenarios**:
1. **Given** brak pułapu, **When** panel/czat/X pokazuje koszty,
   **Then** podaje kwotę i jawny brak pułapu, bez procentowego zużycia limitu.
2. **Given** nieuzgodnione koszty, **When** panel,
   **Then** pokazuje ostrzeżenie i dostęp do rozliczenia, nie fałszywy zakaz pracy AI.
3. **Given** prywatna publikacja, **When** aktualizacja,
   **Then** odbiorcy, historia badań, harmonogramy i rachunki nie zmieniają się.

### Edge Cases

- Zerowy koszt nie oznacza braku pułapu; brak konfiguracji nie oznacza zgody na wydatki.
- Nieprawidłowa, ujemna albo niefinitywna kwota nie może wejść do rozliczenia.
- Zmiana miesiąca nie usuwa niepewnych kosztów; ponowienie rozliczenia nie nalicza ich drugi raz.
- Koszt potwierdzony ponad 25 USD ma zostać przyjęty, nie odrzucony przez dawny limit.
- Przekroczenie oszacowania nie jest tożsame z awarią dostawcy.
- Limity techniczne wejścia/odpowiedzi, terminy oczekiwania i zabezpieczenia powtórzeń pozostają.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: AI i X MUST mieć jawny stan „bez pułapu”, odrębny od zera i braku decyzji.
- **FR-002**: W tym stanie wydatki miesiąca ani kategorii MUST NOT blokować nowego zadania.
- **FR-003**: Wiarygodny koszt AI przekraczający oszacowanie MUST być zapisany bez utraty odpowiedzi i blokowania kolejnych zadań.
- **FR-004**: Historia, rezerwacje i koszty nieuzgodnione MUST pozostać; brak danych MUST NOT być zerem.
- **FR-005**: Powtórzona partia X i ponowne rozliczenie MUST NOT tworzyć podwójnego kosztu.
- **FR-006**: Błędy i ograniczenia dostawców MUST być rozróżniane, bez zmiany płatności lub automatycznego doładowania.
- **FR-007**: Wszystkie bieżące widoki kosztów AI/X MUST pokazywać brak pułapu zgodnie ze stanem usługi.
- **FR-008**: Zmiana MUST zachować prywatny dostęp, stare dane, harmonogramy i rozdzielenie od wykonania zleceń.
- **FR-009**: Testy MUST obejmować koszty ponad stare pułapy, przekroczenie rezerwacji, niepewność, izolację właścicieli i błędne kwoty.

### Key Entities

- **Polityka wydatków**: decyzja właściciela, tryb, pułap lub jego jawny brak, data wersji.
- **Rozliczenie wywołania**: właściciel, usługa, zadanie, okres, rezerwacja, koszt i stan pewności.
- **Podsumowanie kosztów**: wykorzystanie, brak pułapu, kwoty nieuzgodnione i opis przyczyn.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% testów nowych zadań powyżej dawnych pułapów nie ma odmowy z powodu kwoty.
- **SC-002**: Każdy przypadek niepewnego kosztu pozostaje oznaczony; zero podwójnych rozliczeń w testach ponowień.
- **SC-003**: Wszystkie bieżące widoki AI/X pokazują brak pułapu, bez wartości Infinity/NaN.
- **SC-004**: Publikacja zachowuje dostęp wyłącznie właściciela; nie wykonuje zleceń brokerskich ani masowego wznowienia kolejki.

## Assumptions

- Decyzja z 2026-09-20 jest zatwierdzona; nie pytamy ponownie o budżet 1/25 USD.
- Rozwijamy istniejącą Astrę, bez scalenia jej baz z lokalnym rdzeniem.
- MT5, wybór funkcji sizingu i wykonawcy DEMO/LIVE to kolejne odrębne przyrosty.
  Pozostają zatwierdzonym kierunkiem, nie są wdrażane ani deklarowane jako gotowe w tym przyroście.
- Nie zmieniamy modeli, cenników, technicznych wielkości partii ani harmonogramów.
- Publikacja tej zmiany pozwala istniejącym zaplanowanym zadaniom korzystać z nowej polityki;
  nie uruchamia nowych harmonogramów ani ręcznych płatnych testów.
