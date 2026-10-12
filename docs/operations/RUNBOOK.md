# Runbook — lokalne badania i odczyt AstralJet

Stan: 20.09.2026. Nie jest instrukcją uruchomienia live ani zastanego DEMO MT5.

## Odczyt bez migracji

W PowerShell, z katalogu `D:\Astra Jet`:

```powershell
& '.\.venv\Scripts\python.exe' -m astraljet.cli --state-dir 'D:\Astra Jet\.runtime\quickstart-2026-09-19' system inspect
& '.\.venv\Scripts\python.exe' -m astraljet.cli --state-dir 'D:\Astra Jet\.runtime\quickstart-2026-09-19' strategy list
& '.\.venv\Scripts\python.exe' -m astraljet.cli --state-dir 'D:\Astra Jet\.runtime\quickstart-2026-09-19' strategy lineage --strategy-id 'STRAT-5fb2fbd40d9f4842afdcaa2b2898a411' --version 1
```

Identyfikator powyżej został odczytany z istniejącej bazy; strategia pozostaje `needs_input`. Dane w `.runtime/state` nie zostaną automatycznie dołączone. `system inspect`, `strategy list`, `strategy lineage`, `status` i `audit export` otwierają bazę tylko do odczytu. Brak pliku zwraca błąd, nie nowy pusty rejestr. Opcjonalne `audit export --output` zapisuje eksport, lecz nie zmienia bazy; pełny eksport traktuj jako lokalny materiał prywatny.

`system inspect` pokazuje **wybrany lokalny rejestr**, nie całą platformę. `mode=READ_ONLY` opisuje odczyt, nie stan istniejących botów. `broker_connection=not_checked` nie oznacza braku działającego MT5. `execution_authorized=false` zabrania traktowania wyniku zapytania jako mandatu.

## Jak czytać lineage

- `exact`: rodzic wskazany przez ID i konkretną zapisaną wersję.
- `pinned`: natywny zapis D1 wskazuje ID, rewizję i hash; ten widok nie pobiera ani nie weryfikuje archiwum. Nie oznacza `exact` ani zgody na wykonanie. Plik lokalnego snapshotu nie może deklarować tego rodzaju referencji.
- `unversioned_single`: zapis nie ma wersji rodzica, obecnie istnieje tylko jeden kandydat. To **nie** dowód zamrożonego pochodzenia.
- `ambiguous`: jest kilka wersji; program żadnej nie wybiera.
- `missing` / `invalid`: brak rekordu, wersji lub poprawnej referencji.

Wspólne źródło lub DATA nie dołącza wyników innej strategii do profilu. BACKTEST, LATER_DATA_REPLAY, PAPER_CONTINUOUS i BROKER_DEMO mają osobne liczniki; historyczny replay nie jest ciągłym forward testem. Metryki, surowe teksty, lokalizatory, rachunki i klucze nie są polami nowego read modelu. Stary pełny eksport audytu ma szerszy, prywatny zakres.

## Snapshot do widoku Pochodzenie

W istniejącym frontendzie dodano lokalny kod strony `/research/lineage` i link **Badania → Pochodzenie**. Nie jest jeszcze opublikowany. Strona nie montuje ResearchDesk ani łącznika MT5; jej nowy endpoint obsługuje wyłącznie GET. Istniejąca otoczka aplikacji/czat zachowuje własne funkcje, których ten widok nie wywołuje.

Przygotuj nowy plik (zmień `v2` przy każdym kolejnym eksporcie):

```powershell
& '.\.venv\Scripts\python.exe' -m astraljet.cli --state-dir 'D:\Astra Jet\.runtime\quickstart-2026-09-19' system snapshot --registry-id quickstart-2026-09-19 --output 'D:\Astra Jet\.runtime\exports\lineage-quickstart-2026-09-19-v2.json'
& '.\.venv\Scripts\python.exe' -m astraljet.cli --state-dir 'D:\Astra Jet\.runtime\state' system snapshot --registry-id alpaca-state --output 'D:\Astra Jet\.runtime\exports\lineage-alpaca-state-2026-09-19-v2.json'
```

