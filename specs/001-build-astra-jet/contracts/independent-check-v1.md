# Niezależne sprawdzenie RUN — kontrakt v1

Zakres: lokalny import obserwacji kontrolnych do `review create`. To nie format
zleceń, podpis tożsamości, automatyczna walidacja rentowności ani raport
`weekly-offline-report-v1`. Metadane synchronizacji etapu 13 nie przesyłają REVIEW
ani tego artefaktu do D1.

## Dostarczenie i zaufanie

Operator dostarcza JSON z osobnego silnika lub obliczenia kontrolnego. CLI nie
uruchamia programu wskazanego raportem i nie generuje takiego raportu z badanego
RUN. Wymagana odrębność deklarowanego autora oraz hashu implementacji pomaga
wykryć pomylenie źródeł, lecz nie dowodzi tożsamości ani faktycznego uruchomienia
innego programu. Skopiowanie wyników pod inną nazwą nie jest niezależną kontrolą.

Operator odpowiada za metodę, pochodzenie oraz przechowanie implementacji
kontrolnej. Hash jest dowodem spójności treści, nie autoryzacji. Testowe artefakty
z `tests/` są syntetyczne; nie wolno ich rejestrować jako dowodów rynkowych.

## Pola

Wszystkie poniższe pola są wymagane; dodatkowe i powtórzone klucze JSON są
odrzucane. Jeden plik: maksymalnie 1 MiB, jedno wywołanie: do 8 plików.

| Pole | Wymaganie |
|---|---|
| `schema` | `astraljet-independent-check-v1` |
| `method` | `independent_engine` albo `control_calculation` |
| `verifier` | Niepusta nazwa autora, do 120 znaków; różna od autorów RUN po strip/casefold |
| `implementation_hash` | SHA-256 wersji implementacji kontrolnej, różny od `EXP.code_hash` |
| `experiment_id`, `experiment_version` | Dokładny EXP przypięty przez wszystkie oceniane RUN |
| `plan_hash` | Hash tego zamrożonego EXP |
| `observations` | 1–100 obserwacji, dokładnie jeden wpis na każdą ocenianą parę RUN ID/wersja |
| `report_hash` | SHA-256 kanonicznego obiektu bez pola `report_hash` |

Każda obserwacja zawiera dokładnie:

| Pole | Wymaganie |
|---|---|
| `run_id`, `run_version` | Identyfikator i dodatnia całkowita wersja RUN |
| `record_hash` | `record_content_hash(asdict(run))` — pełny rekord, nie jego historyczne pole `content_hash` |
| `input_hash` | Hash wejścia zapisany w RUN |
| `trace_hash` | Hash obiektu z dokładnie `trades`, `rejected_signals`, `exposure`, `equity_curve` z RUN |
| `metrics` | Obserwacje kontrolne wszystkich i wyłącznie metryk wymaganych przez EXP |
| `total_cost` | Skończony, nieujemny koszt z obliczenia kontrolnego, zgodny z RUN |

Hashe mają 64 znaki hex. Kanonizacja jest zgodna z
`astraljet.domain.validation.canonical_json`: UTF-8, klucze sortowane,
`ensure_ascii=False`, separatory `,` i `:`, bez białych znaków formatowania.
Hash liczony jest z rzeczywistych wartości i pisowni JSON; wielkość liter hex
normalizowana jest przy porównaniu hashy, nie przed wyliczeniem treści raportu.

Metryki i tolerancje: zalecane teksty dziesiętne; do 100 metryk, nazwy
`[A-Za-z0-9_]{1,80}`. Odrzucane są boolean, NaN/Infinity i wartości poza zakresem
parsowania (do 100 znaków, wykładnik znaczącej cyfry od −1000 do 1000).
Tolerancja pochodzi wyłącznie z EXP i musi być nieujemna. Różnica jest liczona
bez zaokrąglenia, które mogłoby ukryć jej przekroczenie. To limity formatu
wejściowego, nie kapitału, pozycji ani wydatków AI.

## Ocena i zapis

- Co najmniej dwa różne RUN, dokładnie powiązane z tym samym EXP i jego wersją.
- Każdy RUN musi być ukończony, bez błędów i z wynikiem `passed`; sprawdzane są
  porządek czasu oraz integralność legacy pakietu wyjściowego. Ten kod nie
  przelicza cen ze źródłowego CSV ani nie zastępuje weryfikacji STRAT/DATA.
- Odtworzenie obejmuje każdy kolejny RUN względem pierwszego, nie tylko dwa.
  Zgodne metryki nie wystarczają przy różnych hashach wyjściowych tej samej
  deterministycznej implementacji.
- Każdy dostarczony raport kontrolny musi obejmować cały zestaw RUN i przejść
  sprawdzenie. Nie wybieramy korzystnego raportu z zestawu sprzecznych.
- Sam replay tego samego silnika bez raportu kontrolnego daje `unverified`.
  Jawne odrzucenie przez recenzenta daje `rejected`.
- REVIEW utrwala kopię raportu, wynik każdej kontroli, dokładne referencje
  RUN/EXP i hash żądania. Późniejsza mutacja wejściowego obiektu nie zmienia kopii.
- Identyczne ponowienie z tym samym kluczem zwraca ten sam REVIEW. Zmienione
  wejścia/wnioski/raport lub klucz innego typu rekordu powodują błąd walidacji,
  bez dopisania ani nadpisania REVIEW.
- Nowa RISK-DECISION sprawdza kompletność, spójność i integralność zachowanych
  dowodów. Historyczna etykieta `verified` bez tego pakietu nie wystarcza.
  Istniejące decyzje i mandaty nie są przepisywane ani automatycznie cofane.

`verified` nadal oznacza ocenę przedstawionych dowodów w zadeklarowanym zakresie.
Nie uruchamia PAPER, DEMO, LIVE, kolejki AI ani synchronizacji do D1. Nie jest
podpisaną zgodą Karola i nie stanowi dowodu zyskowności.

## Tygodniowe RUN — etap 18

`run weekly-recorded` zapisuje osobny RUN dla każdego scenariusza. Kontrola
integralności obejmuje jego pełny artefakt i projekcje, lecz wynik pozostaje
`inconclusive`. Nie spełnia warunku `passed` wymaganego wyżej: nawet zgodny
replay i raport kontrolny nie zastępują brakującej oceny kryteriów hipotezy.
Odrębne scenariusze kosztu/opóźnienia nie są wzajemnymi reprodukcjami.
`weekly-export` odtwarza oryginalny raport obliczeń, nie niezależną kontrolę.
Nie przepisuj outcome ani hashy RUN, aby uzyskać pozytywny REVIEW.
