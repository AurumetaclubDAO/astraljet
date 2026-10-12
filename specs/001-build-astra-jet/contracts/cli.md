# Kontrakt CLI AstralJet

CLI jest pierwszym interfejsem użytkownika i zawsze wymaga jawnego `--state-dir`.
Komendy zwracają kod 0 dla sukcesu, 2 dla błędu walidacji, 3 dla blokady domenowej i 4 dla
błędu technicznego. `--json` zwraca jedną kanoniczną wartość JSON bez dodatkowego tekstu.

## Inicjalizacja

```text
astraljet --state-dir PATH init
```

Tworzy bazę i migracje idempotentnie. Nie tworzy połączenia sieciowego.

## Rejestracja źródła

```text
astraljet --state-dir PATH source add --file FILE [--author TEXT] --idempotency-key KEY
```

Oblicza SHA-256 lokalnego pliku, zapisuje SRC i zdarzenie. Nie wykonuje instrukcji z pliku
i nie kopiuje treści do repozytorium. Ponowienie z tym samym kluczem zwraca ten sam SRC.

## Rejestracja pakietu pięciu kandydatów

```text
astraljet --state-dir PATH candidates seed-2026 --source-id SRC_ID --idempotency-key KEY
```

Tworzy dokładnie pięć rekordów CAND opisanych w specyfikacji. Nie oznacza ich jako
zweryfikowane i nie tworzy RUN.

## Status

```text
astraljet --state-dir PATH status [--record-id ID] [--json]
```

Pokazuje: badany obiekt, etap, stan techniczny, wynik merytoryczny, bloker, właściciela,
koszt, artefakty i dozwolony następny krok. Brak wartości jest jawny jako `unknown`.

## Audyt

```text
astraljet --state-dir PATH audit export --record-id ID --output FILE
```

Eksportuje tylko do odczytu pełny łańcuch rekordów i zdarzeń. Eksport nie zawiera sekretów
ani treści plików źródłowych, jeśli nie zatwierdzono tego osobno.

## REVIEW — lokalna kontrola dowodów, etap 14

```text
astraljet --state-dir EXISTING_STATE review create --run-id RUN_A --run-id RUN_B --reviewer NAME --evidence TEXT --independent-check CONTROL.json --idempotency-key NEW_KEY
```

`--run-id` i `--independent-check` są powtarzalne; maksymalnie 100 RUN i 8 raportów
po 1 MiB. CLI odczytuje najnowsze wersje wskazanych RUN oraz ich dokładne EXP w
jednej transakcji odczytu; wybrane wersje i pełne hashe utrwala w REVIEW.
Ponowienie po dodaniu nowej wersji RUN jest innym żądaniem, wymaga nowego klucza.

Istniejąca baza jest wymagana. Nieprawidłowy plik kontrolny jest odrzucany przed
inicjalizacją/migracją bazy. Prawidłowe polecenie zapisujące nadal korzysta ze
standardowej inicjalizacji schematu: przed pracą na starym rejestrze wymagany jest
backup. Nie uruchamiaj tego polecenia na produkcji tylko w celu odczytu.

Brak drugiego RUN lub raportu kontrolnego pozwala zapisać `unverified`, nie
`verified`. Jawny `--reject-reason` daje `rejected`. `--finding`, `--condition`,
`--missing-evidence` zapisują uzasadnienie i braki. Kod 0 oznacza zapis oceny,
nie pozytywny werdykt: czytaj `review.verdict` oraz `missing_evidence`.

Identyczne ponowienie jest idempotentne (`created=false`). Zmienione argumenty,
wejścia lub raporty z wcześniej użytym kluczem dają kod 2; stary wynik i jego
zdarzenie pozostają niezmienione. Historyczny REVIEW bez hashu żądania wymaga
nowej oceny z nowym kluczem. `status --json` nie proponuje mandatu dla
`unverified`/`rejected` REVIEW albo zablokowanej RISK-DECISION.

Pełny format i granice zaufania:
[independent-check-v1.md](independent-check-v1.md). Od etapu 18 sprawdzana jest
także integralność lokalnego tygodniowego RUN. Jego `inconclusive` nie spełnia
warunku kwalifikacji: sam zapis lub replay nie daje `verified`. To nie worker
witryny i nie wykonanie zleceń.

## Odczyt wejść szkicu eksperymentu (etap 04)

```text
astraljet --state-dir STRATEGY_STATE experiment inspect-inputs --strategy-id ID --strategy-version N --data-state-dir DATA_STATE --data-id ID --data-version N --csv FILE --metadata FILE --start YYYY-MM-DD --is-end YYYY-MM-DD --oos-start YYYY-MM-DD --end YYYY-MM-DD --ma-window N --slope-lookback N --signal-weekday 0..6 [--output NEW.json]
```

