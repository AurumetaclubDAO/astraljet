# Astra / Alpaca Paper Challenge

Lokalne rozszerzenie istniejącej Astry (`astraljet.alpaca_challenge`).
**Wyłącznie Alpaca Paper. Pierwszy tryb: dry-run.** Stan odbioru znajduje się w
`docs/alpaca_challenge/STATUS.md` oraz `.runtime/alpaca/acceptance.json`.
Nie myl działającego API ani testów z potwierdzeniem gotowości brokera.

## Instalacja na Windows 11

1. Zainstaluj Python **3.12**. Sprawdź w PowerShell: `py -3.12 --version`.
2. Otwórz PowerShell i przejdź do katalogu:

   ```powershell
   Set-Location 'D:\Astra Jet'
   ```

3. Uzupełnij `.env`. Jeśli go nie masz, skopiuj `.env.example` do `.env`.
   **Nie nadpisuj istniejącego pliku**: korzysta z niego również moduł danych Astry.
4. W panelu Alpaca wybierz konto **Paper**, wygeneruj jego klucze i wpisz:

   ```dotenv
   ALPACA_API_KEY_ID=twoj_klucz_paper
   ALPACA_API_SECRET_KEY=twoj_sekret_paper
   PAPER_ONLY=true
   ALPACA_TRADING_BASE_URL=https://paper-api.alpaca.markets
   EXECUTE_ORDERS=false
   EXECUTOR_BEARER_TOKEN=twoj_losowy_token_minimum_32_znaki
   ```

   Token API można wygenerować poleceniem
   `py -3.12 -c "import secrets; print(secrets.token_urlsafe(36))"` i wkleić lokalnie
   do `.env`. Token kontroluje Twój lokalny executor, nie jest kluczem Alpaca.
   Nie przesyłaj sekretów do czatu, Git ani screenshotów.

5. Uruchom:

   ```powershell
   .\run_windows.ps1
   ```

   Skrypt tworzy izolowany Python 3.12 w `.runtime/alpaca-venv`, instaluje
   zależności, wykonuje testy, acceptance i uruchamia pojedynczy proces API.
   Zastany `.venv` Astry używał Python 3.14; nie został zmodyfikowany.
   Nie uruchamiaj wielu workerów. Blokada pliku uniemożliwia dwa procesy na tej samej bazie.

6. Otwórz `http://127.0.0.1:8876` albo Swagger `http://127.0.0.1:8876/docs`.
   Panel wymaga tokenu do danych. Przycisk **Authorize** w Swagger przyjmuje token.

## Gdy acceptance nie przechodzi

`NOT READY` zatrzymuje zwykły start. Diagnostyczny start API i scannera:

```powershell
.\run_windows.ps1 -Diagnostic
```

Jest dozwolony wyłącznie przy `EXECUTE_ORDERS=false`. `/health` może wtedy
zwrócić `degraded`; scanner zapisuje `NO_TRADE` z powodem błędu.
Kod 200 z `/health` oznacza działający proces, a `broker_reconciled=true`
oznacza udane uzgodnienie stanu konta. Nie ma automatycznego pozyskiwania
kluczy z przeglądarki ani przełączania na konto LIVE.

## Ustawienia i ryzyko

| Ustawienie | Domyślnie | Znaczenie |
|---|---:|---|
| STARTING_EQUITY | 1000 | Wymagane equity pustego, dedykowanego konta na starcie wykonania |
| CHALLENGE_DAYS | 7 | Siedem kolejnych okresów 24 h od pierwszego startu execution |
| MAX_RISK_PER_TRADE_USD | 150 | Maksymalny budżet ryzyka jednej pozycji |
| MAX_DAILY_LOSS_USD | 250 | Spadek equity dziennego, realizowany i niezrealizowany |
| MAX_TOTAL_DRAWDOWN_USD | 450 | Spadek od HWM oraz kapitału początkowego |
| MAX_OPEN_POSITIONS | 3 | Łącznie pozycje i symbole oczekujących wejść |
| MAX_POSITION_NOTIONAL_USD | 700 | Limit wartości jednej pozycji |
| MAX_CORRELATED_NOTIONAL_USD | 700 | Łączna ekspozycja grup QQQ/NVDA/AMD i BTC/COIN |
| ALLOW_EQUITY_SHORT | false | Short akcji wymaga dodatkowo shortable/easy_to_borrow |
| ALLOW_EXTENDED_HOURS | false | Extended/overnight wymaga danych, kalendarza i atrybutów asset |
| STOCK_FEED | iex | Feed akcji; SIP wymaga odpowiedniego dostępu |
| OPTIONS_FEED | opra | Wymagany bieżący feed; brak fallbacku na delayed/indicative |
| ORB_MINUTES | 15 | Dostępne 5, 15, 30 |
| SCANNER_INTERVAL_SECONDS | 60 | Przerwa po zakończeniu pełnego skanu |
| MONITOR_INTERVAL_SECONDS | 5 | Przerwa po pełnej kontroli pozycji |
| TIME_STOP_MINUTES | 120 | Limit czasu pozycji |

