<!--
Sync Impact Report

- Version change: 1.0.0 -> 2.0.0 (MAJOR)
- Modified principles:
  - I. Ochrona kapitału przed wynikiem -> I. Sygnały i pozycje wyznaczane przez Risk Management
  - III. Bramki przed handlem LIVE -> III. DEMO i LIVE jako odrębne tryby
  - VI. Jednoznaczne i bezpieczne wykonanie (doprecyzowanie granicy aktywacji)
- Added sections:
  - VII. Brak stałego pułapu wydatków i koszty z MT5
  - Decyzja Karola z 2026-09-20 i zakres jej wdrożenia
- Removed sections: none
- Removed requirements: obowiązkowy zestaw stałych pułapów ryzyka, ekspozycji,
  straty dziennej i drawdownu jako warunek każdego uruchomienia.
- Follow-up TODOs:
  - MIGRATION: spec.md FR-022–025, FR-030, plan.md oraz modele MANDATE,
    RISK-DECISION i BUDGET-STATUS wymagają nowej specyfikacji i testów;
    nie zostały zmienione w tym kroku.
  - RISK_POLICY: wskazać lub opracować konkretną wersję funkcji sizingu,
    obsługę nakładających się sygnałów i pozycji; brak wartości domyślnych
    ustalających za Karola zaangażowanie realnego kapitału.
  - MT5_COSTS: podłączyć odczyt i uzgodnienie kosztów, oddzielając rachunki,
    koszty rozliczone i szacunki; obecny adapter nie jest pełnym źródłem kosztów.
  - EXECUTION: przygotować kod DEMO/LIVE i instrukcję aktywacji przez właściciela;
    nie aktywować LIVE ani nie wysyłać zleceń w ramach tej zmiany.
- Runtime impact now: none. Nie zmieniono kodu, baz, usług, rachunków ani budżetów
  dostawców. Nie zmieniono szablonów Spec Kit ani istniejących specyfikacji.
-->

# Konstytucja projektu Astra JET

## Core Principles

### I. Sygnały i pozycje wyznaczane przez Risk Management

Każdy nowy, poprawny sygnał aktywnej strategii MUSI trafić do oceny Risk Management.
Nie ustanawia się stałego limitu liczby transakcji ani ręcznego zatwierdzania każdej
transakcji w uprzednio skonfigurowanym systemie. Ponowienie tego samego sygnału NIE JEST
nowym sygnałem i NIE MOŻE tworzyć dodatkowej pozycji.

Wielkość pozycji MUSI wyznaczać identyfikowalna, wersjonowana funkcja Risk Management,
uwzględniająca stan rachunku, istniejące pozycje, parametry strategii oraz specyfikację
instrumentu. Wynik MUSI zawierać skończony wolumen, dane wejściowe, czas i uzasadnienie.
Wykonawca NIE MOŻE samowolnie zwiększać tego wolumenu. Brak stałego pułapu NIE OZNACZA
nieskończonej pozycji, automatycznego użycia całego depozytu ani zgody na wymyślenie
reguły sizingu przez generator sygnałów.

Konstytucja nie narzuca stałych kwot/procentów ryzyka, ekspozycji, straty dziennej ani
drawdownu. Dotychczasowy obowiązek wpisania wszystkich takich pułapów zostaje zastąpiony
obowiązkiem konkretnej polityki Risk Management. Te wielkości MUSZĄ nadal być mierzone
i widoczne. Jeśli polityka stosuje ograniczenia dynamiczne, MUSZĄ one być jawne,
testowalne i odróżnione od limitu liczby transakcji.

Brak poprawnych danych, nierozstrzygnięty stan poprzedniego zlecenia, niezgodny rachunek,
niewystarczający depozyt, niedozwolony wolumen brokera albo brak wyniku Risk Management
MUSZĄ blokować nowe zlecenie z zapisaną przyczyną. Nie wolno podwyższać za małego
wolumenu do minimum brokera wbrew decyzji Risk Management. Ocena każdego sygnału nie
jest obietnicą jego realizacji przez brokera. Ręczny kill switch pozostaje dostępny.

### II. Zero obietnic zysku i uczciwe twierdzenia

