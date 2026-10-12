# Astra / Alpaca Challenge — architektura

Rozszerzenie pakietu AstralJet, osobny wykonawca i baza. Lab nie otrzymuje
kluczy ani prawa wywołania zleceń. Integracja nie migruje runtime MT5 i nie
zmienia istniejących mandatów ani rejestru badawczego.

```text
Alpaca Data (HTTPS, quotes, CLOSED bars)
       |                        GET Calendar / Clock / Assets
       v                                     |
Scanner watchlists ----> Strategy + Regime <--+
       |                  |                  |
       | NO_TRADE         | A/A+ Signal      |
       v                  v                  v
SQLite audit       /v1/signals + Bearer + schema
                          |
              durable idempotency reservation
                          |
              account/positions/pending/quote
                          |
                Risk Engine + Kill Switch
                          |
               payload -> DRY RUN journal
                          |
              execute_orders? PAPER ONLY guard
                          |
               Alpaca Paper /v2/orders
                          |
             reconciliation -> fills -> protections
                          |
              SL / TP / break-even / time stop
                          |
                 journal + local Dashboard/API
```

## Odpowiedzialności

`config.py`: pydantic-settings, plik .env, sekrety, walidacja fail-closed.
Dokładny endpoint jest dodatkowo sprawdzany przy każdym HTTP. Brak przekierowań,
ambient proxy i alternatywnego trading hosta; host Market Data stały, tylko GET.

`broker.py`: httpx/asyncio, retry wyłącznie GET (0,5/1 sekundy), kontrola statusu,
brak drukowania odpowiedzi błędów lub kluczy. POST ma trwały client_order_id,
sprawdzenie przed wysyłką i po niepewnym wyniku. 404 po timeout nie daje prawa
ponowić POST. Ustawienie dry-run blokuje każdą mutację już w transporcie.

`sessions.py`: zegar brokera, kalendarz świąt i wcześniejszych zamknięć,
America/New_York przez tzdata. Crypto 24/7; opcje konserwatywnie wyłącznie
regular equities session. Extended equities wyłącznie LIMIT/DAY i potwierdzone
overnight_tradable/overnight_halted. Nocne quote korzystają z overnight feed;
brak jego uprawnień/danych blokuje wejście. Nie wymuszamy 24/5 na koncie, które
nie ma danych lub dostępu.

`strategies.py`: czyste deterministyczne reguły. Struktura HH/HL/LH/LL, ATR,
średnie, realized volatility oraz VWAP służą filtrowaniu, nie przewidywaniu
prawdopodobieństwa. Świeca aktualnie budowana nie jest sygnałem. Brak katalizatora
news nie jest zastępowany fikcyjnym newsem. ORB i crypto wymagają oddzielnego
breakoutu i retestu; momentum używa impulsu/konsolidacji/kontynuacji.

`risk.py`: wielkość pozycji i reguły instrumentu. Ryzyko otwartych i oczekujących
wejść jest rezerwowane. Limity korelacji sumują ekspozycję brutto, bez kompensowania
long/short. Equity/P&L rzeczywistego Paper account, nie wirtualne 1000 USD przy
rachunku 100000 USD. Sam budżet challenge'u nie resetuje salda brokera.

`service.py`: scanner, executor, aktywny position manager. Globalna blokada
asyncio serializuje mutacje i risk snapshot, blokada systemowa chroni bazę
przed drugim procesem. Stan niepewny blokuje wejścia. Reconciliation odzyskuje
przerwane intencje i częściowe fille. Monitoring istniejących pozycji działa
nawet przy włączonym kill switch albo wykryciu obcych pozycji.

`journal.py`: SQLite WAL, transakcyjne rezerwowanie idempotencji przed HTTP,
oddzielne intencje wejścia/wyjścia, mapping broker/client IDs, trwałe protections.
Audit jest append-only, bez endpointu kasowania. Częściowe wyjścia księgowane
różnicowo; powtórne odczytanie tego samego fillu nie tworzy drugiej transakcji.

`main.py`: publiczny health i lokalny dashboard; wszystkie /v1 wymagają Bearer,
porównanie constant-time. Signal API nie ufa samemu grade podanemu przez klienta:
ponownie ocenia bieżący setup. Walidacja nie zwraca pełnych wejść w błędach.

## Ograniczenia MVP i odbioru

Pełne equities LONG otrzymują brokerowy GTC stop-loss w regularnej sesji.
W pozostałych przypadkach SL jest lokalny; TP, break-even i time stop także
wymagają procesu, internetu, aktualnego quote i właściwej sesji. Lokalny exit
czeka na anulowanie natywnego stopu. Brak automatycznego doboru opcji,
trailing i integracji panelu w istniejącym Command Center. Runtime pozostaje dry-run.

Niepewny order wymaga reconciliation, nigdy ponowienia w ciemno. Flatten
potwierdza anulowania przed zleceniami zamknięcia, status CLOSING nie jest
potwierdzeniem fillu. Jawny flatten obejmuje też niezarządzane pozycje,
z audytem ich snapshotu i bez tworzenia nieznanej historii wejścia.
Wygaśnięcia opcji, corporate actions lub zewnętrzne zmiany konta, które nie
pasują do journal, blokują automatyczne wejścia zamiast dopisywać fikcyjne fille.

## Źródła kontraktu brokera (sprawdzone 30.09.2026)

- [Alpaca — składanie zleceń](https://docs.alpaca.markets/us/docs/orders-at-alpaca)
- [Alpaca — 24/5 dla Trading API](https://docs.alpaca.markets/us/docs/245-trading-for-trading-api)
- [Alpaca — options](https://docs.alpaca.markets/us/docs/options-trading)
- [Alpaca — Create Order](https://docs.alpaca.markets/us/v1.1/reference/postorder)

Dokumentacja opisuje kontrakt; rzeczywiste uprawnienia konta sprawdza acceptance.
