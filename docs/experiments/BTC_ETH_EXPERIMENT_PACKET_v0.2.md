# BTC/ETH — karta pierwszego eksperymentu v0.2

Data: 20.09.2026. **DRAFT_BLOCKED — przygotowanie, nie zamrożony EXP i nie wynik.**

Powstała karta jednego konkretnego badania oraz powtarzalna kontrola jego wejść. Nie dopisano STRAT, DATA, EXP ani RUN. Nie zatwierdzono parametrów, nie przeniesiono danych, nie uruchomiono brokera. Poniższe reguły są propozycją do decyzji Karola; obecna STRAT v1 pozostaje `needs_input`.

## 1. Co sprawdzono na rzeczywistych plikach

| Wejście | Dokładne odniesienie | Wynik odczytu |
|---|---|---|
| Materiał | SRC-029, sekcja 6 pliku `5_strategii_inwestycyjnych_2026_PL.md`; runtime SRC-b85ac93a0ecd481ab685ce4189fc877c | SHA-256 zgodny z katalogiem; treść jest źródłem hipotezy, nie instrukcją wykonania |
| Szkic strategii | STRAT-5fb2fbd40d9f4842afdcaa2b2898a411, **v1**, rejestr `quickstart-2026-09-19` | `needs_input`, schemat bazy 3 |
| Dane | DATA-1e44487b0074425f959c2758c497c046, **v1**, rejestr `state` | `gaps`, blokada nieznanych kosztów; schemat bazy 4 |
| CSV Alpaca US | `alpaca_crypto_us_full_2015-01-01_2026-09-19.csv` | 4174 wiersze: BTCUSD 2087, ETHUSD 2087 |
| Zakres faktyczny | 2021-01-01–2026-09-18, dzienne znaczniki 00:00 UTC | Brak luk, duplikatów, niepoprawnego OHLC i braków opcjonalnych liczb w tym pliku; zero wierszy z zerowym wolumenem |
| Spójność plików | SHA-256 CSV i sidecar porównany z DATA/metadanymi | Zgodne. Obie bazy, CSV i sidecar mają identyczne hashe przed i po kontroli |

Status `gaps` jest zastanym statusem DATA, a nie wynikiem wykrycia luk w obecnej kontroli kalendarza. Nie zmieniamy go bez nowego poprawnego zapisu. W STRAT venue jest nieuzgodnione, a timeframe opisowy różni się od `1d` w DATA — to dodatkowe blokady formalne.

Pełny raport maszynowy: `.runtime/exports/btc-eth-inputs-2026-09-20-v1.json` (ignorowany przez Git). Hash raportu: `77c8dab5a0b94a240f7f25e4fe72c5e58a34aadd05600c66af0882e71b07a5e1`.

Hashe wejść:

- Źródło: `ED708DAF399C9851CA925F4050817936CD2F6F80D3C14A29899699CEA8FB6998`.
- CSV: `5012CA5FA52653633438853CEBEC8AE98C6DA5253B7C987A836E475FFE42CEFF`.
- Sidecar: `3DA30894AF73ACCC05DDB4B7E438EF344EFAE777185EE43D9C8F7445B069E61A`.

