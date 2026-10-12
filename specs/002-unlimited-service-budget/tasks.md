# Tasks: Wydatki AI i X bez stałego pułapu

**Input**: spec.md, plan.md, research.md, data-model.md, contracts/spending.md.
**Tests**: wymagane przed implementacją (FR-009).
Ścieżki kodu względem repo astra_site; izolowany checkout wydania na dysku D,
bez zmiany istniejącego dirty worktree i jego procesów.

## Phase 1: Setup

- [x] T001 Zweryfikować prywatny projekt i czysty checkout na podstawie .openai/hosting.json; zachować zmiany użytkownika (FR-008).

## Phase 2: Foundational

- [x] T002 Dodać czerwone testy kontraktu w tests/spending-policy.test.mjs (FR-001, FR-009).
- [x] T003 W lib/spending-policy.ts dodać spendingMode=unlimited oraz limit/remaining=null; kwoty „nieujemne bezpieczne całkowite micro-USD” (FR-001).

## Phase 3: US1 — AI (P1)

Cel: brak pułapu, poprawne księgowanie. Test niezależny: AI transport testowy powyżej 25 USD.

- [x] T004 [US1] Zmienić oczekiwania i dodać czerwone testy w tests/discovery.test.mjs oraz tests/ai-settlement.test.mjs (FR-002–006, FR-009).
- [x] T005 [US1] Zmienić lib/ai-ledger.ts i lib/ai-policy.ts: usunąć progi kwotowe, settled ponad rezerwację, legacy overrun nie blokuje, dowody nadal wymagane (FR-002–006).

## Phase 4: US2 — X (P2)

Cel: brak pułapu X. Test niezależny: równoległe partie ponad 5 USD oraz powtórzenie id.

- [x] T006 [US2] Dodać czerwone testy powyżej limitu i niepewnych partii w tests/x-research.test.mjs (FR-002, FR-004–006, FR-009).
- [x] T007 [US2] Zmienić lib/research/x-ledger.ts i x-policy.ts bez utraty unikalności id i błędów dostawcy; poprawić app/api/research/x/route.ts (FR-002, FR-004–006).

## Phase 5: US3 — Widoki (P2)

Cel: prawdziwa informacja. Test niezależny: rendering kosztu, statusy ról i kontrakt null.

- [x] T008 [US3] Dodać/zmienić testy w tests/spending-policy.test.mjs i tests/office-operations.test.mjs (FR-007, FR-009).
- [x] T009 [US3] Podłączyć politykę do app/astra-chat.tsx, app/ai-settlement.tsx, app/platform-home.tsx, app/research/discovery-desk.tsx, app/research/x-desk.tsx oraz lib/office-operations.ts i app/command/command-center.tsx (FR-007).

## Phase 6: Polish

- [x] T010 Pełne tests/*.test.mjs, tsc, build i instrukcja research/discovery/README.md; zachować błędy dostawców i granice transportu (FR-006, FR-009).
- [x] T011 Selektywny commit i prywatna publikacja z .openai/hosting.json; odczyt UI bez płatnych testów (FR-008, SC-003–004).
- [x] T012 Zapisać dowody i pozostałe prace w D:/Astra Jet/docs/operations/ETAP_10_2026-09-20.md oraz START_ASTRALJET.md (SC-001–004).

## Dependencies & Execution Order

T001 → T002 → T003. Dla US1 T004 → T005; US2 T006 → T007; US3 T008 → T009.
T009 wymaga kontraktów obu usług; T010–T012 po historiach. Testy każdej historii
można wykonywać równolegle na osobnych bazach pamięciowych; pliki ledger i UI kolejno.

## Implementation Strategy

MVP: US1 (AI), potem X, następnie spójny UI. Jedna publikacja backendu i UI.
Nie zmieniać harmonogramów, historycznych blocked ani ustawień rachunków.
