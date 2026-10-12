# ADR-002 — podgląd pochodzenia bez migracji i wysyłania lokalnego rejestru

Status: zaimplementowano lokalny kod, bez wdrożenia na witrynę.

## Kontekst

Obecna Astra korzysta z D1, a nowy lokalny rdzeń z kilku rejestrów SQLite. Nie ma uzgodnionej relokacji runtime ani wspólnego autorytatywnego rejestru. D1 zapisuje bieżące dokumenty z rewizjami; relacje `materialId/candidateId` nie zamrażają rewizji. Wyniki eksperymentów są osadzone w ich payloadach. Nie wolno przedstawiać ich automatycznie jako zgodnych rekordów STRAT/EXP/RUN z lokalnego rdzenia.

## Rozwiązanie w tym etapie

- Rozwijamy istniejący frontend w `C:\Users\karol\Documents\Claude\Projects\Trading\astra_site`. Nie kopiujemy go do nowego katalogu ani nie tworzymy drugiej witryny.
- Nowa strona `/research/lineage` używa istniejącego uwierzytelniania i wspólnych komponentów. Odczyt D1 jest właścicielski, bez zapisów, cache, pobierania treści R2 i uruchamiania AI/workerów.
- Python eksportuje allowlistę metadanych wybranej SQLite do nowego pliku. Przeglądarka odczytuje go lokalnie; brak synchronizacji w tle, portu lokalnego API i transferu do chmury.
- Węzły D1 zachowują swoje nazwy i rewizje od 0. Lokalne węzły zachowują typy i wersje od 1. Przestrzenie ID pozostają odrębne; podobne nazwy/ID nie łączą rekordów.
- `execution_authorized=false` jest stałym wymogiem kontraktu. Żaden fragment tego widoku nie jest wejściem do workflow ani wykonawcy.
- Braki, niejednoznaczności, ograniczony zakres, wiek snapshotu i nieuwierzytelnione pochodzenie pliku są widoczne.

## Ograniczenia

To dodatek odczytowy, nie integracja runtime ani spełnienie pełnego kryterium odbioru. Metadane nie weryfikują treści źródeł, wyników, mandatu, rachunku ani prawdziwości lokalnego pliku. Hash nie jest podpisem. Uprawnienia API dziedziczą istniejącą granicę zaufania uwierzytelniania Sites; nie dodano nowego serwera dostępnego z internetu. Nie zmieniono reguł, budżetu ani aktywnego DEMO.

## Odwracalność

Usunięcie dodatku kodu usuwa tylko widok i komendę eksportu. Nie potrzeba migracji wstecznej: bazy, archiwa D1, dane i procesy pozostały bez zmian. Eksporty są lokalnymi plikami w ignorowanym `.runtime/exports` i nie są automatycznie dodawane do Git.
