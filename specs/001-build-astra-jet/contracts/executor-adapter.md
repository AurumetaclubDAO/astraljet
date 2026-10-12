# Kontrakt Wykonawcy AstralJet

## Granica

Wykonawca otrzymuje wyłącznie zamrożone identyfikatory STRAT/EXP/kodu, aktualną decyzję
ryzyka i mandat. ASTRA Pro nie wywołuje metod adaptera. Adapter nie przyjmuje swobodnego
tekstu źródłowego.

## Dozwolone środowiska

- `PAPER_CONTINUOUS`
- `BROKER_DEMO`

Wartość `REAL` nie istnieje w typie, konfiguracji ani migracji. Nieznana wartość jest
odrzucana fail-closed.

## Operacje portu

```text
health() -> Health
acquire_lease(environment_id, worker_id, ttl, idempotency_key) -> Lease
submit_intent(frozen_context, order_intent, idempotency_key) -> ExecutionReceipt
reconcile(external_reference, idempotency_key) -> ReconciliationResult
positions(environment_id) -> PositionSnapshot
heartbeat(lease_id) -> Heartbeat
activate_kill_switch(environment_id, reason, idempotency_key) -> KillSwitchReceipt
```

## Warunki przed `submit_intent`

1. Mandat istnieje, jest podpisany przez Karola i nie wygasł.
2. Środowisko, instrument, STRAT, kod i limity są identyczne z mandatem.
3. RISK-DECISION ma `allowed` i nie wygasła.
4. Dane oraz heartbeat są świeże według mandatu.
5. Proces posiada aktywny, wyłączny lease.
6. Kill switch nie jest aktywny.
7. Poprzednia próba z tym kluczem ma stan rozstrzygnięty albo zostaje zwrócona bez ponowienia.

Niespełnienie dowolnego warunku zwraca blokadę i EVENT; nie powstaje nowe ryzyko.

## Stany rezultatu

- `accepted`: adapter potwierdził przyjęcie w odpowiednim środowisku;
- `rejected`: brak działania, znany powód;
- `uncertain`: wynik zewnętrzny nie jest znany; wymagane `reconcile`, nowe ryzyko zablokowane;
- `duplicate`: zwrócono rezultat wcześniejszej próby o tym samym kluczu.

Adapter BROKER_DEMO musi dodatkowo potwierdzić identyfikator rachunku demonstracyjnego.
Brak takiego potwierdzenia kończy się `rejected`.