Astra JET NIE MOŻE obiecywać, gwarantować ani sugerować pewnego zysku. Każde twierdzenie
o skuteczności MUSI jednoznacznie wskazywać środowisko: backtest, test poza próbą,
walk-forward, paper/DEMO albo LIVE. Wynik MUSI być raportowany netto po zweryfikowanych
kosztach wraz z okresem, liczbą transakcji, maksymalnym obsunięciem, przyjętym ryzykiem,
przedziałem niepewności i ograniczeniami danych.

Pojedynczy zysk, krótka seria, wynik najlepszego wariantu ani deklaracja z materiału
poradnikowego NIE SĄ dowodem trwałej przewagi. Wyniki historyczne i demonstracyjne MUSZĄ
być opisywane jako historyczne lub eksperymentalne i nie mogą być przedstawiane jako
prognoza. Niezweryfikowane liczby MUSZĄ być oznaczone jako twierdzenie, przykład lub
hipoteza, nigdy jako potwierdzony rezultat Astra JET.

### III. DEMO i LIVE jako odrębne tryby

Docelowy zakres Astra JET obejmuje DEMO i LIVE zgodnie z decyzją Karola z 2026-09-20.
Nie należy ponownie pytać, czy system ma obsługiwać oba tryby. Rozszerzenie zakresu
NIE JEST dowodem gotowości obecnego kodu ani wyborem konkretnego rachunku lub strategii.

Każda strategia MUSI przejść udokumentowaną sekwencję: hipoteza i plan, poprawny backtest,
test poza próbą lub walk-forward, testy odporności, paper/DEMO w warunkach zgodnych z
badaniem, a dopiero potem wdrożenie LIVE aktywowane przez właściciela. Przejście między etapami wymaga
spełnienia kryteriów zapisanych przed poznaniem wyniku. Kryteria MUSZĄ obejmować co
najmniej przewagę netto, niepewność statystyczną, obsunięcie, liczbę transakcji, stabilność
w reżimach rynku, koszty, poślizg i poprawność wykonania.

Konfiguracja walidacyjna MUSI odtwarzać przebadane instrumenty, okna czasowe, logikę
rozmiaru pozycji, koszty i politykę Risk Management. Jeżeli różni się od badania, MUSI być nazwana nowym
eksperymentem i nie może potwierdzać poprzedniego wyniku. Decyzja LIVE wymaga jawnej,
datowanej konfiguracji właściciela dla konkretnego rachunku, wersji strategii i polityki
Risk Management oraz planu wycofania. Nie wymaga ponownego zatwierdzania samego zamiaru
budowy LIVE ani każdej transakcji w tej konfiguracji. Spełnienie bramki
technicznej nie zastępuje dowodu przewagi.

### IV. Powtarzalne i prerejestrowane eksperymenty

Przed uruchomieniem eksperymentu MUSZĄ zostać zapisane: hipoteza, źródła i wersje danych,
uniwersum, okresy in-sample i out-of-sample, kod lub commit i jego skrót, parametry,
model kosztów, seed losowy, metryki, progi decyzji oraz reguły przerwania. Plan MUSI mieć
znacznik czasu i niezmienny skrót. Dane surowe, konfiguracja, kod, logi i wyniki MUSZĄ być
przechowane tak, aby inna osoba lub proces mogły odtworzyć rezultat.

Kod i konfiguracja rundy MUSZĄ być zamrożone na czas pomiaru. Zmiana w trakcie rundy
tworzy nową wersję eksperymentu; wyników różnych wersji NIE WOLNO łączyć bez jawnej
segmentacji. Negatywne i niejednoznaczne wyniki MUSZĄ pozostać w rejestrze. Uzasadnienie:
prerejestracja i pełna historia ograniczają dopasowanie do danych, selekcję zwycięzców i
niemożliwe do odtworzenia decyzje.

### V. Obowiązkowa niezależna weryfikacja

Żaden wynik wpływający na kapitał NIE MOŻE zostać zaakceptowany na podstawie jednego
silnika, jednego raportu ani własnego opisu autora. Wynik MUSI zostać sprawdzony co najmniej
przez odtworzenie z zapisanych artefaktów i porównanie z niezależnym źródłem właściwym dla
ryzyka, na przykład drugim silnikiem, obliczeniem kontrolnym, danymi brokera lub audytem
tylko do odczytu. Koszty i wykonanie MUSZĄ zostać uzgodnione z faktycznie rozliczonymi
transakcjami przed decyzją LIVE.

