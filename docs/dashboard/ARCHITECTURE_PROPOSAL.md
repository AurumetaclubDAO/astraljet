# Dashboard AstralJet — propozycja architektury P1

Data: 13.10.2026. Status: **ZAAKCEPTOWANA PRZEZ KAROLA**. Bezpośrednia akceptacja w rozmowie: „Akceptuję. Ruszamy dalej”. Dodatkowo odczytano komentarz BOSS MAESTRO w Notion potwierdzający zgodę P2–P5. Podstawa: [audyt](AUDIT.md), [backup PASS](BACKUP_VERIFY.md), [brief P0–P5](https://app.notion.com/p/3f8cb4db3956818e9b62c227107a3100).

## Decyzja proponowana

Oddzielny moduł `src/astraljet/dashboard`, FastAPI + uvicorn na **127.0.0.1:8877**, pojedynczy proces API, statyczny HTML/CSS/JS bez Vite i bez CDN. Izolowany Python **3.12** w `.runtime/dashboard-venv`. Dashboard odczytuje wskazane pliki i stan DEMO; nie importuje wykonawców Astry ani modułów TQ. Port 8876 i obecne interfejsy pozostają niezależne.

Uzasadnienie: zastane `.venv` ma Python 3.14 bez zależności; środowisko Alpaca należy do osobnego wykonawcy. Panel o stałych sekcjach nie wymaga toolchainu Node, a statyczne zasoby ułatwiają lokalną pracę bez usług zewnętrznych. FastAPI jest już stosowane w tym repo, lecz nowa aplikacja nie korzysta z jego istniejącego `Service` lub konfiguracji `.env`.

Starszy `MIGRATION_PLAN.md` preferuje jeden frontend. Nowy, wskazany przez Karola zakres budowy dotyczy lokalnego pulpitu TQ na 8877. Propozycja nie zastępuje ani nie migruje Command Center; ewentualne późniejsze scalenie interfejsów wymaga osobnego zakresu.

## Moduły i przepływ

```text
dashboard_config.toml (jawne ścieżki i progi; bez poświadczeń)
   → collectors/{mt5, runners, schedule, risk, arena, funding, alpaca}
   → models/{data_state, snapshot, bot, account}
   → normalizacja + kontrola pochodzenia + redact + snapshot w pamięci
   → api/{app, routes} (wyłącznie GET)
   → web/{index.html, app.js, styles.css} (jeden origin)
```

Pomocnicze: `security.py` (redakcja i dozwolone ścieżki), `config.py` (TOML przez `tomllib`, bez dotenv), `service.py` (koordynacja odczytów i cache), `__main__.py` (sztywne bind/port). Brak importów `astraljet.executor`, `astraljet.alpaca_challenge`, `tq_core`, `gated_order`, runnerów lub producenta Areny.

Wspólny, spójny snapshot ma `snapshot_id`, `generated_at` UTC oraz stan każdego pola. GET-y nie uruchamiają osobnej pełnej rundy odczytów dla każdej karty. Cykliczny odczyt co 45 s, bez nakładania rund; Harmonogram może mieć osobny cache 60 s. UI pokazuje zegar odświeżania i czas źródła w Europe/Warsaw.

I/O ma limity: pliki CSV/JSON kontrolowane rozmiarem i poprawnością; logi od końca, maks. 2000 linii i ograniczenie bajtów; Harmonogram przez dozwoloną listę nazw z timeoutem. Zmiana pliku w czasie odczytu: jedno ponowienie, następnie jawny błąd. Blokujący collector MT5 w kontrolowanym procesie pomocniczym z limitem czasu; przekroczenie czasu zamyka tylko ten proces, nigdy terminal lub runner. Brak automatycznych restartów cudzych usług.

## Kontrakt danych

Każdy wynik: `{value, state, source, as_of, age_s, error}`. Dodatkowo jawne `observed_at`, `unit`, `coverage` tam, gdzie są potrzebne do interpretacji. Czas pomiaru i czas odczytu pliku są rozdzielone.

| Stan | Warunek |
|---|---|
| CONFIRMED / POTWIERDZONE | Poprawny odczyt konkretnego źródła, walidacja schematu i pochodzenia, kompletność dla danego pola, wiek w progu |
| UNCONFIRMED / NIEPOTWIERDZONE | Dane częściowe, stare, niejednoznaczny czas lub wynik wywnioskowany; widoczne źródło i powód |
| MISSING / BRAK | Brak źródła, odmowa gate, timeout/błąd odczytu, brak wymaganej wartości; `value=null` |

Puste, poprawnie pobrane pozycje to potwierdzona pusta lista. `positions_get() is None` to błąd, nie zero pozycji. Pusty `state.json` nie potwierdza zerowego PnL. Niekompletny wynik zbiorczy nie staje się potwierdzony dzięki jednej dobrej składowej. Timestamp znacznie w przyszłości nie daje świeżości; tolerancja przesunięcia zegarów 5 s, dalej UNCONFIRMED.

### Mapa źródło → widget i progi

| Źródło | Widget | Proponowany próg / warunek |
|---|---|---|
| MT5 `account_info`, `terminal_info` | DEMO, saldo, equity, połączenie, Algo Trading | 90 s; pozytywny gate, connected, waluta konta |
| MT5 `positions_get` | Pozycje, floating PnL, liczba pozycji, grupowanie botów | 90 s; gate przed odczytem i ponownie po nim |
| MT5 `history_deals_get` | Zrealizowany PnL dziś, historia zrealizowanego wyniku | 90 s od pobrania, jawne pokrycie zakresu i pełne koszty |
| `signals.csv` czterech runnerów | Ostatnia ewaluacja, sygnał i akcja | 20 min od `eval_time`, nie od mtime; brak sygnału nie oznacza błędu, jeśli ewaluacja była poprawna |
| `state.json` | Dodatkowe pola bota | Tylko rozpoznane pola; obecnie puste obiekty dają BRAK tych pól |
| Logi runnerów | Błędy w dostępnej części ostatnich 24 h | 2000 linii; przy ucięciu „co najmniej N / fragment logu”, nie pełna liczba 24 h |
| `SHADOW-VB/journal_vb.csv` | Oddzielna ostatnia decyzja SHADOW | 30 h od `run_at_utc`, nie utożsamiać z wykonaniem TQ-VB |
| Harmonogram | Stan zadania, ostatni/następny start i kod | 90 s od zapytania; nie interpretować Ready jako Running |
| `risk_config.json` | Budżety i limity | 90 s od udanego odczytu; stara data modyfikacji stałej konfiguracji nie oznacza jej nieaktualności |
| `KILL_SWITCH` | Istnienie blokady | 90 s; potwierdzony brak pliku = nieaktywny, błąd dostępu = BRAK |
| Arena `status.json` | Snapshot/ranking z ograniczeniami | 20 min od `refreshed_at` i osobno `freshMt5Read.readAt`; jakość ustalana per pole |
| CSV funding/OI | Ostatni wiersz per `(source,symbol)` | 30 min; walidacja `error`, wymaganych pól i czasu źródłowego; nie ukrywać nowszego błędu za starszym sukcesem |
| Alpaca | Informacja o integracji | BRAK aktualnej weryfikacji; 401 wyłącznie jako opis historycznego zgłoszenia |
| ATLAS, VEGA, ORION, LUNA, TITAN, NOVA | Pokój decyzyjny | BRAK — nie zidentyfikowano źródła decyzji; bez generowania treści |

## MT5 i granica konta

Warunek wpuszczenia danych do UI: `login ==` numer rachunku DEMO z lokalnej konfiguracji (`.runtime/dashboard/accounts.toml`), `trade_mode == ACCOUNT_TRADE_MODE_DEMO`, serwer zgodny z DEMO (domyślnie VantageMarkets-Demo). Rachunek LIVE i wszystkie inne są odrzucane. Niepowodzenie → `shutdown()` i MISSING; żadnego odczytu pozycji/historii po odrzuceniu gate. Zwracany komunikat nie zawiera salda ani danych odrzuconego rachunku.

Nie wywoływać `login()`, nie podawać loginu/hasła/serwera do inicjalizacji. Jawna ścieżka do istniejącego terminala, kontrola obecności jego procesu przed połączeniem, krótki timeout. Przy niejednoznacznym terminalu lub braku procesu MT5 widget pozostaje BRAK. Przed każdym odczytem i po pobraniu całego snapshotu powtórzyć gate; zmiana konta unieważnia całość i cache.

Ograniczenie SDK: [`initialize()` może uruchomić terminal i korzysta z ostatniego konta](https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py). Sam brak `login()` nie gwarantuje braku tego efektu. Kontrola procesu zmniejsza ryzyko, ale nie usuwa wyścigu zamknięcia terminala pomiędzy kontrolą a inicjalizacją. Nie deklarować absolutnego „attach only”; w P2 trzeba udokumentować zachowanie na tej maszynie. P1 nie wywoływał inicjalizacji.

Mapowanie magiców z briefu zachowane w konfiguracji z pochodzeniem. Pięć mapowań ma dowód w kodzie runnerów; LONG HOLD wymaga dowodu w odczycie brokera. Nieznane magic → „Inne/ręczne”. SHADOW-VB jako badanie nie jest siódmym rachunkiem/botem wykonawczym.

## PnL, equity i ryzyko

- „PnL dzisiaj”: transakcje i koszty zaksięgowane od północy Europe/Warsaw do teraz, po przeliczeniu granic na UTC; dodatkowo jawny bieżący floating. Nie nazywać sumy zmianą equity od północy, bo obejmuje floating pozycji otwartych wcześniej.
- Ująć profit, commission, swap, fee bez podwójnego naliczania. Wpłaty/wypłaty i korekty salda oddzielić od wyniku handlowego. Atrybucja zamknięć według magic oraz `position_id`/historii wejścia; brak pełnej historii powoduje UNCONFIRMED, nie przypisanie na siłę. API historii rozróżnia przedział, order ticket i position: [dokumentacja MT5](https://www.mql5.com/en/docs/python_metatrader5/mt5historydealsget_py).
- Dzienne wykorzystanie limitu = `max(0, -(realized_today + floating_now)) / (sleeve_usd * daily_loss_pct / 100)`. Wyraźnie oznaczona metryka informacyjna; nie zmienia istniejącego `risk_gate` i nie deklaruje identyczności z jego algorytmem, który filtruje po komentarzach i tylko niektórych dealach.
- Potwierdzić walutę konta przed porównaniem kwot z limitami USD. Przy innej walucie i bez kursu konwersji wykorzystanie = BRAK.
- Nie sumować lotów różnych instrumentów jako ekspozycji pieniężnej. Ekspozycja nominalna wymaga `symbol_info`, contract size i konwersji do waluty konta; bez nich pokazać liczby pozycji i loty per instrument, a wartość pieniężną jako BRAK. To odrębna wielkość od ryzyka do SL i przydziału sleeve.
- Historia deali daje krzywą zrealizowanego PnL; nie daje historycznego equity. Wykres nazwać zgodnie z dostępnymi danymi. Historyczne equity = BRAK, dopóki nie ma snapshotów. Ewentualny zapis nowych pomiarów wymaga jawnego, lokalnego formatu i nie odtwarza przeszłości; nie jest częścią tej propozycji.
- Arena: świeży snapshot jest potwierdzeniem odczytu pliku, nie automatycznym potwierdzeniem wszystkich metryk brokera. `freshMt5Read` jako obiekt jest walidowany strukturalnie; brak `trade_mode` i ograniczenia producenta są widoczne. `ret/maxDd/winRate` bez pochodzenia pozostają UNCONFIRMED; `equity` będące budżetem ma etykietę „Przydział”.

## API, sekrety i UI

GET: `/api/health`, `/api/summary`, `/api/bots`, `/api/positions`, `/api/risk`, `/api/arena`, `/api/funding`, `/api/schedule`, `/api/alpaca`. `/api/summary` udostępnia spójny snapshot do odświeżania całego UI. Żaden route nie steruje innym procesem. Metody inne niż GET odrzucane; należy wyłączyć domyślne docs/OpenAPI, jeśli dodają HEAD do rejestru tras. Zasoby statyczne również przez jawne trasy GET.

Oczekiwane błędy źródła → HTTP 200 z MISSING i bez surowego wyjątku. Nieznana trasa → 404, niedozwolona metoda → 405. Nie ukrywać awarii aplikacji jako „potwierdzonych” danych; nieoczekiwany wyjątek zwraca ogólny, zredagowany błąd, a health ujawnia degradację.

Bind wyłącznie `127.0.0.1`, brak CORS *, kontrola nagłówka Host (localhost/127.0.0.1), bez debug i stack trace. `Cache-Control: no-store`, lokalne zasoby i CSP. Brak żądań do internetu z przeglądarki. Rendering danych przez `textContent`, nie `innerHTML`.

Sekrety: schematy dozwolonych pól + rekurencyjny `redact()` dla tekstów/struktur + ograniczone komunikaty błędów. Maskowanie kluczy, tokenów, haseł, credential URLs i długich ciągów wymagane, lecz sam regex nie daje pełnej gwarancji. Nie przesyłać surowych logów i dowolnych obiektów do UI. Dozwolone tylko sprawdzenie bool obecności jawnie wskazanych zmiennych; żadnego dotenv ani odczytu `.env`. Nie przekazywać sekretów odziedziczonych przez proces do UI lub raportów.

UI: polskie etykiety, tło #0B0F17, akcent #7C5CFF, 12 kolumn, promień 16 px, systemowy font, ruch <=200 ms i reduced-motion. Sześć kart botów, pozycje, wynik zrealizowany, risk, Arena, funding/OI, Alpaca i sześciu agentów. Każda metryka ma źródło/czas/stan; tooltip dostępny klawiaturą. Baner Algo Trading oparty na aktualnym `terminal_info`, nie na starym błędzie. Komunikat KILL_SWITCH mówi o wykrytej blokadzie TQ, nie o potwierdzonym zatrzymaniu wszystkich procesów. Kolor nie jest jedynym nośnikiem informacji.

## Launchery i odwrócenie zmian

`start_dashboard.bat` wywołuje dedykowany launcher PowerShell z katalogu projektu; środowisko `.runtime/dashboard-venv`, Python 3.12. Instalacja zależności jako osobny jawny krok, nie przy każdym starcie. Zależności przypięte po weryfikacji zgodności; nie modyfikować `requirements-alpaca.*`.

Start sprawdza port 8877 i tożsamość poprzedniego procesu; nie zabija właściciela zajętego portu. Proces w tle z `-WindowStyle Hidden`. `stop_dashboard.bat` zatrzymuje wyłącznie własny proces, zweryfikowany przez PID, czas startu i ścieżkę; po zmianie tożsamości odmawia. Brak zadań autostartu.

Rollback: zatrzymać tylko dashboard, zachować jego raporty, odłączyć nowe launchery/moduł. Nie przywracać całego starego katalogu na działający projekt i nie cofać baz. Nie zmieniać Desktop, terminala, Harmonogramu, KILL_SWITCH, wykonawców lub `.env`.

## Plan testów i odbioru P2–P5

1. Gate MT5: dozwolone DEMO, rachunek LIVE, obcy login, zły trade_mode/serwer, brak konta, przełączenie w trakcie odczytu, disconnect/timeout; shutdown i brak odczytu chronionych danych po odmowie. Testy na mockach, bez transakcji.
2. Granice modułów: AST importów i wywołań, zakaz brokerów, `.order_send`, `.order_check`, `.submit_order`, dynamicznych importów wykonawców, HTTP mutacji, poleceń zmieniających zadania i zapisu KILL_SWITCH. Test przechwytuje dostęp do plików z sekretami, również przez pathlib. Kontrola wszystkich tras oraz prób metod POST/PUT/PATCH/DELETE/HEAD/OPTIONS.
3. Dane: null vs zero/pusta lista, trzy stany, granice wieku, zegar w przyszłości, DST Warszawa, błędny JSON/CSV, częściowy zapis, brak pliku/odmowa dostępu, ograniczenie logu, deduplikacja deali i kosztów, obca waluta.
4. Arena: rzeczywisty format obiektu `freshMt5Read`, brak/nieprawidłowa wartość, przeterminowane readAt, świeży plik ze starymi metrykami, brak trade_mode, budżet v-B zamiast equity. Funding: najnowszy wiersz z błędem, uszkodzona wartość, cztery pary źródło/symbol.
5. Redakcja: syntetyczne klucze/hasła, nested JSON, teksty HTML i błędy; brak wycieku w API, UI i logu. Test XSS/Host/CORS/bind.
6. Smoke API: wszystkie endpointy GET zwracają 200 i poprawny kontrakt również przy wyłączonych źródłach; timeout nie blokuje innych kolektorów, cache wygasa; brak otwartego portu poza loopback.
7. Playwright: 1440, 1024, 390 px; brak przycisków sterowania i poziomego overflow, badge w każdej karcie, widoczność braków, obsługa klawiatury, kontrast AA, aktualizacja bez przeładowania. Screenshoty w `docs/dashboard/screenshots/`, wyłącznie z danych bez sekretów.
8. Regresja: istniejące `tests/` w zgodnym środowisku oraz `TQ-Common/tests`. Najpierw przegląd testów pod kątem I/O, potem izolowane katalogi tymczasowe/cache pod `D:\Astra Jet`, `PYTHONDONTWRITEBYTECODE=1`; bez zapisu do zewnętrznych runnerów i bez połączeń brokerskich. Nie uruchamiać `scripts/acceptance_test.py`, który czyta Settings i kontaktuje się z Alpaca.
9. Odbiór rzeczywistego panelu: uruchomienie tylko dashboardu, dowód źródeł i odmowy konta poza DEMO, zrzuty, pełny wynik testów, kontrola zakresu zmian, README i ROLLBACK. Zielone mocki nie zastępują odbioru MT5. Niezależny review wymagany do końcowego statusu „Zrobione”.

## Konkretny zakres do akceptacji

Akceptacja tego dokumentu pozwala przejść do implementacji P2–P5: FastAPI + statyczny frontend na 8877, nowe środowisko Python 3.12, źródła i reguły jakości powyżej, skorygowane znaczenie Areny/Alpaca/equity/KILL_SWITCH. Nie obejmuje zleceń, zmian ryzyka, naprawy botów, migracji, udostępnienia w sieci, publikacji lub wysyłki wiadomości do innych osób/agentów.

Karol zatwierdził architekturę po P1 i polecił kontynuować. Nie wykonano implementacji, instalacji zależności ani startu serwera w samym P1; kolejne prace dokumentuje README i raport odbioru.