Eksport nie tworzy/migruje bazy. Publikacja kompletnego pliku jest nienadpisywalna także przy współbieżnym zapisie; wymaga systemu plików obsługującego hard link. Przy odmowie nie ma fallbacku nadpisującego plik. Pliki `v1` zostały już przygotowane i sprawdzone w etapie 02.

Wybierz jeden plik w polu **Rejestr lokalny · snapshot**. Nowy wybór zastępuje podgląd, nie scala rejestrów. Moduł odczytuje plik w przeglądarce bez POST, localStorage, zapisu na serwerze lub wywołania AI. Odświeżenie strony usuwa lokalny podgląd. Format ma ścisłą listę pól, limit 4 MiB / 5000 wersji / 20000 relacji. Nie importuj pełnego eksportu audytu ani konfiguracji z sekretami; obce pola są odrzucane.

`registry_id` to **etykieta podana autorowi eksportu**, nie podpis ani dowód tożsamości bazy. Zapisany SHA-256 służy porównaniu plików, nie potwierdza ich autora. Źródło lokalnego pliku pozostaje nieuwierzytelnione; widok nie udziela zgody na handel.

Sekcja D1 czyta jeden spójny SELECT dla zalogowanego użytkownika, maksymalnie 1000 najnowszych bieżących rekordów `material/candidate/experiment`. Limit jest jawnie oznaczony. Archiwalne `revision`, inne moduły, osadzone raporty i rekordy wykonawcy nie są osobnymi węzłami tego widoku. Rewizja D1 od 0 nie jest wersją STRAT od 1. Bez zapisanej wersji rodzica relacja pozostaje `unversioned`; brak rodzica znaczy **brak w wybranym odczycie**, nie brak w całym systemie.

Odczyty starsze niż 24 godziny oraz czas ponad 5 minut w przyszłości mają ostrzeżenia. Przycisk „Odśwież D1” nie odświeża lokalnego pliku. Kontrola świeżości jest informacyjna, nie zastępuje kontroli wykonawcy.

## Przegląd i zamrożenie nowych eksperymentów — kod lokalny etapu 03

Poniższy opis dotyczy zmienionego kodu istniejącej aplikacji, **nie jeszcze opublikowanej strony**. Nie wykonano tych operacji na produkcyjnym D1. Zamrożenie nadal korzysta z istniejącej kolejki badań, więc nie jest operacją samego podglądu ani zgodą na nowe koszty/uruchomienie workera.

1. Otwórz bieżącą kartę kandydata. Przegląd przesyła jej `revision`, sprawdzone reguły i decyzję o założeniach. Serwer sprawdza cytaty, archiwizuje źródło oraz wcześniejszą kartę i zapisuje nową rewizję karty w jednej transakcji.
2. Karta pokazuje przypięte ID i rewizję źródła. Starszy przegląd bez takiego przypięcia wymaga ponownego sprawdzenia i zapisu. Nie uzupełniaj go automatycznie najnowszym źródłem.
3. Zamrożenie wymaga tej samej rewizji i zapisanych reguł. Niezapisane zmiany, konflikt rewizji, brak zaakceptowanych założeń lub brak poprawnego archiwum blokują operację. Plan przechodzi dotychczasową walidację; limity i wartości domyślne nie zostały zmienione.
4. Nowy eksperyment ma pin źródła i kandydata, hashe reguł/planu oraz stały protokół. Zmiana bieżącego źródła nie podmienia przypiętej starej wersji. Ponowienie identycznego zamrożenia zwraca to samo ID. Kolejka jest oddzielną operacją z istniejącą deduplikacją; po błędzie kolejki ponów żądanie, nie twórz ręcznie kopii eksperymentu.
5. Worker badawczy sprawdza archiwa przed wydaniem zadania i ponownie przed przyjęciem wyniku. Błąd przy wydaniu oznacza zablokowane zadanie bez lease. Błąd przy zapisie wyniku odrzuca zapis; dotychczasowe wygasanie lease/obsługa awarii pozostają bez zmian. Te kontrole nie dotyczą łącznika zleceń MT5 i go nie uruchamiają.

