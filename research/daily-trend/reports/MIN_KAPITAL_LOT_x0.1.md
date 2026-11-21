# Najmniejszy kapitał dla koszyka H2 bez dźwigni

Dni decyzji: 2024-12-31 do 2026-10-31 (23 decyzji). Kapitał w USD. Nie ma tu wyników strategii.

**Wariant hipotetyczny:** najmniejszy lot i krok pomnożone przez 0.1. To nie są warunki obecnego brokera.

## Najmniejsza pozycja w wariancie hipotetycznym

Ceny z 2026-10-31.

| Rynek | Symbol | Najmniejszy lot | Wartość najmniejszego lota |
|---|---|---|---|
| BTCUSD | BTCUSD | 0.001 | 78 USD |
| EURUSD | EURUSD+ | 0.001 | 112 USD |
| DAX | GER40.r | 0.01 | 288 USD |
| NAS100 | NAS100.r | 0.01 | 284 USD |
| SP500 | SP500.r | 0.01 | 76 USD |
| BRENT | UKOUSD | 0.001 | 117 USD |
| GOLD | XAUUSD+ | 0.001 | 388 USD |

## sam koszyk (zawsze w rynku)

Kapitał, przy którym każdy rynek z wagą powyżej zera dostaje choć najmniejszy lot: mediana 4 466 USD, najwięcej 9 342 USD (z 23 decyzji).

Wagi z ostatniej decyzji (2026-10-31) i ich zakres od 2024-12-31:

| Rynek | Waga ostatnio | Zakres wag | Kapitał potrzebny na najmniejszy lot |
|---|---|---|---|
| BTCUSD | 5.7% | 3.9% do 11.3% | 1 349 USD |
| EURUSD | 37.6% | 23.0% do 44.4% | 297 USD |
| DAX | 15.1% | 10.6% do 18.4% | 1 913 USD |
| NAS100 | 10.5% | 8.1% do 14.9% | 2 699 USD |
| SP500 | 18.8% | 10.8% do 19.6% | 403 USD |
| BRENT | 4.6% | 3.4% do 10.8% | 2 519 USD |
| GOLD | 7.5% | 5.7% do 18.5% | 5 134 USD |

Co da się kupić przy danym kapitale (ostatnia decyzja, zaokrąglenie lotów w dół):

| Kapitał | Rynki z pozycją | Rynki pominięte | Zainwestowane | Powinno być |
|---|---|---|---|---|
| 1 000 USD | 2 z 7 | 5 | 49% | 100% |
| 2 500 USD | 4 z 7 | 3 | 69% | 100% |
| 5 000 USD | 6 z 7 | 1 | 78% | 100% |
| 10 000 USD | 7 z 7 | 0 | 91% | 100% |
| 25 000 USD | 7 z 7 | 0 | 98% | 100% |
| 50 000 USD | 7 z 7 | 0 | 99% | 100% |
| 100 000 USD | 7 z 7 | 0 | 100% | 100% |
| 250 000 USD | 7 z 7 | 0 | 100% | 100% |

## H2 (z filtrem trendu)

Kapitał, przy którym każdy rynek z wagą powyżej zera dostaje choć najmniejszy lot: mediana 4 379 USD, najwięcej 9 342 USD (z 23 decyzji).

Wagi z ostatniej decyzji (2026-10-31) i ich zakres od 2024-12-31:

| Rynek | Waga ostatnio | Zakres wag | Kapitał potrzebny na najmniejszy lot |
|---|---|---|---|
| BTCUSD | 5.7% | 0.0% do 11.3% | 1 349 USD |
| EURUSD | 0.0% | 0.0% do 44.4% | poza rynkiem |
| DAX | 15.1% | 10.6% do 18.4% | 1 913 USD |
| NAS100 | 10.5% | 8.1% do 14.9% | 2 699 USD |
| SP500 | 18.8% | 10.8% do 19.6% | 403 USD |
| BRENT | 4.6% | 0.0% do 7.2% | 2 519 USD |
| GOLD | 0.0% | 0.0% do 18.5% | poza rynkiem |

Co da się kupić przy danym kapitale (ostatnia decyzja, zaokrąglenie lotów w dół):

| Kapitał | Rynki z pozycją | Rynki pominięte | Zainwestowane | Powinno być |
|---|---|---|---|---|
| 1 000 USD | 1 z 5 | 4 | 15% | 55% |
| 2 500 USD | 3 z 5 | 2 | 33% | 55% |
| 5 000 USD | 5 z 5 | 0 | 42% | 55% |
| 10 000 USD | 5 z 5 | 0 | 50% | 55% |
| 25 000 USD | 5 z 5 | 0 | 54% | 55% |
| 50 000 USD | 5 z 5 | 0 | 54% | 55% |
| 100 000 USD | 5 z 5 | 0 | 55% | 55% |
| 250 000 USD | 5 z 5 | 0 | 55% | 55% |

Bez dźwigni oznacza, że suma wartości pozycji nie przekracza kapitału, tak jak w badaniu.
