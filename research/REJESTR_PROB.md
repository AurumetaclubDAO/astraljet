# Rejestr prób

Każdy uruchomiony wariant każdej hipotezy, także nieudany. Plik tworzy `research/tools/rejestr_prob.py`
z plików wyników. Nie edytuj go ręcznie. Zasady: `docs/research/PROTOKOL_WALIDACJI.md`.

Uruchomionych wariantów łącznie: 60. Im więcej prób, tym większa szansa, że dobry wynik jest
przypadkiem, dlatego ta liczba stoi na górze.

## Hipotezy

| Hipoteza | Opis | Werdykt | Kryteria spełnione | Warianty | Data | Dane (SHA-256) |
|---|---|---|---|---|---|---|
| H1 | tygodniowy model BTC/ETH z filtrem reżimu | FAIL | 1 z 6 | 12 | 2026-11-17 | 5012ca5fa526 |
| H2 | podążanie za trendem | FAIL | 4 z 6 | 12 | 2026-11-18 | w pliku wyniku |
| H3 | rotacja momentum | FAIL | 1 z 6 | 12 | 2026-11-18 | w pliku wyniku |
| H4 | trend w obie strony, koszyk CFD w lotach | FAIL | 1 z 6 | 12 | 2026-11-21 | 11 plików, w pliku wyniku |
| H5 | trend tylko długi, koszyk CFD w lotach | FAIL | 1 z 6 | 12 | 2026-11-21 | 11 plików, w pliku wyniku |

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
| H4 | główny_base_opóźnienie0 | główny | 252, 60 | bazowy | 0 | -10.6% | 13.0% | -0.59 |
| H4 | główny_base_opóźnienie1 | główny | 252, 60 | bazowy | 1 | -8.7% | 10.6% | -0.49 |
| H4 | główny_stress_opóźnienie0 | główny | 252, 60 | stresowy | 0 | -29.0% | 29.0% | -1.60 |
| H4 | główny_stress_opóźnienie1 | główny | 252, 60 | stresowy | 1 | -29.2% | 29.2% | -1.81 |
| H4 | sąsiad_202_48 | sąsiad | 202, 48 | bazowy | 0 | -22.9% | 22.9% | -1.38 |
| H4 | sąsiad_202_60 | sąsiad | 202, 60 | bazowy | 0 | -21.7% | 21.7% | -1.32 |
| H4 | sąsiad_202_72 | sąsiad | 202, 72 | bazowy | 0 | -21.0% | 21.0% | -1.25 |
| H4 | sąsiad_252_48 | sąsiad | 252, 48 | bazowy | 0 | -13.7% | 16.2% | -0.75 |
| H4 | sąsiad_252_72 | sąsiad | 252, 72 | bazowy | 0 | -10.6% | 13.0% | -0.59 |
| H4 | sąsiad_302_48 | sąsiad | 302, 48 | bazowy | 0 | -20.8% | 21.2% | -1.07 |
| H4 | sąsiad_302_60 | sąsiad | 302, 60 | bazowy | 0 | -14.7% | 17.7% | -0.70 |
| H4 | sąsiad_302_72 | sąsiad | 302, 72 | bazowy | 0 | -15.7% | 17.9% | -0.74 |
| H5 | główny_base_opóźnienie0 | główny | 252, 60 | bazowy | 0 | -6.5% | 10.7% | -0.32 |
| H5 | główny_base_opóźnienie1 | główny | 252, 60 | bazowy | 1 | -3.4% | 10.4% | -0.15 |
| H5 | główny_stress_opóźnienie0 | główny | 252, 60 | stresowy | 0 | -17.8% | 19.0% | -0.98 |
| H5 | główny_stress_opóźnienie1 | główny | 252, 60 | stresowy | 1 | -16.4% | 17.1% | -0.95 |
| H5 | sąsiad_202_48 | sąsiad | 202, 48 | bazowy | 0 | -14.5% | 15.1% | -0.79 |
| H5 | sąsiad_202_60 | sąsiad | 202, 60 | bazowy | 0 | -12.4% | 13.5% | -0.66 |
| H5 | sąsiad_202_72 | sąsiad | 202, 72 | bazowy | 0 | -12.0% | 14.1% | -0.62 |
| H5 | sąsiad_252_48 | sąsiad | 252, 48 | bazowy | 0 | -10.3% | 12.3% | -0.54 |
| H5 | sąsiad_252_72 | sąsiad | 252, 72 | bazowy | 0 | -7.2% | 10.9% | -0.35 |
| H5 | sąsiad_302_48 | sąsiad | 302, 48 | bazowy | 0 | -12.7% | 14.6% | -0.58 |
| H5 | sąsiad_302_60 | sąsiad | 302, 60 | bazowy | 0 | -9.7% | 15.8% | -0.43 |
| H5 | sąsiad_302_72 | sąsiad | 302, 72 | bazowy | 0 | -7.7% | 15.4% | -0.32 |

## Przebiegi diagnostyczne

Bez werdyktu, na okresie oglądanym wcześniej. Liczba przebiegów: 6 (2026-11-18). Też są spojrzeniem na próbę, więc liczą się do ostrożności.

| Diagnoza | Strategia | Mnożnik finansowania | Zwrot | Obsunięcie | Sharpe |
|---|---|---|---|---|---|
| wpływ finansowania | H2 | 0.0 | +20.3% | 8.4% | 1.16 |
| wpływ finansowania | punkt_odniesienia | 0.0 | +23.3% | 8.9% | 1.15 |
| wpływ finansowania | H2 | 0.5 | +14.8% | 8.5% | 0.88 |
| wpływ finansowania | punkt_odniesienia | 0.5 | +17.0% | 9.1% | 0.87 |
| wpływ finansowania | H2 | 1.0 | +9.6% | 8.8% | 0.60 |
| wpływ finansowania | punkt_odniesienia | 1.0 | +10.5% | 9.5% | 0.57 |
