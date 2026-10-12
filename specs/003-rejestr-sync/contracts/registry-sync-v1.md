# Kontrakt: Registry Sync v1

## Endpoint

`POST /api/astra/registry-sync` — wyłącznie zapis metadanych przez urządzenie `registry:sync`. `GET /api/astra/registry-sync` — status odczytowy w sesji właściciela, bez body batchy. Parametr `?registry=local:ETYKIETA` zwraca najnowszą kopię pochodzenia tego rejestru (według sekwencji źródła).

## Request

Nagłówki: `Authorization: Bearer …`, `X-AJ-Key-Id`, `X-AJ-Timestamp`, `X-AJ-Nonce`, `X-AJ-Content-SHA256`, `X-AJ-Signature`, `Content-Type: application/json`.

```json
{
  "format": "astraljet-registry-sync-v1",
  "installation_id": "uuid",
  "registry_id": "local:etykieta",
  "batch_id": "uuid",
  "generated_at": "2026-09-23T12:00:00Z",
  "sequence": 1,
  "cursor": { "event_id": "EVT-identyfikator-lub-null" },
  "execution_authorized": false,
  "records": [{ "id": "STRAT-…", "version": 1, "kind": "STRAT", "status": "needs_input", "technical_status": "…", "created_at": "2026-09-23T12:00:00Z", "content_hash": "64-lowercase-hex", "evidence_type": null }],
  "edges": [{ "child": { "id": "STRAT-…", "version": 1 }, "parent": { "id": "CAND-…", "version": 1 }, "relation": "candidate_id", "resolution": "exact" }],
  "warnings": []
}
```

Nieznane pola są odrzucane. Dozwolone `kind`: SRC, CAND, STRAT, DATA, EXP, RUN. `execution_authorized` musi być `false`.

Limity: 4 MiB UTF-8, 5000 wersji, 20000 relacji; nadmiar jest odrzucany, nie obcinany. Etykieta: `[a-z0-9][a-z0-9-]{0,47}`. Identyfikatory instalacji/batcha/nonce: UUID. Statusy, typy dowodów, relacje i ostrzeżenia korzystają ze ścisłej allowlisty istniejącego kontraktu `astraljet-lineage-v1`. Brak tekstów źródeł, reguł strategii, świec, lokalnych ścieżek i sekretów.

Podpis HMAC-SHA256 obejmuje dokładne bajty UTF-8. Tekst podpisywany to siedem linii połączonych rzeczywistym LF, bez końcowego LF: `AJ-SYNC-V1`, `POST`, `/api/astra/registry-sync`, key ID, timestamp Unix w sekundach, nonce, SHA-256 body (lowercase hex). Okno czasu ±300 s. Nonce chroniony atomowo w D1. Retry: identyczny zamrożony body/batch/sequence, nowy timestamp i nonce. Wyłącznie HTTPS; klient nie podąża za przekierowaniami. Nagłówek `OAI-Sites-Authorization` obsługuje prywatną bramę Sites, nie zastępuje urządzenia ani podpisu.

Urządzenie przypisuje właściciela; pole właściciela nie jest przyjmowane w body. Etykieta rejestru wiąże się z jedną instalacją. Konflikt dowolnych metadanych istniejącej wersji, instalacji albo tożsamości sekwencji kończy cały zapis bez częściowego sukcesu.

## Odpowiedzi

- `200`: ścisły ACK `astraljet-registry-ack-v1`: `request_id`, `server_time`, `batch_id`, `registry_id`, `installation_id`, `body_hash`, `accepted`, `cursor`, `execution_authorized:false`. Klient sprawdza każde powiązanie i pełny licznik; zwykłe `{ok:true}` nie jest sukcesem. Retry zwraca oryginalny ACK.
- `401/403`: brak lub niewystarczający scope, podpis, czas albo nonce; bez szczegółów sekretu.
- `409`: powtórzony batch z innym hashem lub konflikt wersji/hashu; bez zapisu elementów.
- `413/422`: limit lub niepoprawny format; bez echo payloadu.
- `503`, inne 5xx, 408/429 albo niepewny transport/ACK: lokalny batch otrzymuje `retryable_failure`. 409 → `conflict`; pozostałe błędy HTTP → `rejected`.

Cały batch waliduje się przed atomowym zapisem. Endpoint nie tworzy jobów, nie steruje MT5 i nie zapisuje do istniejącego `astra_discovery`.

Lokalna dzierżawa wysyłki trwa 120 s. Przesunięcie kursora następuje tylko po sprawdzonym ACK; spóźniona starsza paczka nie cofa kursora ani widoku. `sync-status` jest tylko odczytem. Polecenie wysyłki to `registry sync-push` (nie `registry sync push`). Poświadczenia pochodzą z prywatnego pliku lub zmiennych procesu, nigdy z argumentów CLI.

Parowanie: sesja właścicielska + zgodny Origin, `POST /api/astra/devices` z `action:pair-registry`. Pobierany plik jest sekretną konfiguracją poza repozytorium, a nie snapshotem badań. D1 przechowuje tylko hash tokenu urządzenia; sekret podpisu pozostaje w środowisku Sites i prywatnym pliku klienta.
