# Research: Bezpieczny MVP Astra JET

## Decyzja 1 — lokalny rdzeń Python bez zewnętrznych zależności

**Decyzja**: Python >=3.12, standardowa biblioteka i CLI; lokalnie dostępny jest Python
3.14.4.

**Uzasadnienie**: pierwsze ryzyko projektu dotyczy wiarygodności stanu, wersji i dowodów,
nie skali ruchu HTTP. Brak zależności skraca start, upraszcza odtworzenie i pozwala testować
rdzeń bez sieci. Python pasuje do późniejszych obliczeń ilościowych.

**Rozważane alternatywy**: TypeScript/Next.js od początku (lepszy dashboard, większa
powierzchnia pierwszego przyrostu); FastAPI/Pydantic (wygodne kontrakty, ale zbędne przed
pojawieniem się usługi sieciowej); kopiowanie starego `astra_site` (odrzucone decyzją C).

## Decyzja 2 — SQLite: zdarzenia niezmienne plus projekcje relacyjne

**Decyzja**: jedna lokalna baza SQLite. `events` jest dopisywane, a tabele rekordów
przechowują wersjonowane projekcje. Korekta tworzy nowe zdarzenie i nową wersję rekordu.

**Uzasadnienie**: rozwiązanie zapewnia transakcje, trwałość, audyt i prosty backup bez
uruchamiania serwera. Sama kolekcja plików JSON utrudnia atomowe idempotentne operacje;
pełny event sourcing bez projekcji utrudnia status użytkownika.

**Rozważane alternatywy**: PostgreSQL (za ciężki dla jednego lokalnego użytkownika), same
pliki JSON/JSONL (słabsza spójność), wyłącznie tabele mutowalne (utrata historii).

## Decyzja 3 — jeden model koperty i jawne wersje artefaktów

**Decyzja**: każdy SRC/CAND/STRAT/DATA/EXP/RUN/REVIEW/RISK-DECISION/MANDATE/INCU ma
stabilne `record_id`, rosnącą `version`, właściciela, czas UTC, stan techniczny, hash
kanonicznej treści i ograniczenia. Zmiana znaczenia tworzy następną wersję.

**Uzasadnienie**: wspólna koperta pozwala łączyć Lab, przegląd i Wykonawcę bez ukrytych
założeń. Hash jest identyfikatorem treści, a nie dowodem jej prawdziwości.

**Rozważane alternatywy**: osobne, niespójne identyfikatory w każdym module (utrudniony
audyt); nadpisywanie rekordów (sprzeczne z konstytucją).

## Decyzja 4 — idempotencja przez klucz żądania i atomową transakcję

**Decyzja**: zapis operacji wymaga `idempotency_key`; unikalny indeks zwraca istniejący
rezultat dla identycznego żądania. Stan `uncertain` nie jest automatycznie ponawiany.

**Uzasadnienie**: chroni koszt, RUN i intencje zleceń przed duplikacją po restarcie.

**Rozważane alternatywy**: deduplikacja tylko po czasie (niejednoznaczna); pamięć procesu
(znika po restarcie); bezwarunkowy retry (niebezpieczny dla wykonania).

## Decyzja 5 — ASTRA Pro i Wykonawca przez port, nie bezpośredni import

**Decyzja**: Lab kończy pracę na pakiecie dowodów i nigdy nie importuje `executor`.
Wykonawca przyjmuje tylko identyfikatory zamrożonych wersji, decyzję ryzyka i ważny mandat.

**Uzasadnienie**: połączenie modułów zachowuje rozdział odpowiedzialności. Wspólny rejestr
nie daje Lab uprawnień wykonawczych.

**Rozważane alternatywy**: jeden serwis z komendą `trade` wywoływaną z Lab (odrzucone);
osobne procesy od pierwszego dnia (możliwe później, niepotrzebne dla granicy logicznej).

## Decyzja 6 — PAPER i DEMO, ale bez adaptera REAL

**Decyzja**: enum środowiska zawiera wyłącznie `PAPER_CONTINUOUS` i `BROKER_DEMO`.
Adapter DEMO ma jawny kontrakt, a pierwsza implementacja jest atrapą testową fail-closed.

**Uzasadnienie**: użytkownik zatwierdził oba tryby, lecz nie wybrał brokera ani sposobu
przechowywania sekretów. Brak wartości REAL w modelu jest mocniejszą kontrolą niż flaga.

**Rozważane alternatywy**: wspólny adapter z `is_live=false` (ryzyko błędnej konfiguracji);
wyłącznie PAPER (niezgodne z zatwierdzonym zakresem).

## Decyzja 7 — pierwszy materiał i kolejność strategii

**Decyzja**: plik `5_strategii_inwestycyjnych_2026_PL.md` jest rejestrowany jako SRC po
lokalizatorze i SHA-256, bez kopiowania do repo. Wszystkie pięć tez staje się CAND.
Pierwsza formalizacja dotyczy #5 BTC/ETH; niejasne pojęcie „pogorszenie struktury trendu”,
koszty, timing i dokładny dostawca danych muszą zostać jawnie uzupełnione przed EXP.

**Uzasadnienie**: #5 zawiera najbardziej mechaniczny zarys (200DMA), ale materiał nie jest
gotową strategią i nie dowodzi wskazanych zakresów zwrotu. Pozostałe cztery to głównie
tezy alokacyjne i wymagają osobnych reguł, danych, benchmarków oraz rebalansowania.

**Rozważane alternatywy**: traktowanie opisów jako gotowych strategii (odrzucone);
rozpoczęcie od pięciu pełnych backtestów równolegle (ryzyko pięciu różnych braków).

## Decyzja 8 — dane wejściowe jako jawny import, nie automatyczny download

**Decyzja**: MVP przyjmuje lokalny CSV dziennych danych spot. DATA zapisuje schemat,
strefę UTC, zakres, hash, dostawcę, miejsce notowań, transformacje, koszty i raport jakości.

**Uzasadnienie**: dokładny dostawca nie został jeszcze zatwierdzony. Import pozwala
zbudować i sprawdzić deterministyczny pipeline bez ukrytej zależności sieciowej.

**Rozważane alternatywy**: automatyczny publiczny feed (ryzyko rewizji i warunków użycia),
API brokera (miesza badanie z wykonaniem), syntetyczne dane jako jedyny odbiór (niezgodne z
wybraną strategią rynkową; syntetyczne przypadki pozostają testami mechaniki).
