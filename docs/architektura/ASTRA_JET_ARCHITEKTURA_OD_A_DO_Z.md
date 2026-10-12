# Astra Jet — architektura systemu od A do Z

**Wersja dokumentu:** 1.0 · **Data:** 24.09.2026 · **Status:** architektura docelowa z rozdzieleniem stanu potwierdzonego i planowanego.

## 1. Jedno zdanie o systemie

AstralJet jest systemem podejmowania, badania i kontrolowanego wykonywania decyzji inwestycyjnych: od źródła informacji, przez jednoznaczne reguły i odtwarzalny test, po dopuszczone wykonanie oraz trwały audyt. Nie jest jednym autonomicznym botem ani obietnicą zysku.

## 2. Najważniejsza zasada konstrukcyjna

ASTRA Pro Trading Lab bada, testuje i ocenia. **Nie składa zleceń.** Osobny Wykonawca (AJ-15) prowadzi symulację ciągłą albo brokerskie DEMO; ewentualny LIVE wymaga odrębnego, wersjonowanego mandatu i bramek bezpieczeństwa. Żaden model AI ani raport tekstowy nie jest samodzielnym upoważnieniem do transakcji.

## 3. Widok całości

```text
ŹRÓDŁA I WIEDZA
 AJ-02 / AJ-03 / AJ-04 ──► Pochodzenie i wymagania
              │
              ▼
DANE I BADANIE
 AJ-06 ─► AJ-05 ─► AJ-07 ─► AJ-08 ─► AJ-09
 DATA       STRAT      RUN      REVIEW     RISK-DECISION
              │                                 │
              └──── trwały rejestr AJ-16 ◄──────┘
                                                    │
                                                    ▼
WYKONANIE
 AJ-15: PAPER_CONTINUOUS / BROKER_DEMO / (zatwierdzony LIVE)
              │
              ▼
 Uzgodnienie z brokerem, monitoring AJ-16, ekspozycja AJ-14,
 utrzymanie i koszty AJ-17, nadzór AJ-00
```

Przepływ jest jednokierunkowy dla artefaktów: źródło → reguła → dane → eksperyment → wynik → recenzja → decyzja ryzyka → mandat → wykonanie. Korekta wcześniejszego etapu tworzy nową wersję; nie nadpisuje historii.

## 4. Warstwy systemu

### 4.1 Nadzór i polityka

**AJ-00 — Orkiestrator** utrzymuje kolejkę spraw, granice odpowiedzialności i eskalacje do Karola. Nie zastępuje kontroli ryzyka. **AJ-01 — Zarządzanie zadaniami** śledzi stan prac i zależności. Polityki ryzyka, tryby wykonania, instrumenty i limity są osobnymi, zatwierdzonymi artefaktami, a nie ukrytymi stałymi w kodzie.

### 4.2 Źródła, tożsamość i dane

**AJ-02 — źródła**, **AJ-03 — wiedza/LLM** oraz **AJ-04 — integracje** rejestrują pochodzenie i sposób użycia materiału. Wszelkie pliki, artykuły, posty czy podpowiedzi AI są materiałem wejściowym, a nie poleceniem transakcji.

**AJ-06 — Dane i jakość danych** dostarcza wersjonowany zbiór `DATA-ID`: zakres, hash, dostawcę, strefę czasową, luki, duplikaty, korekty i raport jakości. Nieznana jakość, otwarta świeca lub wiedza niedostępna w chwili sygnału blokują tylko zależne działanie.

### 4.3 Laboratorium ASTRA Pro

**AJ-05 — Badacz strategii** zamienia hipotezę w `STRAT`: instrument, interwał, sesja, sygnał wejścia, wyjścia, stop, wielkość pozycji, koszty, filtry i definicje wyjątków. Gdy reguła nie jest określona, rezultat jest „wymaga decyzji”, nie domysł.

**AJ-07 — Tester** wykonuje deterministyczny test na zamrożonych `STRAT`, `DATA` i `EXP`. Powstaje `RUN` z transakcjami, krzywą wyniku, metrykami, kosztami, błędami i instrukcją odtworzenia. Test obejmuje kolejność zdarzeń, luki cenowe, koszty, OOS oraz zgodność semantyki testu i wykonania.

