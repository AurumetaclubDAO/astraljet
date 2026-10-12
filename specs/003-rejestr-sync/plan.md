# Implementation Plan: Jednokierunkowa synchronizacja rejestru badań

**Branch**: `003-rejestr-sync` | **Date**: 2026-09-23 | **Spec**: [spec.md](spec.md)

**Input**: Uzgodniony wariant 1 — SQLite rdzenia jest źródłem prawdy, D1 ma tylko owner-scoped odczyt metadanych.

**Note**: This template is filled in by the `$speckit-plan` command; its definition describes the execution workflow.

## Summary

Wprowadzić jawny, podpisany transport metadanych z lokalnego rdzenia do oddzielnego rejestru synchronizacji D1. Lokalne wersje i wydarzenia są właścicielskie; D1 zapisuje atomowe receipty i materializowany widok. Brak scalenia historii oraz brak jakiejkolwiek ścieżki do MT5/DEMO/LIVE.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.12+ (rdzeń); TypeScript/Node w istniejącej witrynie

**Primary Dependencies**: stdlib Python, istniejące CLI/repository SQLite; istniejące route handlers, Zod/Drizzle i D1 binding

**Storage**: lokalne SQLite v7 addytywnie (trwały body outboxa i kursory); D1 z siedmioma osobnymi tabelami synchronizacji; sekret wyłącznie poza bazami i repo

**Testing**: unittest Python; testy Node/in-memory D1 kontraktu, API i renderowania

**Target Platform**: Windows lokalnego rdzenia; istniejąca prywatna witryna/Worker

**Project Type**: dwa istniejące projekty: CLI/rdzeń oraz web application; bez migracji runtime

**Performance Goals**: batch metadanych do 5000 rekordów; status odczytowy ograniczony i bez payloadów; retry bez duplikatu

**Constraints**: strict allowlist; limit body; clock window ±300 s; nonce/replay protection; batch jest atomowy; nie wysyła sekretów ani pełnej SQLite

**Scale/Scope**: jedna instalacja lokalna i owner-scoped v1; historyczne D1/SQLite bez automatycznego mapowania

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Uzasadnienie |
|---|---|---|
| I Risk Management | PASS | Brak sygnałów, sizingu i zleceń. |
| II Uczciwe wyniki | PASS | D1 pokazuje raportowane metadane, nie potwierdzoną przewagę. |
| III Rozdzielenie DEMO/LIVE | PASS | Kontrakt wymaga `execution_authorized=false`; endpoint nie zna rachunków. |
| IV Powtarzalność | PASS | Wersje, hash, cursor, receipt i append-only audit. |
| V Niezależna weryfikacja | PASS | Nie promuje wyniku ani nie zmienia jego werdyktu. |
| VI Bezpieczne wykonanie | PASS | Brak wywołania workera wykonawczego/MT5; retry jest idempotentne. |
| VII Koszty | PASS | Nie dotyka kosztów AI ani brokerskich. |

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── contracts/           # Phase 1 output ($speckit-plan command)
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
D:\Astra Jet/
├── src/astraljet/application/registry_sync.py
├── src/astraljet/infrastructure/{migrations,repositories}.py
├── src/astraljet/cli.py
└── tests/{unit,integration}/test_registry_sync*.py

D:\Astra Jet\.runtime\command-center-release-20260920/
├── app/api/astra/registry-sync/route.ts
├── app/command/data/…
├── db/{schema.ts,migrations/}
├── lib/{astra-device,registry-sync}.ts
└── tests/registry-sync-*.test.mjs
```

**Structure Decision**: Rdzeń w katalogu głównym oraz istniejący checkout wydawniczy Sites. Brudny roboczy `C:\Users\karol\Documents\Claude\Projects\Trading\astra_site` pozostaje nietknięty; nie przenosimy aktywnych procesów ani baz runtime. Kod wydania opiera się na wersji 56 i zachowuje jej historię. Publikacja prywatnego API nie jest aktywacją wykonawcy.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