Watchlisty `EQUITIES` i `CRYPTO` są listami symboli rozdzielonych przecinkiem.
Broker rozstrzyga, czy dany instrument (również SOL/AVAX) jest dostępny.
Brak danych lub tradability oznacza `NO_TRADE`, a nie usunięcie kontroli.

Kwota 150 USD jest limitem, nie obowiązkową wielkością każdej transakcji.
Sizing ograniczają także notional, equity, buying power i pozostały budżet
łącznego ryzyka. SL dla akcji/krypto jest estymacją straty z buforem 0,5%
ceny; gap, koszty i poślizg mogą przekroczyć tę estymację. Dla opcji liczona
jest cała premia × 100. Bez martingale i bez automatycznego wzrostu ryzyka.

## Strategie

- ORB: zamknięta świeca wybicia, późniejszy retest, obrona poziomu, VWAP,
  wolumen i wyższy timeframe. Nie kupuje pierwszej świecy wybicia.
- Momentum: impuls co najmniej 2 ATR, cztery świece konsolidacji i zamknięte
  wybicie z potwierdzeniem wolumenu/VWAP/trendu.
- Crypto: lokalny range, wcześniejsze wybicie, retest; filtry 5m/15m/1h/4h.
- Siła względna: NVDA/AMD vs QQQ oraz COIN vs BTC; dodatek punktowy, nie trigger.

Wagi: trend 15, volume 15, VWAP 10, retest 15, relative strength 5,
liquidity 10, spread 10, ATR 5, risk/reward 5, wyższy timeframe 10.
RANGE odejmuje 15 punktów; skrajna zmienność 25. A+ ≥95, A ≥85, B ≥70.
Automatycznie wykonywalne są tylko A/A+. To punkty, nie prawdopodobieństwo.
API ponownie weryfikuje setup na danych brokera; sam wpis `setup_grade=A+`
nie daje prawa do zlecenia.

Scanner automatyczny dotyczy akcji i krypto. Opcje przyjmuje API: OCC,
`buy_to_open` CALL/PUT i `sell_to_close` posiadanej pozycji. Weryfikowany jest
setup instrumentu bazowego, bieżący kontrakt, uprawnienia i kwotowanie OPRA.
Brak automatycznego doboru strike/expiry. Wykluczone kontrakty wygasające
dzisiaj i niestandardowe mnożniki. Brak short premium i spreadów.

## API i dry-run

Publiczny: `GET /health`. Wszystkie `/v1/*` wymagają
`Authorization: Bearer <EXECUTOR_BEARER_TOKEN>`.

Odczyt: `/v1/account`, `/positions`, `/orders`, `/signals`, `/audit`,
`/challenge`, `/strategies`, `/scanner/status` (każda ścieżka z prefiksem `/v1`).
Operacje POST: `/v1/signals`, `/v1/scanner/start`, `/v1/scanner/stop`,
`/v1/kill-switch/on`, `/v1/kill-switch/off`, `/v1/flatten`.

W Swagger użyj schematu Signal. `timestamp` musi być świeżym UTC,
`idempotency_key` unikalnym identyfikatorem setupu. Powtórzony klucz nie
wykonuje sygnału ponownie; zmieniona treść z tym samym kluczem zwraca konflikt.
Przykład struktury jest w `samples/alpaca_challenge/signal.json` — historyczny
timestamp świadomie wymusza NO_TRADE, nie jest rekomendacją transakcji.

Przy `EXECUTE_ORDERS=false` nie są wysyłane również anulowania ani zamknięcia.
`flatten` zapisuje kill switch i plan operacji. Test acceptance używa osobnej
tymczasowej bazy i wymuszonego dry-run niezależnie od ustawienia produkcyjnego.

```powershell
& .runtime/alpaca-venv/Scripts/python.exe -m pytest tests/alpaca_challenge -q
& .runtime/alpaca-venv/Scripts/python.exe scripts/acceptance_test.py
```

## Kill switch, flatten i zatrzymanie

Kill switch ON blokuje nowe wejścia. Ochrona istniejących pozycji nadal działa.
OFF wymaga ponownego uzgodnienia brokera i nie przekracza limitów ryzyka.
Stan przeżywa restart. Zatrzymanie scannera nie zatrzymuje monitorowania.

