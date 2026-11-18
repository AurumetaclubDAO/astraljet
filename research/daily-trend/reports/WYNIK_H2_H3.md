# H2 i H3 — wynik badania offline na świecach dziennych z MT5

Wygenerowano: 2026-11-18T05:56:57+00:00. To obliczenie modelu, nie rekord RUN i nie zgoda na handel.
Reguły i kryteria zapisano przed zobaczeniem danych: `research/daily-trend/SPEC_H2_H3.md`.

Kalendarz: 2018-03-19 do 2026-11-17. Próba poza strojeniem od 2025-01-01.

| Rynek | Symbol | Świece | Od | Do | Spread | Finansowanie bazowe |
|---|---|---|---|---|---|---|
| BTCUSD | BTCUSD | 3010 | 2017-05-02 | 2026-11-17 | 0.026% | 20.0% (swap w procentach rocznie) |
| EURUSD | EURUSD+ | 4936 | 2007-11-07 | 2026-11-17 | 0.001% | 2.1% (swap w punktach) |
| DAX | GER40.r | 2885 | 2008-12-30 | 2026-11-17 | 0.018% | 5.8% (swap kwotowy (przybliżenie)) |
| NAS100 | NAS100.r | 2242 | 2018-03-16 | 2026-11-17 | 0.007% | 8.1% (swap kwotowy (przybliżenie)) |
| SP500 | SP500.r | 2660 | 2009-09-17 | 2026-11-17 | 0.008% | 8.1% (swap kwotowy (przybliżenie)) |
| BRENT | UKOUSD | 2243 | 2018-03-09 | 2026-11-17 | 0.032% | 0.0% (swap w punktach) |
| GOLD | XAUUSD+ | 2238 | 2018-03-19 | 2026-11-17 | 0.003% | 6.6% (swap w punktach) |

## H2: podążanie za trendem — werdykt FAIL

| Kryterium | Wynik | Zaliczone |
|---|---|---|
| 1. Wynik po kosztach stresowych dodatni | +2.8% | tak |
| 2. Sharpe po kosztach bazowych >= 0.7 | 0.60 | NIE |
| 3. Zysk do obsunięcia lepszy niż punkt odniesienia | 0.57 wobec 0.58 | NIE |
| 4. Największe obsunięcie <= 25% | 8.8% | tak |
| 5. Dodatnie kwartały >= 60% | 5 z 8 | tak |
| 6. Wszyscy sąsiedzi dodatni | 8 z 8 | tak |

| Wariant | Wynik poza strojeniem | Obsunięcie | Sharpe | Wynik w okresie strojenia |
|---|---|---|---|---|
| główny_base_opóźnienie0 | +9.6% | 8.8% | 0.60 | +25.6% |
| główny_base_opóźnienie1 | +9.7% | 9.2% | 0.60 | +22.9% |
| główny_stress_opóźnienie0 | +2.8% | 9.5% | 0.21 | +9.0% |
| główny_stress_opóźnienie1 | +3.3% | 9.5% | 0.24 | +6.6% |
| punkt_odniesienia | +10.5% | 9.5% | 0.57 | +23.4% |
| sąsiad_202_48 | +10.2% | 7.5% | 0.66 | +28.9% |
| sąsiad_202_60 | +10.0% | 7.5% | 0.66 | +30.5% |
| sąsiad_202_72 | +9.4% | 7.9% | 0.61 | +29.7% |
| sąsiad_252_48 | +9.8% | 9.2% | 0.60 | +24.8% |
| sąsiad_252_72 | +8.8% | 9.8% | 0.54 | +25.7% |
| sąsiad_302_48 | +9.8% | 9.2% | 0.59 | +22.0% |
| sąsiad_302_60 | +9.5% | 8.8% | 0.58 | +21.6% |
| sąsiad_302_72 | +9.4% | 9.7% | 0.56 | +22.8% |

## H3: rotacja momentum — werdykt FAIL

| Kryterium | Wynik | Zaliczone |
|---|---|---|
| 1. Wynik po kosztach stresowych dodatni | -11.0% | NIE |
| 2. Sharpe po kosztach bazowych >= 0.7 | 0.01 | NIE |
| 3. Zysk do obsunięcia lepszy niż punkt odniesienia | -0.05 wobec 0.26 | NIE |
| 4. Największe obsunięcie <= 25% | 25.2% | NIE |
| 5. Dodatnie kwartały >= 60% | 5 z 8 | tak |
| 6. Wszyscy sąsiedzi dodatni | 3 z 8 | NIE |

| Wariant | Wynik poza strojeniem | Obsunięcie | Sharpe | Wynik w okresie strojenia |
|---|---|---|---|---|
| główny_base_opóźnienie0 | -2.3% | 25.2% | 0.01 | +120.0% |
| główny_base_opóźnienie1 | +1.2% | 22.6% | 0.12 | +114.1% |
| główny_stress_opóźnienie0 | -11.0% | 27.8% | -0.28 | +66.9% |
| główny_stress_opóźnienie1 | -7.9% | 25.4% | -0.17 | +62.2% |
| punkt_odniesienia | +6.7% | 13.8% | 0.32 | +68.1% |
| sąsiad_101_2 | -17.3% | 41.3% | -0.34 | +41.2% |
| sąsiad_101_3 | -13.8% | 29.3% | -0.37 | +95.4% |
| sąsiad_101_4 | -6.1% | 22.9% | -0.15 | +76.9% |
| sąsiad_126_2 | -21.6% | 37.8% | -0.46 | +119.9% |
| sąsiad_126_4 | +11.7% | 14.7% | 0.49 | +89.3% |
| sąsiad_151_2 | -5.0% | 30.9% | 0.00 | +137.1% |
| sąsiad_151_3 | +10.1% | 22.1% | 0.37 | +95.7% |
| sąsiad_151_4 | +4.3% | 15.4% | 0.22 | +108.6% |
