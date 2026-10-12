# Zadania: Bezpieczny MVP Astra JET

**Wejście**: dokumenty w `specs/001-build-astra-jet/`  
**Testy**: obowiązkowe; testy historii, idempotencji, granicy Lab/Wykonawca i braku REAL
wynikają ze specyfikacji oraz konstytucji.

## Format

`[ID] [P?] [Story?] Opis z dokładną ścieżką`

## Phase 1 — Setup

- [x] T001 Utworzyć konfigurację pakietu Python >=3.12 i komendę `astraljet` w `pyproject.toml`
- [x] T002 Utworzyć strukturę pakietu i pliki `__init__.py` w `src/astraljet/`, `src/astraljet/domain/`, `src/astraljet/application/`, `src/astraljet/lab/`, `src/astraljet/executor/` i `src/astraljet/infrastructure/`
- [x] T003 [P] Utworzyć strukturę testów w `tests/contract/`, `tests/integration/`, `tests/unit/` i `tests/fixtures/`
- [x] T004 Zweryfikować i uzupełnić bezpieczne reguły Python/runtime w `.gitignore`, w tym `.venv/`, `__pycache__/`, `*.pyc`, `.runtime/`, `*.sqlite*`, `.env*`, logi i sekrety, bez przyjmowania szerokiej reguły `lib/`

## Phase 2 — Fundament wspólny

**Cel**: trwały, audytowalny zapis i wspólne typy blokujące wszystkie historie.

- [x] T005 [P] Napisać najpierw testy migracji, WAL, foreign keys i restartu w `tests/integration/test_database.py`
- [x] T006 [P] Napisać najpierw testy kontraktu EVENT, append-only i idempotencji w `tests/contract/test_event_store.py`
- [x] T007 Zaimplementować enumy bez wartości REAL oraz błędy domenowe w `src/astraljet/domain/enums.py` i `src/astraljet/domain/errors.py`
- [x] T008 Zaimplementować wspólną kopertę w `src/astraljet/domain/records.py`: `record_id` z prefiksem typu, `version` jako liczba całkowita `>=1`, `owner` niepusty, `created_at` UTC ISO-8601, dozwolony `technical_status`, 64-znakowy SHA-256, jawne `limitations` i opcjonalne `supersedes`
- [x] T009 Zaimplementować kanonizację JSON, hash i walidację UTC/identyfikatorów w `src/astraljet/domain/validation.py`
- [x] T010 Zaimplementować wymagany jawny katalog stanu i ścieżkę bazy w `src/astraljet/config.py`
- [x] T011 Zaimplementować schemat SQLite, migrację v1, WAL i foreign keys w `src/astraljet/infrastructure/migrations.py` i `src/astraljet/infrastructure/database.py`
- [x] T012 Zaimplementować dopisywany EVENT z unikalnym `idempotency_key`, niepustym `reason`, `record_version >=1` i atomowym zwrotem wcześniejszego wyniku w `src/astraljet/infrastructure/event_store.py`
- [x] T013 Zaimplementować wersjonowane repozytorium rekordów oraz atomowy zapis rekord+EVENT w `src/astraljet/infrastructure/repositories.py`
- [x] T014 Zaimplementować parser CLI, kody wyjścia 0/2/3/4, `--state-dir` i komendę `init` w `src/astraljet/cli.py`
- [x] T015 Uruchomić `tests/contract/test_event_store.py` i `tests/integration/test_database.py`, poprawić implementację i oznaczyć checkpoint fundamentu

## Phase 3 — User Story 1: Odtwarzalne badanie jednej strategii (P1) — MVP

**Cel**: źródło i pięciu kandydatów przechodzą do kompletnej STRAT/DATA/EXP/RUN bez
zgadywania braków; pierwszy oceniany przypadek to BTC/ETH na rynku spot dziennym w USD.

**Test niezależny**: drugi RUN dla tych samych wersji odtwarza zdarzenia i metryki w
zamrożonej tolerancji; niekompletna strategia kończy się blokadą z właścicielem decyzji.

