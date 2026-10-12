# ASTRALJET CURRENT STATE — 19.09.2026

Audyt kodu, metadanych, schematów i wybranych testów obu lokalizacji. Odczyty do 21:05 UTC / 23:05 Warszawa. Nie jest to pełny audyt bezpieczeństwa, potwierdzenie wyników inwestycyjnych ani odbiór całego systemu.

## Wynik

Istniejąca Astra jest punktem rozbudowy. Frontend, badania i wykonawcy już istnieją; nie należy odtwarzać ich w nowym projekcie. Lokalny rejestr `src/astraljet` nie jest jeszcze połączony z bazą witryny ani z działającym łącznikiem. Samo zgromadzenie różnych rekordów w folderze nie tworzy powiązanego eksperymentu.

## Git

| Lokalizacja | Stan odczytany |
|---|---|
| `D:\Astra Jet` | `main`, bez commitów; pliki rdzenia i dokumentacji nieśledzone. Origin: `https://github.com/AurumetaclubDAO/astraljet.git` |
| `C:\Users\karol\Documents\Claude\Projects\Trading\astra_site` | Gałąź `codex/astra-discovery-chat-20260913`, HEAD `5073f65`; osobna historia i origin Sites. Zachowane gałęzie i worktree |

`git -c credential.interactive=never ls-remote --symref origin HEAD` w katalogu głównym zwrócił `Repository not found`. NIE DZIAŁA dostęp Git do docelowego repozytorium. Nie wykonano fetch/push, commita, resetu, przeniesienia ani nadpisania historii. Zawartość zdalnego `main` pozostaje NIEZWERYFIKOWANA w tej sesji; historyczny opis początkowego commita nie zastępuje odczytu.

W starej Astrze zastano zmodyfikowane `README_ASTRA.md` oraz nieśledzone `.claude/`, `docs/AUR001_AUDIT_2026-09-19.md` i trzy pliki `research/recovery/*intraday_momentum*`. Nie zmieniono ich. `site-spotkania` jest odrębnym projektem witryny, nie kodem silnika tradingowego.

Lokalny `.gitignore` nie ignoruje TypeScript `lib/`. `.env` i `.runtime/` są ignorowane. W śledzonych plikach starej Astry nie znaleziono plików dopasowanych do `.env*`, `*.sqlite`, `*.sqlite3`, `*.db`; `outputs/webhook_test/.env` jest ignorowany przez `/outputs/`. To kontrola nazw i ignorowania, nie pełny skan sekretów w treści i historii.

## Inwentarz komponentów

| Komponent / lokalizacja | Technologia, wejście i zależności | Dane / porty / stan | Migracja i ryzyko |
|---|---|---|---|
| `D:\Astra Jet\src\astraljet` | Python >=3.12; `astraljet.cli`; biblioteka standardowa, setuptools do pakowania | Jawny `--state-dir`; lokalny CLI, bez serwera | Rozwijać istniejący rdzeń. Nie jest zamiennikiem działających botów |
| `astra_site\app`, `components`, `lib` | Next 16.2.6, React 19.2.6, TS 5.9.3, Vinext/Vite; `app/page.tsx`, `app/research/page.tsx` | Frontend, badania, biblioteka, Decision Inbox i integracje częściowo istnieją | Zachować; nie przepisywać do nowego UI. Publikacja poza zakresem tej sesji |
| `astra_site\db`, `drizzle` | Drizzle 0.45.2, D1/SQLite; `db/schema.ts`, migracje SQL | Journal, raporty, materiały, kolejka, urządzenia, telemetria i koszty; pliki w R2 | Nie migrować chmurowych danych bez eksportu, mapowania właścicieli i testu odtworzenia |
| `astra_site\research\astra_lab_v3` | Python; `astra_lab/strategies.py`, `execution.py`, `contest.py`; CONTRACT, reguły wykonania i kwalifikacji | Biblioteka strategii i backtestów. Dokumentacja nie potwierdza bieżącej kwalifikacji | Zachować implementacje; najpierw porównać kontrakty i wersje runtime |
| `astra_site\research\discovery` | Lokalny worker Python + witryna; README opisuje zadania i trwałą kolejkę | Dane w AstraResearch, poświadczenie urządzenia poza Git | Zachować interfejs kolejki. Uruchomienie nowego workera wymaga sprawdzenia duplikacji |
| `astra_site\research\research_cli` | `webhook.py` + Node `run.mjs`; SQLite alertów | Walidacja schematu, wspólny sekret, tolerancja czasu, hash deduplikacji; badania, nie zlecenia | Nie przepinać na wykonawcę. E2E TradingView → DEMO NIEZWERYFIKOWANE |
| `astra_site\research\mt5_connector` | Python + MetaTrader5; `astra_connection.py` | Odczyty i osobne POST sterujące DEMO; nie jest modułem wyłącznie read-only | Najpierw izolować adapter odczytu; nie łączyć automatycznie sterowania |
| Faktyczny proces `...\Trading\Astra_Lab_v2\mt5\astra_connection.py` | Python 3.12; PID 48212 podczas odczytu | Nasłuch `127.0.0.1:8765`. `/status`: `connected=true`, `mode=DEMO`, `executionEnabled=true`, `readOnly=false`, `connectorVersion=3.7` o 21:04:55 UTC | Działający runtime, pozostawiony bez zmian. Nie restartować ani relokować w ramach zmian CLI |
| `%LOCALAPPDATA%\AstraMT5` | `monitor.sqlite3`, konfiguracja, logi | Odczyt schematu: alerts, candles, candles_utc, diagnostics, diagnostics_utc, history, research_jobs, research_summaries, state, workbench_settings | Nie kopiować aktywnej bazy jak zwykłego pliku; osobny plan snapshotu SQLite |
| `%LOCALAPPDATA%\AstraResearch` | `discovery.sqlite3`, plik urządzenia, worker | Odczyt schematu: exposures, jobs, state | Kolejka lokalna nie jest D1 ani rejestrem `astraljet.sqlite3` |
| `D:\Astra Jet\site-spotkania` | Osobna witryna statyczna / Node; port 4173 | Miejsce spotkań, nie panel wykonawczy | Nie scalać automatycznie z botem |

