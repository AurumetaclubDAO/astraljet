# AstralJet — Trade Workspace v0.1 (SIMULATED)

**Status 16.11.2026: ZAIMPLEMENTOWANE W SYMULACJI / TESTY AUTORA PRZECHODZĄ / NIEZALEŻNY PRZEGLĄD OCZEKUJE.**
Zlecenie: BB-36 `HG-ASTRAJET-PRODUCT-CLAUDE-20261115`. Wykonawca: Claude Code, lokalnie w `E:\Astra Jet`.

Workspace to nowy moduł `src/astraljet/workspace/`. Służy do planowania transakcji, ochrony pozycji (BE, trailing, ręczny SL), wejść po przecięciu linii (Trend Trigger), przeglądu historii i widgetów. **W tej wersji cały rynek, rachunek i broker są SYMULOWANE.** Moduł nie importuje MetaTrader5, nie otwiera połączeń z brokerem, nie korzysta z `.env` i nie dotyka DEMO, LIVE, botów, harmonogramów ani KILL_SWITCH na pulpicie. To nie jest gotowy produkt handlowy, a testy autora nie są odbiorem.

## Mapa stanu (przed i po)

| Obszar | Przed BB-36 | Po v0.1 |
|---|---|---|
| Obserwatorium `astraljet.dashboard` (8877) | Działa tylko do odczytu, GET, 67 testów (wymaga pytest/fastapi) | **Bez zmian**; test granic sprawdza, że nadal odrzuca metody inne niż GET i nie importuje Workspace |
| Rdzeń badań, rejestr, Krytyk, `executor` PAPER | 198 testów unittest | **Bez zmian**, 199/199 na kopii (z katalogiem `specs`) |
| Alpaca challenge | Osobny wykonawca, ma BE uproszczony | **Bez zmian**; testy wymagają pydantic/httpx |
| Model danych plan / żądanie / wykonanie / pozycja | Brak | `plan.py`, `model.py`, `execution.py` |
| Trade Workspace z wykresem i wizualnym entry/SL/TP | Brak | `session.py`, `server.py`, `web/` (port 8878) |
| BE / trailing / ręczny SL ze stanami | Brak dla MT5 | `protection.py` |
| Trend Trigger | Brak | `trigger.py` |
| Review Center / Analytics | Wyłącznie krzywa zrealizowana w Obserwatorium | `analytics.py` |
| Widgety | Część w Obserwatorium (odczyt MT5) | `widgets.py` (symulacja) |
| Adapter DEMO/LIVE | Brak | **Tylko projekt** (sekcja niżej); w kodzie blokada `guard_adapter_mode` |

## Uruchomienie lokalne

Wymagany wyłącznie Python 3.12 (biblioteka standardowa). Na obecnym komputerze `.venv` i `.runtime/dashboard-venv` są zepsute (wskazują Pythona z poprzedniego laptopa), dlatego trzeba użyć osobnej instalacji Pythona 3.12 (poniżej `python`).

```powershell
Set-Location 'E:\Astra Jet'
$env:PYTHONPATH = 'src'; $env:PYTHONDONTWRITEBYTECODE = '1'
python -m astraljet.workspace
```