- [x] T016 [P] [US1] Napisać test kontraktowy bezpiecznego `source add` i niezmiennego SHA-256 w `tests/contract/test_source_intake.py`
- [x] T017 [P] [US1] Napisać test integracyjny utworzenia dokładnie pięciu CAND bez RUN i bez `verified` w `tests/integration/test_candidate_intake.py`
- [x] T018 [P] [US1] Napisać testy walidacji STRAT: instrument/venue, częstotliwość, czas sygnału, wejście, wyjście, sizing, koszty, ograniczenia, brak danych, benchmark i parametry muszą istnieć przed `ready` w `tests/unit/test_strategy_validation.py`
- [x] T019 [P] [US1] Napisać przypadki mechaniki 200DMA, informacji przyszłej, kosztów, tej samej świecy i braku transakcji w `tests/unit/test_backtest_mechanics.py`
- [x] T020 [US1] Zaimplementować SRC i rejestrację lokalnego pliku bez wykonywania lub kopiowania treści w `src/astraljet/application/intake.py`
- [x] T021 [US1] Zaimplementować pięć początkowych CAND ze statusem `unassessed`/`needs_input` i powiązaniem do SRC w `src/astraljet/application/intake.py`
- [x] T022 [US1] Zaimplementować STRAT i walidator blokujący niejasną „strukturę trendu”, timing, sizing lub koszt w `src/astraljet/lab/strategy.py`
- [x] T023 [US1] Zaimplementować import DATA CSV z wymaganymi `provider`, `venue`, instrumentami, `timeframe`, `timezone`, zakresem, `available_at_rule`, lokalizatorem, SHA-256, transformacjami, modelem kosztu i wynikiem jakości w `src/astraljet/lab/data_quality.py`
- [x] T024 [US1] Zaimplementować zamrożenie EXP z wersjami STRAT/DATA/kodu, zakresami, wariantami, kryteriami, budżetem, seed, metrykami, tolerance i regułami przerwania w `src/astraljet/application/experiments.py`
- [x] T025 [US1] Zaimplementować deterministyczny silnik RUN oraz pełny zapis transakcji, odrzuconych sygnałów, kosztów, ekspozycji, equity, błędów, metryk i instrukcji odtworzenia w `src/astraljet/lab/backtest.py`
- [x] T026 [US1] Zaimplementować drugi przebieg i porównanie z zamrożoną tolerancją w `src/astraljet/lab/reproduction.py`
- [x] T027 [US1] Dodać komendy `source add`, `candidates seed-2026`, `strategy validate`, `data import`, `experiment freeze` i `run backtest` w `src/astraljet/cli.py`
- [x] T028 [US1] Zbudować test LAB-01–LAB-12 oraz pakiet dowodów dla przypadku BTC/ETH w `tests/integration/test_lab_pipeline.py`

## Phase 4 — User Story 2: Niezależny przegląd i decyzja (P2)

**Cel**: odrębny recenzent wydaje wyłącznie `verified`, `unverified` albo `rejected`, a
nieporównywalne wersje nie trafiają do rankingu.

**Test niezależny**: autor RUN nie może sam potwierdzić wyniku; brak drugiego przebiegu,
kosztu lub zgodności wersji zawsze daje `unverified` lub `rejected`.

- [x] T029 [P] [US2] Napisać testy niezależności recenzenta, werdyktów i `NIEPORÓWNYWALNE` w `tests/contract/test_review.py`
- [x] T030 [P] [US2] Napisać test integracyjny RUN -> REVIEW -> RISK-DECISION w `tests/integration/test_review_flow.py`
- [x] T031 [US2] Zaimplementować REVIEW z `run_ids`, recenzentem różnym od autora, dowodami, brakami, werdyktem i warunkami w `src/astraljet/application/reviews.py`
- [x] T032 [US2] Zaimplementować porównywalność instrumentu, DATA, kosztu, EXP i kodu w `src/astraljet/application/reviews.py`
- [x] T033 [US2] Zaimplementować RISK-DECISION `allowed`/`blocked` z zakresem i ważnością w `src/astraljet/application/mandates.py`
- [x] T034 [US2] Dodać komendy `review create`, `risk decide` i czytelny pakiet dowodów w `src/astraljet/cli.py`

## Phase 5 — User Story 3: Kontrolowana inkubacja bez REAL (P3)

**Cel**: ważny mandat uruchamia PAPER albo DEMO; restart, konflikt wykonawców i stan
niepewny blokują duplikację i nowe ryzyko.

**Test niezależny**: wszystkie próby REAL, brak mandatu, niewłaściwy rachunek DEMO,
konflikt lease, nieświeże dane i retry po `uncertain` zostają zablokowane.