Odczyt jawnych wersji bez fallbacku do latest, zapisów do rejestrów i migracji. Sprawdza hash CSV względem DATA i sidecar, dzienny kalendarz UTC, instrumenty, OHLC, braki i duplikaty oraz proponowany warm-up. Limit CSV 50 MiB, metadanych 1 MiB. Nie rozwiązuje zatwierdzeń, nie scala baz, nie wykonuje RUN ani zleceń.

Kod 0 oznacza sukces odczytu/eksportu, również gdy wynik zawiera findings. Wynik **zawsze** pozostaje `DRAFT_BLOCKED`, `can_freeze=false`, `execution_authorized=false`, `experiment_id=null`. `--output` publikuje tylko nowy JSON; istniejący plik daje kod 2. Brak bazy, wersji lub niepoprawna konfiguracja również daje kod 2. Dane do wyświetlenia nie są formatem wejściowym `experiment freeze`.

## Zamrożony model tygodniowy — etap 06

```text
astraljet --state-dir EXISTING_STATE experiment inspect-weekly --experiment-id EXP_ID --version N --csv FILE [--output NEW.json]
astraljet --state-dir EXISTING_STATE run weekly-offline --experiment-id EXP_ID --version N --csv FILE [--output NEW.json]
```

Obie ścieżki pobierają konkretny EXP i przypięte wersje STRAT/DATA z **jednej transakcji odczytu** w istniejącym rejestrze. Nie wybierają `latest`, nie scalają rejestrów i nie inicjalizują/migrują bazy. Brak któregokolwiek rekordu jest błędem, nie pustym stanem zastępczym.

Kontrakt dopuszczonego EXP:

- `code_hash` wskazuje bieżący `weekly_adapter_fingerprint()`; sam hash silnika z etapu 05 nie wystarcza. `criteria.weekly_binding` jest wynikiem `weekly_binding(strategy, data)` i obejmuje pełne rekordy STRAT/DATA oraz hash silnika. Obliczenie bindingu nie jest zgodą Karola.
- Sprawdzane są statusy, hash reguł STRAT, pełny `plan_hash` EXP i profil `weekly_strategy_definition(...)`. Inne reguły — nawet ze statusem `ready` — są odrzucane.
- `allowed_variants` zawiera 1–8 obiektów z dokładnie polami: `model_id=weekly-btc-eth-state-v1`, `ma_window`, `slope_lookback`, `initial_equity` (tekst dziesiętny), `scenario_name`, `cost_bps` (tekst dziesiętny), `extra_delay_days` (0/1). Warianty mogą różnić się tylko nazwą, kosztem i dodatkowym dniem realizacji. Nie ma nadpisywania parametrów przez CLI ani selekcji najlepszego wariantu.
- `criteria` zawiera wyłącznie binding oraz `assessment=manual_review_required`; `stop_rules` to `validation_error`, `input_or_code_changed`. `budget="0"` oznacza brak zgody na płatne wywołania, nie kapitał portfela. `seed=0` oznacza ścieżkę deterministyczną, bez Monte Carlo. Ten przyrost **nie ocenia automatycznie hipotezy**.
- Metryki: `net_return`, `annualized_return`, `max_drawdown`, `total_cost`, `executed_notional`, `number_of_rebalances`, `mean_gross_exposure_at_close`; tolerancje muszą obejmować dokładnie zadane metryki i być nieujemnymi tekstami dziesiętnymi. Sharpe/PF/Monte Carlo nie są dopowiadane. Tolerancje są przypięte, ale ich ocena reprodukcji jest nadal osobnym krokiem.
- IS/OOS są ciągłe, granice to znaczniki świec 00:00 UTC, obustronnie włącznie. IS musi zmieścić warm-up, pierwszy sygnał i wykonanie wszystkich scenariuszy. Wykonanie na granicy next-open jest uproszczeniem, nie pomiarem dostępności świecy.
- DATA: dokładne BTCUSD/ETHUSD, `1d`, UTC, `ohlcv-v1`, koszt zgodny ze STRAT/EXP, brak findings oraz jawne `available_at_rule=bar_close_utc_next_open_proxy`. CSV (maks. 50 MiB) musi wskazywać przypiętą lokalizację. Te same raz odczytane bajty są hashowane i parsowane. Sprawdzany jest cały kalendarz snapshotu, OHLC i metadane, także poza wybranym okresem EXP.

`inspect-weekly` nie oblicza portfeli: zwraca `INPUTS_VERIFIED_ONLY`. `weekly-offline` wykonuje po jednym przebiegu każdego wariantu i zwraca `OFFLINE_UNQUALIFIED` wraz z sygnałami, symulowanymi realizacjami, jednostkami, gotówką, wyceną i metrykami IS/OOS. Obie ścieżki: `execution_authorized=false`, `run_record_created=false`, `records_written=0`, `criteria_status=not_evaluated`, `reproduction_status=not_independently_verified`.

