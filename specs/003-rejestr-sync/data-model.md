# Model danych — 003-rejestr-sync

| Encja | Klucz / pola | Reguły |
|---|---|---|
| Installation | `installation_id`, czas utworzenia | Trwała tożsamość lokalna. Urządzenie ma osobny token z zakresem `registry:sync`; D1 zapisuje hash tokenu. Klucz HMAC jest poza bazą. |
| Sync batch | `installation_id`, `registry_id`, `batch_id`, `sequence`, zamrożony `body_json`, `body_hash`, cursor, status, próby, dzierżawa, ACK | Body metadanych i cel są niezmienne; ten sam batch jest idempotentny. Starsza sekwencja nie cofa widoku. |
| Sync item | owner, `registry_id`, kind, record ID, version, content hash, statusy, czasy | Insert-only dla wersji; brak nadpisywania; tylko allowlista pól. |
| Sync edge | owner, batch, ordinal, dziecko i rodzic z wersją, relation, resolution | Obserwacja w konkretnej paczce. Nie tworzy relacji przez podobną nazwę; nieokreślona wersja zachowuje status niejednoznaczny. |
| Snapshot members | owner, batch, registry, record ID, version | Kopia widoku zawiera tylko elementy danej paczki, a nie sumę historycznych rekordów. |
| Nonce | owner, key ID, nonce, expiry | Użycie zapisywane atomowo razem z paczką; ponowienie użytego nonce odrzucane. |
| Receipt/event | request ID, batch, czas serwera, wynik, liczniki, error code | Brak body, podpisu, tokenu i sekretu; audyt append-only. |

Stany batcha: `pending` → `sending` → `acknowledged` albo `retryable_failure` / `conflict` / `rejected`. Tylko `acknowledged` przesuwa lokalny cursor. `conflict` i `rejected` wymagają jawnego działania operatora; nie mają automatycznego fallbacku.

Publikowany model Drizzle, snapshot schematu 0008 i SQL opisują siedem osobnych tabel. Lokalny schemat 7 rozszerza outbox z wersji 6, bez zmiany rekordów badań.
