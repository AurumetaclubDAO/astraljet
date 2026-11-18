# AstralJet — Obserwatorium

**Publikacja 14.10.2026:** [Otwórz dashboard online](https://tradebot-astra-pro.solyg.chatgpt.site/observatory). Dostęp prywatny po zalogowaniu. Dane są przesyłane z komputera co 45 sekund; po jego wyłączeniu pozostaje ostatni odczyt z ostrzeżeniem. [Raport publikacji](SITE_RELEASE_20261014.md).

Lokalny dashboard **tylko do odczytu**, zbudowany w zatwierdzonym module `src/astraljet/dashboard`. Serwer działa pod [http://127.0.0.1:8877/](http://127.0.0.1:8877/), wyłącznie na Solyg. Link nie zapewnia dostępu z telefonu ani innego komputera. Kontrola 390 px dotyczy układu mobilnego w przeglądarce, nie publikacji w sieci.

Status dostawy: **IMPLEMENTED / TECHNICAL ACCEPTANCE PASS / INDEPENDENT REVIEW PENDING**. Zewnętrzny review Claude wskazany w briefie jeszcze nie został przeprowadzony. Nie nazywamy całego procesu P0–P5 zamkniętym przed tym review.

## Start i stop

Uruchom `D:\Astra Jet\start_dashboard.bat`. Zatrzymaj tylko dashboard przez `D:\Astra Jet\stop_dashboard.bat`.

Start nie instaluje pakietów, nie zajmuje portu należącego do innego procesu i nie uruchamia botów. Stop sprawdza PID, czas startu, ścieżkę procesu oraz nazwę modułu. Istniejący terminal MT5 musi już działać; brak jednoznacznego terminala daje BRAK danych. Pierwsza runda odczytu może potrwać do 30 sekund.

Dashboard używa `.runtime/dashboard-venv` (Python 3.12). Nie używa `.venv` ani `.runtime/alpaca-venv`. Nie uruchamiać `run_windows.ps1` w celu startu tego panelu — tamten skrypt obsługuje Alpaca.

Odtworzenie osobnego środowiska, jeśli zostało usunięte:

```powershell
Set-Location 'D:\Astra Jet'
New-Item -ItemType Directory -Force '.runtime/dashboard/tmp' | Out-Null
$env:TEMP = (Resolve-Path '.runtime/dashboard/tmp').Path
$env:TMP = $env:TEMP
py -3.12 -m venv .runtime/dashboard-venv
.\.runtime\dashboard-venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements-dashboard.lock
.\start_dashboard.bat
```

### Numery rachunków (tylko lokalnie)

Repozytorium jest publiczne, więc numerów rachunków nie ma w kodzie, testach ani dokumentach. Dashboard czyta je z lokalnego pliku `.runtime/dashboard/accounts.toml`, który jest pomijany przez Git:

```toml
demo_login = 0          # zamień 0 na numer jedynego rachunku DEMO, z którego wolno czytać dane
forbidden_logins = [0]  # zamień 0 na numery rachunków zawsze blokowanych (LIVE)
```

Bez tego pliku bramka MT5 blokuje każdy odczyt, a publikator nie wysyła snapshotu z danymi rachunku. Testy używają jawnie fikcyjnych numerów `90000001` (DEMO) i `90000002` (LIVE). Zrzuty ekranu z `docs/dashboard/screenshots/` pokazują numer rachunku i salda, dlatego zostają tylko lokalnie.

`requirements-dashboard.lock` przypina wersje dostawy; `.in` jest listą wejściową dla kolejnego jawnego odświeżenia zależności. Zależności do testów także znajdują się w izolowanym środowisku. Nie instalować ich do środowisk wykonawców.

## Linki

### Witryna i automatyczne przywracanie

[Prywatne Obserwatorium](https://tradebot-astra-pro.solyg.chatgpt.site/observatory#main) otrzymuje pomiary z tego komputera. Od 27/28.10.2026 zadanie Windows `AstralJet-Observatory-Publisher` sprawdza start usług co 5 minut, a także przy logowaniu. `scripts/dashboard_site_start.ps1` uruchamia brakujący dashboard i publikator; ponowne wywołanie nie restartuje działających usług. Komputer musi być włączony, Karol zalogowany, a zadanie włączone. Dane MT5 wymagają działającego terminala i łączności.

Kontrola przywraca zakończone procesy; nie naprawia zawieszonego MT5 ani publikatora, który nadal istnieje, ale nie wysyła danych. [Wynik rzeczywistego testu przywracania](RECOVERY_20261028.md).

**Celowe zatrzymanie:** najpierw wyłącz zadanie, inaczej usługi mogą wrócić przy następnej kontroli:

```powershell
Disable-ScheduledTask -TaskName 'AstralJet-Observatory-Publisher'
& 'D:\Astra Jet\scripts\dashboard_site_stop.ps1'
& 'D:\Astra Jet\scripts\dashboard_stop.ps1'
```

Wznowienie: `Enable-ScheduledTask -TaskName 'AstralJet-Observatory-Publisher'`, następnie `scripts/dashboard_site_start.ps1`.

### Adresy lokalne

- [Przegląd](http://127.0.0.1:8877/)
- [Boty DEMO](http://127.0.0.1:8877/#bots)
- [Pozycje](http://127.0.0.1:8877/#positions)
- [Kontrola ryzyka](http://127.0.0.1:8877/#risk)
- [Funding/OI](http://127.0.0.1:8877/#markets)
- [Pokój decyzyjny](http://127.0.0.1:8877/#agents)
- [Health API](http://127.0.0.1:8877/api/health)
- [Spójny snapshot JSON](http://127.0.0.1:8877/api/summary)

Pozostałe GET: `/api/bots`, `/api/positions`, `/api/risk`, `/api/arena`, `/api/funding`, `/api/schedule`, `/api/alpaca`. Pozostałe metody HTTP są odrzucane. Brak proxy do API wykonawcy, CORS * i przycisków sterowania.

## Konfiguracja i źródła

`dashboard_config.toml`: ścieżka Desktop i uruchomionego terminala, oczekiwany serwer DEMO, 45 s odświeżania, 30 dni historii oraz progi świeżości. Konto dozwolone i blokada LIVE są zapisane w adapterze, nie mogą być wyłączone przez TOML. Brak `.env` i obsługi poświadczeń.

| Źródło | Zawartość | Ograniczenia |
|---|---|---|
| MT5 SDK | Konto DEMO, stan terminala, pozycje, historia | Gate konta i serwera przed odczytem; dwukrotnie sprawdzany snapshot; błędy nie dają pustych list |
| TQ runner CSV/JSON/log | Ostatnia ewaluacja, akcja, licznik błędów | Pusty state.json nie potwierdza braku pozycji; log max 2000 linii / 256 KiB |
| Harmonogram Windows | 8 nazwanych zadań, stan, ostatni i następny start, kod | Ready nie oznacza ciągłego działania ani sukcesu brokerskiego |
| TQ-Common | Konfiguracja ryzyka, istnienie KILL_SWITCH | Tylko odczyt, brak wywołania istniejącego risk gate |
| Arena | Snapshot 6 botów | Metryki pozostają NIEPOTWIERDZONE; `equity` pokazane jako przydział |
| Funding/OI | Binance/Bybit × BTC/ETH | Najnowszy błędny wiersz nie jest zastępowany starym sukcesem |
| Alpaca | Informacja historyczna | BRAK aktualnego odczytu; zgłoszenie 401 nie jest wynikiem nowego testu |
| Pokój decyzyjny | 6 nazwanych ról | BRAK źródeł decyzji; dashboard niczego nie generuje |

Każda wartość ma badge z pochodzeniem, czasem, wiekiem i powodem ograniczenia. Tooltip dostępny także po przejściu klawiaturą. Wiek przeliczany przy odpowiedzi API i po stronie przeglądarki, także po utracie połączenia.

POTWIERDZONE = poprawny, świeży odczyt w zakresie danego pola. NIEPOTWIERDZONE = stare, częściowe lub niejednoznaczne dane. BRAK = brak źródła/odmowa/błąd. Zera są wyświetlane tylko jako wynik poprawnego odczytu, nigdy jako zamiennik braków.

## Interpretacja liczb

Wynik zrealizowany dziś obejmuje deale kupna/sprzedaży z ich polami profit, commission, swap i fee, od północy Europe/Warsaw. Wpłaty i wypłaty nie są wynikiem handlowym. Osobne opłaty księgowane przez brokera w innych typach dealu nie są automatycznie przypisywane do botów. Floating obejmuje też pozycje otwarte wcześniej; jego suma z wynikiem dziś nie jest zmianą equity od północy.

Atrybucja: znane magic, następnie position_id, jeśli pochodzenie widnieje w pobranym oknie historii. Brak wcześniejszego wejścia daje „Inne/ręczne” i ostrożny status wyników botów. Nie pobieramy nieograniczonej historii. Krzywa to skumulowany wynik **zrealizowany** w pobranym oknie, nie historyczne equity. Wykres rozkładu przedstawia liczbę pozycji, nie ich nominalną ekspozycję pieniężną.

Limit straty jest wskaźnikiem informacyjnym, nie kopią działania zewnętrznego `risk_gate`. Wymaga waluty USD. Suma przydziałów nie jest saldem konta. Potwierdzony brak KILL_SWITCH oznacza nieaktywną blokadę plikową; błąd odczytu katalogu oznacza BRAK.

## Weryfikacja

- [Raport odbioru](ACCEPTANCE.md)
- [67 testów dashboardu](TEST_DASHBOARD.txt)
- [315 testów projektu, w tym dashboard](TEST_ALL.txt)
- [16 testów TQ na kopii](TEST_TQ.txt)
- [Odbiór przeglądarkowy i API](BROWSER_CHECK.json)
- [Widok 1440 px](screenshots/dashboard-1440.png), [1024 px](screenshots/dashboard-1024.png), [390 px](screenshots/dashboard-390.png)

Testy można odtworzyć z `PYTHONPATH=src` i `PYTHONDONTWRITEBYTECODE=1`, kierując TEMP/TMP i katalog `--basetemp` pod `.runtime/dashboard`. Testy dashboardu nie otwierają prawdziwego `.env`; istniejące testy rdzenia mogą tworzyć syntetyczne pliki o tej nazwie w katalogu tymczasowym. `scripts/dashboard_regression.py` kopiuje wyłącznie jawne pliki risk gate do izolowanego folderu. **Nie uruchamiać TQ testów bezpośrednio na Desktop**: oryginalny test tworzy i usuwa produkcyjny KILL_SWITCH.

Do screenshotów: ustaw `PLAYWRIGHT_BROWSERS_PATH` na `.runtime/dashboard/browsers`, zainstaluj Chromium w tym miejscu poleceniem `python -m playwright install chromium`, uruchom `scripts/dashboard_browser_check.py`. Skrypt testuje wyłącznie localhost. Kontrola kontrastu i klawiatury nie jest formalnym audytem całego WCAG.

## FAQ

**Czy to stary adres?** Nie. Nowy panel to port 8877. Nie przejmuje starego panelu na 8876 ani Command Center.

**Czy można otworzyć na telefonie?** Tak, prywatną witrynę po zalogowaniu właściciela. Adres loopback 127.0.0.1 działa wyłącznie na komputerze serwera. Świeże dane na witrynie nadal wymagają działającego komputera i terminala; lokalnego portu nie wystawiono do sieci.

**Dlaczego widzę Algo Trading OFF?** To odczyt flagi terminala. Dashboard jej nie zmienia.

**Dlaczego LONG HOLD i v-B nie mają zadania?** Nie ma potwierdzonego przypisania zadania wykonawczego. SHADOW-VB jest oddzielnym badaniem. Pozycje i wynik mogą nadal pochodzić z MT5.

**Dlaczego Arena jest żółta?** Jej producent nie daje pełnego pochodzenia metryk. Zapis świeżego pliku nie wystarcza, aby je potwierdzić.

**Co z bezpieczeństwem inicjalizacji MT5?** SDK może uruchomić terminal; przed inicjalizacją sprawdzamy istniejący, jednoznaczny proces i konkretną ścieżkę. Wyścig zamknięcia terminala między kontrolą a inicjalizacją pozostaje ograniczeniem SDK. Brak loginu/hasła w wywołaniu; proces pomocniczy ma timeout i nigdy nie wysyła zleceń.

**Gdzie status dla Grogu?** W istniejącym zadaniu Notion, uzupełnionym na bezpośrednie polecenie Karola. Zapis raportu nie potwierdza, że Grogu już go przeczytał. Raport nie zmienia ustawień udostępniania strony.
