# Dashboard AstralJet — audyt P1

Data: 13.10.2026, odczyty od 19:03 Europe/Warsaw. Host potwierdzony przez `socket.gethostname()`: **Solyg**. Wykonawca: Codex, bieżąca sesja rozmowy „Go dla budowy”.

Status: **audyt i propozycja, bez implementacji produkcyjnej**. Źródło zakresu: [P0–P5 ASTRA QUANT](https://app.notion.com/p/3f8cb4db3956818e9b62c227107a3100). Akceptacja konkretnej architektury po P1 pozostaje osobnym krokiem wskazanym w tym dokumencie.

## Zakres i dowody

Przeczytano `AGENTS.md`, `START_ASTRALJET.md`, `docs/LOKALIZACJA_I_STAN_2026-09-19.md`, `ARCHITECTURE.md`, `CURRENT_ASTRA_INVENTORY.md`, `MIGRATION_PLAN.md`, `README_PL.md`, `pyproject.toml`, `run_windows.ps1`, pliki wejściowe API oraz wybrane moduły wykonawcy. Sprawdzono strukturę `src/astraljet`, `tests`, metadane źródeł TQ, kod producenta Areny i zadania Harmonogramu. To audyt integracyjny wskazanych granic, nie pełny audyt wszystkich plików lub skuteczności strategii.

Nie odczytywano zawartości `.env`, `KLUCZE.txt` ani poświadczeń. Nie importowano i nie uruchamiano modułów wykonawczych, `Settings`, runnerów lub `refresh_status.py`. Nie wywoływano MT5, brokera, skryptu acceptance ani launcherów. Zewnętrzne źródła na Desktop były tylko odczytywane.

ACK zasad przekazano Karolowi w rozmowie. **ACK na Agent Bus nie został wysłany** — w tej sesji nie było bezpośredniego polecenia wysyłki wiadomości. Nie przypisano potwierdzenia ani akceptacji innym agentom. Ten audyt nie jest dowodem wykonania protokołu komunikacji Agent Bus.

Backup przeszedł wymaganą kontrolę przed zapisami: [BACKUP_VERIFY.md](BACKUP_VERIFY.md).

## Stan Git

Odczyt lokalny: `git status --short`, `git log -1`, `git branch -vv`.

- Przed pracą drzewo robocze czyste.
- HEAD: `65703eceec0333c8b6b1847eeb5b7b5243a20117`.
- Gałąź: `claude/wersjonowanie-rdzenia-i-dokumentacji`.
- `ahead 2` względem lokalnej referencji `origin/claude/wersjonowanie-rdzenia-i-dokumentacji`.
- Bez fetch, push, commita, przełączania gałęzi lub zmiany historii. Nie potwierdzono aktualnej synchronizacji z GitHub.

Wrześniowe opisy stanu Git w dokumentach są historyczne. Nowa dokumentacja zawiera lokalne ścieżki i dane operacyjne; nie została dodana do indeksu ani opublikowana.

## API i interfejsy

| Element | Dowód | Wniosek |
|---|---|---|
| API Alpaca | `scripts/run_alpaca_api.py`: `uvicorn.run(create_app(settings), host='127.0.0.1', port=8876, workers=1)` | Znany entrypoint istniejącego serwisu |
| Stan portu 8876 | Udany odczyt `Get-NetTCPConnection -State Listen` bez wierszy dla 8876; GET `/health` zakończył się `HttpRequestException` | Podczas audytu brak dostępnego API na tym porcie; nie twierdzimy, że serwis działa |
| Port 8877 | Brak wierszy nasłuchu podczas audytu | Dostępny w chwili sprawdzenia, start musi sprawdzić ponownie |
| Panel Alpaca | `src/astraljet/alpaca_challenge/main.py:136`: HTML osadzony w odpowiedzi GET `/` | Istnieje prosty panel z tokenem oraz przyciskami Kill switch i Flatten; nie nadaje się do bezpośredniego włączenia do panelu tylko do odczytu |
| Cykl życia Alpaca | `main.py:create_app` tworzy `Service`, lifespan uruchamia `service.start()` | Nie importować aplikacji Alpaca jako zależności nowego panelu |
| Poprzednia Astra | Katalog `C:\Users\karol\Documents\Claude\Projects\Trading\astra_site` istnieje, zawiera `app`, `components`, `lib`, `research`, `package.json` | Oddzielny frontend pozostaje na miejscu; nie sprawdzano jego bieżącej publikacji |
| `site-spotkania` | `public`, `dist`, `serve.mjs`, `build.mjs` | Osobna witryna, nie źródło bieżącego stanu TQ |

`run_windows.ps1` instaluje zależności, uruchamia testy/acceptance i może wystartować wykonawcę. Nie używać go do uruchamiania dashboardu. Kontrola `EXECUTE_ORDERS=false` w tym launcherze dotyczy ścieżki `-Diagnostic`; nie odczytywano bieżącej wartości ustawienia.

## Pakiet, środowiska i testy

`pyproject.toml`: Python >=3.12, setuptools, CLI `astraljet.cli:main`, brak zależności w głównej liście `dependencies`. Warstwy: `domain`, `application`, `infrastructure`, `executor`, `lab`, `alpaca_challenge`. Brak modułu `dashboard` przed audytem.

| Środowisko | Potwierdzony stan |
|---|---|
| `.venv` | Python **3.14.4**; brak fastapi, uvicorn, pydantic, pytest, MetaTrader5, psutil, playwright |
| `.runtime/alpaca-venv` | Python **3.12.10**; fastapi 0.142.2, uvicorn 0.54.0, pydantic 2.13.5, pytest 8.4.2; brak MetaTrader5, psutil, playwright |
| `py -0p` | Dostępny Python 3.12 oraz 3.14 |

Wersje odczytano przez `importlib.metadata`, bez importowania aplikacji. Launcher P5 aktywujący zastane `.venv` nie zadziała w postulowanym środowisku. Propozycja: dedykowany `.runtime/dashboard-venv`, Python 3.12, bez zmian dwóch istniejących środowisk.

`tests/` zawiera 35 plików `test_*.py`, w podkatalogach `unit`, `contract`, `integration`, `alpaca_challenge`; istnieją również `fixtures`. W P1 nie uruchamiano testów aplikacji — zmieniono tylko dokumentację. Liczba plików nie jest liczbą przypadków testowych ani wynikiem PASS.

## Punkty wykonujące operacje

Wyszukiwanie tekstowe i odczyt AST objęły kod Python w `src/` i `scripts/`; dodatkowo wybrane źródła TQ. Sama nieobecność nazwy `order_send` nie dowodzi braku ścieżki wykonania.

| Miejsce | Operacja | Granica dla dashboardu |
|---|---|---|
| `alpaca_challenge/broker.py:27–35` | Ogólny transport `httpx`, kontrola Paper i `execute_orders` przed mutacją | Nie tworzyć klienta `Broker` |
| `alpaca_challenge/broker.py:92–98` | `submit()` → POST `/v2/orders` | Zakaz importu i wywołania |
| `alpaca_challenge/service.py` | Wysyłki przez `broker.submit`; DELETE zleceń m.in. w liniach 112, 274, 276, 341, 423 | Zakaz tworzenia `Service`; nie uruchamiać reconcile/flatten/scannera |
| `alpaca_challenge/main.py` | POST `/v1/signals`, `/scanner/start`, `/scanner/stop`, `/kill-switch/on`, `/kill-switch/off`, `/flatten` | Nie montować istniejących routerów i nie proxy'ować ich |
| `executor/demo.py` | `DemoAdapter.submit_intent` zapisuje wynik testowy do SQLite; brak klienta brokera | To adapter testowy, nie dowód brokerskiego DEMO; nie korzystać do odczytu panelu |
| `executor/paper.py` | `PaperExecutor.submit_intent` zmienia rejestr symulacji | Zakaz użycia w panelu |
| Desktop `TQ-Common/gated_order.py:35` | Faktyczne `mt5.order_send(req)` | Źródło poza projektem, bez importu i bez zmian |
| Desktop `TQ-Common/tq_core.py:72` | `gated_order.place(...)` | Nie uruchamiać runnerów |

Nie znaleziono bezpośrednich wywołań `.order_send`, `.order_check`, `.submit_order` w AST lokalnych `src/` i `scripts/`. Rzeczywista mutacja Alpaca odbywa się pod inną nazwą (`submit`/transport HTTP).

## Źródła TQ i ich ograniczenia

Baza ścieżek: `C:\Users\karol\Desktop`.

| Źródło | Potwierdzony stan odczytu |
|---|---|
| `TQ-HORMUZ/signals.csv` | 32 wiersze, mtime 16:58:04 UTC |
| `TQ-TECH-VOL/signals.csv` | 64 wiersze, mtime 16:59:05 UTC |
| `TQ-XASSET-LAG/signals.csv` | 16 wierszy, mtime 17:00:06 UTC |
| `TQ-ALT-SPEC/signals.csv` | 68 wierszy, mtime 17:01:06 UTC |
| Cztery `state.json` powyższych runnerów | Puste obiekty `{}`; nie dowodzą braku pozycji lub zleceń |
| `TQ-VB/runner.log` | Istnieje, mtime 13:50:55 UTC; brak `signals.csv` i `state.json` w sprawdzonych lokalizacjach |
| `SHADOW-VB/journal_vb.csv` | 2 wiersze, `run_at_utc`, `decision`, wskaźniki i pola wyników symulacji; to osobne dane SHADOW |
| `TQ-LONG-HOLD` | Wskazany katalog nie istnieje; jego bot występuje w Arenie i konfiguracji ryzyka |
| `TQ-Common/funding_oi/funding_oi_snapshots.csv` | 132 wiersze; cztery pary Binance/Bybit × BTCUSDT/ETHUSDT; ostatni `collected_at_utc` 17:04:16Z |
| `TQ-Common/risk_config.json` | login DEMO i zabroniony login LIVE (numery tylko lokalnie), globalnie 8 pozycji; per trade 1%, strata dzienna 3% |
| `TQ-Common/KILL_SWITCH` | Pliku nie było w dostępnym katalogu w czasie sprawdzenia; wymaga ponownego odczytu przez panel |

Nagłówek sygnałów potwierdzony: `eval_time,bar_time_srv,symbol,signal,reason,indicators,atr,lot,sl,tp,action,detail`. Mtime nie jest czasem ostatniego sukcesu bota. Nie odczytywano surowych logów do raportu.

Suma przydziałów z konfiguracji to 24 000 USD: LONG HOLD 5000; TECH VOL, XASSET LAG, ALT SPEC i v-B po 4000; HORMUZ 3000. To limity budżetowe, nie dowód kapitału, ekspozycji lub equity konta.

Mapowanie magiców 2026101301/02/03/04/05 do HORMUZ/v-B/TECH VOL/XASSET LAG/ALT SPEC potwierdzone w kodzie odpowiednich runnerów. Magici LONG HOLD `2026093002`, `20261002` pochodzą z briefu; **nie potwierdzono ich w bieżącym odczycie brokera ani źródle runnera**. Nie przypisywać dowolnych pozycji po samym podobieństwie komentarza jako potwierdzonego mappingu.

### Arena — rozbieżności względem promptu

`TQ-Arena/status.json` ma 6 botów. W czasie odczytu `refreshed_at` = `2026-10-13T18:59:32+02:00`.

- `freshMt5Read` jest **obiektem**, zawierającym `readAt`, `login`, `server`, balance, equity i pozycje. Nie jest bool. W snapshotcie login = rachunek DEMO, serwer = VantageMarkets-Demo; brak `trade_mode` i informacji Algo Trading.
- `refresh_status.py:46` potwierdza ten format. Nie można stosować wyłącznie warunku `freshMt5Read == true`.
- Producent przypisuje statusy części botów na podstawie stałej mapy, a nie stanu Harmonogramu.
- Aktualizuje `metrics.trades` i `lastRefresh`, ale nie przelicza całego `ret/maxDd/winRate`. Świeży plik nie czyni wszystkich metryk świeżymi lub potwierdzonymi.
- Dla v-B wpisuje `equity = 4000.0`, czyli przydział, nie odczyt equity bota. Nie etykietować tej kwoty jako wynik brokera.
- Producent mapuje boty po komentarzach; snapshot pozycji nie zawiera magic. Nie mieszać tych danych z autorytatywną tabelą MT5 według magic.
- `positions_get() or []` i `history_deals_get(...) or []` w producencie gubią rozróżnienie błędu i pustego wyniku. Panel musi zachować ten brak dowodu jako ograniczenie źródła.

### Harmonogram i terminal

Odczyt przez `Get-ScheduledTask` i `Get-ScheduledTaskInfo`, bez zmian zadań:

| Zadanie | Stan | Ostatnie uruchomienie, Europe/Warsaw | Kod wyniku |
|---|---|---|---:|
| TQ-HORMUZ-Demo | Ready | 18:58:04 | 0 |
| TQ-HORMUZ-Signal | Disabled | 15:19:04 | 0 |
| TQ-TECHVOL-Demo | Ready | 18:59:05 | 0 |
| TQ-XASSET-Demo | Ready | 19:00:05 | 0 |
| TQ-ALTSPEC-Demo | Ready | 19:01:05 | 0 |
| SHADOW-VB-Daily | Ready | 11:18:15 | 0 |
| TQ-Arena-Refresh | Ready | 18:59:31 | 0 |
| TQ-FundingOI-Collector | Ready | 19:04:16 | 0 |

`Ready` oznacza stan zadania, nie ciągłe działanie procesu ani przyjęcie zlecenia. Dla `Astra Discovery Research` odczyt szczegółów zakończył się `RuntimeException`; późniejszy spis zadań potwierdził istnienie i stan 4 (Running), ale nie ostatni wynik. Nie znaleziono osobnego zadania dla TQ-VB lub LONG HOLD w odczycie nazw zawierających VB/LONG; SHADOW-VB nie jest harmonogramem wykonania TQ-VB.

Proces terminala istnieje: PID 31216, `C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe`. Nie potwierdza to aktualnego konta, połączenia, Algo Trading ani prawa handlu. W P1 nie inicjalizowano połączenia MT5.

## Martwy kod i duplikaty

- Nie ma wystarczających dowodów, aby uznać istniejący moduł za martwy. Brak nasłuchu 8876 nie uzasadnia usunięcia Alpaca.
- `acceptance_test.py` w korzeniu ma 7 linii i deleguje do `scripts.acceptance_test.run`; plik w `scripts/` ma 96 linii. To wrapper i implementacja, nie dwa niezależne testy do scalenia.
- Pythonowy panel Alpaca, historyczny frontend Astry i `site-spotkania` pełnią różne role. Nie usuwać ani migrować ich podczas budowy nowego panelu.
- Dokumenty z września oraz P0 opisują częściowo inne momenty; niniejszy raport koryguje fakty bieżące bez nadpisania historii.

## Nierozstrzygnięte i następny etap

Nie potwierdzono bezpośrednio bieżącego konta MT5, Algo Trading, historycznego equity ani obecnego błędu Alpaca 401. Nie wykonano testów ani niezależnego review. Nie uruchomiono dashboardu.

Propozycja rozwiązania, uwzględniająca te luki: [ARCHITECTURE_PROPOSAL.md](ARCHITECTURE_PROPOSAL.md). P1 kończy się akceptacją tego konkretnego projektu przez Karola; P2–P5 pozostają do wykonania po akceptacji zgodnie z kolejnością briefu.
