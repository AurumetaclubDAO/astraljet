# H1: tygodniowy model BTC/ETH (pakiet A) — wynik badania offline

Wygenerowano: 2026-11-17T22:54:51+00:00. To obliczenie modelu, nie rekord RUN i nie zgoda na handel.

- Dane: `alpaca_crypto_us_full_2015-01-01_2026-09-19.csv`, SHA-256 `5012ca5fa5265363…`, 4174 świec dziennych.
- Okres strojenia: 2021-01-01 do 2024-12-31. Próba poza strojeniem: 2025-01-01 do 2026-09-18.
- Silnik: `astraljet.lab.weekly_portfolio`, odcisk `90DB20F196B206BD…`.
- Liczba uruchomionych wariantów: 12 (wszystkie w `wynik_h1.json`).
- Kryteria zapisano przed testem (17.11.2026, `PLAN_BUDOWY.md`).

## Werdykt: FAIL

| Kryterium | Wynik | Zaliczone |
|---|---|---|
| 1. Wynik po kosztach stresowych dodatni | -2.6% | NIE |
| 2. Sharpe po kosztach bazowych >= 0.7 | 0.13 | NIE |
| 3. Zysk do obsunięcia lepszy niż dla kup i trzymaj | -0.03 wobec -0.14 | tak |
| 4. Największe obsunięcie <= 25% | 35.0% | NIE |
| 5. Dodatnie okna kwartalne >= 60% | 3 z 7 | NIE |
| 6. Sąsiednie parametry (+/-20%) też dodatnie | 6 z 8 | NIE |

## Próba poza strojeniem, wariant główny (SMA 200, nachylenie 20)

| Wariant | Strategia: wynik | Strategia: obsunięcie | Kup i trzymaj 80/20: wynik | Kup i trzymaj: obsunięcie |
|---|---|---|---|---|
| bazowy_40pb | -1.8% | 35.0% | -12.8% | 56.1% |
| stres_75pb | -2.6% | 35.1% | -13.0% | 56.1% |
| bazowy_40pb_opoznienie | -3.4% | 34.8% | -12.8% | 56.0% |
| stres_75pb_opoznienie | -4.2% | 34.9% | -13.1% | 56.0% |

## Okres strojenia, wariant bazowy (dla porównania)

- Strategia: +56.0%, obsunięcie 50.8%.
- Kup i trzymaj 80/20: +91.0%, obsunięcie 76.4%.

## Okna kwartalne poza strojeniem, wariant bazowy

| Kwartał | Strategia | Kup i trzymaj |
|---|---|---|
| 2025Q1 | -18.7% | -19.3% |
| 2025Q2 | +22.7% | +31.8% |
| 2025Q3 | +20.1% | +18.1% |
| 2025Q4 | -16.3% | -24.3% |
| 2026Q1 | -9.6% | -23.4% |
| 2026Q2 | -5.7% | -16.5% |
| 2026Q3 | +14.8% | +43.5% |

## Sąsiednie parametry, koszty bazowe, próba poza strojeniem

| SMA | Nachylenie | Wynik | Obsunięcie |
|---|---|---|---|
| 160 | 16 | +2.0% | 32.9% |
| 160 | 20 | +2.0% | 32.9% |
| 160 | 24 | +2.0% | 32.9% |
| 200 | 16 | -1.8% | 35.0% |
| 200 | 24 | -2.3% | 35.0% |
| 240 | 16 | +0.8% | 35.2% |
| 240 | 20 | +0.8% | 35.2% |
| 240 | 24 | +0.8% | 35.2% |