Następnie [http://127.0.0.1:8878/](http://127.0.0.1:8878/). Zatrzymanie: Ctrl+C w tym oknie. Serwer nasłuchuje wyłącznie na 127.0.0.1, sprawdza nagłówek Host, a POST wymaga `X-Astra-Workspace: SIMULATED` i JSON. Stan sesji jest w pamięci; restart serwera zaczyna nową symulację.

Testy (na kopii; testy Workspace nie piszą poza katalogiem tymczasowym):

```powershell
python -m unittest discover -s tests/workspace -t .
```

## Co robi v0.1

1. **Wspólny model.** Plan = PLANOWANE, `OrderRequest`+`RequestState` = ŻĄDANE (SENT, ACCEPTED, PARTIALLY_FILLED, FILLED, REJECTED, UNCERTAIN, NOT_FOUND, NOT_SENT, CANCELLED), deale i pozycje = POTWIERDZONE przez symulator. Jedna sesja daje jeden snapshot z numerem wersji; wykres, plan, ryzyko, pozycje, triggery, przegląd i widgety są z niego renderowane jednocześnie.
2. **Plan i wykres.** Symbol (EURUSD, USDJPY, XAUUSD, US500), interwał M1–D1, BUY/SELL, MARKET/LIMIT/STOP (symulator wykonuje tylko MARKET), wolumen. Liczy punkty, pipsy, kwoty w walucie zysku i rachunku (jawny kurs; brak kursu = brak wartości, nie 0), R:R, wymagany win rate, koszty prowizji (szacunek z oznaczonym źródłem; brak = „nieznane”), stratę przy SL / equity. Sprawdza tick, krok i limity wolumenu (nigdy nie podnosi wolumenu), stronę i stops level SL/TP. Oś wykresu obejmuje świece i wszystkie poziomy; linie są rysowane formułą `y = (hi − cena) / (hi − lo) · H`, tą samą co w `session.price_to_y`. SL/TP (i wejście zlecenia oczekującego) można przeciągać; cena jest przyciągana do ticka.
3. **Żądania.** Zapis przed przekazaniem, deduplikacja po `request_id` (podwójne kliknięcie nie tworzy drugiej pozycji), timeout → UNCERTAIN bez ponawiania, „Uzgodnij” pyta o ten sam identyfikator, NOT_FOUND dopiero po oknie karencji, kill switch Workspace blokuje otwarcia, ale nie zamknięcia i ochronę. Dziennik żądań może być trwały (JSON, zapis atomowy) i jest odtwarzany po restarcie.
4. **BE / trailing / ręczny SL.** Osobne stany: DISABLED, WAITING, CONDITION_MET, SENT, CONFIRMED, SATISFIED, UNCERTAIN, ERROR. Cel BE = wejście ± bufor (znak wg kierunku); trigger tylko określa moment. Trailing ma własną odległość, próg aktywacji i krok. Wybierany jest najlepszy kandydat; nic nie pogarsza SL; ręczne pogorszenie wymaga jawnego potwierdzenia i jest oznaczone w żądaniu. Odrzucony identyczny cel nie jest ponawiany. PROTECTED dopiero po potwierdzeniu SL na pozycji; wynik przy SL to szacunek brutto.
5. **Trend Trigger.** Linia pozioma lub trendu (opcjonalnie przedłużona), jawna cena oceny (Bid/Ask), kierunek przecięcia, BUY/SELL, wolumen, SL/TP w punktach, termin. Definicje uzbrojenia, ceny już po stronie warunku (WAITING_RESET), jednorazowości (deterministyczny `request_id`), przesunięcia (rewizja), usunięcia, restartu, nieświeżych danych i wygaśnięcia są w docstringu `trigger.py`. Podsumowanie jednym zdaniem; brak SL jest ostrzeżeniem.
6. **Review Center.** Jawny rachunek, okres, filtr symbolu i kierunku, definicje w odpowiedzi API. Transakcja = pozycja w pełni zamknięta w okresie; częściowe zamknięcia, koszty wejścia pozycji otwartych, wpłaty/wypłaty i opłaty są rozdzielone; składniki sumują się dokładnie do „zrealizowane w okresie”. Krzywa = saldo (nie equity); floating tylko „teraz”. Wykres kierunków i tabela używają tych samych liczb.
7. **Widgety.** Wykorzystanie depozytu (margin/equity, opisane jako nie-strata), ryzyko do SL (INCOMPLETE przy pozycjach bez SL, bez sumy i bez %), czas świecy, spread, RSI(14) Wildera, MACD(12,26,9) z konwencją histogramu — tylko z zamkniętych świec, ze źródłem, symbolem, interwałem i trybem. Bez procentu „Health”. Ustawienia UI mają białą listę i nie mogą zmienić automatyki.
8. **Symulacja w UI.** Krok, auto-krok, ruch ceny ±60 pkt, scenariusz następnego żądania (odrzucenie, częściowe, timeout po wykonaniu, timeout bez dotarcia), rozłączenie (pozycje i historia pokazane jako BRAK, nie zero), kill switch, dziennik zdarzeń.

## Testy odbioru ze zlecenia → dowód

| Wymaganie | Test (`tests/workspace/…`) |
|---|---|
| EURUSD 1067/1489 pkt, +10,67/−14,89 USD, R:R 0,7166 | `test_calculations.AcceptanceNumbers.test_hero_eurusd_points_money_and_rr` |
| R:R 2,5109 | `…test_widget_reward_risk_2_5109` |
| Trailing +724, odl. 250 → +474 pkt | `…test_trailing_candidate_plus_474_points` |
| 2459,34 / 10247,25 = 24% depozytu, nie straty | `…test_margin_usage_is_not_loss` |
| BUY/SELL, strona i stops level | `PlanSidesAndLevels` |
| Inny tick, JPY, złoto, waluta rachunku EUR, wolumen | `InstrumentUnits` |
| Geometria wykresu | `ChartGeometry`, `SessionEndToEnd.test_single_snapshot_consistency…` + odbiór w przeglądarce |
| Brak SL | `test_missing_sl_is_not_zero_risk`, `Widgets.test_risk_to_sl_incomplete_without_sl` |
| Świeżość i brak połączenia | `Freshness_`, `test_disconnected_not_sent…`, `SessionEndToEnd.test_disconnect_shows_missing_not_zero` |
| Restart i deduplikacja | `test_restart_restores_journal…`, `test_fill_and_dedup…`, `test_fired_request_is_deduplicated…` |
| Odrzucenie i częściowe wykonanie | `test_reject_is_visible…`, `test_partial_fill`, `test_rejected_modification…` |
| Netting / hedging | `NettingHedging` |
| Konflikt BE/trailing, brak pogorszenia | `test_trailing_and_be_conflict_never_worsens` |
| Trigger po stronie warunku, ruch i usunięcie linii, restart, termin | `Trigger` |
| Koszty i częściowe zamknięcia w historii | `Review`, `test_partial_close_and_commission` |
| Granice: brak MT5/sieci, Obserwatorium nadal GET, blokada DEMO/LIVE | `ModuleBoundaries`, `test_non_simulated_adapter_blocked`, `Server` |

Wyniki: [TEST_WORKSPACE.txt](TEST_WORKSPACE.txt) (69/69) i [TEST_ALL.txt](TEST_ALL.txt) (276 uruchomionych, 268 OK, 8 błędów importu w testach dashboardu i Alpaca — brak pytest/httpx/pydantic w dostępnym Pythonie, stan sprzed zmian).

Odbiór w przeglądarce (lokalny, autor): wysłanie planu, włączenie trailing, 14 ruchów ceny → SL potwierdzony na +582 pkt przy +832 pkt; scenariusz timeoutu po wykonaniu → UNCERTAIN → „Uzgodnij” → FILLED przy jednej wysyłce; zamknięcie pozycji → wpis w Review Center; 375 px bez przewijania w poziomie. Testu klawiatury i czytnika ekranu nie przeprowadzono.

## Niewykonane i ograniczenia

- **Brak adaptera DEMO/LIVE i brak odczytu MT5** w Workspace. Kwotowania, świece, specyfikacje instrumentów, prowizje i margin to dane i model symulatora, nie brokera.
- Symulator nie wykonuje zleceń oczekujących, nie nalicza swapu, a SL/TP zamyka po bieżącej cenie (luka = poślizg).
- Margin w symulatorze = nominał / dźwignia 1:100 — uproszczenie, nie reguła brokera.
- Stan sesji serwera nie jest trwały (trwałość dziennika żądań i triggerów jest zaimplementowana i przetestowana na poziomie modułów, nie podłączona do serwera).
- Brak historii floating/equity — zgodnie z wymaganiem nie jest rekonstruowana.
- Wskaźniki i świece nie są sygnałami; Workspace nie generuje decyzji.
- Brak połączenia z procesem badań (EXP/RUN/REVIEW) i rolami agentów — pozostają bez zmian; integracja to kolejny krok.
- Brak testów JS w automacie (odbiór interfejsu ręczny przez autora).

## Projekt docelowy DEMO/LIVE (nie zaimplementowany)

1. Osobny adapter `Mt5Adapter` w procesie wykonawcy (nie w Obserwatorium), z tym samym portem co `SimulatedBroker`: `send`, `lookup` po `client_order_id`/comment, `positions`, `history`, `account`.
2. Osobne konfiguracje i dzienniki DEMO/LIVE; sprawdzenie loginu, serwera i trybu rachunku przed każdą operacją (wzorzec gate z Obserwatorium); brak automatycznego przełączenia po błędzie.
3. Aktywacja przez właściciela: datowana konfiguracja rachunku, wersji strategii i polityki Risk Management (konstytucja III, VI); `guard_adapter_mode` dopuszcza tryb dopiero po jej odczycie.
4. Specyfikacje instrumentów, kursy i koszty z MT5 (`symbol_info`, historia deali), z rozdzieleniem kosztów zaobserwowanych, rozliczonych i szacowanych (konstytucja VII).
5. Uzgadnianie stanów niepewnych z historią zleceń brokera; alarm i bezpieczna ścieżka wyjścia.
6. Wolumen z wersjonowanej funkcji Risk Management (konstytucja I) — Workspace nie wymyśla sizingu.

## Kolejne kroki (propozycja)

1. Niezależny przegląd kodu i dowodów przez Codex/SENECA.
2. Odtworzenie środowiska testów dashboardu/Alpaca na obecnym komputerze (nowy venv z `requirements-dashboard.lock`), żeby pełny zestaw był zielony.
3. Odczyt specyfikacji instrumentów i świec z MT5 w trybie tylko do odczytu jako źródło DEMO danych dla Workspace (bez wysyłania zleceń).
4. Trwały stan sesji serwera (dziennik żądań, triggery, reguły ochrony) i scenariusz restartu end-to-end.
5. Integracja z evidence Astry: zapis planów i żądań jako artefaktów z pochodzeniem.
