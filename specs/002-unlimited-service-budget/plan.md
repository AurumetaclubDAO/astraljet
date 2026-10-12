# Implementation Plan: Wydatki AI i X bez stałego pułapu

**Branch**: codex/unlimited-service-budget, od istniejącego commita 50d8ee144bb47aa4f19a0675f87f5a4a086d176f
**Date**: 2026-09-20 | **Spec**: [spec.md](spec.md)

## Summary

Jawna polityka unlimited w istniejącym backendzie i widokach kosztów. Usuwamy pułapy,
nie księgowanie i ograniczenia techniczne dostawcy. Bez migracji baz, restartu Windows,
nowego harmonogramu i wysyłania zleceń.

## Technical Context

- Language/Version: TypeScript, Node >=22.13; zastany React/Vinext.
- Dependencies: istniejące; bez nowych pakietów.
- Storage: D1/SQLite, astra_ai_calls i astra_x_calls, bez migracji schematu.
- Testing: node:test + node:sqlite, transporty testowe; tsc/build i prywatny podgląd.
- Platform: istniejąca witryna Sites, właściciel jako jedyny odbiorca.
- Performance: bez dodatkowych sieciowych kontroli w rozliczeniu.
- Constraints: selektywny commit, zachowanie niezwiązanych zmian, bez sekretów w paczce.
- Scope: dwie usługi płatne; nie sizing ani zlecenia MT5.

## Constitution Check

I/III/VI: brak zmian mandatów, sizingu i rachunków. II/IV/V: brak deklaracji rentowności,
niezmienione eksperymenty, kontrolne sumowanie SQLite. VII: jawny brak pułapu, zachowana
historia i niepewność, bez obchodzenia dostawcy.
Zgodność sprawdzona przed i po projekcie. Pełna migracja Astry do 2.0.0 to osobne zadania.

## Project Structure

Dokumenty w D:/Astra Jet/specs/002-unlimited-service-budget.
Kod nadal w C:/Users/karol/Documents/Claude/Projects/Trading/astra_site:

- lib/spending-policy.ts, ai-ledger.ts, ai-policy.ts
- lib/research/x-ledger.ts, x-policy.ts
- app/ai-settlement.tsx, astra-chat.tsx, platform-home.tsx, research/*
- lib/office-operations.ts, app/command/command-center.tsx, app/api/research/x/route.ts
- tests/*

Implementacja w czystym, istniejącym checkout wydania:
`D:/Astra Jet/.runtime/command-center-release-20260920`.
Nie publikować zastanych zmian pochodzenia z dirty worktree na C. To izolacja prac,
nie migracja kodu/baz/procesów; główny checkout i jego zmiany pozostają nietknięte.

## Rollout i wycofanie

Czerwone testy → kod → pełne testy/tsc/build → selektywny commit → czyste wydanie →
prywatna publikacja → odczyt budżetu/UI bez płatnych wywołań.
Nie wznawiać hurtowo blocked ani nie kasować niepewnych kosztów.
Rollback: poprzednia zapisana wersja, bez cofania rozliczeń w bazie.

## Complexity Tracking

Brak nowej bazy/uprawnień. Kontrakt nullable wymaga atomowej publikacji backendu i UI.
