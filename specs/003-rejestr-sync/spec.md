# Feature Specification: Jednokierunkowa synchronizacja rejestru badań

**Feature Branch**: `003-rejestr-sync`  
**Created**: 2026-09-23  
**Status**: Draft  
**Input**: Uzgodniony wariant 1: lokalny rdzeń badań jest źródłem prawdy dla nowych rekordów, a Command Center otrzymuje jednokierunkowo wyłącznie metadane potrzebne do wglądu.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Aktualny wgląd do rejestru badań (Priority: P1)

Karol kończy lub aktualizuje badanie w lokalnym rdzeniu i inicjuje synchronizację. W Command Center widzi aktualne, wersjonowane metadane tego samego rekordu wraz z jego źródłem, czasem ostatniej synchronizacji i statusem.

**Why this priority**: Usuwa ręczne wczytywanie snapshotów jako podstawowy sposób obserwacji pracy badawczej, nie zmieniając środowiska wykonawczego.

**Independent Test**: Można utworzyć testowy rekord w lokalnym rejestrze, zsynchronizować go i potwierdzić jego widoczność oraz identyfikowalność w Command Center.

**Acceptance Scenarios**:

1. **Given** nowy lub zmieniony rekord badań, **When** Karol uruchamia synchronizację, **Then** Command Center pokazuje jego metadane, wersję, hash, źródło lokalne i czas obserwacji.
2. **Given** rekord już zsynchronizowany bez zmian, **When** synchronizacja jest ponowiona, **Then** nie powstaje jego duplikat ani nowa wersja bez zmiany treści.

---

### User Story 2 - Bezpieczne rozpoznanie konfliktu (Priority: P2)

Karol otrzymuje jednoznaczny komunikat, gdy docelowy rejestr zawiera sprzeczną wersję tego samego lokalnego rekordu. System nie zastępuje istniejących danych automatycznie.

**Why this priority**: Rejestr badań ma zachowywać historię i dowody, więc ciche nadpisanie unieważniałoby wartość synchronizacji.

**Independent Test**: Można zasymulować sprzeczne metadane po stronie docelowej i potwierdzić brak zmiany oraz zapis przyczyny konfliktu.

**Acceptance Scenarios**:

1. **Given** sprzeczny zapis o tej samej tożsamości źródłowej, **When** uruchomiona zostaje synchronizacja, **Then** operacja kończy się statusem konfliktu bez modyfikacji istniejącego rekordu.

---

### User Story 3 - Jawna granica z wykonaniem (Priority: P3)

Karol może korzystać ze wspólnego widoku rejestru bez ryzyka uruchomienia strategii, procesu brokera, DEMO albo LIVE.

**Why this priority**: Wgląd badawczy nie może rozszerzyć mandatu wykonawczego.

**Independent Test**: Testy potwierdzają, że synchronizacja nie zawiera danych uwierzytelniających, poleceń wykonawczych ani możliwości ich wywołania.

**Acceptance Scenarios**:

1. **Given** poprawnie przeprowadzona synchronizacja, **When** rekord jest oglądany w Command Center, **Then** nie tworzy zlecenia, zadania wykonawczego ani zmiany rachunku.

### Edge Cases

