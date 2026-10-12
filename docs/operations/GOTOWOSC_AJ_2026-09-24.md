# AJ-00–AJ-18 — warunki rzeczywistej gotowości

To lista odbiorowa dalszego wdrożenia, nie deklaracja działania wszystkich ról. Stan procesu oraz stan ukończenia badania są osobne. Role mogą pracować w jednym procesie. Etap 13 dotyczy wyłącznie rejestru metadanych.

| Rola | Wymagany dowód, zanim powiemy „działa” |
|---|---|
| AJ-00 ChatGPT | Karol widzi źródła, decyzje i niepotwierdzone obszary; brak automatycznego mandatu |
| AJ-01 Orkiestrator | Zadanie przechodzi kolejkę, dzierżawę, wykonanie i zapis wyniku bez duplikatu |
| AJ-02 Bibliotekarz | Import rzeczywistego materiału, hash, wersja i możliwy do odczytu ślad |
| AJ-03 Scout | Źródło znalezione i zapisane z datą; bez udawania gotowej strategii |
| AJ-04 Odkrywca wzorców | Jawna hipoteza wyprowadzona z wersjonowanych danych, bez przyszłych obserwacji |
| AJ-05 Badacz | Kompletne, sprawdzone reguły powiązane ze źródłem i wersją strategii |
| AJ-06 Dane | Snapshot rynku, hash, zakres czasu, jakość i dostępność w chwili decyzji |
| AJ-07 Tester | Zamrożony EXP → rzeczywisty RUN → odtwarzalny raport z OOS i kosztami |
| AJ-08 Krytyk | Niezależny przegląd konkretnego RUN z werdyktem i uzasadnieniem |
| AJ-09 Ryzyko | Sprawdzony sizing i bieżąca kontrola właściwego mandatu/rachunku |
| AJ-10 AT | Wersjonowane reguły i wskaźniki potrzebne konkretnej strategii |
| AJ-11 AF | Dane fundamentalne z datą dostępności, powiązane z hipotezą |
| AJ-12 News | Źródło i czas wydarzenia, kontrola duplikatów, brak domyślnych filtrów |
| AJ-13 Makro | Wersja danych i opóźnienia publikacji, bez użycia przyszłych rewizji |
| AJ-14 Portfel | Jawny plan alokacji/hedgingu zatwierdzony w konkretnym zakresie |
| AJ-15 Wykonawca | Osobny mandat, poprawny rachunek/tryb, zgodność dziennika i brokera |
| AJ-16 Monitoring | Świeży odczyt i historia; rozpoznanie opóźnienia, braku danych i awarii |
| AJ-17 Utrzymanie | Faktyczne koszty i niepewne rozliczenia, bez zgadywania zera i sztucznych pułapów |
| AJ-18 Promo | Wyłącznie treści zatwierdzone przez Karola; brak automatycznej publikacji |

Odbiór podpisanej kopii metadanych zakończono 24.09: 7 wersji i 6 relacji widocznych w panelu. To nie uruchomienie ról. Najbliższa zależność: rzeczywisty przepływ jednego zamrożonego eksperymentu → niezależny przegląd. Nie zastępuje to istniejących turnusów DEMO ani nie rozszerza ich mandatów. Harmonogram synchronizacji nie został uruchomiony.

Uzupełnienie — [etap 14](ETAP_14_2026-09-24.md): lokalna implementacja AJ-08
sprawdza integralność i wersje RUN, wszystkie porównania oraz jawny raport
kontrolny. 174/174 testy całego rdzenia, w tym pozytywne i negatywne ścieżki
REVIEW/RISK. Nadal brak niezależnego raportu dla rzeczywistej strategii i
podłączenia tej ścieżki do workera witryny. To naprawa warunku odbioru, nie
spełnienie całego warunku AJ-08. Kopia D1 nadal obejmuje wyłącznie SRC–RUN.

