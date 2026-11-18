# Rejestr prób

Każdy uruchomiony wariant każdej hipotezy, także nieudany. Plik tworzy `research/tools/rejestr_prob.py`
z plików wyników. Nie edytuj go ręcznie. Zasady: `docs/research/PROTOKOL_WALIDACJI.md`.

Uruchomionych wariantów łącznie: 36. Im więcej prób, tym większa szansa, że dobry wynik jest
przypadkiem, dlatego ta liczba stoi na górze.

## Hipotezy

| Hipoteza | Opis | Werdykt | Kryteria spełnione | Warianty | Data | Dane (SHA-256) |
|---|---|---|---|---|---|---|
| H1 | tygodniowy model BTC/ETH z filtrem reżimu | FAIL | 1 z 6 | 12 | 2026-11-17 | 5012ca5fa526 |
| H2 | podążanie za trendem | FAIL | 4 z 6 | 12 | 2026-11-18 | w pliku wyniku |
| H3 | rotacja momentum | FAIL | 1 z 6 | 12 | 2026-11-18 | w pliku wyniku |

## Warianty

Liczby dotyczą próby poza strojeniem (od 01.01.2025).

| Hipoteza | Wariant | Rola | Parametry | Koszt | Opóźnienie | Zwrot | Obsunięcie | Sharpe |
|---|---|---|---|---|---|---|---|---|
| H1 | bazowy_40pb | główny | SMA 200, nachylenie 20 | 40 pb | 0 | -1.8% | 35.0% | 0.13 |
| H1 | stres_75pb | główny | SMA 200, nachylenie 20 | 75 pb | 0 | -2.6% | 35.1% | 0.11 |
| H1 | bazowy_40pb_opoznienie | główny | SMA 200, nachylenie 20 | 40 pb | 1 | -3.4% | 34.8% | 0.10 |
| H1 | stres_75pb_opoznienie | główny | SMA 200, nachylenie 20 | 75 pb | 1 | -4.2% | 34.9% | 0.08 |
| H1 | sasiad_sma160_nach16 | sąsiad | SMA 160, nachylenie 16 | 40 pb | 0 | +2.0% | 32.9% | 0.19 |
| H1 | sasiad_sma160_nach20 | sąsiad | SMA 160, nachylenie 20 | 40 pb | 0 | +2.0% | 32.9% | 0.19 |
| H1 | sasiad_sma160_nach24 | sąsiad | SMA 160, nachylenie 24 | 40 pb | 0 | +2.0% | 32.9% | 0.19 |
| H1 | sasiad_sma200_nach16 | sąsiad | SMA 200, nachylenie 16 | 40 pb | 0 | -1.8% | 35.0% | 0.13 |
| H1 | sasiad_sma200_nach24 | sąsiad | SMA 200, nachylenie 24 | 40 pb | 0 | -2.3% | 35.0% | 0.12 |
| H1 | sasiad_sma240_nach16 | sąsiad | SMA 240, nachylenie 16 | 40 pb | 0 | +0.8% | 35.2% | 0.18 |
| H1 | sasiad_sma240_nach20 | sąsiad | SMA 240, nachylenie 20 | 40 pb | 0 | +0.8% | 35.2% | 0.18 |
| H1 | sasiad_sma240_nach24 | sąsiad | SMA 240, nachylenie 24 | 40 pb | 0 | +0.8% | 35.2% | 0.18 |
| H2 | główny_base_opóźnienie0 | główny | 252, 60 | bazowy | 0 | +9.6% | 8.8% | 0.60 |
| H2 | główny_base_opóźnienie1 | główny | 252, 60 | bazowy | 1 | +9.7% | 9.2% | 0.60 |
| H2 | główny_stress_opóźnienie0 | główny | 252, 60 | stresowy | 0 | +2.8% | 9.5% | 0.21 |
| H2 | główny_stress_opóźnienie1 | główny | 252, 60 | stresowy | 1 | +3.3% | 9.5% | 0.24 |
| H2 | sąsiad_202_48 | sąsiad | 202, 48 | bazowy | 0 | +10.2% | 7.5% | 0.66 |
| H2 | sąsiad_202_60 | sąsiad | 202, 60 | bazowy | 0 | +10.0% | 7.5% | 0.66 |
| H2 | sąsiad_202_72 | sąsiad | 202, 72 | bazowy | 0 | +9.4% | 7.9% | 0.61 |
| H2 | sąsiad_252_48 | sąsiad | 252, 48 | bazowy | 0 | +9.8% | 9.2% | 0.60 |
| H2 | sąsiad_252_72 | sąsiad | 252, 72 | bazowy | 0 | +8.8% | 9.8% | 0.54 |
| H2 | sąsiad_302_48 | sąsiad | 302, 48 | bazowy | 0 | +9.8% | 9.2% | 0.59 |
| H2 | sąsiad_302_60 | sąsiad | 302, 60 | bazowy | 0 | +9.5% | 8.8% | 0.58 |
| H2 | sąsiad_302_72 | sąsiad | 302, 72 | bazowy | 0 | +9.4% | 9.7% | 0.56 |
| H3 | główny_base_opóźnienie0 | główny | 126, 3 | bazowy | 0 | -2.3% | 25.2% | 0.01 |
| H3 | główny_base_opóźnienie1 | główny | 126, 3 | bazowy | 1 | +1.2% | 22.6% | 0.12 |
| H3 | główny_stress_opóźnienie0 | główny | 126, 3 | stresowy | 0 | -11.0% | 27.8% | -0.28 |
| H3 | główny_stress_opóźnienie1 | główny | 126, 3 | stresowy | 1 | -7.9% | 25.4% | -0.17 |
| H3 | sąsiad_101_2 | sąsiad | 101, 2 | bazowy | 0 | -17.3% | 41.3% | -0.34 |
| H3 | sąsiad_101_3 | sąsiad | 101, 3 | bazowy | 0 | -13.8% | 29.3% | -0.37 |
| H3 | sąsiad_101_4 | sąsiad | 101, 4 | bazowy | 0 | -6.1% | 22.9% | -0.15 |
| H3 | sąsiad_126_2 | sąsiad | 126, 2 | bazowy | 0 | -21.6% | 37.8% | -0.46 |
| H3 | sąsiad_126_4 | sąsiad | 126, 4 | bazowy | 0 | +11.7% | 14.7% | 0.49 |
| H3 | sąsiad_151_2 | sąsiad | 151, 2 | bazowy | 0 | -5.0% | 30.9% | 0.00 |
| H3 | sąsiad_151_3 | sąsiad | 151, 3 | bazowy | 0 | +10.1% | 22.1% | 0.37 |
| H3 | sąsiad_151_4 | sąsiad | 151, 4 | bazowy | 0 | +4.3% | 15.4% | 0.22 |
