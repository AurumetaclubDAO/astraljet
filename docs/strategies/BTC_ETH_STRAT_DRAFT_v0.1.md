# BTC/ETH z kontrolą trendu i ryzyka — formalizacja źródłowa v0.1

**Stan:** `NEEDS_INPUT`  
**Źródło:** `SRC-029`, SHA-256
`ED708DAF399C9851CA925F4050817936CD2F6F80D3C14A29899699CEA8FB6998`  
**Kandydat runtime:** `CAND-1fc9fb54868542fdbbd0a1862c4f5fbb`
**Szkic STRAT runtime:** `STRAT-5fb2fbd40d9f4842afdcaa2b2898a411`

Ten dokument porządkuje treść źródła. Nie zatwierdza parametrów, nie jest rekomendacją
inwestycyjną i nie upoważnia Wykonawcy do PAPER, DEMO ani REAL.

## Co rzeczywiście mówi źródło

- sleeve bazowy: 70% BTC, 20% ETH, 10% cash lub krótkie bony;
- filtr: BTC względem 200-dniowej średniej;
- risk-on: BTC powyżej 200DMA i „średnia rośnie”;
- risk-off: tygodniowe zamknięcie poniżej 200DMA oraz „pogorszenie struktury trendu”;
- w risk-off ekspozycja ma zostać zredukowana o 50%;
- po powrocie nad 200DMA ekspozycja ma być odbudowana w 2–3 transzach;
- benchmark: statyczne 80% BTC / 20% ETH;
- bez dźwigni, horyzont 12–36 miesięcy.

Podane w materiale zakresy 8–22% p.a. i 10–25 pp ochrony w risk-off są wyłącznie
hipotezami autora. Nie są kryteriami odbioru i nie będą wpisane do EXP bez osobnej decyzji.

## Decyzje wymagane przed stanem READY

| Obszar | Warianty do wyboru | Stan |
|---|---|---|
| Dane i venue | A: jedna giełda spot; B: indeks/agregat wielu giełd; C: notowania ETP w godzinach giełdy | brak decyzji |
| Granica dnia | A: świece UTC 00:00–00:00; B: granica dostawcy; C: sesja ETP | brak decyzji |
| „Średnia rośnie” | A: SMA200 dziś > SMA200 sprzed N dni; B: dodatnie nachylenie regresji; C: dodatnia zmiana przez N kolejnych dni | brak N i wariantu |
| „Struktura trendu” | A: usunąć warunek jako nieoperacyjny; B: lower high/lower low z algorytmem; C: dodatkowy filtr momentum | brak definicji |
| Timing wykonania | A: następne dzienne otwarcie; B: następny dostępny close/VWAP; C: tygodniowy rebalans | brak decyzji |
| Odbudowa | A: 2 równe transze; B: 3 równe transze; C: transze zależne od kolejnych potwierdzeń | brak reguły |
| ETH | A: ETH sterowane wyłącznie sygnałem BTC; B: osobny filtr ETH; C: ETH=0 w risk-off | brak decyzji |
| Cash | A: syntetyczna gotówka USD; B: indeks bonów skarbowych; C: konkretny instrument PAPER/DEMO | brak decyzji |
| Koszty | fee, spread, slippage i ewentualne finansowanie dla wskazanego venue | brak danych |
| Benchmark | częstotliwość rebalansu statycznego 80/20 i identyczny model kosztów | brak decyzji |

## Rekomendowany wariant do pierwszego testu mechaniki

To rekomendacja robocza, nie zatwierdzona STRAT:

1. dane spot BTCUSD i ETHUSD, dzienne świece UTC;
2. sygnał wyliczany po niedzielnym zamknięciu UTC;
3. „SMA rośnie” jako `SMA200[t] > SMA200[t-20]`;
4. usunięcie nieoperacyjnego „pogorszenia struktury trendu” z pierwszej wersji;
5. wykonanie na otwarciu następnej dziennej świecy;
6. risk-off: BTC 35%, ETH 10%, cash 55%;
7. odbudowa w dwóch równych transzach po dwóch kolejnych tygodniowych potwierdzeniach;
8. koszty ustalone dopiero po wskazaniu konkretnego źródła danych i venue;
9. benchmark 80/20 rebalansowany miesięcznie, z tym samym modelem kosztów.

Wariant jest prosty do odtworzenia i ogranicza swobodę interpretacji. Nadal wymaga jawnej
akceptacji parametrów, zatwierdzonego DATA i zamrożenia EXP przed poznaniem wyniku.

## Artefakt maszynowy

Szkic wejściowy znajduje się w
`specs/001-build-astra-jet/examples/btc_eth_strat_source_draft.json`. Walidator ma
obowiązkowo zwrócić `NEEDS_INPUT` do czasu uzupełnienia decyzji z tabeli.

Rzeczywisty zapis szkicu zwrócił blokery: `missing_venue`, `missing_execution_timing`,
`missing_allowed_parameters`, `ambiguous_entry_rule`, `ambiguous_exit_rule`,
`ambiguous_sizing_rule` i `unknown_cost_model`. Projekcja statusu wskazuje
`strategy_needs_input` i nie pozwala sugerować przejścia do DATA/EXP.