- [x] T035 [P] [US3] Napisać test kontraktowy dozwolonych środowisk i bezwarunkowego odrzucenia REAL w `tests/contract/test_executor_port.py`
- [x] T036 [P] [US3] Napisać testy mandatu, lease, kill switch, świeżości i idempotencji w `tests/unit/test_executor_guard.py`
- [x] T037 [P] [US3] Napisać test integracyjny restartu PAPER i reconciliation DEMO `uncertain` w `tests/integration/test_incubation.py`
- [x] T038 [US3] Zaimplementować MANDATE tylko dla `PAPER_CONTINUOUS`/`BROKER_DEMO`, z konkretną STRAT, kodem, instrumentami, limitami, datami i zatrzymaniem w `src/astraljet/application/mandates.py`
- [x] T039 [US3] Zaimplementować port Wykonawcy oraz stany `accepted`, `rejected`, `uncertain`, `duplicate` w `src/astraljet/executor/ports.py`
- [x] T040 [US3] Zaimplementować fail-closed guard, wyłączny lease, heartbeat i kill switch w `src/astraljet/executor/guard.py`
- [x] T041 [US3] Zaimplementować deterministyczny `PAPER_CONTINUOUS` z ORDER-INTENT i symulowaną realizacją w `src/astraljet/executor/paper.py`
- [x] T042 [US3] Zaimplementować testowy adapter `BROKER_DEMO`, sprawdzenie identyfikatora konta i reconciliation bez sekretów w `src/astraljet/executor/demo.py`
- [x] T043 [US3] Dodać komendy mandatu, PAPER/DEMO, heartbeat, reconcile i kill switch w `src/astraljet/cli.py`

## Phase 6 — User Story 4: Czytelny stan, koszt i ślad decyzji (P4)

**Cel**: użytkownik bez czytania logów widzi obiekt, etap, wynik, bloker, właściciela,
artefakty, koszt i bezpieczny następny krok.

**Test niezależny**: po restarcie cały łańcuch jest widoczny, duplikat nie tworzy kosztu,
a korekta dopisuje nowe zdarzenie.

- [x] T044 [P] [US4] Napisać test kontraktu statusu i błędu JSON z polami `blocker`, `owner` i `allowed_next_action` w `tests/contract/test_status.py`
- [x] T045 [P] [US4] Napisać test integracyjny eksportu łańcucha SRC -> INCU i korekty append-only w `tests/integration/test_audit_export.py`
- [x] T046 [US4] Zaimplementować BUDGET-STATUS z limitem, kosztem rozliczonym, aktywną rezerwacją i kosztem nieuzgodnionym w `src/astraljet/application/status.py`
- [x] T047 [US4] Zaimplementować projekcję statusu z jawnym `unknown` oraz bezpiecznym następnym krokiem w `src/astraljet/application/status.py`
- [x] T048 [US4] Zaimplementować eksport audytowy bez sekretów i treści prywatnych źródeł w `src/astraljet/application/status.py`
- [x] T049 [US4] Dodać komendy `status` i `audit export` oraz kontrakt JSON w `src/astraljet/cli.py`

## Phase 7 — Polish i kontrole przekrojowe

- [x] T050 [P] Uruchomić test wydajności statusu dla 100 000 EVENT w `tests/integration/test_performance.py`
- [x] T051 [P] Dodać test importów potwierdzający, że `src/astraljet/lab/` nie importuje `src/astraljet/executor/` w `tests/contract/test_module_boundaries.py`
- [x] T052 Uruchomić pełne `python -m unittest discover -s tests -v` i zapisać wynik odbioru w `docs/ODBIOR_MVP.md`
- [x] T053 Wykonać scenariusze z `specs/001-build-astra-jet/quickstart.md` i uzupełnić rzeczywiste identyfikatory/wyniki w `docs/ODBIOR_MVP.md`
- [x] T054 Przejrzeć `.gitignore`, `git status --short` i listę plików przed jakimkolwiek `git add`; nie dodawać źródeł, baz, sekretów ani logów

## Zależności

- Phase 1 -> Phase 2 -> US1 -> US2 -> US3; US4 może rozpocząć się po Phase 2 i kończy się
  po udostępnieniu rekordów pozostałych historii.
- T005–T006 są testami przed T011–T013.
- T016–T019 są testami przed T020–T026.
- T029–T030 są testami przed T031–T034.
- T035–T037 są testami przed T038–T043.
- T044–T045 są testami przed T046–T049.
- T052–T054 wymagają wybranego zakresu historii ukończonego i nie tworzą commita.

## Możliwości równoległe

- T003 może powstać równolegle z T001–T002; T004 po rozpoznaniu układu repo.
- W każdej historii testy oznaczone `[P]` dotyczą różnych plików.
- US4 może rozwijać projekcję podstawowych SRC/CAND/EVENT po Phase 2, lecz pełny eksport
  czeka na encje kolejnych historii.
- Po fundamencie formalizacja pozostałych czterech CAND może przebiegać niezależnie, ale
  nie wchodzi do pierwszego RUN i nie może wspólnie zmieniać zamrożonego EXP.

## Strategia wdrożenia

Pierwszy mierzalny przyrost obejmuje T001–T021 oraz minimalny status SRC/CAND. Następnie
domykamy pełną US1 (T022–T028) i zatrzymujemy się na odbiór odtwarzalności. Dopiero po
pozytywnym odbiorze przechodzimy do REVIEW, a następnie PAPER/DEMO. Żaden checkpoint nie
zmienia faktu, że wynik źródłowy i backtest nie są dowodem przyszłego zysku.
