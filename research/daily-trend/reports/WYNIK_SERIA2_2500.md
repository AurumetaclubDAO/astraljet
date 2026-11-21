# Seria 2 (H4, H5): wynik na danych dziennych, kapitał 2 500 USD

Wygenerowano: 2026-11-21T02:56:30+00:00. To obliczenie modelu, nie rekord RUN i nie zgoda na handel.
Reguły i kryteria: `research/daily-trend/SPEC_SERIA2.md`. Kryteria liczone na widoku rachunku w lotach, poza strojeniem (od 2025-01-01). Łączna ekspozycja G = 1.
Widok modelu (wagi ciągłe, bez lotów) nie jest w tym raporcie policzony. Specyfikacja przewiduje go tylko do porównania, więc nie zmienia werdyktu.

| Klasa | Rynek | Symbol | Spread | Prowizja za stronę | Długa rocznie | Krótka rocznie (z dopłatą) |
|---|---|---|---:|---:|---:|---:|
| Akcje USA | USA małe spółki | `IWM` | 0.007% | 6.00 USD | 6.0% | 3.0% |
| Akcje USA | USA finanse | `XLF` | 0.018% | 6.00 USD | 6.0% | 3.0% |
| Akcje USA | USA technologia | `XLK` | 0.012% | 6.00 USD | 6.0% | 3.0% |
| Akcje poza USA | Rynki rozwinięte | `EFA` | 0.010% | 6.00 USD | 6.0% | 3.0% |
| Akcje poza USA | Rynki wschodzące | `EEM` | 0.017% | 6.00 USD | 6.0% | 3.0% |
| Akcje poza USA | Chiny | `FXI` | 0.030% | 6.00 USD | 6.0% | 3.0% |
| Złoto i metale | Spółki złota | `GDX` | 0.025% | 6.00 USD | 6.0% | 3.0% |
| Energia i surowce | Ropa WTI | `USO` | 0.029% | 6.00 USD | 6.0% | 0.0% |
| Energia i surowce | Koszyk surowców | `DBC` | 0.032% | 6.00 USD | 6.0% | 0.0% |
| Energia i surowce | Ropa Brent | `BNO` | 0.042% | 6.00 USD | 6.0% | 0.0% |
| Krypto | Ethereum | `ETHUSD` | 0.118% | 0.00 USD | 8.3% | 0.0% |

## H4: werdykt FAIL

| Kryterium | Wynik | Zaliczone |
|---|---|---|
| 1. Wynik po kosztach stresowych dodatni | -29.0% | NIE |
| 2. Sharpe po kosztach bazowych >= 0.7 | -0.59 | NIE |
| 3. Zysk do obsunięcia lepszy niż punkt odniesienia | -0.44 wobec -0.15 | NIE |
| 4. Największe obsunięcie <= 25% | 13.0% | tak |
| 5. Dodatnie kwartały >= 60% | 3 z 8 | NIE |
| 6. Wszyscy sąsiedzi dodatni | 0 z 8 | NIE |

| Wariant | Wynik poza strojeniem | Obsunięcie | Sharpe | Transakcje | Koszt spreadu | prowizja | finansowanie | Pominięte przez lot | Wynik w okresie strojenia |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| główny_base_opóźnienie0 | -10.6% | 13.0% | -0.59 | 163 | 5.62 USD | 852.00 USD | 239.49 USD | 53 | -19.5% |
| główny_base_opóźnienie1 | -8.7% | 10.6% | -0.49 | 175 | 5.95 USD | 912.00 USD | 244.35 USD | 50 | -18.6% |
| główny_stress_opóźnienie0 | -29.0% | 29.0% | -1.60 | 168 | 9.50 USD | 1305.00 USD | 317.32 USD | 77 | -31.5% |
| główny_stress_opóźnienie1 | -29.2% | 29.2% | -1.81 | 170 | 9.62 USD | 1332.00 USD | 318.93 USD | 78 | -31.5% |
| punkt_odniesienia | -4.8% | 17.4% | -0.14 | 176 | 3.11 USD | 924.00 USD | 357.33 USD | 34 | -7.1% |
| sąsiad_202_48 | -22.9% | 22.9% | -1.38 | 190 | 7.02 USD | 972.00 USD | 231.31 USD | 55 | -15.3% |
| sąsiad_202_60 | -21.7% | 21.7% | -1.32 | 180 | 6.88 USD | 924.00 USD | 232.57 USD | 53 | -14.8% |
| sąsiad_202_72 | -21.0% | 21.0% | -1.25 | 172 | 6.70 USD | 888.00 USD | 234.08 USD | 53 | -14.6% |
| sąsiad_252_48 | -13.7% | 16.2% | -0.75 | 192 | 5.88 USD | 996.00 USD | 235.02 USD | 53 | -21.0% |
| sąsiad_252_72 | -10.6% | 13.0% | -0.59 | 163 | 5.61 USD | 846.00 USD | 238.40 USD | 53 | -19.8% |
| sąsiad_302_48 | -20.8% | 21.2% | -1.07 | 195 | 6.21 USD | 1014.00 USD | 227.21 USD | 57 | -17.4% |
| sąsiad_302_60 | -14.7% | 17.7% | -0.70 | 169 | 5.98 USD | 876.00 USD | 234.75 USD | 52 | -16.6% |
| sąsiad_302_72 | -15.7% | 17.9% | -0.74 | 171 | 5.85 USD | 888.00 USD | 235.91 USD | 53 | -15.6% |