Bez `--output` pełny raport trafia do stdout. Z `--output` nowy JSON jest publikowany atomowo (maks. 64 MiB), a stdout zawiera małe potwierdzenie z hashem raportu. Istniejący plik/symlink jest odrzucany jeszcze przed obliczeniami; równoległe utworzenie celu także nie prowadzi do nadpisania. Dotychczasowe eksporty zachowują domyślny limit 4 MiB. Błąd nie publikuje częściowego raportu.

Kod 0 oznacza ukończenie odczytu/modelu, **nie** potwierdzenie hipotezy czy zysku. Kod 2 — błędne wejście, brak wersji/pliku lub konflikt eksportu; kod 3 — niespójność/blokada; kod 4 — błąd techniczny. Raport nie jest rekordem RUN ani formatem zlecenia. Wykonawca, legacy `run backtest` i worker witryny nie są podłączone do tej ścieżki.

## Trwały zapis modelu tygodniowego — etap 18

```text
astraljet --state-dir EXISTING_STATE run weekly-recorded --experiment-id EXP_ID --version N --csv FILE --owner NAME --idempotency-key KEY
astraljet --state-dir EXISTING_STATE run weekly-export --idempotency-key KEY --output NEW.json
```

`weekly-recorded` jest jawną ścieżką zapisującą. Wymaga istniejącej bazy w
aktualnym schemacie 7 i triggerów ochrony historii; **nie** wywołuje `init`
ani migracji. Wymagania STRAT/DATA/EXP są takie jak w etapie 06. CLI nie
zatwierdza planu, nie zmienia reguł i nie dodaje zgody na handel. Autor jest
niepusty (maks. 120 znaków; domyślnie `AJ-07 — model tygodniowy`), klucz serii
ma 8–200 znaków. CSV musi wskazywać przypiętą lokalizację DATA.

Obliczane są wszystkie 1–8 scenariuszy. Powstaje po jednym RUN i EVENT na
scenariusz oraz jeden EVENT manifestu serii, atomowo. Limit serializowanej
serii: 64 MiB; przekroczenie nie powoduje zapisu części wyników. Awaria
obliczenia lub transakcji nie zapisuje częściowego RUN, ale również nie
utrwala osobnego zdarzenia nieudanej próby. Pełny audyt błędów jest dalszą pracą.

Odpowiedź jest małym `weekly-recorded-v1`: `created`, `report_hash`,
`runs` (dokładne ID, wersja, hash rekordu i scenariusz),
`criteria_status=not_evaluated`, `execution_authorized=false`.
RUN ma `BACKTEST/completed/inconclusive`, nigdy automatyczne `passed`.
Główne metryki to OOS strategii; `RUN.total_cost` obejmuje pełny okres
strategii jednego scenariusza. Pełne IS/OOS, benchmark, sygnały i historia
pozostają w `reproduction.weekly_result`, objęte kontrolą integralności.

Ponowienie tego samego klucza i argumentów zwraca zapisaną serię z
`created=false`, bez nowego liczenia i zapisu. Działa również po usunięciu
CSV, bo to odczyt historycznego wyniku, nie ponowna kontrola aktualnych danych.
Zmiana autora, przypiętych rekordów albo żądania pod użytym kluczem jest
konfliktem; nie nadpisuje historii. Nowy klucz oznacza nowe obliczenie z
pełną walidacją. Wyścig może policzyć model dwukrotnie, lecz zapis pozostaje
pojedynczy. Zmiana kodu wymaga nowego zamrożonego planu, nie edycji starego hashu.

`weekly-export` jest odczytem manifestu i dokładnych RUN. Odtwarza raport
`weekly-offline-report-v1` z oryginalnym hashem, bez CSV, modelu, migracji,
rekordów lub zdarzeń. Wymaga nowego pliku wyjściowego, maks. 64 MiB. Flagi
raportu `run_record_created=false` i `records_written=0` nadal opisują
oryginalne obliczenie offline, nie stan rejestru po osobnym zapisie serii.
Zapis potwierdza receipt `weekly-recorded-v1` i EVENT manifestu.

Istniejący Analytics odczytuje wyeksportowany plik lokalnie w przeglądarce.
Istniejące `registry:sync` może osobno przesłać metadane RUN, nie pełne
wyniki. Żadne z tych poleceń nie wysyła ich automatycznie, nie uruchamia
workera i nie tworzy REVIEW/mandatu. Kod 0 oznacza wykonanie polecenia,
nie spełnienie hipotezy. Błędy korzystają ze standardowych kodów CLI.

## Kontrakt błędu JSON — przykład

```json
{
  "error": {
    "code": "DOMAIN_BLOCKED",
    "message": "Krótki opis po polsku",
    "blocker": "missing_strategy_exit_rule",
    "owner": "Karol",
    "allowed_next_action": "Uzupełnij regułę wyjścia i utwórz nową wersję STRAT"
  }
}
```

Żaden błąd źródła nie może zostać przekształcony w komendę systemową ani wykonawczą.