Weryfikacja MUSI kończyć się werdyktem `verified`, `unverified` albo `rejected` oraz listą
dowodów i nierozstrzygniętych luk. Brak danych, niezgodność konfiguracji albo brak próby
niezależnej oznaczają `unverified`, a nie sukces. Osoba lub agent dokonujący weryfikacji
NIE MOŻE potajemnie zmieniać badanego systemu w trakcie audytu.

### VI. Jednoznaczne i bezpieczne wykonanie

W jednym środowisku wykonawczym może działać tylko jedna zatwierdzona wersja wykonawcy.
Start MUSI wykrywać konkurencyjny proces, a stan rund, pozycji i decyzji MUSI znajdować się
w jawnej, trwałej lokalizacji niezależnej od prywatnego katalogu aplikacji. Każda akcja
MUSI mieć identyfikator, czas, źródło wykonania, wersję kodu i wynik brokera. Zlecenia oraz
zamknięcia MUSZĄ być idempotentne.

Stany niepewne MUSZĄ mieć limit czasu, procedurę uzgodnienia z brokerem, alarm i bezpieczną
ścieżkę wyjścia. System MUSI zapewniać ręczny kill switch, monitoring procesu i terminala,
powiadomienie o utracie działania oraz rozdzielenie kont DEMO i REAL. Wdrożenia do
aktywnego wykonawcy są dozwolone wyłącznie między rundami, z określonego commita i z
udokumentowanym planem powrotu.

DEMO i LIVE MUSZĄ mieć osobne konfiguracje, identyfikatory rachunków i zapis stanu.
NIE WOLNO przełączać ich automatycznie po błędzie, skopiować mandatu DEMO jako LIVE ani
uznać aktualnie zalogowanego terminala za zamierzony rachunek bez sprawdzenia tożsamości.
Asystent budujący system może przygotować i przetestować kod oraz instrukcję obsługi;
nie składa zleceń LIVE ani nie aktywuje za właściciela automatycznego handlu LIVE.

### VII. Brak stałego pułapu wydatków i koszty z MT5

Karol zniósł stały pułap wydatków AI i pracy istniejącego systemu. Nie należy ponownie
pytać o dodatkowe 1 USD ani traktować wcześniejszego 25 USD/miesiąc jako aktualnego
życzenia właściciela. Docelowy model MUSI jawnie rozróżniać brak pułapu od pułapu równego
zero i od nieustalonego budżetu; NIE WOLNO zastąpić tej decyzji dowolną wysoką liczbą.
Dotyczy to pracy nad Astrą w istniejących integracjach, nie zakupu niepowiązanych usług,
zawarcia nowej umowy lub zmiany rachunku rozliczeniowego.

Brak pułapu NIE ZWALNIA z ewidencji kosztu rozliczonego, aktywnych rezerwacji i kosztu
nieuzgodnionego. Te same płatne zadania NIE MOGĄ wykonywać się wielokrotnie wskutek
utraty odpowiedzi. Błędy uwierzytelnienia, brak środków u dostawcy i jego ograniczenia
techniczne MUSZĄ być zgłaszane; nie wolno ich obchodzić lub bez końca ponawiać wywołań.
Nie ma obowiązku wydawania pieniędzy, gdy zadanie da się wiarygodnie wykonać lokalnie.