Wiersz laboratorium powyżej dotyczy kodu do zachowania, nie zgody na stosowanie zawartych w dawnych konfiguracjach wartości kapitału/ryzyka. Każdy kontrakt jest przypisany do własnej rundy.

SHA-256 `astra_connection.py` w checkout i w ścieżce działającego procesu: `EF8FDC1B3FE7459B8C2199BAADC364B259C68F3AB160B93EAFA87A9DA43ED04A`. Potwierdzono ten plik, nie zgodność wszystkich importowanych modułów. Bieżący GET nie składał zleceń; nie pobierano do raportu salda, numeru rachunku ani sekretu.

Uwaga do AppData: Python w środowisku Codex rozwiązał ścieżki baz do `C:\Users\karol\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\AstraMT5` i analogicznego `AstraResearch`. Nie potwierdzono tożsamości plików obu widoków systemu plików. Zestawienie schematu nie jest dowodem odczytu dokładnie tej instancji bazy, którą ma otwartą proces MT5. To warunek do rozstrzygnięcia przed migracją.

## Lokalne rejestry AstralJet — odczyt bez migracji

| `--state-dir` w `.runtime` | Schemat | Faktyczne rekordy | Zdarzenia |
|---|---:|---|---:|
| `dev` | 1 | 1 SRC, 5 CAND | 6 |
| `quickstart-2026-09-19` | 3 | 1 SRC, 5 CAND, 1 STRAT | 7 |
| `state` | 4 | 2 DATA | 2 |

STRAT `STRAT-5fb2fbd40d9f4842afdcaa2b2898a411` v1 pozostaje `needs_input/blocked` w `quickstart-2026-09-19`. Dane Alpaca są w `state`. Nie ma zapisanych EXP/RUN/REVIEW/mandatów w tych trzech rejestrach. Nie oznacza to braku takich obiektów w osobnej D1 czy u istniejącego wykonawcy.

Nie połączono tych baz, nie dopisano brakujących relacji i nie uznano propozycji parametrów BTC/ETH za zatwierdzoną. Dawne relacje SRC/CAND bez numeru wersji są jawnie oznaczane, nie zamieniane na rzekomo zamrożony łańcuch.

## ENV i źródła

W lokalnym `.env` występują nazwy `ALPACA_PAPER_BASE_URL`, `ALPACA_DATA_BASE_URL`, `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`. Nie publikowano wartości. Po stronie starej Astry istnieją osobne sekrety urządzenia/MT5, sekret webhooka i ustawienia dostawców chmurowych. Nie wolno ich przenosić razem z kodem. Klucze wcześniej ujawnione w rozmowie wymagają wymiany u dostawcy; nie kopiujemy ich do nowych plików.

Zweryfikowano istnienie i SHA-256 wszystkich 29 wpisów `docs/KATALOG_PLIKOW_LOKALNYCH.csv`; brak rozbieżności. To weryfikacja plików, nie poprawności twierdzeń zawartych w książkach, grafikach i PDF. `Trading 2.0/` i `materials/inbox/` pozostają biblioteką materiałów.

Przejrzano dokumentację startową, wybrane sekcje v0.2, katalog, README i kontrakty, schematy, CLI oraz wskazane ścieżki badań i integracji. Nie wykonano ponownej pełnej analizy wszystkich PDF/DOCX/raportów. Starsze `00_AUDYT/raw/90...`, `91...`, `93...`, `94...` zawierają sekcje „w trakcie”; ich istnienie nie dowodzi zakończonego audytu.

## Weryfikacja i luki

- Przed zmianami: 53/53 testy rdzenia; 31/31 wybranych testów JS (`strategy-factory`, `discovery`, `mt5-data`, `contest`); TypeScript `tsc --noEmit --incremental false`: exit 0.
- Po zmianach pierwszego etapu: 70/70 testów rdzenia na Pythonie 3.12.10. Dalsze wyniki: [raport etapu](docs/operations/ETAP_01_2026-09-19.md).
- Build/deploy frontendu, pełny zestaw wszystkich testów starej Astry, audyt historii sekretów, broker reconciliation oraz kryteria finansowe: NIEZWERYFIKOWANE w tej sesji.
- Brak wspólnego autorytatywnego modelu tożsamości i wersji pomiędzy D1, local research i nowym rejestrem.
- Lokalny `DemoAdapter` jest adapterem testowym; nie jest zastanym wykonawcą MT5 i nie potwierdza rzeczywistych fills.
- Pełna maszyna stanów z briefu, uwierzytelnione decyzje człowieka, cztery zakresy kill switch, kompletny risk engine portfela i cały test odbiorowy pozostają do implementacji/integracji. 70 testów nie zamyka tych luk.
- Nie przeprowadzono pełnego niezależnego audytu bezpieczeństwa. Nowe triggery blokują modyfikację danych przez zwykły SQL aplikacji, nie administratora mogącego zmienić plik/schemat.
