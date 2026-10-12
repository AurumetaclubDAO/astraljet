# Quickstart walidacyjny: Bezpieczny MVP Astra JET

## Wymagania

- Python 3.12 lub nowszy (`python --version`)
- PowerShell
- lokalny plik źródłowy wskazany przez użytkownika
- brak wymaganego brokera, kluczy API i połączenia sieciowego

## Instalacja deweloperska

```powershell
Set-Location -LiteralPath 'D:\Astra Jet'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Katalog `.venv` i katalog stanu muszą być ignorowane przez Git.

## Scenariusz 1 — inicjalizacja i import źródła

```powershell
$state = 'D:\Astra Jet\.runtime\quickstart'
astraljet --state-dir $state init
astraljet --state-dir $state source add `
  --file 'C:\Users\karol\Downloads\5_strategii_inwestycyjnych_2026_PL.md' `
  --author 'unknown' `
  --idempotency-key 'quickstart-source-v1'
```

Oczekiwane: SRC ma SHA-256
`ED708DAF399C9851CA925F4050817936CD2F6F80D3C14A29899699CEA8FB6998`, a treść pliku
nie jest wykonywana ani kopiowana do repozytorium.

## Scenariusz 2 — pięciu kandydatów bez fałszywej weryfikacji

```powershell
astraljet --state-dir $state candidates seed-2026 `
  --source-id SRC_ID `
  --idempotency-key 'quickstart-candidates-v1'
astraljet --state-dir $state status --json
```

Oczekiwane: dokładnie pięć CAND; wszystkie mają stan `unassessed` albo `needs_input`.
Strategia #5 jest pierwsza w kolejce, lecz nie ma RUN ani werdyktu `verified`.

## Scenariusz 3 — idempotencja i restart

Powtórzyć oba polecenia z tymi samymi kluczami, zamknąć proces i uruchomić `status`.
Oczekiwane: brak drugiego SRC, CAND, kosztu lub zdarzenia skutkowego; stan zostaje odtworzony.

## Scenariusz 4 — granica wykonania

Testy kontraktowe próbują utworzyć mandat dla `REAL`, uruchomić wykonawcę bez mandatu,
użyć wygasłej decyzji ryzyka i powtórzyć `uncertain` intent. Wszystkie przypadki muszą
zostać zablokowane i pozostawić EVENT z właścicielem oraz następnym krokiem.

## Testy

```powershell
python -m unittest discover -s tests -v
```

Pełny przebieg BTC/ETH wymaga później zatwierdzonego lokalnego DATA CSV, kompletnej STRAT
i zamrożonego EXP. Brak tych elementów ma dać `blocked`, a nie wynik domyślny.