Komunikat o konflikcie oznacza: odśwież kartę, porównaj zmiany i ponownie sprawdź reguły. Brak lub niezgodny hash archiwum oznacza: wstrzymaj badanie i ustal przyczynę; nie podstawiaj bieżącej wersji, nie usuwaj `provenance` i nie edytuj archiwum, aby wymusić przejście. Odrzucenie eksperymentu lub skierowanie do dalszych badań pozostają możliwe; uszkodzone pochodzenie nie pozwala zatwierdzić propozycji DEMO ani zwolnić holdoutu.

Zwykły zapis może dopisać wynik/decyzję, lecz nie zmieni definicji przypiętego eksperymentu. Nowe reguły/plan wymagają nowego eksperymentu. Starsze eksperymenty bez pinów zachowują dotychczasową obsługę i status legacy — ten etap ich nie audytuje ani nie podnosi ich wiarygodności.

Przypięcie zapewnia kontrolę spójności zapisów, nie podpis autora, ocenę jakości danych rynkowych, dowód rentowności lub mandat handlowy. To zabezpieczenie aplikacyjne; istniejąca tabela D1 nie otrzymała triggerów niezmienności z lokalnego rdzenia Python. Przyszłe wdrożenie musi objąć razem frontend i API, ponieważ zamrożenie wymaga teraz pól `revision` i `spec`.

## Nowe bazy i aktualizacja schematu

### Kontrola wejść przed eksperymentem

`experiment inspect-inputs` odczytuje jawne wersje STRAT i DATA, także z dwóch osobnych rejestrów. Nie inicjalizuje ani nie migruje baz, nie odczytuje `.env`, nie odpytuje brokera, nie uruchamia backtestu i nie zmienia rekordów. Jawne pliki CSV/metadanych są czytane raz do ograniczonego bufora (50 MiB / 1 MiB); hash i kontrola dotyczą tych samych bajtów.

Z `D:\Astra Jet`, przy użyciu sprawdzonego lokalnego Pythona 3.12:

```powershell
$env:PYTHONPATH='D:\Astra Jet\src'
& 'C:\Users\karol\AppData\Local\Python\pythoncore-3.12-64\python.exe' -m astraljet.cli --state-dir '.runtime/quickstart-2026-09-19' experiment inspect-inputs `
  --strategy-id STRAT-5fb2fbd40d9f4842afdcaa2b2898a411 --strategy-version 1 `
  --data-state-dir '.runtime/state' --data-id DATA-1e44487b0074425f959c2758c497c046 --data-version 1 `
  --csv '.runtime/data/alpaca_crypto_us_full_2015-01-01_2026-09-19.csv' `
  --metadata '.runtime/data/alpaca_crypto_us_full_2015-01-01_2026-09-19.csv.metadata.json' `
  --start 2021-01-01 --is-end 2024-12-31 --oos-start 2025-01-01 --end 2026-09-18 `
  --ma-window 200 --slope-lookback 20 --signal-weekday 6 `
  --output '.runtime/exports/btc-eth-inputs-2026-09-20-v2.json'
