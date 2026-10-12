# AstralJet — główne miejsce budowy

**Decyzja Karola, 19.09.2026:** cały system rozwijamy w `D:\Astra Jet`, z docelowym repozytorium [AurumetaclubDAO/astraljet](https://github.com/AurumetaclubDAO/astraljet).

## Bieżący etap budowy — 24.09.2026

**Aktualna publikacja: wersja 61, etap 19.** [Trwałe wyszukiwanie źródeł AJ-03](docs/operations/ETAP_19_2026-09-24.md) — zamrożone wejście wyszukiwania, zachowana odpowiedź AI, atomowy import i ochrona przed zapisem ze starej dzierżawy. 287/287 testów, TypeScript, lint i build. Jedno kontrolowane wznowienie: 4 cytowane źródła, 1 nowy materiał i 27 odczytanych fragmentów PDF. Późniejsza ekstrakcja zatrzymana przez niepotwierdzony cytat; nie utworzono nowej karty. Łączny koszt tego przebiegu 0,029523 USD według ewidencji. Biblioteka 85 materiałów / 24 karty. Istniejący ACK SQLite → D1 ponownie potwierdzony, bez nowego klucza i transferu. Bez restartu procesów i zmian handlu; nie jest to odbiór wszystkich ról.

**Najnowszy przyrost lokalnego rdzenia: etap 18.** [Trwały zapis tygodniowych RUN i odtworzenie raportu](docs/operations/ETAP_18_2026-09-24.md) — wszystkie scenariusze zamrożonego EXP zapisują się atomowo do SQLite; powtórzenie tego samego żądania nie tworzy duplikatu. 187/187 testów rdzenia, 34/34 testy adaptera na Python 3.12 oraz zgodność eksportu z parserami istniejącej witryny. Wyniki pozostają `inconclusive`; nie zatwierdzono rzeczywistego planu BTC/ETH, nie utworzono produkcyjnego EXP/RUN i nie podłączono workera. Etap 18 nie publikował witryny. Potwierdzono istniejący ACK SQLite → D1, bez kolejnego parowania i transferu.

**Poprzednia publikacja: wersja 60, etap 17.** [Odczyt źródeł, pełne liczniki biblioteki i odbiór rzeczywistej analizy](docs/operations/ETAP_17_2026-09-24.md) — 269/269 testów witryny, TypeScript i build; prywatna publikacja oraz podgląd wersji źródła potwierdzone. Jedno kontrolowane wznowienie zakończyło odczyt 8/8 fragmentów i utworzyło jedną kartę: jedno rozliczone wywołanie 0,142990 USD w ewidencji, odpowiedź AI `ready` w D1. Kolejka 152 zakończone / 22 wymagające uwagi, biblioteka 84 materiały / 24 karty. Nowa karta wymaga sprawdzenia reguł i sześciu uzupełnień. Bez EXP/RUN i zmian handlu; rozbieżność tożsamości lokalnego procesu/plików nadal nie jest wyjaśniona. To nie odbiór wszystkich ról.

**Poprzednia publikacja: wersja 59, etap 16.** [Ochrona przed ponownymi kosztami AI i atomowy zapis materiału](docs/operations/ETAP_16_2026-09-24.md) — 262/262 testy witryny, TypeScript i build; migracja D1 oraz prywatna publikacja potwierdzone. Zapisaną odpowiedź odczytu materiału można odtworzyć, a nieznany wynik nie jest automatycznie opłacany drugi raz. W tym etapie bez nowych analiz AI i zmian handlu. Historyczny stan: 151 zakończonych / 23 wymagające uwagi; biblioteka 84 materiały / 23 karty. Odbiór całego AJ-01 i pozostałych ról nadal nieukończony.

**Poprzedni odbiór operacyjny: etap 15.** [Jedna wznowiona analiza i błąd ponowienia AI](docs/operations/ETAP_15_2026-09-24.md) — materiał odczytany 7/7, kolejka 151 complete / 23 blocked. Wykryto dwa rozliczone wywołania (łącznie 0,26479 USD w ewidencji) oraz dwie pary podobnych kart po jednym wznowieniu. Naprawę ścieżki odczytu opublikowano w etapie 16; nie wznawiamy wszystkich blokad na podstawie samego statusu complete. Brak EXP/RUN i zmiany handlu. Potwierdzono istniejący ACK synchronizacji SQLite → D1, bez nowego parowania lub wysyłki.

**Poprzednia poprawka lokalnego rdzenia: Krytyk AJ-08, etap 14.** [Integralność REVIEW i raporty kontrolne](docs/operations/ETAP_14_2026-09-24.md) — 174/174 testy, komplet dowodów zamiast samego replay lub flagi `verified`; kontrola idempotencji, jawne blokady i sprawdzenie nowych decyzji ryzyka. Wyłącznie kod lokalny i testowe rejestry. Nie powstał rzeczywisty EXP/RUN ani niezależny raport rynkowy; nie podłączono nowej ścieżki do workera i nie zmieniono DEMO/LIVE. Wszystkie 8 istniejących rekordów i 7 wydarzeń wybranego rejestru zachowano bez zmian.

**Wersja 58, etap 13: podpisane metadane Python / SQLite → Sites / D1.** [Połączenie lokalnego rejestru](docs/operations/ETAP_13_2026-09-24.md) — 7 wersji i 6 relacji przyjętych o 03:31 Warszawa, ACK sprawdzony w lokalnym CLI, tabelach D1 i zalogowanym panelu. Lokalna historia zachowana po spójnym backupie; wyłącznie zakres `registry:sync`, sekrety poza repo. 152/152 testy rdzenia i 244/244 witryny na zakończenie tego etapu. Synchronizacja na żądanie, bez harmonogramu; nie oznacza działania wszystkich agentów ani utworzenia EXP/RUN. [Warunki odbioru AJ-00–AJ-18](docs/operations/GOTOWOSC_AJ_2026-09-24.md).

**Poprzednia publikacja: naprawa obsługi agentów i odczytu wykonawców, prywatna.** [Etap 12: audyt, refaktor, testy i wdrożenie](docs/operations/ETAP_12_2026-09-23.md) — prawdziwa telemetria DEMO dla AJ-15 i istniejących kontroli AJ-09, poprawna klasyfikacja blokad, naprawa cytowań różniących się wyłącznie białymi znakami oraz aktualizacja procesu badań Windows. 230/230 testów witryny, 31/31 testów procesu, TypeScript, lint i build. Publikacja potwierdzona 23.09 o 22:49; proces badań uruchomiony po kopii bazy. Krypto i indeksy potwierdzone RUNNING w DEMO, bez zmiany ich procesów i mandatów. 24 historyczne zadania nie zostały wznowione, pozostałe niepodłączone role nie zostały ukończone. Brak wizualnego odbioru zalogowanej witryny w etapie 12.

Poprzednia publikacja: [Etap 11: dashboard botów według grafiki Karola](docs/operations/ETAP_11_2026-09-23.md) — ciemno-złoty układ, tabela Badanie/DEMO, prawdziwe krzywe zapisanych testów, istniejące źródła GET i jawne braki danych. 223/223 testy, TypeScript, lint, build oraz odbiór desktop/mobile. Publikacja potwierdzona przez Sites; bez zleceń i bez deklaracji ukończenia całego bota.

Poprzednia publikacja: wersja 54. [Etap 10: wydatki AI i X bez stałego pułapu](docs/operations/ETAP_10_2026-09-20.md) — usunięto limity 25/20/5 USD, zachowano ewidencję, naprawiono utratę odpowiedzi AI droższej od oszacowania. Bez zbiorczego wznowienia starej kolejki i uruchomienia handlu.

Decyzja Karola „no limit wszędzie; DEMO i LIVE” jest zatwierdzona w [konstytucji 2.0.0](.specify/memory/constitution.md). Etap 10 wdraża ją dla AI/X; konkretna funkcja Risk Management, koszty MT5 i ścieżki wykonania pozostają do zbudowania. Nie pytamy ponownie o dawny budżet 1/25 USD. Datowane raporty poniżej opisują stan historyczny.

- [Audyt obu lokalizacji i faktyczny stan](CURRENT_ASTRA_INVENTORY.md).
- [Plan połączenia istniejącej Astry, bez wykonanej migracji runtime](MIGRATION_PLAN.md).
- [Wdrożony lokalnie etap: ochrona historii i odczyt powiązań](docs/operations/ETAP_01_2026-09-19.md).
- [Etap 02: widok Pochodzenie w istniejącym frontendzie i lokalne snapshoty](docs/operations/ETAP_02_2026-09-19.md) — kod lokalny, bez publikacji.
- [Etap 03: przypięte źródła, reguły i plan nowych eksperymentów](docs/operations/ETAP_03_2026-09-20.md) — kod lokalny, testy konfliktów i blokad workera badawczego; bez publikacji.
- [Etap 04: kontrola rzeczywistych wejść i karta eksperymentu BTC/ETH](docs/operations/ETAP_04_2026-09-20.md) — 4174 świece sprawdzone lokalnie; plan pozostaje zablokowany, bez RUN i zmian baz.
- [Etap 05: tygodniowy model i ledger jednostek/gotówki](docs/operations/ETAP_05_2026-09-20.md) — lokalna implementacja na syntetycznych danych; 115 testów, jeszcze bez podłączenia do EXP/workera.
- [Etap 06: adapter zamrożonego EXP i raport offline](docs/operations/ETAP_06_2026-09-20.md) — jawna ścieżka lokalnego modelu do wersji STRAT/DATA/EXP; 136/136 testów, bez utworzenia rzeczywistego EXP/RUN i bez podłączenia workera.
- [Command Center: główny panel AstralJet i pełna nawigacja](docs/operations/COMMAND_CENTER_2026-09-20.md) — opublikowana prywatnie wersja 50 istniejącej witryny; odczyt rejestru D1, bez zleceń i bez połączenia lokalnego modelu z EXP.
- [Etap 07: naprawa procesów, pochodzenia i importu PDF](docs/operations/ETAP_07_2026-09-20.md) — prywatna wersja 52; rzeczywiste statusy i blokady w panelu agentów, usunięty błąd 503, obsługa AES w środowisku badań. 196/196 testów wydania i 7/7 testów procesu. Brak wznowienia płatnych analiz, zmian budżetu, migracji baz i uruchomienia handlu.
- [Etap 08: raport lokalnego silnika w Analytics](docs/operations/ETAP_08_2026-09-20.md) — prywatna wersja 53 na zakończenie etapu, 207/207 testów witryny i 136/136 rdzenia. Odczyt pliku z equity/DD, IS/OOS, kosztami i benchmarkiem albo blokadami szkicu. Potwierdzono rzeczywiste 4174 wiersze / 8 blokad. Bez wysyłki raportu, synchronizacji rejestrów, utworzenia EXP/RUN, płatnego AI i handlu.
- [Etap 09: lokalny test importu bez AI](docs/operations/ETAP_09_2026-09-20.md) — wspólny parser i inspektor; 22 wpisy / 21 plików ze zgodnymi hashami, dwa dokumenty wymagają przeglądu brakującej treści. Dodano kontrolę integralności pliku przed importem; 30/30 testów badań. Kod lokalny, bez publikacji paczki, restartu procesu, wznowienia płatnej kolejki i handlu.
- [Karta BTC/ETH v0.2: propozycja reguł, kosztów i trzy decyzje](docs/experiments/BTC_ETH_EXPERIMENT_PACKET_v0.2.md).
- [Polecenia odczytu i zasady obsługi](docs/operations/RUNBOOK.md).

Lokalny rdzeń Python zachowuje SQLite jako źródło prawdy. Od etapu 13 wybrany rejestr `quickstart-2026-09-19` ma podpisaną, odczytową kopię metadanych w osobnych tabelach D1, widoczną w Data Center i Pochodzeniu. Nie jest to współdzielona baza ani ciągły dostęp do SQLite; `state` i `dev` nie zostały połączone. Ręczne wczytanie pliku snapshotu nadal pozostaje tylko w pamięci strony. Etap 13 nie zmienił MT5, rachunków, mandatów, ryzyka i procesów DEMO. Publikacja interfejsu nie jest zatrzymaniem ani uruchomieniem wykonawców.

Etapy 14–19 nie rozszerzają synchronizacji: REVIEW i pełne raporty pozostają lokalne. Istniejący format obejmuje metadane RUN, nie ich pełne wyniki. Bieżąca wersja witryny to 61. Stan gotowości ról należy odbierać osobno; poprawne testy Krytyka, zapis syntetycznych RUN i wybrane zakończone zadania nie są potwierdzeniem działania wszystkich agentów.

Etap 03 wymaga dla nowego eksperymentu przeglądu konkretnej rewizji źródła i reguł. Zmiana źródła po przeglądzie nie podmienia archiwum używanego przez eksperyment. Brak lub naruszenie przypiętych archiwów blokuje wydanie zadania badawczego i przyjęcie wyniku. Stare eksperymenty pozostają legacy; nie nadano im wstecznie potwierdzonego pochodzenia. To nie zatwierdzenie strategii, danych rynkowych ani mandatu DEMO. Stanu aktywnego MT5 nie odpytywano ponownie w etapie 03.

## Dokumentacja i wcześniejsze ustalenia

1. [Dokumentacja architektury v0.2](docs/architektura/START.md): 19 ról, 12 zadań ASTRA Pro, źródła i decyzje. Wersja v0.1 zachowana.
2. [Ustalenie lokalizacji i aktualny zakres](docs/LOKALIZACJA_I_STAN_2026-09-19.md).
3. [Aktualne położenie 28 załączników na dysku D](docs/KATALOG_PLIKOW_LOKALNYCH.csv).

| Miejsce | Przeznaczenie |
|---|---|
| `docs/architektura/` | Sprawdzona dokumentacja Markdown i tabele, zachowana bez zmiany treści |
| `docs/KATALOG_PLIKOW_LOKALNYCH.csv` | Mapa SRC → plik na dysku D, z potwierdzeniem tożsamości SHA-256 |
| `Trading 2.0/` | Materiały zastane w katalogu wskazanym przez Karola |
| `materials/inbox/` | Kopie brakujących załączników z wcześniejszej rozmowy |
| `00_AUDYT/` | Istniejący katalog audytu, zachowany |

W archiwalnej dokumentacji v0.2 pozostają wcześniejsze ścieżki z komputera. Do bieżącego odnalezienia materiału używamy mapy SRC w katalogu lokalnym. Numery, zawartość i sumy źródeł pozostały zgodne.

**Stan GitHub — sprawdzony 20.09.2026:** dostęp do odczytu przez HTTPS działa. `origin` wskazuje `https://github.com/AurumetaclubDAO/astraljet.git`; pobrano istniejącą historię, a lokalna `main` śledzi `origin/main`. Obie gałęzie wskazują początkowy commit `8419bc52b1192eae7d65661a8891a1e858a22667`, zawierający README oraz .gitignore. Pobrano README, zachowując lokalny .gitignore jako zmianę roboczą — zdalna reguła `lib/` nie została przyjęta. Pozostałe pliki projektu nadal są lokalne i niezatwierdzone w Git. Nie wykonano push ani nowego commita; dostęp do zapisu nie był sprawdzany. Datowany dokument lokalizacji z 19.09 opisuje wcześniejszy stan przed pobraniem historii.

**Istniejąca Astra:** kod nadal znajduje się w `C:\Users\karol\Documents\Claude\Projects\Trading\astra_site`, a działające procesy w swoich wcześniejszych lokalizacjach. Ich migracja wymaga zachowania historii i odrębnego sprawdzenia ścieżek danych oraz uruchomienia. Samo wskazanie nowego katalogu nie jest restartem działających botów.

ChatGPT pozostaje rozmówcą Karola. Omawiamy ustalenia, drobne poprawki robimy samodzielnie, istotne zmiany odpowiedzialności, strategii, ryzyka, wydatków i działania uzgadniamy.
