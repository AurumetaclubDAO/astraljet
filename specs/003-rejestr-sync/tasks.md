# Tasks: Jednokierunkowa synchronizacja rejestru badań

## Phase 1: Setup

- [X] T001 Potwierdź kontrakt allowlisty i limity w `specs/003-rejestr-sync/contracts/registry-sync-v1.md`

## Phase 2: Foundational

- [X] T002 Dodaj addytywną migrację lokalnego outboxa i tożsamości instalacji w `src/astraljet/infrastructure/migrations.py`
- [X] T003 Dodaj migrację D1 osobnych tabel receipt/item/edge/event w `D:/Astra Jet/.runtime/command-center-release-20260920/drizzle/`
- [X] T004 Dodaj scope urządzenia `registry:sync` oraz wspólną walidację transportu w `D:/Astra Jet/.runtime/command-center-release-20260920/lib/astra-device.ts` i `lib/registry-sync.ts`

## Phase 3: User Story 1 - Aktualny wgląd (P1)

**Independent Test**: rekord lokalny po poprawnym ACK jest widoczny właścicielowi z wersją, hashem, źródłem i świeżością.

- [X] T005 [US1] Napisz testy outboxa, batcha i retry w `tests/integration/test_registry_sync.py`
- [X] T006 [US1] Zaimplementuj budowę batcha, podpis i obsługę ACK w `src/astraljet/application/registry_sync.py`
- [X] T007 [US1] Dodaj komendę `registry sync-push` w `src/astraljet/cli.py`
- [X] T008 [US1] Napisz testy API oraz owner-scoped statusu w `D:/Astra Jet/.runtime/command-center-release-20260920/tests/registry-sync-api.test.mjs`
- [X] T009 [US1] Zaimplementuj POST/GET rejestru synchronizacji w `D:/Astra Jet/.runtime/command-center-release-20260920/app/api/astra/registry-sync/route.ts`
- [X] T010 [US1] Dodaj odczyt statusu i kartę Command Center w `D:/Astra Jet/.runtime/command-center-release-20260920/lib/registry-sync.ts` oraz `app/command/command-center.tsx`

## Phase 4: User Story 2 - Konflikty (P2)

- [X] T011 [US2] Dodaj testy konfliktu hash/revision i atomowości w `tests/integration/test_registry_sync.py` oraz `D:/Astra Jet/.runtime/command-center-release-20260920/tests/registry-sync-api.test.mjs`
- [X] T012 [US2] Zablokuj nadpisywanie, częściowy ACK i błędne replaye w `src/astraljet/application/registry_sync.py` oraz `app/api/astra/registry-sync/route.ts`

## Phase 5: User Story 3 - Granica wykonania (P3)

- [X] T013 [US3] Dodaj testy odrzucania sekretów/payloadów/authorizations i braku wywołań wykonawcy w `tests/integration/test_registry_sync.py` oraz `D:/Astra Jet/.runtime/command-center-release-20260920/tests/registry-sync-api.test.mjs`
- [X] T014 [US3] Wymuś `execution_authorized=false`, limity body i bezpieczne błędy w obu kontraktach synchronizacji

## Phase 6: Validation

- [X] T015 Uruchom testy rdzenia i witryny oraz zaktualizuj dowody w `docs/operations/ETAP_13_2026-09-24.md`

## Dependencies

T001 → T002–T004 → T005–T010 → T011–T014 → T015. Publikacja zatwierdzonego prywatnego Command Center nie aktywuje środowiska wykonawczego. MT5/DEMO/LIVE bez zmian.

## Odbiór produkcyjny (nie zastępuje testów implementacji)

- [X] P001 Potwierdzić siedem tabel synchronizacji w produkcyjnym D1 po publikacji.
- [X] P002 Sparować jedno urządzenie `registry:sync` po potwierdzeniu uprawnienia przez Karola; nie ujawniać sekretu.
- [X] P003 Wykonać spójny backup wybranej lokalnej SQLite i sprawdzić zachowanie historii po migracji outboxa.
- [X] P004 Przesłać rzeczywiste metadane, odebrać zweryfikowany ACK i odczytać je w zalogowanym panelu.

T001–T015 oznaczają zakończoną implementację oraz testy lokalne. Nie są deklaracją aktywnej synchronizacji produkcyjnej ani ukończenia AJ-00–AJ-18.

P001–P004 odebrano 24.09.2026: wersja 58, siedem tabel, ACK paczki `131214ef-3f8a-4368-93e4-26510418c78c`, siedem wersji i sześć relacji widocznych w zalogowanym panelu. Dowody: `docs/operations/ETAP_13_2026-09-24.md`. Uruchomiono pojedynczą synchronizację na żądanie, nie harmonogram ani ciągły proces.
