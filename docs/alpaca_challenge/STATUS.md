# Odbiór Astra / Alpaca Challenge — 30.09.2026

**STATUS: NOT READY — lokalnie uruchomiony dry-run, odbiór brokera zablokowany.**

Kod jest rozszerzeniem obecnego AstralJet w `src/astraljet/alpaca_challenge`.
Nie zastąpiono istniejącego Lab, symulatora ani uruchomionych wykonawców MT5.
Snapshot poprzedza zmiany: `.runtime/snapshots/alpaca-before-20260930-150408`.

## Co działa

- Python 3.12 w oddzielnym venv; lokalne API i panel na http://127.0.0.1:8876.
- `/health` odpowiada; bez tokenu `/v1/audit` zwraca 401. Wszystkie `/v1/*`
  mają wspólną kontrolę Bearer, schema i stałoczasowe porównanie tokenu.
- Scanner działa, zapisuje również odrzucenia; przy 401 każdy odczyt kończy NO_TRADE.
- SQLite journal i trwały kill switch sprawdzone w uruchomionym procesie.
- Skrypty start/stop uruchomione; restart zachowuje historię i kill switch ON.
- Testy offline obejmują Paper guard, błędne URL, auth, schema, duplikaty,
  limity ryzyka, korelację, pending, stale data, crypto short, naked options,
  BTO/STC, extended hours, dry-run, flatten, SL/TP/break-even, natywny SL,
  partial fills, restart i niepewny POST bez ponowienia.
- Deterministyczny setup A i NO_TRADE potwierdzone na jawnych fixtures testowych.
  Nie są prezentowane jako obserwacja aktualnego rynku.

## Co nie działa / nie zostało potwierdzone

Rzeczywisty Paper account oraz Market Data zwracają **HTTP 401** przy kluczach
z istniejącego `.env`. Nie można potwierdzić salda, pozycji, uprawnień instrumentów,
feedów ani działania strategii na aktualnych danych tego konta.

Nie wysłano żadnego zlecenia Paper/LIVE ani anulowania do brokera.
Brokerowy native SL, flatten i fills sprawdzono na kontrolowanym transporcie,
nie przez rzeczywiste wykonanie — zgodnie z zakazem składania zleceń na tym etapie.
Runtime: `PAPER_ONLY=true`, `EXECUTE_ORDERS=false`, scanner ON, kill switch ON,
health `degraded`, challenge nie rozpoczęty.

## Testy i acceptance

49 testów modułu challenge. Pełny zestaw Astry uruchomiony ponownie po zmianach;
ostateczny wynik zapisany w `VERIFICATION.json` obok tego raportu.
Pojedyncze ostrzeżenie dotyczy przyszłej zmiany transportu TestClient Starlette;
testy aktualnego httpx przechodzą.

Acceptance: PAPER ONLY i JOURNAL PASS; ACCOUNT/MARKET DATA FAIL (401),
zależne kroki SCANNER/STRATEGY/RISK/DRY RUN/KILL SWITCH nie otrzymują PASS
zamiast rzeczywistego sprawdzenia. Wynik: **RESULT: NOT READY**.
Pełny raport: `.runtime/alpaca/acceptance.json`.

## Blockery i następny krok

1. Lokalnie wpisać aktualne klucze **Alpaca Paper** do `.env` (bez wysyłania do czatu).
2. Zrestartować moduł i powtórzyć `acceptance_test.py`.
3. Potwierdzić dedykowane konto z equity 1000 USD, bez pozycji/zleceń;
   feedy i tradability muszą być odczytane, nie założone.
4. Po pozytywnym odbiorze przygotować HOW_TO_ENABLE_PAPER_EXECUTION.md.
   Nie utworzono go przed spełnieniem warunku użytkownika.

Funkcje świadomie poza V1: trailing (V1.1), automatyczny wybór kontraktów
opcyjnych i publikacja panelu w zewnętrznym Command Center. Opcje obsługuje API
z weryfikacją setupu instrumentu bazowego. Nocne akcje wymagają aktualnego feedu
i atrybutów; jego brak oznacza NO_TRADE. Crypto/option/extended protections
lokalne wymagają ciągłej pracy aplikacji; pełne akcje LONG mają natywny SL w RTH.
