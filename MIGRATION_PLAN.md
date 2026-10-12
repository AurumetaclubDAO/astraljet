# Plan połączenia istniejącej Astry — bez uruchomionej migracji

Podstawa: [inwentarz bieżący](CURRENT_ASTRA_INVENTORY.md). Decyzja o głównym katalogu pozostaje w mocy; nie jest automatyczną zgodą na relokację działających procesów i rachunków.

## Etap wykonany lokalnie

Dodano odczyt `system inspect`, `strategy list`, `strategy lineage`, ochronę rekordów/zdarzeń w schemacie 5 oraz nienadpisywalne nowe snapshoty Alpaca. Stare bazy pozostały w schematach 1/3/4. Nie przeniesiono frontendu, D1, R2, kolejek, plików urządzeń ani wykonawcy.

Etap 02 dodaje kod widoku `/research/lineage` w dotychczasowym frontendzie, GET metadanych D1 oraz `system snapshot` w Pythonie. Lokalny plik jest ręcznie wczytywany do pamięci strony; nie jest transportem do chmury. Źródła zachowują oddzielne przestrzenie ID. Nie opublikowano widoku i nie wprowadzono wspólnego rejestru ani mapowania tożsamości D1/local. Szczegóły: `docs/operations/ETAP_02_2026-09-19.md`.

Etap 03 dodaje w istniejącym frontendzie przypinanie rewizji źródeł i sprawdzonych reguł dla nowych eksperymentów, niezmienność zamrożonego planu oraz kontrolę archiwów przy pobieraniu zadań i zapisie wyników workera badawczego. Wykorzystuje istniejącą tabelę D1 i jej rekordy `revision`; nie wykonano migracji danych ani publikacji kodu. Nie przypisuje danych Alpaca do STRAT/EXP. Stare eksperymenty pozostają legacy. Szczegóły: [raport etapu 03](docs/operations/ETAP_03_2026-09-20.md) i [ADR-003](docs/decisions/ADR-003-przypinanie-pochodzenia.md).

## Kolejność dalszej pracy

1. **Historia Git.** Po przywróceniu dostępu pobrać istniejące `main` do referencji, bez checkout/reset na nieśledzonych plikach. Porównać README, `.gitignore` oraz listę kolizji. Zachować historię Sites i docelowego GitHub; sposób scalenia opisać przed zmianą. Nie stosować zdalnej reguły `lib/` bez sprawdzenia TypeScript. Żadnego force push i konkurencyjnego pierwszego commita.
2. **Mapowanie modelu, bez zapisów.** Zestawić D1 `astra_discovery/astra_jobs/research_runs` z SRC/CAND/STRAT/DATA/EXP/RUN. Zachować `user_id`, identyfikator urządzenia, jawny namespace systemu źródłowego, wersję/revision, czas obserwacji i hash. Ten sam tekst nazwy strategii nie jest dowodem tożsamości. Nie wybierać `latest` dla historycznego wyniku.
3. **Rozstrzygnąć granicę stanu.** Zaproponować jeden autorytatywny rejestr nowych eksperymentów oraz adapter odczytu starej Astry. Wybór miejsca runtime/bazy i fizycznych ścieżek AppData uzgodnić z Karolem. Zachować stare rejestry jako oddzielne źródła; bez automatycznego merge.
4. **Backup i próba odtworzenia.** Ustalić dokładne aktywne bazy, WAL/SHM, wersje schematów i procesy. Snapshot przez SQLite backup / wspierany eksport D1 oraz manifest obiektów R2. Przećwiczyć odtworzenie w nowym izolowanym katalogu. Nie kopiować otwartego pliku `.sqlite3` bez WAL i nie mieszać kopii testowej z produkcyjną.
5. **Wspólny panel tylko do odczytu.** Rozszerzyć istniejący frontend, bez drugiego dashboardu. Wprowadzić API/query adapter z izolacją właściciela, świeżością, rozróżnieniem źródeł i wersji. Local SQLite nie jest dostępne dla chmury bez jawnego transportu; nie otwierać portów i nie wysyłać pełnych baz/sekretów.
6. **Domena i workflow.** Pełna maszyna stanów, oddzielne BACKTEST/OOS/FORWARD/DEMO, role AJ-00–AJ-18 jako rejestr logiczny. Zatwierdzenia przejść muszą pochodzić z uwierzytelnionej decyzji, nie pola tekstowego `authorized_by`. Krytyk, ryzyko i aktualny mandat mają realnie blokować proces.
7. **Badanie jednej strategii.** Zamknąć braki reguł/kosztów, zapisać zatwierdzone STRAT i EXP, przypisać konkretny DATA snapshot, wykonać testy/OOS/odtworzenie i niezależny przegląd. Dotychczasowy szkic BTC/ETH nie zostaje zatwierdzony przez ten plan.
8. **Dopiero oddzielna inkubacja i DEMO.** Po decyzjach Karola: adapter odczytu MT5 oddzielony od executor, twarde limity, replay/idempotency, lease, stale-data, reconciliation, kill switch per system/strategia/broker/symbol. Zastanego aktywnego DEMO nie przepinać do nowego kodu automatycznie.

## Rollback

- Do etapu transportu integracja jest dodatkiem kodu. Stary frontend i procesy działają w swoich miejscach.
- Nowe odczyty nie inicjalizują ani nie migrują baz. Można wrócić do wcześniejszego CLI bez zmiany danych.
- Schemat 5 jest addytywny; zachowuje rekordy i pozwala dopisywać wersje. Nie usuwać triggerów w celu „naprawienia” kodu nadpisującego historię. Dla rzeczywistej migracji rollback wymaga wcześniej sprawdzonego snapshotu; odtworzenie nigdy nie może utracić zdarzeń/zleceń powstałych później.
- Nowy snapshot Alpaca ma nową nazwę i sidecar metadanych; stare pliki pozostają bez zmian. Nieudane pobranie nie daje zgody na usunięcie wcześniejszej wersji.
- Produkcyjna publikacja, nowy transport danych, koszty usług, zmiana runtime i uruchomienie/zmiana DEMO wymagają konkretnego uzgodnionego zakresu.
- Po przyszłej publikacji etapu 03 powrót do starego API nie będzie bezpiecznym odpowiednikiem usunięcia widoku: stare API nie zna kontroli nowych przypiętych eksperymentów. Zachować archiwa i nową walidację albo wstrzymać ich obsługę; nie usuwać pinów w celu obejścia błędu. Przed publikacją przygotować oddzielny plan wdrożenia i odtworzenia.

## Warunek połączenia

Jedna przykładowa strategia widoczna w istniejącej witrynie musi prowadzić do dokładnych źródeł, wersji reguł, danych, EXP, wyników, przeglądów i decyzji. Błędy/niejednoznaczności są widoczne. Brak dowodów nie daje zielonego statusu. Następnie test odbiorowy z briefu 1–18, z rzeczywistymi decyzjami Karola i osobnym dowodem DEMO, nie syntetycznym raportem.
