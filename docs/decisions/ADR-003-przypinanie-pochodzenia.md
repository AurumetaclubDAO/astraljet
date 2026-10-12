# ADR-003 — przypięte pochodzenie nowych eksperymentów Discovery

Data: 20.09.2026. Status: zaimplementowano i przetestowano lokalnie, bez publikacji i migracji danych.

## Kontekst

Dotychczasowe `materialId` i `candidateId` wskazywały dokument, ale nie gwarantowały użycia tej samej rewizji po jego zmianie. Archiwa `id:vN` już istnieją w `astra_discovery` jako `kind=revision`. Rozwijamy ten model bez tworzenia drugiej bazy i bez łączenia go z lokalnymi STRAT/DATA/EXP.

## Decyzja

- Przegląd wymaga oczekiwanej rewizji kandydata. Sprawdza cytaty względem konkretnego źródła, archiwizuje źródło i poprzednią kartę, następnie zapisuje w przeglądzie pin źródła oraz hash reguł.
- Zamrożenie wymaga tej samej sprawdzonej rewizji, niezmienionych reguł i poprawnego archiwum źródła. Archiwizuje sprawdzonego kandydata i tworzy eksperyment z pinami `id/revision/hash`, regułami, planem i protokołem. Nigdy nie wybiera `latest` zamiast brakującego archiwum.
- Nowe ID `exp-pin-v1-<hash>` wynika z pinów i hashy reguł/planu. Identyczny retry lub równoległe żądanie używa jednego eksperymentu. Prefiks pozwala wykryć usunięcie całego pola `provenance`; taki rekord nie może cicho stać się legacy.
- Hashe pełnych przypiętych rekordów używają stabilnego porządku kluczy JSON. Dotychczasowe kodowanie `specHash` i `planHash` pozostaje zgodne z workerem. Wszystkie odczyty i zapisy ograniczono do właściciela.
- Kontrola archiwów obowiązuje na ścieżkach pobrania zadania i przyjęcia wyniku workera badawczego, zwolnienia holdoutu i zatwierdzenia propozycji DEMO. Odrzucenie lub dalsze badanie nie wymaga nadawania uszkodzonemu rekordowi poprawnego statusu.
- Ogólny zapis nie może podmienić źródeł, reguł, planu, hashy, protokołu ani czasu zamrożenia nowego eksperymentu. Wyniki i decyzje można dopisywać według dotychczasowego workflow.

## Transakcje i konflikty

Przegląd oraz zamrożenie mają osobne transakcje `D1.batch`. Każdy zapis powtarza warunki zgodności odczytanych rekordów i istniejących archiwów. Konflikt powoduje brak zmian, a błąd instrukcji wycofanie całej transakcji. Nie nadpisujemy kolidującego archiwum. Założenie o atomowości błędnego batcha wynika z [dokumentacji Cloudflare D1](https://developers.cloudflare.com/d1/worker-api/d1-database/#batch); zachowanie SQL zweryfikowano lokalnie na SQLite, nie na produkcyjnym D1.

Utworzenie eksperymentu i zakolejkowanie badania **nie są jedną transakcją**. Zachowano dotychczasową deduplikację kolejki i możliwość ponowienia po błędzie. Nie dodano nowej gwarancji exactly-once dla całego workera.

## Legacy i ograniczenia

Stare przeglądy trzeba ponownie sprawdzić przed utworzeniem nowego przypiętego eksperymentu. Stare eksperymenty pozostają legacy i nie otrzymują automatycznie nowych dowodów. Widok Pochodzenie prezentuje pin jako deklarację konkretnej rewizji, ale nie pobiera jej archiwum; nie nazywa jej zweryfikowaną relacją `exact`.

Nie dodano triggerów do D1. Kod aplikacyjny wykrywa niespójność, lecz hash nie uwierzytelnia autora ani nie zabezpiecza przed uprzywilejowanym napastnikiem przepisującym całą bazę. Przypięty materiał to dokument źródłowy, nie nowy, zweryfikowany zbiór danych rynkowych. Ten etap nie rozstrzyga jakości strategii, kosztów, decyzji inwestycyjnych i mandatów wykonania.

## Wdrożenie i odwracalność

Brak publikacji, zmian schematu, produkcyjnych zapisów i zmian procesu MT5. Przyszła publikacja obejmuje frontend i API razem. Przy późniejszym wycofaniu nie wolno usuwać pinów/archiwów ani obsługiwać nowych rekordów przez stare API bez tych kontroli. Plan odtworzenia i próba na izolowanych danych należą do osobnego zakresu wdrożenia.
