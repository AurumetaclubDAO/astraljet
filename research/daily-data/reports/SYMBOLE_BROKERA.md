# Symbole brokera — parametry wielkości i kosztu

- Odczyt: 2026-11-19T19:06:15+00:00 UTC, skrypt `research/daily-data/scripts/collect_symbols.py` (tylko odczyt: `symbols_get`, `symbol_info_tick` dla symboli już widocznych w Market Watch).
- Pełna lista: `research/daily-data/data/symbols_all.json` (pomijana przez Git).
- Symboli razem: 1418; widocznych w Market Watch przed odczytem 23, po odczycie 23; odczytanych ticków: 23.
- Kursy walut do przeliczenia na USD (z tej samej listy): AED, AUD, BCH, BRL, BTC, CAD, CHF, CLP, CNH, COP, CZK, DKK, ETH, EUR, GBP, GBX, HKD, HUF, IDR, ILS, INR, JPY, KRW, LTC, MXN, NOK, NZD, PLN, SEK, SGD, SOL, THB, TRY, TWD, USC, USD, XAU, XRP, ZAR.

## Symbole według kategorii

| Kategoria | Symboli |
|---|---:|
| Stocks | 968 |
| 247 Product | 165 |
| ETF | 73 |
| Forex+ | 64 |
| Crypto Currency | 63 |
| CFDs.r | 29 |
| Forex Major | 24 |
| Commodities.r | 13 |
| bond CFDs | 7 |
| Gold+ | 4 |
| Oil | 4 |
| Nikkei | 2 |
| Silver | 2 |

## Najmniejszy lot wart najwyżej 500 USD

Wartość nominalna = `volume_min` × `trade_contract_size` × cena, w walucie zysku, przeliczona kursem z tej samej listy. Cena to środek bid/ask; dla symboli spoza Market Watch pochodzi z ostatnich danych terminala i może być nieświeża. Swap w jednostkach trybu (`swap_mode`).

Spełnia warunek: 11 symboli.

| Symbol | Opis | Kategoria | Najmniejszy lot [USD] | Lot min / krok | Swap long / short (tryb) | Tryb handlu | MW |
|---|---|---|---:|---|---|---|---|
| `INTEL` | INTEL CORP | Stocks | 5.60 | 0.1 / 0.1 | -6 / 2 (INTEREST_CURRENT) | FULL | tak |
| `SOLUSD` | Solana | Crypto Currency | 7.38 | 0.01 / 0.01 | -25 / 0 (INTEREST_CURRENT) | FULL | tak |
| `USDUSC` | USC | Forex Major | 10.00 | 0.01 / 0.01 | 0 / 0 (POINTS) | DISABLED | nie |
| `GBXUSD` | Great Britain Pence vs US Dollar | Forex Major | 13.15 | 0.01 / 0.01 | 0 / 0 (POINTS) | DISABLED | nie |
| `SPCX` | Space Exploration Technologies Corp. | Stocks | 13.75 | 0.1 / 0.1 | -12 / -3 (INTEREST_CURRENT) | FULL | tak |
| `NVIDIA` | NVIDIA CORP | Stocks | 14.82 | 0.1 / 0.1 | -6 / 2 (INTEREST_CURRENT) | FULL | tak |
| `ETHUSD` | Ethereum | Crypto Currency | 17.74 | 0.01 / 0.01 | -25 / 0 (INTEREST_CURRENT) | FULL | tak |
| `BCHUSD` | Bitcoin Cash | Crypto Currency | 20.74 | 0.01 / 0.01 | -25 / 0 (INTEREST_CURRENT) | FULL | nie |
| `LTCUSD` | Litecoin | Crypto Currency | 42.94 | 0.01 / 0.01 | -25 / 0 (INTEREST_CURRENT) | FULL | nie |
| `MU` | Micron | Stocks | 69.76 | 0.1 / 0.1 | -6 / 2 (INTEREST_CURRENT) | FULL | tak |
| `XRPUSD` | Ripple | Crypto Currency | 97.06 | 0.01 / 0.01 | -25 / 0 (INTEREST_CURRENT) | FULL | tak |

## Czego nie udało się policzyć

Wartości najmniejszego lota nie da się policzyć dla 1350 symboli.
- brak ceny: 1350

Symbole bez ceny według kategorii (z ceną / razem):

- Stocks: 4 / 968
- 247 Product: 1 / 165
- ETF: 0 / 73
- Crypto Currency: 6 / 63
- Forex+: 28 / 64
- CFDs.r: 3 / 29
- Commodities.r: 0 / 13
- bond CFDs: 0 / 7
- Gold+: 1 / 4
- Nikkei: 0 / 2
- Oil: 2 / 4
- Silver: 0 / 2
- Forex Major: 23 / 24

Uwagi:
- Symbole spoza Market Watch nie były do niego dodawane. Gdy terminal nie ma dla nich ceny, pole `price` w JSON jest puste, a wartość lota nieobliczona.
- Dla trybów wyceny innych niż FOREX/CFD (`trade_calc_mode_name` w JSON) wzór nominalny może nie odpowiadać depozytowi u brokera; tabela pokazuje ekspozycję, nie wymagany depozyt.