```

`v1` już istnieje; przy kolejnym odczycie użyj nowej nazwy albo pomiń `--output`, by zobaczyć JSON w terminalu. Plik wynikowy jest nienadpisywalny. Kod wyjścia 0 oznacza **wykonaną inspekcję**, nie gotowość badania: wynik zawsze ma `DRAFT_BLOCKED`, `can_freeze=false`, `execution_authorized=false`. Nie ma przełącznika zatwierdzającego.

Parametry kalendarza to propozycja diagnostyczna. Status `checked_local_structure` nie potwierdza ceny realizacji, taryfy rachunku, praw dostępu, danych point-in-time, nietkniętego OOS ani zgodności silnika z regułami. Brak poprawnego hashu, luki i duplikaty dają jawne findings i wygaszają wyliczone granice sygnału. Pole `observation_sha256` identyfikuje odczytaną treść rekordu; nie jest podpisem bazy. Wersje źródłowe STRAT/DATA pozostają oddzielne, bez dopisania relacji.

Propozycja badawcza i braki implementacji są opisane w [karcie BTC/ETH v0.2](../experiments/BTC_ETH_EXPERIMENT_PACKET_v0.2.md). Nie podawaj JSON propozycji do `experiment freeze`.

### Zapisy i migracje

`init` oraz polecenia zapisujące mogą inicjalizować/migrować **jawnie wybraną** bazę. Kod etapu 13 obsługuje schemat 7. Nie wywołuj ich na działającym runtime tylko po to, aby sprawdzić status. Najpierw audyt ścieżki, sprawdzony snapshot i plan odtworzenia. Na 24.09 rejestr `quickstart-2026-09-19` po backupie podniesiono z 3 do 7; pozostałych baz nie migrowano. Stany 1/3/4 opisane w wcześniejszych raportach są historyczne.

Nowa wersja rekordu jest dopisywana pod nową parą `(record_id, version)`. Próba UPDATE, DELETE albo REPLACE starej wersji ma zakończyć się błędem; nie obchodzimy go wyłączaniem triggerów.

## Dane Alpaca

Każde pobranie otrzymuje nową nazwę CSV. Istnienie CSV **lub** jego `.csv.metadata.json` blokuje ponowne użycie nazwy przed żądaniem HTTP. Wyścig zapisu nie nadpisuje konkurencyjnego pliku.

Kompletny snapshot ma oba pliki oraz zgodny `csv_sha256`. Awaria między publikacją CSV i metadanych może pozostawić niekompletną parę; zachowaj ją do diagnostyki i użyj nowej nazwy. Nie uznawaj takiego pobrania za udane. Zbiór nadal wymaga jakości danych, czasu dostępności oraz osobnego modelu kosztów. Brak wolumenu/liczby transakcji/VWAP jest pustym polem CSV i licznikiem braków w metadanych v2.

## Weryfikacja kodu

### Tygodniowy model — tylko mechanika syntetyczna

Nowe `lab/weekly_portfolio.py` i `lab/portfolio_ledger.py` nie są uruchamiane przez istniejące `run backtest` ani workera. Nie przełączaj starych eksperymentów na tę implementację na podstawie podobnego opisu reguł. Model wymaga jawnego fingerprintu kodu i zwraca wyłącznie niezakwalifikowany wynik. Od etapu 18 osobne `weekly-recorded` może utrwalić go jako RUN, bez mandatu.

Weryfikacja z `D:\Astra Jet` nie wymaga wskazania bazy, kluczy lub danych Alpaca:

```powershell
$env:PYTHONPATH='D:\Astra Jet\src'
& 'C:\Users\karol\AppData\Local\Python\pythoncore-3.12-64\python.exe' -m unittest discover -s tests/unit -p test_portfolio_ledger.py -v
& 'C:\Users\karol\AppData\Local\Python\pythoncore-3.12-64\python.exe' -m unittest discover -s tests/unit -p test_weekly_portfolio.py -v
```

Zmienione pliki po załadowaniu modułu wymagają nowego procesu Pythona. Nie podmieniaj przypiętego hashu eksperymentu, aby ominąć błąd `engine_hash_mismatch`/`loaded_code_changed`. Testy i fingerprint sprawdzają zgodność implementacji, nie rentowność ani uwierzytelnioną akceptację parametrów. Szczegóły i ograniczenia: [etap 05](ETAP_05_2026-09-20.md).

### Adapter zamrożonego modelu — etap 06

`experiment inspect-weekly` sprawdza przypięty EXP bez wyliczania portfela.
`run weekly-offline` liczy wszystkie zadeklarowane scenariusze i może zapisać nowy
raport JSON. Nie zapisuje RUN/EVENT, nie podłącza witryny ani Wykonawcy.
Nie używaj legacy `run backtest` jako zastępstwa.

Kontrakt wymaganych wersji, reguł i parametrów opisano w
[kontrakcie CLI](../../specs/001-build-astra-jet/contracts/cli.md#zamrożony-model-tygodniowy--etap-06).
Reguły i binding muszą istnieć w EXP przed obliczeniami; CLI nie ma opcji ich
nadpisania. Podobny opis strategii lub `ready` bez zgodnego profilu nie wystarcza.
Powiązanie hashem sprawdza zgodność, nie uwierzytelnia zgody Karola.

Na 20.09.2026 nie istnieje zatwierdzony rzeczywisty EXP tej ścieżki. Rejestry
`quickstart-2026-09-19` i `state` pozostały osobne; nie uruchamiaj inicjalizacji,
importu lub freeze tylko po to, aby usunąć blokadę. Propozycja v0.2 nadal czeka na
decyzje reguł, kosztów, danych i miejsca rejestru. Nie zmieniaj jej `approved` ręcznie.

Bezpieczny test samego adaptera, bez danych rynkowych i poświadczeń:

```powershell
$env:PYTHONPATH='D:\Astra Jet\src'
& 'C:\Users\karol\AppData\Local\Python\pythoncore-3.12-64\python.exe' -m unittest tests.integration.test_weekly_experiment -v
```

Test tworzy wyłącznie tymczasowe rekordy i syntetyczne ceny. Raport poprawnej próby
ma `OFFLINE_UNQUALIFIED`, nie `passed`; hipoteza i niezależna reprodukcja nie są
ocenione. Istniejący plik wyjściowy jest odrzucany; używaj nowej nazwy. Limit CSV:
50 MiB, raportu tej ścieżki: 64 MiB. Zmiana kodu wymaga nowego procesu i nowego
zamrożonego planu, nie podmiany hashu starego EXP.

### Zapis wyników tygodniowych — etap 18

Po zatwierdzeniu konkretnego planu i zapisaniu zamrożonego EXP można użyć
`run weekly-recorded`. To operacja zapisująca do jawnie wybranego rejestru;
nie uruchamiaj jej tylko w celu sprawdzenia połączenia. Najpierw sprawdź
ścieżkę i backup. Wymagany aktualny schemat z ochroną historii; komenda nie
migruje bazy. Dokładną składnię podaje
[kontrakt CLI](../../specs/001-build-astra-jet/contracts/cli.md#trwały-zapis-modelu-tygodniowego--etap-18).

Na 24.09.2026 etap 18 sprawdzono wyłącznie na syntetycznych danych. Zgoda
na `registry:sync` nie jest zgodą na parametry planu BTC/ETH. Nie zmieniaj
`approved`, nie kopiuj fixture do produkcji i nie podmieniaj hashy starego EXP.

Wyniki wszystkich wariantów trafiają do jednej transakcji, po RUN/EVENT na
wariant oraz manifest. Zachowaj klucz serii i receipt CLI. Ponowienie tego
samego żądania odczytuje już zapisany wynik (`created=false`); **nie sprawdza
ponownie aktualności CSV**. Nowy klucz uruchamia nowe obliczenie i walidację.
Nie powstaje automatycznie ocena `passed`, REVIEW, mandat ani synchronizacja.
Główne metryki RUN są z OOS; pole kosztu RUN dotyczy pełnego okresu strategii.

`run weekly-export --idempotency-key KEY --output NEW.json` odtwarza cały
raport ze zgodnych RUN bez CSV i bez zapisu do SQLite. Plik można odczytać
w istniejącym Analytics. Flagi offline w raporcie opisują obliczenie przed
zapisem; zapis potwierdza receipt oraz manifest, nie zmieniona etykieta raportu.
Pełne wyniki pozostają lokalne, a osobna synchronizacja obejmuje tylko metadane.

Bezpieczne testy w katalogach tymczasowych:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest tests.integration.test_weekly_recorded tests.integration.test_weekly_experiment -q
& 'C:\Users\karol\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' `
  --experimental-strip-types scripts/check_weekly_site_contract.mjs '.runtime/command-center-release-20260920'