Hashe potwierdzają zgodność lokalnych bajtów, nie autentyczność kwotowań. Dokumentacja dostawcy wskazuje, że świece krypto mogą zawierać midpoint kwotowań; zerowy wolumen nie jest jedynym ograniczeniem interpretacji OHLC. [Alpaca — Historical Crypto Data](https://docs.alpaca.markets/us/docs/historical-crypto-data-1).

## 2. Hipoteza, nie obietnica

Sprawdzamy, czy tygodniowy filtr trendu BTC ogranicza maksymalne obsunięcie wobec benchmarku 80/20 po kosztach. Równocześnie mierzymy utracony lub uzyskany zwrot. Zakresów zysku autora materiału nie używamy jako prognozy, wymaganego wyniku ani automatycznej przepustki do DEMO.

Proponowane kryterium **samej hipotezy**: mniejsze maksymalne obsunięcie strategii w chronologicznym OOS niż benchmarku we wszystkich czterech wcześniej zadeklarowanych scenariuszach. Niespełnienie albo brak wystarczających obserwacji oznacza brak potwierdzenia/nierozstrzygnięcie. Nie oceniamy jeszcze atrakcyjności inwestycyjnej i nie nadajemy statusu kwalifikacji finansowej. Kryterium wymaga zgody Karola przed wynikiem.

## 3. Proponowane reguły — wymagają akceptacji

- Dane dzienne Alpaca US BTCUSD/ETHUSD, zegar UTC; ocena po zamknięciu świecy niedzielnej.
- Warunek dodatni: `BTC close[t] > SMA200[t]` i `SMA200[t] > SMA200[t-20]`. Równość traktowana jako warunek niespełniony.
- Gdy warunek jest fałszywy: cel BTC 35%, ETH 10%, cash 55%.
- Pierwsze tygodniowe spełnienie: BTC 52,5%, ETH 15%, cash 32,5%; drugie kolejne: 70% / 20% / 10%. Przerwanie serii przywraca cel risk-off.
- Przed pierwszym możliwym sygnałem 100% syntetycznej gotówki. Pierwszy sygnał ujemny inicjuje risk-off, dodatni pierwszą transzę; to jawny wybór modelowy, nie reguła potwierdzona w materiale.
- ETH sterowane wyłącznie sygnałem BTC; cash USD z oprocentowaniem 0%, bez shortów i dźwigni.
- Zmiana liczby jednostek tylko po przejściu stanu. Przy utrzymaniu stanu wagi **dryfują z cenami**; nie ma ukrytego codziennego rebalansu. Docelowe wagi nie są sztywnymi limitami ekspozycji całego rzeczywistego portfela.
- Benchmark 80/20 zaczyna na tej samej granicy wykonania; później rebalans na pierwszym dostępnym otwarciu miesiąca. Ten sam scenariusz czasu i kosztów, jawny koszt każdego obrotu.

**Zmiana wobec źródła:** reguła risk-off „zamknięcie poniżej 200DMA + pogorszenie struktury” zostaje zastąpiona negacją całego warunku dodatniego. Dodajemy N=20, konkretną odbudowę, stan początkowy i częstotliwość rebalansu. To adaptacja wymagająca zgody, nie wierna transkrypcja gotowej strategii.

## 4. Kalendarz i brak look-ahead

SMA200 porównana z SMA200 sprzed 20 dni potrzebuje **220 obserwacji z bieżącą świecą**, czyli 219 wcześniejszych. Poprzednia propozycja „pierwsze 200 dni warm-up” była niewystarczająca.

| Segment | Proponowany zakres / granica | Zweryfikowane pokrycie |
|---|---|---:|
| Dane IS, w tym warm-up | 2021-01-01–2024-12-31 | 1461 wspólnych dni |
| Pierwsza świeca z pełnym wskaźnikiem | niedziela 2021-08-08 | 220. obserwacja |
| Pierwsza modelowa granica wykonania | 2021-08-09 00:00 UTC | następna świeca istnieje |
| Chronologiczny OOS | 2025-01-01–2026-09-18 | 626 wspólnych dni |
| Historia przed OOS | 219 wcześniejszych wspólnych dni | dostępna |

Dzienne `open[t+1]` po `close[t]` nie używa tej samej świecy, lecz zakłada idealną dostępność danych na granicy dnia. Snapshot nie dowodzi opóźnienia publikacji ani ceny dostępnej zleceniu. Dlatego proponujemy cztery scenariusze: koszty bazowe/stress × następne otwarcie/opóźnienie o jeszcze jedną dobę. Scenariusz następnego otwarcia trzeba opisać jako uproszczenie, nie realistyczny model realizacji.

Wyłącznie metryki po pierwszej modelowej realizacji; warm-up nie jest okresem zarabiania. Do OOS przechodzą rzeczywiste jednostki, cash i stan maszyny z IS; resetuje się jedynie podstawa pomiaru zwrotu. Nie resetujemy portfela ani nie dopisujemy wcześniejszych zwrotów do OOS. Nie potwierdzono, że historyczny okres 2025–2026 nigdy wcześniej nie służył analizie: „OOS” oznacza tu podział chronologiczny, nie poświadczony nietknięty holdout.

## 5. Koszty: oddzielamy dane dostawcy od założeń

Tabela Alpaca odczytana 20.09.2026 podaje w pierwszym progu wolumenu 0,15% maker i 0,25% taker. Nie odpytywano taryfy konkretnego rachunku. [Alpaca — Crypto Spot Trading Fees](https://docs.alpaca.markets/us/docs/crypto-fees).

Propozycja A, **niezatwierdzona**:

| Scenariusz | Fee | Half-spread | Slippage | Suma na kupno lub sprzedaż |
|---|---:|---:|---:|---:|
| Bazowy | 25 bps | 5 bps | 10 bps | 40 bps |
| Stress | 25 bps | 20 bps | 30 bps | 75 bps |

Spread i slippage są założeniami wrażliwości, nie pomiarem. Dzisiejsza opłata zastosowana do całej historii jest stałym scenariuszem badawczym, nie odtworzonym historycznym cennikiem. Uproszczenie kosztu w ekwiwalencie USD nie odtwarza dokładnie pobierania opłaty w otrzymanym aktywie przez brokera.

Podstawa naliczenia: **suma bezwzględnych nominałów wykonanych kupien i sprzedaży BTC/ETH**. Nie połowa zmian wag z cash. Przykład techniczny: sprzedaż BTC za 100 i kupno ETH za 100 oznacza obrót 200 i przy 40 bps koszt 0,80, nie 0,40. Ledger musi uwzględniać koszty w bilansie cash i nie dopuszczać finansowania brakującej gotówki.

Alternatywa B: 50/100 bps jako ostrzejsze scenariusze. Alternatywa C: zostawić koszty nieustalone i nie zamrażać badania. Żaden wariant nie ustala budżetu prawdziwego rachunku. Proponowany indeks kapitału 100 służy tylko normalizacji, nie jest kwotą do inwestycji.

## 6. Braki techniczne — do zrobienia przez Codex, nie pytania do Karola

Audyt ograniczono do lokalnego `src/astraljet/lab/backtest.py`, SHA-256 `9956F20556A78029324AC5E2E04C6D86CCEA810B5BA5CC678D372C8E743D9A69`:

1. `generate_trend_targets` liczy zmiany codziennie; brak filtra niedzieli i stanu dwóch transz.
2. Pętla portfela pozostawia te same wagi między wycenami zamiast utrzymywać ilości jednostek. Taki model nie reprezentuje zaproponowanego dryfu i obrotu portfela.
3. Koszt oparty na połowie sumy zmian wag z cash nie reprezentuje opłaty każdej nogi rotacji BTC↔ETH. Wymagany ledger jednostek/cash i testy bilansu.
4. Silnik liczy wspólny zakres IS–OOS i wspólne metryki; brak oddzielnego raportu OOS i benchmarku w tej ścieżce.
5. Przebieg nie weryfikuje `experiment.code_hash` względem aktualnego kodu silnika. Przed badaniem potrzebny hash implementacji i zależności, kontrolowany przy wykonaniu i odtworzeniu.
6. STRAT i DATA znajdują się w dwóch rejestrach. Inspekcja nie przenosi ich i nie tworzy relacji. Miejsce zamrożonego badania oraz integracja z dotychczasową witryną wymagają uzgodnionego rozwiązania, nie automatycznej kopii bazy.

Nie zmieniono teraz starego silnika ani reguł działającego DEMO. Samo zaakceptowanie propozycji nie usuwa tych braków. Zanim powstanie oceniany RUN, implementacja musi przejść testy syntetyczne: przyszłe dane nie zmieniają wcześniejszych sygnałów, zgodność jednostek/cash, każda noga kosztu, granice niedzieli i OOS, odbudowa/jej przerwanie, opóźnienie realizacji, dwukrotna odtwarzalność i niezgodny hash kodu.

## 7. Trzy decyzje Karola przed zamrożeniem

1. **Reguły i mechanika:** zaakceptować pakiet z sekcji 3 albo wskazać zmianę. To nadal prywatne badanie spot BTC/ETH, nie wybór wykonawcy lub rachunku.
2. **Koszty:** A = 40/75 bps, B = 50/100 bps lub pozostawienie nieustalonych kosztów.
3. **Protokół:** zaakceptować daty, cztery stałe scenariusze czasu/kosztu i kryterium samej hipotezy. Bez optymalizacji po OOS, nowych płatnych usług i automatycznej kwalifikacji do DEMO.

Akceptacja dotyczy projektu badania; nie upoważnia do transakcji ani migracji runtime. Do czasu jej otrzymania pola `approved`, `execution_authorized` i `can_freeze` pozostają false. Wpisanie `approved=true` ręcznie do JSON nie stanowi uwierzytelnionej decyzji.

Maszynowa wersja propozycji: [btc_eth_experiment_proposal_v0.2.json](../../specs/001-build-astra-jet/examples/btc_eth_experiment_proposal_v0.2.json). To osobny format propozycji, **nie plik dla `experiment freeze`**. Dokumenty v0.1 zachowano jako historię; ta karta precyzuje ich braki i nie zmienia istniejących rekordów.
