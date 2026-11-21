# Najmniejsze pozycje CFD przy kapitale 2 500 USD

Ceny z 2026-10-31, najmniejsze loty i stawki finansowania z odczytu terminala. Historia zmian cen od 2018-03-19.
To nie jest test strategii. Tabele pokazują ryzyko i koszt trzymania pozycji długiej, a nie oczekiwany zysk.

## Jedna najmniejsza pozycja długa

| Rynek | Symbol | Wartość | Część kapitału | Finansowanie rocznie | Typowy dzień | Najgorszy dzień od 2018 |
|---|---|---|---|---|---|---|
| ETHUSD | ETHUSD | 23 USD | 1% | 6 USD (0.2% kapitału) | ±1 USD | -7 USD (-0.3% kapitału, 2020-03-12) |
| SP500 | SP500.r | 759 USD | 30% | 59 USD (2.4% kapitału) | ±6 USD | -81 USD (-3.2% kapitału, 2020-03-12) |
| BTCUSD | BTCUSD | 775 USD | 31% | 155 USD (6.2% kapitału) | ±16 USD | -211 USD (-8.4% kapitału, 2020-03-12) |
| WTI | USOUSD | 1 036 USD | 41% | 0 USD (0.0% kapitału) | ±35 USD | -566 USD (-22.6% kapitału, 2020-04-21) |
| EURUSD | EURUSD+ | 1 116 USD | 45% | 23 USD (0.9% kapitału) | ±4 USD | -23 USD (-0.9% kapitału, 2020-03-19) |
| BRENT | UKOUSD | 1 169 USD | 47% | 0 USD (0.0% kapitału) | ±36 USD | -309 USD (-12.4% kapitału, 2020-03-09) |
| NAS100 | NAS100.r | 2 842 USD | 114% | 219 USD (8.7% kapitału) | ±37 USD | -298 USD (-11.9% kapitału, 2020-03-12) |
| DAX | GER40.r | 2 879 USD | 115% | 169 USD (6.8% kapitału) | ±29 USD | -366 USD (-14.7% kapitału, 2020-03-12) |
| GOLD | XAUUSD+ | 3 876 USD | 155% | 253 USD (10.1% kapitału) | ±68 USD | -354 USD (-14.2% kapitału, 2026-01-30) |

## Zestawy: po jednej najmniejszej pozycji długiej na każdym rynku

Obsunięcie liczone tak: dzisiejsze wartości pozycji przechodzą przez dzienne zmiany cen od 2018 roku, bez kosztów.

| Zestaw | Rynki | Łączna wartość pozycji | Razy kapitał | Finansowanie rocznie | Typowy dzień | Najgorszy dzień | Największe obsunięcie |
|---|---|---|---|---|---|---|---|
| Cztery najtańsze rynki koszyka | SP500, BTCUSD, EURUSD, BRENT | 3 819 USD | 1.5 | 238 USD (9.5% kapitału) | ±33 USD (1.3%) | -460 USD (-18.4%, 2020-03-09) | -1 633 USD (-65% kapitału, 2019-07-12 do 2020-04-01) |
| Cały koszyk z badania (7 rynków) | SP500, BTCUSD, EURUSD, BRENT, NAS100, DAX, GOLD | 13 416 USD | 5.4 | 878 USD (35.1% kapitału) | ±92 USD (3.7%) | -1 208 USD (-48.3%, 2020-03-12) | -3 844 USD (-154% kapitału, 2020-02-19 do 2020-03-18) |
| Wszystko, co pojedynczo mieści się w kapitale | ETHUSD, SP500, BTCUSD, WTI, EURUSD, BRENT | 4 877 USD | 2.0 | 243 USD (9.7% kapitału) | ±62 USD (2.5%) | -863 USD (-34.5%, 2020-04-21) | -3 387 USD (-135% kapitału, 2019-07-12 do 2020-04-21) |

Obsunięcie większe niż 100% kapitału oznacza, że rachunek zostałby zamknięty przez brokera, zanim okres by się skończył.
Finansowanie dotyczy pozycji długich i pochodzi z jednego odczytu stawek; dodatni swap liczę jako zero.
