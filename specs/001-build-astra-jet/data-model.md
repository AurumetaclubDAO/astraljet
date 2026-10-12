# Model danych: Bezpieczny MVP Astra JET

## Wspólna koperta rekordu

Każdy rekord domenowy zawiera:

- `record_id`: stabilny identyfikator z prefiksem typu, np. `SRC-...`;
- `version`: liczba całkowita >=1; zmiana znaczenia tworzy nową wersję;
- `owner`: osoba albo proces odpowiedzialny;
- `created_at`: czas UTC ISO-8601;
- `technical_status`: `queued`, `blocked`, `running`, `completed`, `failed`, `cancelled`;
- `content_hash`: SHA-256 kanonicznej treści rekordu;
- `limitations`: lista jawnych ograniczeń, nigdy puste przemilczenie;
- `supersedes`: opcjonalny identyfikator wcześniejszej wersji.

Stan techniczny nie koduje wyniku merytorycznego.

## Encje

### SRC

Pochodzenie materiału: `locator`, `sha256`, `size_bytes`, `observed_at`, `author` lub
`unknown`, `media_type`, `trust_status` (`unverified`, `verified_origin`). Treść źródła
jest danymi; sam SRC nie może wywołać komendy wykonawczej.

### CAND

Kandydat strategii: `title`, `source_ids`, `thesis`, `asset_class`, `market_scope`,
`missing_decisions`, `candidate_status` (`unassessed`, `needs_input`, `qualified`,
`rejected`). Pięć początkowych CAND wskazuje jeden SRC.

### STRAT

Jednoznaczna reguła: instrument i venue, częstotliwość, dostępność sygnału, wejście,
wyjście, sizing, koszty, ograniczenia, brak danych, benchmark i dozwolone parametry.
`strategy_status`: `draft`, `needs_input`, `ready`, `frozen`, `retired`.

Walidacja blokuje `ready`, jeżeli brakuje którejkolwiek istotnej reguły.

### DATA

Wersja danych: `provider`, `venue`, `instruments`, `timeframe`, `timezone`, `start`, `end`,
`available_at_rule`, `locator`, `sha256`, `schema_version`, `transformations`,
`cost_model`, `quality_findings`, `data_status` (`ready`, `gaps`, `unsuitable`).

### EXP

Zamrożony plan: wersje STRAT/DATA/kodu, zakresy in-sample/out-of-sample, warianty,
kryteria, budżet, seed, metryki, tolerance, reguły przerwania i `frozen_at`. Po zamrożeniu
nie jest modyfikowany; zmiana tworzy nową wersję.

### RUN

Przebieg: `experiment_id`, `evidence_type` (`BACKTEST`, `LATER_DATA_REPLAY`,
`PAPER_CONTINUOUS`, `BROKER_DEMO`), czasy, wersja silnika, transakcje, odrzucone sygnały,
koszty, ekspozycja, equity, błędy, metryki, artefakty i instrukcja odtworzenia.
`run_outcome`: `passed`, `failed_criteria`, `inconclusive`, `technical_failure`.

### REVIEW

Oddzielny przegląd: `run_ids`, `reviewer`, `evidence`, `findings`, `missing_evidence`,
`verdict` (`verified`, `unverified`, `rejected`), `conditions`. `reviewer` nie może być
autorem ocenianego RUN.

### RISK-DECISION

Zakres, wersje, ważność, limity i decyzja `allowed` albo `blocked`. Brak decyzji oznacza
`blocked`; wygaśniętej decyzji nie można użyć.

### MANDATE

Datowana zgoda Karola: konkretna STRAT, kod, środowisko (`PAPER_CONTINUOUS` lub
`BROKER_DEMO`), instrumenty, limity, start, koniec, kill switch i warunki zatrzymania.
Nie istnieje wartość REAL.

### INCU

Seria inkubacji: mandat, lease wykonawcy, stan, sygnały, ORDER-INTENT, realizacje,
reconciliation, pozycje, alarmy i heartbeat. Stany: `planned`, `active`, `paused`,
`blocked`, `stopped`, `completed`, `uncertain`.

### EVENT

Niezmienny wpis: `event_id`, `occurred_at`, `recorded_at`, `actor`, `event_type`,
`record_type`, `record_id`, `record_version`, `reason`, `outcome`, `payload`,
`correlation_id`, `causation_id`, `idempotency_key`. Unikalność klucza zapobiega
podwójnemu skutkowi.

### BUDGET-STATUS

`scope`, `currency`, `approved_limit`, `settled_cost`, `active_reservation`,
`unreconciled_cost`, `valid_at`. Operacja kosztowa wymaga dostępnego limitu po odjęciu
wszystkich trzech rodzajów obciążenia.

## Relacje

```text
SRC -> CAND -> STRAT -> DATA + EXP -> RUN -> REVIEW -> RISK-DECISION -> MANDATE -> INCU
                         \_______________________________________________/
                                           EVENT
```

- CAND może mieć wiele STRAT; STRAT wskazuje co najmniej jeden SRC.
- EXP wskazuje dokładnie jedną wersję STRAT i co najmniej jedną wersję DATA.
- RUN wskazuje dokładnie jedną wersję EXP; wiele RUN służy odtworzeniu.
- REVIEW może porównywać RUN tylko przy zgodnych wersjach albo oznacza je jako
  `NIEPORÓWNYWALNE`.
- MANDATE wymaga REVIEW i RISK-DECISION dla tych samych zamrożonych wersji.
- INCU należy do jednego MANDATE; aktywny lease jest unikalny dla środowiska.
- Każda zmiana stanu tworzy EVENT w tej samej transakcji.

## Przejścia krytyczne

1. `CAND.needs_input -> qualified` dopiero po kompletnej STRAT.
2. `STRAT.ready -> frozen` tylko razem z DATA ready i utworzeniem EXP.
3. `EXP -> RUN` wyłącznie po zapisaniu kryteriów i tolerancji.
4. `RUN -> REVIEW.verified` wymaga odtworzenia i osobnego recenzenta.
5. `REVIEW + RISK-DECISION -> MANDATE` wymaga datowanej decyzji Karola.
6. `MANDATE -> INCU.active` wymaga ważności, właściwego środowiska, lease i świeżych danych.
7. Każdy stan nieznany, konflikt lease, brak heartbeat lub kill switch blokuje nowe ryzyko.
