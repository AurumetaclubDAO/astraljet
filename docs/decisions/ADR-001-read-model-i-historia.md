# ADR-001 — odczyt istniejącego stanu i ochrona historii

Data: 19.09.2026. Status: wdrożono lokalny kod; bez relokacji runtime, bez migracji zastanych baz.

## Context

Witryna ASTRA Pro i lokalny rdzeń używają różnych magazynów. W trzech lokalnych bazach źródła/STRAT oraz DATA znajdują się osobno. Dawny `status` wybierał najbardziej zaawansowany typ rekordu niezależnie od jego relacji i inicjalizował bazę. To nie jest dowód kompletnego workflow. Tabela records dopuszczała modyfikację, a SQL REPLACE mógł obejść ochronę events.

## Decision

Rozszerzyć istniejący rdzeń o read model w jednej transakcji SQLite `mode=ro`, `query_only=ON`, bez auto-migracji. Eksportować do przyszłego panelu tylko metadane z jawnej listy pól. Budować graf przez rzeczywiste referencje, a nie kolejność typów, nazwy ani wspólne DATA. Brak zapisanej wersji pozostaje `unversioned_single/ambiguous`, nie `exact`.

Dodać schemat 5: ochronę records przed UPDATE/DELETE/REPLACE oraz events przed REPLACE/kolizją klucza. Pozostawić dopisywanie nowych wersji i stare API repozytorium. Zabezpieczenie przed administratorem systemu plików nie jest celem triggerów.

Snapshoty Alpaca publikować z nową nazwą. Zamiast `os.replace` zastosować atomowe utworzenie nazwy przez hard link kompletnego pliku tymczasowego na tym samym systemie plików. Brak obsługi hard link oznacza jawny błąd, bez niebezpiecznego fallbacku. Brak pól opcjonalnych jest pustym polem, nie sztucznym pomiarem. Format metadanych nowych plików: v2.

## Alternatives

- Przepisanie frontendu/backendu i scalenie baz: odrzucone; powieliłoby działającą Astrę i wymaga migracji.
- REST serwer/otwarcie portu już teraz: odłożone do ustalenia uwierzytelnionego transportu do istniejącej witryny.
- Domyślne przypisanie najnowszych rodziców: odrzucone; zmienia znaczenie historycznych dowodów.
- Tylko sprawdzenie istnienia pliku przed zapisem: niewystarczające przy konkurencyjnym zapisie.

## Consequences

Nowe polecenia CLI dają kontrakt pod integrację, ale nie są działającym połączeniem D1/MT5. Czytelny graf nie upoważnia do transakcji. Stare dane zachowują swoje luki. CSV i sidecar są dwoma plikami, nie transakcją wieloplikową: awaria po publikacji CSV może pozostawić plik bez metadanych. Nie ma wtedy kompletnego snapshotu; wybieramy nową nazwę i zachowujemy ślad awarii.

## Rollback

Wycofanie dodatków CLI nie wymaga zmian rekordów. Migracja jest testowana na izolowanej bazie v4; nie uruchomiono jej na starym runtime. Dla późniejszej migracji wymagany sprawdzony backup. Nie usuwać ochrony historii w aktywnym systemie jako automatycznego rollbacku.