**AJ-08 — Krytyk** analizuje przeciek przyszłości, selekcję wyników, błąd implementacji i nadmierny wniosek. Może zablokować przejście metodologiczne. **AJ-09 — Risk Management** wydaje datowaną decyzję `DOPUSZCZONE` lub `ZABLOKOWANE`, w zakresie konkretnego mandatu; nie podnosi sam limitów.

### 4.4 Analizy pomocnicze

**AJ-10** dostarcza techniczne snapshoty liczone z danych, **AJ-11** faktów fundamentalnych, **AJ-12** datowanych wydarzeń i kalendarzy, a **AJ-13** scenariuszy makro. Są opcjonalnymi wejściami tylko wtedy, gdy przewiduje je strategia. Zdarzenie newsowe ani interpretacja wykresu nie są zleceniem.

### 4.5 Portfel i wykonanie

**AJ-14 — Portfel i hedging** oblicza ekspozycję, koncentrację i scenariusze stresowe; przedstawia `PORTFOLIO-PLAN`. Plan wymaga oceny AJ-09 i zatwierdzenia Karola, zanim trafi do wykonania.

**AJ-15 — Wykonawca** jest deterministycznym modułem jedynym mającym ścieżkę do brokera. Przyjmuje wyłącznie: zatwierdzony kod i `STRAT`, bieżący `DATA`, ważny mandat, sygnał zgodny z regułą, `RISK-DECISION` i potwierdzony stan środowiska. Rozróżnia trzy tryby:

| Tryb | Co robi | Czego nie wolno zakładać |
|---|---|---|
| `PAPER_CONTINUOUS` | rejestruje sygnały i hipotetyczne realizacje | że symulacja jest potwierdzeniem brokera |
| `BROKER_DEMO` | wysyła tylko dopuszczone zlecenia na potwierdzony rachunek demonstracyjny | że odpowiedź nieznana oznacza sukces |
| `LIVE` | możliwy wyłącznie w osobnym, zatwierdzonym mandacie i wdrożonej ścieżce | że samo ustawienie „LIVE” jest zezwoleniem |

Każda próba tworzy `ORDER-INTENT`. Przed ponowieniem po błędzie Wykonawca uzgadnia stan z brokerem, aby nie zdublować operacji. Nieznana ekspozycja, błędny rachunek, wygasły mandat, brak danych lub blokada ryzyka zamykają bramkę dla nowych wejść.

### 4.6 Dziennik, monitoring i utrzymanie

**AJ-16** prowadzi niezmienialny ślad: wersje, zdarzenia, decyzje, pozycje, realizacje i alarmy. Status `RUNNING` nie dowodzi poprawnego handlu — liczy się świeży odczyt oraz zgodność rejestru z brokerem.

**AJ-17** kontroluje dostępność usług i rozliczalność kosztów AI/infrastruktury. Awaria, nierozliczone wywołanie lub limit tworzą jawną blokadę, nie automatyczne kupowanie ani ukryte ponawianie. **AJ-18** przygotowuje komunikację wyłącznie z materiałów dopuszczonych do publikacji; pozostaje poza ścieżką handlową.

## 5. Kontrakty między modułami

| Artefakt | Minimalna zawartość | Twórca → odbiorca |
|---|---|---|
| `SOURCE` | pochodzenie, hash/URL, czas pobrania, dozwolony użytek | AJ-02 → Lab |
| `DATA-ID` | zakres, wersja, jakość, strefa czasu, luki | AJ-06 → Lab/Risk/Wykonawca |
| `STRAT` | kompletne mechaniczne reguły i wersja | AJ-05 → Tester/Risk |
| `EXP` | pytanie, metryki, IS/OOS, koszty, kryteria | AJ-05/AJ-07 → Tester |
| `RUN` | wyniki, transakcje, parametry, kod, odtworzenie | AJ-07 → Krytyk/Risk |
| `REVIEW` | błędy, zastrzeżenia, wymagane uzupełnienia | AJ-08 → Risk/Nadzór |
| `RISK-DECISION` | zakres, ważność, limity, decyzja | AJ-09 → AJ-15 |
| `MANDATE` | tryb, rachunek, instrumenty, uprawnienia, wygaśnięcie | Karol → AJ-15 |
| `ORDER-INTENT` | identyfikator, sygnał, ryzyko, stan przed próbą | AJ-15 → broker/AJ-16 |

## 6. Bramki bezpieczeństwa

