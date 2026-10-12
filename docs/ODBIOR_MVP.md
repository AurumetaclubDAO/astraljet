# Odbiór MVP Astra JET

**Data odbioru technicznego:** 2026-09-19  
**Katalog:** `D:\Astra Jet`  
**Wynik techniczny:** PASS  
**Wynik inwestycyjny:** ZABLOKOWANE / DO UZUPEŁNIENIA

## Co zostało odebrane

- lokalny, trwały rejestr SQLite dla SRC, CAND, STRAT, DATA, EXP, RUN, REVIEW,
  RISK-DECISION, MANDATE, INCU, BUDGET-STATUS i EVENT;
- append-only EVENT oraz idempotencja operacji skutkowych;
- moduł ASTRA Pro do formalizacji, danych, backtestu, reprodukcji, REVIEW i decyzji ryzyka;
- odrębny Wykonawca dla `PAPER_CONTINUOUS` i testowego `BROKER_DEMO`;
- fail-closed guard: daty, wersje, hash kodu, instrumenty, limity, świeżość danych,
  wyłączny lease, heartbeat, kill switch i blokada przy `uncertain`;
- trwała symulacja PAPER bez podwójnej realizacji po restarcie;
- reconciliation adaptera DEMO bez klienta brokera, sieci i sekretów;
- status JSON, BUDGET-STATUS oraz zredagowany eksport audytowy pełnego łańcucha.

W kodzie, typach i CLI nie istnieje środowisko `REAL`.

## Testy automatyczne

Uruchomiono:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Wynik: **38/38 testów PASS**, `Ran 38 tests in 15.886s`; cały proces polecenia trwał
17,359 s. Zakres obejmuje kontrakty, testy jednostkowe i integracyjne, restart,
idempotencję, mechanikę backtestu, niezależny REVIEW, PAPER/DEMO, status i eksport.

Test wydajności utworzył dokładnie **100 000 EVENT** i potwierdził projekcję statusu
poniżej limitu odbiorowego 5 s. Test granic modułów potwierdził, że
`src/astraljet/lab/` nie importuje `src/astraljet/executor/`.

## Rzeczywisty quickstart

Użyty stan runtime (ignorowany przez Git):
`D:\Astra Jet\.runtime\quickstart-2026-09-19`.

Zarejestrowane źródło:

- SRC: `SRC-b85ac93a0ecd481ab685ce4189fc877c`
- SHA-256: `ED708DAF399C9851CA925F4050817936CD2F6F80D3C14A29899699CEA8FB6998`
- plik pozostał poza repozytorium; zapisana została metadana i hash, nie treść.

Zarejestrowano pięć strategii do opracowania:

1. `CAND-6f681942a1ea4e4d8ebc0a19921bc1fa` — AI Power & Infrastructure — Picks & Shovels
2. `CAND-08be69f6417e4c3fad61824e80b0db59` — Polski Bond Ladder — floating + inflation-linked
3. `CAND-dea2c958a49f4878aba4692d25120804` — Gold Barbell — bullion + miners
4. `CAND-ab0861c34baa44f192ccad96d7e78cad` — Managed Futures / Trend Following
5. `CAND-1fc9fb54868542fdbbd0a1862c4f5fbb` — BTC/ETH z kontrolą trendu i ryzyka

Każdy kandydat ma stan `needs_input`. Status po restarcie wskazał:

```json
{
  "stage": "CAND",
  "object": "CAND-1fc9fb54868542fdbbd0a1862c4f5fbb",
  "blocker": "record_blocked",
  "allowed_next_action": "Sformalizuj jednoznaczną STRAT."
}
```

Powtórzenie importu z tymi samymi kluczami dało `source_created_again=false` oraz
`candidates_created_again=0`. Po restarcie pozostało 6 rekordów i 6 zdarzeń — bez
duplikatu i bez utraty stanu.

## Wyniki kontroli bezpieczeństwa

- `ExecutionEnvironment("REAL")` jest odrzucane;
- BROKER_DEMO bez jawnie potwierdzonego identyfikatora rachunku jest odrzucane;
- wygasły mandat, nieświeże dane, przekroczony limit, konflikt lease i aktywny kill
  switch blokują nowe ryzyko;
- ponowienie tego samego ORDER-INTENT zwraca `duplicate` i nie zmienia pozycji;
- stan `uncertain` blokuje kolejne intencje do czasu rozstrzygnięcia przez reconciliation;
- eksport audytowy zachowuje obie wersje korekty i redaguje lokalne locatory oraz pola
  sekretów/tokenów.

## Jawne ograniczenia i następny krok

PASS dotyczy mechaniki MVP i bezpiecznej architektury, nie jakości inwestycyjnej.
Dotychczasowy backtest używa wyłącznie syntetycznego fixture `test_only`. Nie wykonano
pełnego testu strategii BTC/ETH na zatwierdzonych danych rynkowych, nie ma dowodu przewagi,
prognozy wyniku ani zgody na LIVE/REAL. Adapter BROKER_DEMO jest testowy i nie łączy się
z brokerem.

Bezpieczny następny krok: doprecyzować STRAT dla kandydata BTC/ETH, zatwierdzić lokalny,
wersjonowany snapshot DATA, zamrozić EXP przed poznaniem wyniku, wykonać dwa odtwarzalne
RUN i przekazać cały pakiet do niezależnego REVIEW. Dopiero zweryfikowany REVIEW oraz
datowana RISK-DECISION mogą prowadzić do osobnego mandatu PAPER albo DEMO.

## Kontynuacja po odbiorze — 2026-09-19

Po pierwszym odbiorze wykonano formalizację źródłową BTC/ETH. Utworzony rekord
`STRAT-5fb2fbd40d9f4842afdcaa2b2898a411` ma celowo stan `needs_input`; status pokazuje
siedem konkretnych blokerów i nie sugeruje przejścia do DATA/EXP. Szczegóły oraz warianty
decyzji są w `docs/strategies/BTC_ETH_STRAT_DRAFT_v0.1.md`.

Wykonawca został dodatkowo uszczelniony: lease, heartbeat, kill switch, zaakceptowane
intencje PAPER/DEMO, `uncertain`, reconciliation oraz każda blokada tworzą trwały EVENT
powiązany z rekordem systemowym `SYSTEM-EXECUTOR`. Migracja istniejącego stanu do schematu
v3 zakończyła się poprawnie, a eksport audytowy po restarcie został zweryfikowany.

Aktualny wynik regresji po kontynuacji: **41/41 testów PASS** (`Ran 41 tests in 5.289s`).