Koszty brokerskie dla rachunku MT5 MUSZĄ pochodzić z odczytu jego danych, a nie z
obowiązkowego ręcznego wpisywania przez Karola. Bieżące parametry i spread pochodzą
ze specyfikacji/notowań instrumentu; naliczone prowizje, opłaty i swap z historii
rozliczeń. Osobne operacje prowizyjne MUSZĄ zostać uzgodnione bez podwójnego naliczania.
Brak rekordu NIE JEST dowodem zerowego kosztu. Źródła techniczne:
[specyfikacja instrumentu](https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfo_py)
oraz [właściwości rozliczeń MT5](https://www.mql5.com/en/docs/constants/tradingconstants/dealproperties).

Koszty zaobserwowane, rozliczone i szacowane MUSZĄ być rozdzielone. Dzisiejszy spread,
taryfa lub pojedyncze rozliczenie NIE DOWODZĄ kosztu całej historii ani przyszłego
poślizgu. Wyniki badań MUSZĄ ujawniać zastosowany model kosztów i jego ograniczenia;
nie wolno oznaczyć kosztów jako zweryfikowanych tylko dlatego, że źródłem jest MT5.
Koszty AI i innych usług poza brokerem MUSZĄ być ewidencjonowane oddzielnie — MT5 nie
jest ich źródłem rozliczeniowym.

## Klasyfikacja dowodów i wiążąca baza

Status źródłowy opisuje pochodzenie reguły, nie jej siłę. Po ratyfikacji wszystkie zasady
tej konstytucji są wiążące.

- **Potwierdzone w materiałach projektu:** audyt z 2026-09-15 dokumentuje blokadę DEMO,
  brak przewagi odróżnialnej od zera po kosztach, brak niezależnej próby, niezgodność rundy
  z przebadanymi warunkami, zmianę kodu podczas rundy, ryzyko wielu wykonawców i nietrwałą
  lokalizację stanu. Dokumentuje również dobre praktyki: plan zapisany przed testem ze
  skrótem SHA-256, zachowanie negatywnego wyniku, zamrożenie kodu oraz audyt tylko do
  odczytu. Są to ustalenia historyczne na moment audytu, a nie potwierdzenie stanu obecnego.
- **Potwierdzone jako metodologia, nie jako wynik Astra JET:** materiały o analizie botów,
  architekturze i portfelu konsekwentnie rozdzielają backtest od forward testu, wskazują
  drawdown, koszty, dywersyfikację i inkubację jako elementy walidacji. Nie stanowią one
  niezależnego dowodu rentowności ani poprawności bieżącego wdrożenia.
- **Rekomendacje przyjęte jako nowe reguły zarządcze:** bezwzględny zakaz obietnic zysku,
  trzywartościowy werdykt weryfikacji, obowiązkowa druga ścieżka sprawdzenia, jawna zgoda
  na LIVE, pełna identyfikacja wykonawcy oraz formalne bramki promocji środowisk.
- **Decyzja Karola z 2026-09-20:** odpowiedź „1 no limit wszędzie. 2 demo i live” na
  pytanie o limity transakcji/AI i tryby. Poprzedzająca wypowiedź przekazuje sizing
  Risk Management i wskazuje MT5 jako źródło kosztów brokerskich. Jest to aktualna
  dyspozycja właściciela, nie twierdzenie z materiału źródłowego. Potwierdza brak stałych
  pułapów oraz oba tryby, ale nie podaje konkretnej funkcji sizingu, rachunku LIVE,
  wersji strategii ani dowodów jej walidacji. Nie przypisuje się jej tych brakujących
  parametrów.
- **Niezweryfikowane:** benchmarki, promocyjne stopy zwrotu, prognozy, przykładowe progi i
  wyniki opisane w materiałach poradnikowych pozostają hipotezami do niezależnego
  odtworzenia. Nie wolno ich używać jako podstawy decyzji kapitałowej ani komunikatu
  marketingowego o Astra JET.

## Proces pracy i bramki jakości

1. Każda specyfikacja MUSI określić cel, zakres, środowisko, klasę ryzyka, źródła danych,
   mierzalne kryteria akceptacji i kryteria przerwania. Założenia MUSZĄ być oddzielone od
   faktów, a brak dowodu oznaczony wprost.
2. Plan MUSI mapować każde kryterium na test, artefakt dowodowy i odpowiedzialną rolę.
   Dla zmian wykonawczych MUSI zawierać analizę trybów awarii, migrację stanu, monitoring,
   rollback i dowód rozdzielenia DEMO/REAL.
3. Zadania MUSZĄ obejmować testy, zapis wersji danych i kodu, weryfikację niezależną oraz
   aktualizację dokumentacji. Zadanie nie jest ukończone tylko dlatego, że kod działa.
4. Implementacja NIE MOŻE zmieniać aktywnego eksperymentu. Wersja badawcza, uruchomieniowa
   i audytowana MUSZĄ być jednoznacznie identyfikowalne.
5. Przegląd zgodności MUSI sprawdzić zasady I-VII. Krytyczne lub wysokie ustalenie dotyczące
   bezpieczeństwa, wykonania albo wiarygodności wyniku blokuje promocję do kolejnego etapu.
6. Convergence kończy pracę dopiero wtedy, gdy wymagania, kod, testy i dowody są zgodne,
   a nierozstrzygnięte luki mają właściciela, termin i wpływ na decyzję. Brak weryfikacji
   nie może być raportowany jako zakończenie.

### Zakres wdrożenia decyzji z 2026-09-20

Ta rewizja zmienia wyłącznie zasady projektu. Nie zmienia konfiguracji aktywnych usług,
budżetu dostawcy, rachunków, rejestrów, wykonawców ani wyników wcześniejszych eksperymentów.
Historyczne raporty zachowują znaczenie dla daty ich sporządzenia. Sam zapis „bez limitu”
nie usuwa blokad z istniejącej aplikacji.

Przed implementacją nowej polityki wymagane są następujące prace:

- TODO(MIGRATION): nowa specyfikacja zmian do `specs/001-build-astra-jet/`, szczególnie
  FR-022–025 i FR-030, planu oraz kontraktów MANDATE, RISK-DECISION i BUDGET-STATUS.
  Obecny MVP wyklucza REAL i wymaga liczbowego limitu; nie należy przedstawiać go jako
  już zgodnego z wersją 2.0.0. Nowy tryb musi być odrębnie testowany, nie odblokowany
  wyłącznie przez usunięcie kontroli typu rachunku.
- TODO(RISK_POLICY): wskazać lub przygotować testowalną funkcję sizingu wraz z obsługą
  jednoczesnych sygnałów, pozycji i ograniczeń brokera. Brak pułapów nie definiuje tej
  funkcji. Nie wpisywać zmyślonego procentu ryzyka ani alokacji kapitału jako decyzji Karola.
- TODO(MT5_COSTS): podłączyć i przetestować automatyczny odczyt kosztów dla wskazanego
  rachunku, ich uzgodnienie i jawne oznaczenie braków. Dotychczasowe koszty podane w planie
  eksperymentu nie stają się automatycznie pomiarami MT5.
- TODO(EXECUTION): przygotować odrębne konfiguracje DEMO/LIVE, testy pomylenia rachunków,
  powtórzeń i utraty łączności oraz instrukcję aktywacji przez właściciela. Praca
  projektowa nie składa zleceń na rzeczywistym rachunku.

## Governance

Niniejsza konstytucja ma pierwszeństwo przed lokalnymi skrótami procesu, promptami,
instrukcjami agentów i presją operacyjną. Każda specyfikacja, plan, lista zadań, przegląd i
decyzja o promocji środowiska MUSZĄ zawierać kontrolę zgodności z jej zasadami. Odstępstwo
dotyczące kapitału LIVE, rozdzielenia DEMO/REAL lub obowiązkowej weryfikacji jest
niedozwolone; inne odstępstwo wymaga przed wykonaniem datowanej decyzji właściciela,
uzasadnienia, oceny ryzyka, zakresu czasowego i planu usunięcia.

Zmiana konstytucji wymaga pisemnego uzasadnienia, wskazania dowodów lub statusu
rekomendacji, raportu wpływu na aktywne specyfikacje i akceptacji właściciela projektu.
Wersjonowanie jest semantyczne: MAJOR dla usunięcia lub niezgodnej zmiany zasady, MINOR
dla nowej zasady lub istotnego rozszerzenia obowiązków, PATCH dla doprecyzowania bez zmiany
znaczenia. Każda zmiana MUSI zaktualizować datę ostatniej modyfikacji i opisać wymagane
migracje. Raport Sync Impact Report MUSI zostać przejrzany i usunięty przed commitem.

Przed użyciem kapitału LIVE wymagany jest niezależny przegląd zgodności całego łańcucha
dowodów. Okresowe audyty MUSZĄ być wykonywane tylko do odczytu, o ile odrębnie zatwierdzony
plan nie wymaga testu ingerującego. Złożoność oraz wyjątki MUSZĄ być uzasadnione ryzykiem i
wartością dowodową, a nie wygodą implementacji.

**Version**: 2.0.0 | **Ratified**: 2026-09-19 | **Last Amended**: 2026-09-20
