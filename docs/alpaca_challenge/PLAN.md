# Astra / Alpaca Challenge — plan i audyt 30.09.2026

Zakres zatwierdzony: lokalny executor Alpaca Paper, 1000 USD, 7 dni, profil B;
pierwsze uruchomienie wyłącznie dry-run. Bez zmian procesów MT5 ani Lab.

Audyt: istniejący `executor/paper.py` symuluje fill lokalnie, `demo.py` jest
adapterem testowym bez klienta brokera. `infrastructure/alpaca_market_data.py`
służy do archiwalnych świec 1Day. Nie wolno użyć ich snapshotów jako danych
wykonawczych. Nowy moduł `astraljet.alpaca_challenge` rozszerza obecny pakiet
i zachowuje granicę Lab/Executor. Odrębna baza chroni istniejące rejestry.
Git ma historię (HEAD c14945a), wiele zastanych niezatwierdzonych plików.
Snapshot przed zmianami: `.runtime/snapshots/alpaca-before-20260930-150408`.

Kolejność: konfiguracja i blokady → klient HTTP i sesje → journal → strategie
i scanner → ryzyko/executor → monitoring/reconciliation → API → testy →
rzeczywisty acceptance bez zleceń → uruchomienie → raport.

Decyzje implementacyjne: pojedynczy proces z blokadą systemową bazy;
SQLite WAL, trwałe klucze idempotencji, niepewny POST blokuje kolejne wejścia;
long premium options tylko po aktualnym kwotowaniu i sprawdzeniu kontraktu;
domyślny scanner akcji/krypto, opcje przez sygnał API z OCC.
Ryzyko SL jest estymacją, nie gwarancją ceny wykonania. Budżet rezerwowany
także dla pending orders. Dedykowane konto wymagane; cudze pozycje blokują
wejścia. Challenge nie zaczyna zegara w dry-run.

Odbiór wymaga rzeczywistego account/data, testów offline i restartu.
Brak uprawnień feedu lub kluczy = NOT READY, nigdy sztuczny PASS.