```

Druga komenda sprawdza parsery rzeczywistego checkoutu witryny offline, nie
produkcyjne API, D1 lub DOM. Dowody i ograniczenia: [etap 18](ETAP_18_2026-09-24.md).

### Analytics — raport z lokalnego silnika (etap 08)

Otwórz istniejący [Analytics](https://tradebot-astra-pro.solyg.chatgpt.site/command/analytics).
Wybierz raport JSON przez „Raport JSON AstralJet”. Plik pozostaje tylko w pamięci
strony, bez wysyłki na serwer i bez zmian D1 lub lokalnego rejestru.

Istniejący raport diagnostyczny jest tutaj:
`D:\Astra Jet\.runtime\exports\btc-eth-inputs-2026-09-20-v1.json`.
Pokaże 4174 wiersze i osiem blokad; nie ma obliczonego wyniku.
`weekly-offline-report-v1` z istniejącego CLI pokaże inspekcję albo wszystkie
scenariusze wyniku. Warianty wybiera się jawnie, domyślny zakres to OOS.
Nie wczytuj propozycji eksperymentu jako raportu — zostanie odrzucona.

„Wyczyść podgląd”, opuszczenie Analytics lub przeładowanie strony usuwa odczyt.
Raport nie jest przywracany po ponownym wejściu. Nie wybieraj `.env`, kluczy,
baz SQLite lub CSV; czytnik akceptuje wyłącznie wspierany JSON, do 64 MiB.
Zgodny hash sprawdza integralność pliku, nie autentyczność zgody ani rentowność.
Brak Sharpe/PF/Monte Carlo jest jawny. Wyniki fixture `weekly-synthetic.json`
służą wyłącznie testom oprogramowania, nie ocenie rynku.

Pełny stan publikacji, testy i ograniczenia: [etap 08](ETAP_08_2026-09-20.md).

### Lokalny test materiałów — bez AI (etap 09)

Inspektor nie wymaga uruchomienia `START_ASTRA_BADANIA.cmd`, workera lub MT5.
Korzysta z istniejącego środowiska badań. Pierwszy raport już istnieje;
następny można uzyskać pod nową nazwą:

```powershell
& 'C:\Users\karol\AppData\Local\AstraResearch\.venv\Scripts\python.exe' `
  'C:\Users\karol\Documents\Claude\Projects\Trading\astra_site\research\discovery\inspect_material.py' `
  --catalog 'D:\Astra Jet\docs\KATALOG_PLIKOW_LOKALNYCH.csv' `
  --output 'D:\Astra Jet\.runtime\exports\material-inspection-2026-09-20-v2.json'
```

