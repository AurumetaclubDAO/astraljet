# Plan implementacji: Bezpieczny MVP Astra JET

**Gałąź/specyfikacja**: `001-build-astra-jet` (katalog specyfikacji; lokalny Git pozostaje na `main`)  
**Data**: 2026-09-19  
**Specyfikacja**: [spec.md](spec.md)

## Podsumowanie

Budujemy nowy, lokalny rdzeń AstralJet w `D:\Astra Jet`. ASTRA Pro rejestruje źródła,
formalizuje strategie, zamraża eksperymenty, uruchamia odtwarzalne testy i przekazuje
pakiet dowodów do niezależnego przeglądu. Osobny Wykonawca obsługuje wyłącznie
`PAPER_CONTINUOUS` i `BROKER_DEMO` po otrzymaniu jawnego mandatu. Moduły komunikują się
przez wersjonowane rekordy i dopisywany dziennik zdarzeń SQLite; ścieżka REAL nie istnieje.

Pierwszy przyrost dostarcza fundament: modele domenowe, trwały rejestr, bezpieczny import
źródła, rejestr pięciu kandydatów i czytelny status. Następne przyrosty realizują pełny
LAB-01–LAB-12, przegląd, mandat oraz dwa tryby inkubacji.

## Kontekst techniczny

**Język/wersja**: Python >=3.12; środowisko deweloperskie potwierdzone na Python 3.14.4  
**Główne zależności**: wyłącznie biblioteka standardowa w rdzeniu MVP (`sqlite3`,
`dataclasses`, `enum`, `hashlib`, `json`, `argparse`, `decimal`, `zoneinfo`, `uuid`)  
**Przechowywanie**: SQLite z włączonymi kluczami obcymi i WAL; append-only `EVENT` oraz
relacyjne projekcje rekordów; katalog stanu podawany jawnie i ignorowany przez Git  
**Testowanie**: `unittest`, testy kontraktowe, integracyjne i jednostkowe; dane tymczasowe  
**Platforma docelowa**: Windows 11 lokalnie, kod domenowy przenośny na systemy POSIX  
**Typ projektu**: pojedynczy pakiet biblioteczny + CLI; adaptery danych i DEMO jako porty  
**Cele wydajnościowe**: odczyt statusu poniżej 2 s dla 100 000 zdarzeń; pojedynczy zapis
lokalny p95 poniżej 100 ms; alarm blokujący nowe ryzyko widoczny do 60 s  
**Ograniczenia**: działanie offline w rdzeniu; brak sekretów, danych rynkowych i baz w Git;
brak sieci/brokera bez jawnego adaptera; brak automatycznego ponowienia stanu niepewnego;
kwoty liczone jako `Decimal`; czasy jako UTC ISO-8601  
**Skala/zakres**: jeden właściciel, do 100 strategii, 10 000 przebiegów i 1 000 000 zdarzeń;
pięć początkowych kandydatów, jeden pełny przebieg odbiorowy

## Kontrola konstytucji

*Brama przed Phase 0: PASS. Ponowna kontrola po projekcie: PASS.*

| Zasada | Sposób spełnienia | Dowód/test |
|---|---|---|
| I. Ochrona kapitału | Fail-closed, mandat i decyzja ryzyka przed Wykonawcą; brak REAL | testy odrzucenia bez mandatu, przy nieświeżych danych i przekroczonym limicie |
| II. Uczciwe twierdzenia | Rodzaj dowodu i ograniczenia są wymagane; źródłowe zakresy wyników pozostają hipotezami | test raportu bez nieoznaczonej obietnicy i bez zerowania brakujących kosztów |
| III. Bramki przed LIVE | MVP kończy się na PAPER/DEMO, a typ środowiska nie zawiera REAL | test kontraktowy odrzuca każdą wartość środowiska spoza dozwolonego enum |
| IV. Powtarzalność | EXP wiąże hashe STRAT, DATA, kodu i planu przed RUN | dwa przebiegi kontrolne porównane z zapisaną tolerancją |
| V. Niezależna weryfikacja | REVIEW jest osobnym rekordem i wymaga odrębnego aktora/procesu | test nie pozwala autorowi RUN samodzielnie oznaczyć wyniku `verified` |
| VI. Bezpieczne wykonanie | Idempotency key, lease jednego wykonawcy, reconciliation i kill switch | test restartu, duplikatu, konfliktu lease oraz stanu `uncertain` |

Nie ma odstępstw wymagających wpisu w tabeli złożoności.

## Struktura projektu

### Dokumentacja funkcji

```text
specs/001-build-astra-jet/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── event.schema.json
│   └── executor-adapter.md
└── tasks.md
```

### Kod źródłowy

```text
pyproject.toml
src/astraljet/
├── __init__.py
├── cli.py
├── config.py
├── domain/
│   ├── enums.py
│   ├── errors.py
│   ├── records.py
│   └── validation.py
├── application/
│   ├── intake.py
│   ├── status.py
│   ├── experiments.py
│   ├── reviews.py
│   └── mandates.py
├── lab/
│   ├── strategy.py
│   ├── data_quality.py
│   ├── backtest.py
│   └── reproduction.py
├── executor/
│   ├── ports.py
│   ├── guard.py
│   ├── paper.py
│   └── demo.py
└── infrastructure/
    ├── database.py
    ├── migrations.py
    ├── repositories.py
    └── event_store.py
tests/
├── contract/
├── integration/
├── unit/
└── fixtures/
```

**Decyzja strukturalna**: jeden pakiet zapewnia spójne modele i prosty start lokalny, ale
granice `lab/` i `executor/` są wymuszane zależnościami: Lab nie importuje adapterów
wykonawczych, a Wykonawca otrzymuje tylko zamrożone identyfikatory, decyzję ryzyka i mandat.
Interfejs WWW nie jest częścią pierwszego przyrostu; CLI dostarcza wymagany stan operacyjny.

## Kolejność dostarczania

1. Fundament i intake: baza, EVENT, SRC, CAND, pięć kandydatów oraz status.
2. Formalizacja i dane: STRAT, DATA, EXP z bramką kompletności.
3. Deterministyczny RUN strategii BTC/ETH i odtworzenie.
4. Niezależny REVIEW, RISK-DECISION oraz widok dowodów.
5. MANDATE i `PAPER_CONTINUOUS`.
6. Kontrakt `BROKER_DEMO`, reconciliation, lease, kill switch i alarmy.
7. Pozostałe cztery strategie formalizowane osobno, bez automatycznego awansu.

## Granice pierwszego wdrożenia

- Nie kopiujemy starego `astra_site` ani jego historii.
- Nie pobieramy automatycznie danych rynkowych i nie instalujemy adaptera brokera.
- Nie publikujemy materiału źródłowego ani baz i logów.
- `BROKER_DEMO` jest najpierw kontraktem oraz bezpiecznym adapterem testowym; połączenie z
  konkretnym brokerem wymaga osobnej decyzji o dostawcy i sekretach.
- Przed integracją z GitHub trzeba odzyskać dostęp i połączyć pracę z istniejącym `main`
  bez force push; do tego czasu nie tworzymy lokalnego pierwszego commita.