## H5: werdykt FAIL

| Kryterium | Wynik | Zaliczone |
|---|---|---|
| 1. Wynik po kosztach stresowych dodatni | -17.8% | NIE |
| 2. Sharpe po kosztach bazowych >= 0.7 | -0.32 | NIE |
| 3. Zysk do obsunięcia lepszy niż punkt odniesienia | -0.33 wobec -0.15 | NIE |
| 4. Największe obsunięcie <= 25% | 10.7% | tak |
| 5. Dodatnie kwartały >= 60% | 4 z 8 | NIE |
| 6. Wszyscy sąsiedzi dodatni | 0 z 8 | NIE |

| Wariant | Wynik poza strojeniem | Obsunięcie | Sharpe | Transakcje | Koszt spreadu | prowizja | finansowanie | Pominięte przez lot | Wynik w okresie strojenia |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| główny_base_opóźnienie0 | -6.5% | 10.7% | -0.32 | 154 | 3.69 USD | 840.00 USD | 265.90 USD | 38 | -11.2% |
| główny_base_opóźnienie1 | -3.4% | 10.4% | -0.15 | 152 | 3.74 USD | 834.00 USD | 271.73 USD | 34 | -10.8% |
| główny_stress_opóźnienie0 | -17.8% | 19.0% | -0.98 | 133 | 6.38 USD | 1080.00 USD | 381.97 USD | 50 | -17.0% |
| główny_stress_opóźnienie1 | -16.4% | 17.1% | -0.95 | 136 | 6.57 USD | 1107.00 USD | 380.33 USD | 49 | -16.9% |
| punkt_odniesienia | -4.8% | 17.4% | -0.14 | 176 | 3.11 USD | 924.00 USD | 357.33 USD | 34 | -7.1% |
| sąsiad_202_48 | -14.5% | 15.1% | -0.79 | 175 | 4.39 USD | 942.00 USD | 254.03 USD | 37 | -8.4% |
| sąsiad_202_60 | -12.4% | 13.5% | -0.66 | 164 | 4.28 USD | 876.00 USD | 256.27 USD | 39 | -8.3% |
| sąsiad_202_72 | -12.0% | 14.1% | -0.62 | 157 | 4.23 USD | 828.00 USD | 261.26 USD | 33 | -8.1% |
| sąsiad_252_48 | -10.3% | 12.3% | -0.54 | 169 | 3.92 USD | 924.00 USD | 267.17 USD | 37 | -9.9% |
| sąsiad_252_72 | -7.2% | 10.9% | -0.35 | 152 | 3.69 USD | 828.00 USD | 267.05 USD | 34 | -10.3% |
| sąsiad_302_48 | -12.7% | 14.6% | -0.58 | 172 | 4.21 USD | 930.00 USD | 264.22 USD | 38 | -8.6% |
| sąsiad_302_60 | -9.7% | 15.8% | -0.43 | 157 | 4.00 USD | 846.00 USD | 264.61 USD | 40 | -8.8% |
| sąsiad_302_72 | -7.7% | 15.4% | -0.32 | 147 | 3.87 USD | 780.00 USD | 268.73 USD | 35 | -8.1% |