Zamiast `--catalog` można podać `--file 'D:\ścieżka\materiał.pdf'` i opcjonalnie
`--expected-sha256 HASH_Z_KATALOGU`. Wyniki i ograniczenia opisuje
[etap 09](ETAP_09_2026-09-20.md). Nie traktuj kodu wyjścia 3 jako awarii eksportu:
oznacza raport z blokadą lub potrzebą przeglądu. Kod 2 oznacza błąd wywołania/zapisu.
Nie ponawiaj płatnej kolejki na podstawie samego odczytu pliku.

### Cały lokalny rdzeń — testy

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -q
```

Testy używają katalogów tymczasowych, odpowiedzi testowych i syntetycznych danych; nie składają zleceń i nie kupują danych/API. Nie są dowodem rentowności. Sprawdzono też Python 3.12.10 z `PYTHONPATH=D:\Astra Jet\src`; istniejący `.venv` korzysta z Python 3.14.

Stan GitHub, aktywnego MT5 i innych baz sprawdzaj osobno według [inwentarza](../../CURRENT_ASTRA_INVENTORY.md). Nie uruchamiaj `start_connection`, webhook workerów ani komend arm/start w ramach testu samego CLI.

## Podpisana kopia metadanych w D1 — etap 13

Lokalne poprawki REVIEW etapu 14 nie zmieniają tego kontraktu ani zakresu
połączenia; raporty kontrolne i REVIEW nie są przesyłane do D1.

Połączenie działa **na żądanie**, nie w harmonogramie. Źródło: `.runtime/quickstart-2026-09-19`, kopia: `local:quickstart-2026-09-19`. Nie wysyła payloadów, plików źródłowych, świec ani pełnej SQLite. Nie steruje badaniami ani handlem. Inne bazy pozostają osobne.

Polecenia z `D:\Astra Jet` (sekrety wyłącznie w prywatnym pliku):

```powershell
# Odczyt historii transferów; bez migracji i żądania sieciowego.
& '.\.venv\Scripts\python.exe' -m astraljet.cli --state-dir '.runtime/quickstart-2026-09-19' registry sync-status

