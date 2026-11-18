# Najmniejszy kapitał dla koszyka H2 bez dźwigni

Dni decyzji: 2024-12-31 do 2026-10-31 (23 decyzji). Kapitał w USD. Nie ma tu wyników strategii.

## Najmniejsza pozycja u brokera

Ceny z 2026-10-31.

| Rynek | Symbol | Najmniejszy lot | Wartość najmniejszego lota |
|---|---|---|---|
| BTCUSD | BTCUSD | 0.01 | 775 USD |
| EURUSD | EURUSD+ | 0.01 | 1 116 USD |
| DAX | GER40.r | 0.1 | 2 879 USD |
| NAS100 | NAS100.r | 0.1 | 2 842 USD |
| SP500 | SP500.r | 0.1 | 759 USD |
| BRENT | UKOUSD | 0.01 | 1 169 USD |
| GOLD | XAUUSD+ | 0.01 | 3 876 USD |

## sam koszyk (zawsze w rynku)

Kapitał, przy którym każdy rynek z wagą powyżej zera dostaje choć najmniejszy lot: mediana 44 660 USD, najwięcej 93 422 USD (z 23 decyzji).

Wagi z ostatniej decyzji (2026-10-31) i ich zakres od 2024-12-31:

| Rynek | Waga ostatnio | Zakres wag | Kapitał potrzebny na najmniejszy lot |
|---|---|---|---|
| BTCUSD | 5.7% | 3.9% do 11.3% | 13 490 USD |
| EURUSD | 37.6% | 23.0% do 44.4% | 2 965 USD |
| DAX | 15.1% | 10.6% do 18.4% | 19 129 USD |
| NAS100 | 10.5% | 8.1% do 14.9% | 26 992 USD |
| SP500 | 18.8% | 10.8% do 19.6% | 4 027 USD |
| BRENT | 4.6% | 3.4% do 10.8% | 25 192 USD |
| GOLD | 7.5% | 5.7% do 18.5% | 51 336 USD |

Co da się kupić przy danym kapitale (ostatnia decyzja, zaokrąglenie lotów w dół):

| Kapitał | Rynki z pozycją | Rynki pominięte | Zainwestowane | Powinno być |
|---|---|---|---|---|
| 1 000 USD | 0 z 7 | 7 | 0% | 100% |
| 5 000 USD | 2 z 7 | 5 | 37% | 100% |
| 10 000 USD | 2 z 7 | 5 | 49% | 100% |
| 25 000 USD | 4 z 7 | 3 | 69% | 100% |
| 50 000 USD | 6 z 7 | 1 | 78% | 100% |
| 100 000 USD | 7 z 7 | 0 | 91% | 100% |
| 250 000 USD | 7 z 7 | 0 | 98% | 100% |

## H2 (z filtrem trendu)

Kapitał, przy którym każdy rynek z wagą powyżej zera dostaje choć najmniejszy lot: mediana 43 794 USD, najwięcej 93 422 USD (z 23 decyzji).

Wagi z ostatniej decyzji (2026-10-31) i ich zakres od 2024-12-31:

| Rynek | Waga ostatnio | Zakres wag | Kapitał potrzebny na najmniejszy lot |
|---|---|---|---|
| BTCUSD | 5.7% | 0.0% do 11.3% | 13 490 USD |
| EURUSD | 0.0% | 0.0% do 44.4% | poza rynkiem |
| DAX | 15.1% | 10.6% do 18.4% | 19 129 USD |
| NAS100 | 10.5% | 8.1% do 14.9% | 26 992 USD |
| SP500 | 18.8% | 10.8% do 19.6% | 4 027 USD |
| BRENT | 4.6% | 0.0% do 7.2% | 25 192 USD |
| GOLD | 0.0% | 0.0% do 18.5% | poza rynkiem |

Co da się kupić przy danym kapitale (ostatnia decyzja, zaokrąglenie lotów w dół):

| Kapitał | Rynki z pozycją | Rynki pominięte | Zainwestowane | Powinno być |
|---|---|---|---|---|
| 1 000 USD | 0 z 5 | 5 | 0% | 55% |
| 5 000 USD | 1 z 5 | 4 | 15% | 55% |
| 10 000 USD | 1 z 5 | 4 | 15% | 55% |
| 25 000 USD | 3 z 5 | 2 | 33% | 55% |
| 50 000 USD | 5 z 5 | 0 | 42% | 55% |
| 100 000 USD | 5 z 5 | 0 | 50% | 55% |
| 250 000 USD | 5 z 5 | 0 | 54% | 55% |

Bez dźwigni oznacza, że suma wartości pozycji nie przekracza kapitału, tak jak w badaniu.
