# Decyzja Karola — pierwsza strategia BTC/ETH v0.1

**Stan:** oczekuje na decyzję  
**Skutek akceptacji:** pozwala utworzyć kompletną STRAT i zamrozić plan EXP  
**Nie upoważnia do:** PAPER, DEMO ani REAL

## Rekomendowany pakiet

1. Rynek i dane: Alpaca US spot, `BTC/USD` i `ETH/USD`, świece `1Day` w UTC.
2. Zastosowanie danych: prywatne, lokalne badanie; bez redystrybucji.
3. Sygnał: po niedzielnym zamknięciu UTC.
4. Risk-on: `BTC close > SMA200` oraz `SMA200[t] > SMA200[t-20]`.
5. Risk-off: którykolwiek z dwóch warunków risk-on przestaje być spełniony.
6. Nieoperacyjne „pogorszenie struktury trendu” usuwamy z v0.1.
7. Wykonanie modelowe: otwarcie następnej dziennej świecy; bez użycia tej samej
   świecy do sygnału i realizacji.
8. Wagi risk-on: BTC 70%, ETH 20%, syntetyczny cash USD 10%.
9. Wagi risk-off: BTC 35%, ETH 10%, syntetyczny cash USD 55%.
10. ETH jest sterowane sygnałem BTC; osobny filtr ETH może być późniejszą wersją.
11. Odbudowa: dwie równe transze po dwóch kolejnych tygodniowych potwierdzeniach:
    najpierw BTC 52,5% / ETH 15% / cash 32,5%, potem pełne 70% / 20% / 10%.
    Utrata warunku przed drugą transzą przywraca risk-off.
12. Bez dźwigni i bez krótkich pozycji.
13. Cash ma stopę 0% w pierwszym eksperymencie, aby nie dopisywać niezatwierdzonego
    instrumentu ani historycznych stóp.
14. Benchmark: BTC 80% / ETH 20%, rebalans na pierwszym dostępnym otwarciu miesiąca,
    z tym samym modelem kosztów.
15. Okres danych: 2021-01-01–2026-09-18; pierwsze 200 dni jest warm-up.
16. Podział: IS do 2024-12-31, OOS od 2025-01-01 do 2026-09-18.

## Model kosztów — rekomendacja A

Fakt dostawcy: najniższy próg wolumenu Alpaca ma obecnie 15 bps maker i 25 bps taker.
Backtest nie wie z góry, czy realizacja będzie maker, dlatego używamy 25 bps.

Rekomendowany wariant:

- bazowo 40 bps jednostronnego turnover: 25 bps fee + 5 bps half-spread + 10 bps slippage;
- stress 75 bps: 25 bps fee + 20 bps half-spread + 30 bps slippage;
- każdy zakup, sprzedaż i rebalans obciążamy odpowiednim kosztem;
- wyniki pokazujemy równolegle dla bazowego i stresowego kosztu.

Fee jest faktem z dokumentacji Alpaca. Spread i slippage są konserwatywnymi hipotezami
badawczymi, a nie pomiarem tego rachunku. Po inkubacji należy je zastąpić rozkładem
z rzeczywistych kwotowań i symulowanych realizacji.

Alternatywy:

- B — ostrzejszy test: 50 bps bazowo i 100 bps stress;
- C — pozostawić koszty nieustalone i nie uruchamiać ocenianego backtestu.

Źródło fee:
https://docs.alpaca.markets/us/docs/crypto-fees

## Decyzja

Akceptacja pakietu A oznacza zgodę na założenia badawcze, nie zgodę na handel.
Po akceptacji AstralJet utworzy nową wersję STRAT, zarejestruje DATA z modelem kosztów,
zamrozi EXP przed wynikiem i dopiero wtedy wykona dwa odtwarzalne RUN.

