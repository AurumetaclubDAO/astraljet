# Research — 003-rejestr-sync

## Decision: jednokierunkowy endpoint rejestru

Lokalny klient przekazuje metadane wyłącznie do `POST /api/astra/registry-sync` w istniejącej aplikacji. D1 jest odczytową kopią materializowaną; nie ma API D1 na komputerze lokalnym i nie odsyła rekordów do SQLite.

**Rationale:** binding D1 zostaje po stronie Workera, a oddzielna trasa eliminuje drogę do `astra_jobs`, MT5 i brokera. Istniejący `astra_discovery` ma inną semantykę, więc nie jest bezpiecznym sinkiem rekordów SRC/CAND/STRAT/DATA/EXP/RUN.

**Alternatives considered:** pełna migracja SQLite do D1 (poza zakresem i ryzykowna); dwukierunkowa synchronizacja (konflikty); import snapshotu w przeglądarce (brak trwałego wglądu).

## Decision: osobny namespace i tabele D1

Wprowadzić owner-scoped `astra_registry_sync_batches`, `astra_registry_sync_items`, `astra_registry_sync_edges` i append-only `astra_registry_sync_events`. Unikalna tożsamość elementu to `user_id + registry_id + kind + record_id + version`; hash jest dodatkową kontrolą niezmienności.

**Rationale:** lokalny rdzeń ma append-only wersje, a D1 nie może zmieniać lokalnej historii. Nie ma automatycznego mapowania rekordów historycznych.

## Decision: device token o minimalnym scope

Endpoint przyjmuje urządzenie z nowym scope `registry:sync`; nie używa `research:worker` ani sesji przeglądarki. Token jest przechowywany lokalnie poza Git i eksportami.

**Rationale:** `research:worker` może obsługiwać kolejkę; scope synchronizacji ma uprawnienie wyłącznie do metadanych rejestru. Token wyznacza właściciela po stronie serwera, nigdy request body.

## Decision: idempotencja, replay i konflikty

Każdy batch ma stabilny UUID i hash kanonicznego body. Serwer zapisuje receipt atomowo z elementami. Identyczny batch/hash zwraca pierwotne potwierdzenie; ten sam batch z innym hashem oraz ta sama tożsamość elementu z innym hashem dają konflikt bez nadpisania. Klient utrzymuje lokalny outbox i ponawia ten sam batch po błędzie sieci.

**Rationale:** timeout nie może doprowadzić do duplikatów ani cichej utraty widoczności. Jeden wadliwy element odrzuca cały batch, aby nie tworzyć częściowej prawdy.

## Decision: podpisany transport

Wersja produkcyjna użyje odrębnego klucza instalacji i HMAC-SHA-256 nad surowym body oraz metodą, ścieżką, czasem i nonce. Serwer odrzuci niepoprawny podpis, nonce ponowiony w oknie ochronnym i zegar poza ±300 sekund. HMAC porównuje w czasie stałym. Lokalne testy dostaną atrapę podpisu; klucz produkcyjny jest Cloudflare Secret i lokalnym sekretem, nigdy plikiem repo.

**Rationale:** bearer device token sam nie wiąże requestu z treścią ani nie chroni przed replay. Docelowo klucz można zastąpić Ed25519 bez zmiany batch semantics.

## Decision: zakres danych i obserwowalność

Kontrakt dopuszcza wyłącznie metadane wersjonowanych rekordów i relacji. Nie przyjmuje payloadów, ścieżek, baz, sekretów, kont, danych brokera ani autoryzacji wykonania. Command Center pokazuje źródło, ostatni receipt i świeżość przez osobny GET odczytowy.

**Rationale:** obecny snapshot jest wzorem allowlisty, ale nie jest kontraktem transportu. Wgląd nie może stać się kanałem wykonawczym.

## Sources

- Lokalny read model i snapshot: `src/astraljet/application/read_model.py`; ochrony wersji: `src/astraljet/infrastructure/migrations.py`.
- Dotychczasowa granica: `docs/decisions/ADR-002-lokalny-podglad-snapshotow.md`.
- Istniejące wzorce witryny: `C:/Users/karol/Documents/Claude/Projects/Trading/astra_site/app/api/mt5/telemetry/route.ts`, `lib/astra-device.ts`, `db/schema.ts`.
- Cloudflare: [D1 Worker API](https://developers.cloudflare.com/d1/worker-api/d1-database/), [Secrets](https://developers.cloudflare.com/workers/configuration/secrets/), [Web Crypto](https://developers.cloudflare.com/workers/runtime-apis/web-crypto/), [Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/).
