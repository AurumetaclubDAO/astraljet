# Rejestr prób

Każdy uruchomiony wariant każdej hipotezy, także nieudany. Plik tworzy `research/tools/rejestr_prob.py`
z plików wyników. Nie edytuj go ręcznie. Zasady: `docs/research/PROTOKOL_WALIDACJI.md`.

Uruchomionych wariantów łącznie: 12. Im więcej prób, tym większa szansa, że dobry wynik jest
przypadkiem, dlatego ta liczba stoi na górze.

## Hipotezy

| Hipoteza | Opis | Werdykt | Kryteria spełnione | Warianty | Data | Dane (SHA-256) |
|---|---|---|---|---|---|---|
| H1 | tygodniowy model BTC/ETH z filtrem reżimu | FAIL | 1 z 6 | 12 | 2026-11-17 | 5012ca5fa526 |
| H2 | podążanie za trendem na koszyku rynków | NIEURUCHOMIONE | brak | 0 z 12 zapisanych | brak | brak |
| H3 | rotacja momentum między rynkami | NIEURUCHOMIONE | brak | 0 z 12 zapisanych | brak | brak |

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