# Nowa, podpisana kopia bieżących metadanych.
& '.\.venv\Scripts\python.exe' -m astraljet.cli --state-dir '.runtime/quickstart-2026-09-19' registry sync-push `
  --registry-id 'quickstart-2026-09-19' `
  --connection-file 'C:\Users\karol\AppData\Local\AstralJet\registry-sync\astraljet-registry-connection.json'
```

Jeżeli zapisany transfer ma `retryable_failure`, ponów **tę samą paczkę** dodając `--batch-id ID_Z_SYNC_STATUS`. Zachowa treść i użyje nowego podpisu/nonce. Gdy jest już `acknowledged`, zwróci oryginalny ACK lokalnie bez ponownej wysyłki. `conflict` i `rejected` wymagają diagnozy — nie usuwaj outboxa ani nie zmieniaj zapisanej treści.

Pliku połączenia nie wklejaj do czatu, nie otwieraj jako snapshotu i nie dodawaj do Git. Katalog poza repo ma chronione uprawnienia. Parowanie tworzy nowy klucz; nie klikaj ponownie tylko w celu odświeżenia metadanych. Wcześniejszych plików pobranych i urządzeń nie usuwano automatycznie.

[Data Center](https://tradebot-astra-pro.solyg.chatgpt.site/command/data) pokazuje godzinę przyjęcia, rejestr i liczbę wersji. „Zobacz rekordy i relacje” otwiera kopię z D1. Po 5 minutach bez nowej paczki transport może pokazać starszy odczyt — nie dowodzi to awarii lokalnego procesu. Status transportu nie jest statusem badania.

Backup sprzed pierwszej migracji: `.runtime/backups/registry-sync-20260924T013040422371Z/astraljet.sqlite3`; obok jest `verification.json` z kontrolą historii. Nie nadpisuj bieżącej bazy backupem podczas pracy; przy odtwarzaniu najpierw sprawdź procesy, zachowaj aktualny stan i uzgodnij dokładny zakres. Dowody ACK, wydanie i ograniczenia: [etap 13](ETAP_13_2026-09-24.md).

## Krytyk AJ-08 — lokalny REVIEW, etap 14

Kontrola wymaga dwóch różnych, ukończonych RUN tego samego zamrożonego EXP oraz
rzeczywistego raportu z odrębnego obliczenia. Nie kopiuj wyników RUN do nowego
JSON tylko po to, aby uzyskać `verified`. Zgodny hash nie dowodzi niezależności.

Po przygotowaniu rzeczywistych danych wejściowych użyj składni opisanej w
[kontrakcie CLI](../../specs/001-build-astra-jet/contracts/cli.md#review--lokalna-kontrola-dowodów-etap-14)
i [kontrakcie raportu](../../specs/001-build-astra-jet/contracts/independent-check-v1.md).
To operacja zapisująca wyłącznie do jawnie wskazanego rejestru. Nie wymaga
sekretów brokera ani kluczy AI; nie umieszczaj ich w raporcie lub `--evidence`.

Brak dowodów pozostaje `unverified` z listą powodów. Błędny format/hash raportu
daje błąd walidacji. Po uzupełnieniu danych użyj nowego klucza idempotencji;
identyczny klucz wolno ponawiać wyłącznie z identycznym pakietem wejściowym.
Nie usuwaj starego REVIEW i nie podmieniaj jego hashu lub etykiety werdyktu.

Nowa decyzja ryzyka odmawia awansu starego REVIEW bez kompletnego pakietu
kontrolnego. To nie zmiana aktualnego mandatu ani zatrzymanie działającego DEMO.
Nie oznacza wdrożenia pełnego Risk Management zgodnego z aktualną polityką.

Bezpieczny test implementacji, w katalogach tymczasowych:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest tests.contract.test_review tests.contract.test_review_integrity tests.contract.test_independent_check tests.integration.test_review_flow tests.integration.test_cli_lab -q
```