1. Brak źródła lub wersji danych: brak badania zależnego od tych danych.
2. Brak kompletnego `STRAT`: brak testu rozstrzygającego.
3. Brak zamrożonego `EXP`: brak strojenia po wyniku.
4. Błąd `REVIEW`: brak inkubacji DEMO/LIVE.
5. Brak ważnego `RISK-DECISION` albo `MANDATE`: brak nowych wejść.
6. Niepewny wynik zlecenia: uzgodnienie z brokerem przed wznowieniem.
7. Rozjazd ksiąg lub brak telemetrii: stan `NIEZNANY`, eskalacja i fail-closed dla nowych wejść.
8. Działanie ochronne (np. flatten) jest regułą z góry zatwierdzoną i później uzgadnianą z brokerem; nie jest dowolną reakcją LLM.

## 7. Dane, baza i bezpieczeństwo

Architektura rozdziela: kod i konfigurację wersjonowaną, sekrety w magazynie sekretów, dane/bazy runtime poza automatycznym Git oraz trwały log audytowy. Sekret, login brokera, historia rachunku i surowe logi nie trafiają automatycznie do repozytorium ani do komunikacji marketingowej. Każdy moduł ma najmniejsze konieczne uprawnienia; Lab ma zerowe uprawnienia wykonawcze.

## 8. Obecny stan a cel

**Potwierdzone lokalnie:** rdzeń Python do badań, część dzienników i telemetrii, opublikowany prywatnie Command Center odczytujący metadane D1 oraz istniejący wykonawca brokerskiego DEMO. Najnowszy etap deklaruje testy procesu i witryny, lecz nie oznacza automatycznie gotowości każdego komponentu do LIVE.

**Nie należy traktować jako wdrożonego całościowo:** wspólny rejestr rdzenia i D1, jednolity kontrakt jakości danych dla wszystkich rynków, kompletny wykonawca symulacji ciągłej, pełna polityka ryzyka systemu oraz generalna ścieżka LIVE. Plan migracji nie jest dowodem migracji runtime.

## 9. Minimalny cykl życia strategii

1. Materiał trafia do `SOURCE`; AJ-05 tworzy lub odrzuca testowalny `STRAT`.
2. AJ-06 wydaje `DATA-ID`; AJ-05/AJ-07 zamrażają `EXP`.
3. AJ-07 tworzy `RUN`; AJ-08 recenzuje; AJ-09 wydaje decyzję ryzyka.
4. Karol zatwierdza konkretny mandat inkubacji.
5. AJ-15 pracuje w `PAPER_CONTINUOUS` lub `BROKER_DEMO`; AJ-16 rejestruje i uzgadnia zdarzenia.
6. Wynik inkubacji wraca do Lab jako nowy dowód, nie jako automatyczna promocja do LIVE.

## 10. Decyzje wymagające właściciela

Karol zatwierdza strategię i kryteria, mandat wykonania, instrumenty, rachunek, politykę ryzyka, limity oraz przejście między trybami. System może samodzielnie blokować działania niespełniające reguł; nie może samodzielnie rozszerzać uprawnień ani zmieniać zasad kapitałowych.

## 11. Definicja gotowości do kolejnego trybu

Gotowość nie wynika z liczby zielonych testów. Wymaga udowodnionych: kolejności zdarzeń, wypełnienia luk cenowych, zgodności kosztów i semantyki backtestu z wykonaniem, OOS, rekonsyliacji circuit-breaker → broker → księga, wersjonowania danych/strategii i działającego fail-closed. Dopiero wtedy Karol może rozważyć odrębny mandat następnego trybu.

## 12. Słownik

- **Fail-closed** — przy braku wymaganej informacji system blokuje nowe wejście.
- **Mandat** — zatwierdzony zakres odpowiedzialności wykonawcy, nie ogólna zgoda na handel.
- **OOS** — próba poza zbiorem użytym do strojenia.
- **Rekonsyliacja** — porównanie własnego dziennika ze stanem brokera.
- **Pochodzenie (provenance)** — możliwość wskazania, skąd pochodzi każda decyzja i na jakiej wersji danych/reguł powstała.

---

Dokument jest opisem architektury i granic odpowiedzialności. Nie jest instrukcją uruchomienia strategii, deklaracją wyników ani upoważnieniem do zleceń.