Flatten w execution: włącza kill switch, anuluje oczekujące zlecenia,
czeka na potwierdzenie anulowania i wysyła zamknięcia pozycji całego konta.
`CLOSING` nie oznacza jeszcze `CLOSED`: potwierdź brak pozycji przez API.
Poza sesją lub przy niepewnym API nie zgaduje powodzenia. Obce pozycje
blokują nowe wejścia; jawny flatten może je zamknąć i zapisuje snapshot,
bez tworzenia fikcyjnej historii wejścia. Nieznana klasa instrumentu blokuje zamknięcie.

```powershell
.\stop_windows.ps1
```

Skrypt zapisuje kill switch i zatrzymuje tylko zapamiętany proces API,
sprawdzając PID oraz czas startu. **Nie zamyka pozycji.** Pełne akcje LONG
otrzymują brokerowy GTC stop-loss podczas regularnej sesji. TP i time stop
anulują go przed zamknięciem, a break-even odświeża stop po potwierdzeniu
anulowania. Poza regularną sesją, dla crypto/opcji i częściowych filli
działa monitoring lokalny. TP/break-even/time stop oraz te lokalne SL
wymagają działającego programu i połączenia. Trailing pozostaje V1.1.
Przed wyłączeniem execution zamknij pozycje i potwierdź wykonanie.

## Włączenie Paper execution

W obecnym odbiorze nie zostało zatwierdzone: patrz STATUS.
Nie zmieniaj `EXECUTE_ORDERS` tylko dlatego, że testy offline są zielone.
Po pozytywnym acceptance i domknięciu ograniczeń powstanie osobny
`HOW_TO_ENABLE_PAPER_EXECUTION.md`. Zgodnie z poleceniem nie został utworzony
po nieudanym teście połączenia. Nie ma trybu LIVE ani przełącznika na LIVE.

## Journal, restart i debugowanie

SQLite WAL: `.runtime/alpaca/challenge.sqlite3`. Tabele: signals, orders,
protections, trades, challenge_state, audit. Nie usuwaj bazy w celu resetu.
Proces odzyskuje klucze idempotencji, order IDs i protections, odpytuje brokera
i porównuje ilości. Niepewny POST z niezidentyfikowanym client_order_id pozostaje
zablokowany; restart go nie ponawia. Historia nie jest czyszczona.

`trades` liczy wynik brutto filli; realized P&L challenge'u pochodzi z equity
konta minus kapitał startowy i niezrealizowany P&L. Wymagane dedykowane konto
bez dopłat/wypłat i ręcznych transakcji. Doba ryzyka to UTC; granica używa
ostatniego zapisanego equity poprzedniej doby. Dry-run nie uruchamia 7-dniowego zegara.

Logi procesu: `.runtime/alpaca/logs/service.log`, `stdout.log`, `stderr.log`.
Szczegółowe decyzje: `/v1/audit`. Nie logujemy nagłówków autoryzacji ani kluczy.

Najczęstsze problemy:

- **401**: klucze nieprawidłowe/niezaakceptowane przez Paper. Sprawdź konto Paper,
  wpisz jego aktualną parę kluczy w `.env`, zrestartuj API i powtórz acceptance.
- **403**: uprawnienia instrumentu/feedu; nie zastępuj danymi opóźnionymi.
- **stale quote / bars**: rynek zamknięty, brak płynności albo awaria feedu.
- **NO_TRADE**: normalny wynik niespełnienia setupu lub kontroli ryzyka.
- **equity różne od 1000**: przygotuj osobne puste Paper account w panelu Alpaca;
  aplikacja nigdy sama nie resetuje rachunku.
- **obce pozycje**: dedykowane konto lub jawny flatten/wyjaśnienie stanu; nie usuwaj journal.
- **port 8876 zajęty / lock**: sprawdź istniejący proces, nie uruchamiaj kolejnego workera.

## Struktura

```text
src/astraljet/alpaca_challenge/
  config.py models.py broker.py sessions.py
  strategies.py risk.py service.py journal.py main.py
tests/alpaca_challenge/
scripts/acceptance_test.py
scripts/run_alpaca_api.py
docs/alpaca_challenge/PLAN.md STATUS.md
samples/alpaca_challenge/signal.json
.runtime/alpaca/             # stan, raporty i logi — poza Git
run_windows.ps1 stop_windows.ps1 requirements-alpaca.txt
```

Starsze moduły Lab/Executor i uruchomione procesy MT5 pozostają niezależne.
Panel jest lokalny; nie opublikowano go w dotychczasowym Command Center.