- Przerwana lub niedostępna synchronizacja nie zmienia lokalnego rejestru i pozostawia informację umożliwiającą bezpieczne ponowienie.
- Rekord bez wymaganej tożsamości, wersji lub hashu nie trafia do wspólnego widoku i ma czytelną przyczynę blokady.
- Stare rekordy z D1 oraz historyczne rekordy SQLite bez potwierdzonego powiązania pozostają odrębnymi źródłami; system nie tworzy relacji na podstawie podobnej nazwy.
- Odbiorca bez uprawnień do właścicielskiego widoku nie widzi zsynchronizowanych metadanych.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST uznać lokalny rejestr rdzenia badań za jedyne źródło prawdy dla rekordów utworzonych w tym przepływie.
- **FR-002**: System MUST przekazywać do wspólnego widoku wyłącznie allowlistę metadanych: tożsamość źródłową, typ, wersję, hash, status, relacje, znaczniki czasu i informacje o stanie synchronizacji.
- **FR-003**: System MUST zachować rozróżnienie przestrzeni tożsamości źródłowych i nie może łączyć starych rekordów na podstawie nazw, kolejności ani wspólnych opisów.
- **FR-004**: System MUST zapewnić, że ponowienie identycznej synchronizacji nie tworzy duplikatu ani nie modyfikuje historii.
- **FR-005**: System MUST odrzucić niekompletny, nieautoryzowany albo niespójny przekaz oraz zapisać przyczynę bez ujawniania danych wrażliwych.
- **FR-006**: System MUST zatrzymać zapis przy konflikcie tożsamości lub niezgodności wersji/hashu; rozwiązanie konfliktu wymaga jawnej, audytowalnej decyzji, nie automatycznego nadpisania.
- **FR-007**: System MUST pokazywać w Command Center źródło, świeżość i wynik ostatniej synchronizacji zamiast przedstawiać dane jako bieżące bez dowodu.
- **FR-008**: System MUST zachować istniejące rekordy, snapshoty i widoki odczytowe; nowe połączenie nie wykonuje migracji pełnych baz ani automatycznego scalenia historii.
- **FR-009**: System MUST nie przekazywać sekretów, pełnych baz, payloadów wykonawczych, danych brokera ani autoryzacji wykonania.
- **FR-010**: System MUST nie uruchamiać i nie zmieniać MT5, procesów badawczych, DEMO ani LIVE w wyniku synchronizacji lub jej błędu.

### Key Entities *(include if feature involves data)*

- **Rekord źródłowy**: Wersjonowany rekord badawczy utworzony w lokalnym rdzeniu, z trwałą tożsamością w przestrzeni lokalnej.
- **Przekaz metadanych**: Ograniczony, identyfikowalny zbiór metadanych jednego lub wielu rekordów przekazywany do wspólnego widoku.
- **Stan synchronizacji**: Audytowalny wynik próby przekazania, zawierający czas, zakres, rezultat, liczbę rekordów oraz bezpieczną przyczynę błędu lub konfliktu.
- **Konflikt synchronizacji**: Niezgodność tożsamości, wersji albo hashów, która blokuje zmianę docelowego zapisu.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: W kontrolowanym scenariuszu 100% poprawnych rekordów testowych pojawia się we wspólnym widoku z prawidłowym źródłem, wersją i hashem.
- **SC-002**: Ponowienie tego samego przekazu co najmniej 10 razy nie tworzy duplikatów ani nie zmienia metadanych rekordów.
- **SC-003**: 100% celowo wygenerowanych konfliktów zostaje zablokowanych bez nadpisania istniejącego zapisu i z czytelną przyczyną.
- **SC-004**: W testach zakresu przekazywanych danych nie występują sekrety, pełne pliki rejestru, dane brokerów ani polecenia wykonawcze.
- **SC-005**: Po nieudanej próbie ponowienie może zakończyć się sukcesem bez ręcznej naprawy lokalnego rejestru i bez utraty wcześniejszych danych.

## Assumptions

- Istniejący Command Center oraz jego uwierzytelnianie właścicielskie pozostają miejscem obserwacji, bez tworzenia drugiego dashboardu.
- Historyczne rekordy powstałe przed tą funkcją nie są automatycznie mapowane ani migrowane.
- Zakres obejmuje wyłącznie badania i ich metadane; nie obejmuje uruchomienia handlu, kosztów brokerskich, wyboru rachunku, polityki Risk Management ani publikacji nowego mandatu wykonawczego.
- Dostęp do docelowego rejestru i bezpieczny mechanizm uwierzytelnienia przekazu będą dostępne przed wdrożeniem produkcyjnym.