Uzupełnienie — [etap 15](ETAP_15_2026-09-24.md): rzeczywista analiza zakończyła
odczyt 7/7, ale jedno wznowienie doprowadziło do dwóch płatnych wywołań i
dwóch par podobnych kart po przerwaniu żądania. Kryterium AJ-01 „bez
duplikatu” pozostaje niespełnione; nie należy utożsamiać zakończonego zadania
z poprawną idempotencją. Potwierdzona kopia metadanych SQLite → D1 jest
osobnym mechanizmem i nie została przez ten błąd zakwestionowana.

Uzupełnienie — [etap 16](ETAP_16_2026-09-24.md): prywatna wersja 59 zawiera
trwały zapis odpowiedzi AI i atomową publikację kart/postępu `extractRules`.
262/262 testy witryny, migracja D1 i odczyt panelu potwierdzone. Nie wykonano
nowej płatnej analizy po wdrożeniu. AJ-01 pozostaje częściowy: inne płatne
ścieżki i pełny cykl dzierżawy wymagają zabezpieczenia; brak rzeczywistego
EXP/RUN. Niepewny wynik wymaga wyjaśnienia, a nie ponownego płatnego wywołania.

Uzupełnienie — [etap 17](ETAP_17_2026-09-24.md): prywatna wersja 60 naprawia
podgląd historii i pełne liczniki biblioteki; 269/269 testów witryny.
Rzeczywiste kontrolowane wznowienie jednego zadania dało odczyt 8/8, jedną
nową kartę i jedno rozliczenie 0,142990 USD w ewidencji. Odpowiedź `ready`
jest zapisana w D1. To dowód normalnego przebiegu wybranej ścieżki AJ-01,
nie całej odporności produkcyjnej: innych płatnych ścieżek nie odebrano,
pozostają 22 zadania wymagające uwagi. Nowa karta ma cztery reguły i sześć
braków, więc nie spełnia jeszcze warunku kompletności AJ-05. Nadal brak
rzeczywistego EXP/RUN/niezależnego przeglądu w tej ścieżce. Rozbieżność
między urządzeniem D1 a widocznymi lokalnie plikami Windows pozostaje
otwarta; nie restartowano procesu ani nie podmieniano jego stanu.

Uzupełnienie — [etap 18](ETAP_18_2026-09-24.md): lokalny AJ-07 zapisuje wszystkie
warianty tygodniowego EXP atomowo do RUN/EVENT i odtwarza raport bez ponownego
liczenia. 187/187 testów rdzenia, 34/34 testy adaptera na Python 3.12, zgodność
eksportu z parserami synchronizacji i Analytics wersji 60. To testy syntetyczne,
nie odbiór rzeczywistego badania. RUN pozostaje `inconclusive`, kryteria nie są
ocenione; nie podłączono workera ani nie uzyskano niezależnego REVIEW. Zakres
metadanych D1 i istniejące DEMO pozostają bez zmian. ACK pierwszej paczki
sprawdzono ponownie lokalnie i w D1, bez utworzenia kolejnego klucza.

Uzupełnienie — [etap 19](ETAP_19_2026-09-24.md): prywatna wersja 61 obejmuje
trwałe wyszukiwanie AJ-03 i atomowy zapis importów, 287/287 testów witryny.
Rzeczywiste wznowienie jednego zadania zakończyło wyszukiwanie (4 źródła)
i import jednego PDF (27 fragmentów). Dalsza ekstrakcja reguł została
zablokowana przez niepotwierdzony cytat; nie utworzono nowej karty. Koszt
0,029523 USD w ewidencji obejmuje wyszukiwanie i pierwszą partię ekstrakcji.
Potwierdza to działanie tej ścieżki AJ-03/AJ-02, nie kompletność AJ-05,
odporność wszystkich typów zadań ani gotowość całego systemu. Nadal brak
rzeczywistego EXP/RUN/REVIEW w nowej lokalnej ścieżce. Rozbieżność tożsamości
runtime pozostaje otwarta; bez restartów i zmian handlu. Połączenie rejestru
ponownie potwierdzono bez nowej wysyłki: ten sam ACK, 7 wersji.