Pozytywne artefakty w testach są syntetyczne. Nie dowodzą niezależnego sprawdzenia
rzeczywistej strategii. Nie powstają nowe rekordy badań w `quickstart`, `state`
ani D1; nie są uruchamiane płatne modele, MT5 i zlecenia.

## Wyszukiwanie źródeł — bezpieczne ponowienia, etap 19

Wersja 61 zapisuje wejście `discover_search` przed wywołaniem AI. Kontynuacja
**tego samego zadania** zachowuje jego kontekst i odpowiedź; nie zmieniaj
payloadu, `searchAttempt`, hashy ani `searchLease` ręcznym SQL. Zmiana modelu,
kierunku lub kontekstu oznacza inne badanie, nie techniczne ponowienie.

W panelu **Research → Odkrywanie strategii → Testy** sprawdź ID zadania i
przyczynę blokady. Po ustaleniu przyczyny użyj jednego przycisku „Wznów”
w tym wierszu. Nie klikaj „Szukaj strategii teraz” jako zamiennika retry:
tworzy nowe wyszukiwanie, które może być ponownie płatne. Nie wznawiaj całej
kolejki ani zadań z niepewnym wynikiem lub nierozliczonym kosztem bez diagnozy.

- Odmowa dostawcy potwierdzona jako bezkosztowa może być ponowiona.
- Zapisana odpowiedź `ready` jest odtwarzana; jej niepoprawne cytaty nie
  znikną od wielokrotnego klikania i nie należy wyłączać kontroli cytatów.
- Stan operacji `running` oznacza oczekiwanie; `uncertain` wymaga ustalenia
  wyniku i kosztu, nie automatycznego ponowienia po upływie czasu.
- Stan `complete` wyszukiwania nie dowodzi odczytu źródła, kompletnej
  strategii, backtestu ani uprawnień handlowych. Sprawdź osobno import i reguły.
- Stare ukończone zadania bez snapshotu nie mają wstecznie dodanej ochrony.

Odbiór etapu 19: wyszukiwanie i import zakończone, ekstrakcja nowego PDF
zatrzymana na cytacie. Nie klikaj ponownie wyłącznie w celu zmiany etykiety
na zieloną. Dowody, ID i koszty: [raport etapu 19](ETAP_19_2026-09-24.md).
