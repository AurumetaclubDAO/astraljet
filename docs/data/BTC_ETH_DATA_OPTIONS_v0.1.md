# BTC/ETH — warianty DATA v0.1

**Stan:** rozpoznanie źródeł, bez pobrania i bez utworzenia DATA  
**Data sprawdzenia:** 2026-09-19

## Wariant A — Kraken spot BTC/USD i ETH/USD

Oficjalna strona Kraken udostępnia historyczne OHLCVT w CSV od początku każdego rynku,
w interwałach obejmujących 1440 minut, oraz aktualizacje kwartalne. Dane zawierają
`timestamp, open, high, low, close, volume, trades`. Kraken zaznacza, że puste interwały
nie występują w plikach, jeśli nie było transakcji.

Źródło:
https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data

Zalety:

- pary z kwotowaniem w USD odpowiadają zakresowi kandydata;
- dane jednej, jawnej giełdy zamiast nieokreślonego agregatu;
- dzienne OHLCVT można normalizować do schematu AstralJet;
- pełny plik historyczny i późniejsze przyrosty można hashować i wersjonować.

Ryzyka i braki:

- przed użyciem trzeba potwierdzić nazwy par i granicę dnia w pobranym manifeście;
- brak wiersza może oznaczać brak transakcji, więc polityka luk musi pozostać fail-closed;
- warunki wykorzystania danych trzeba zapisać razem z proweniencją;
- dane nie ustalają fee, spreadu ani slippage dla ocenianego EXP.

## Wariant B — Binance Public Data BTCUSDT i ETHUSDT

Oficjalne archiwum Binance publikuje dane spot jako pliki dzienne i miesięczne, obsługuje
interwał `1d` oraz publikuje sumy kontrolne. Publiczny endpoint market-data-only nie wymaga
klucza API. Od 1 stycznia 2025 znaczniki czasu danych spot są zapisane w mikrosekundach.

Źródła:

- https://github.com/binance/binance-public-data
- https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md

Zalety:

- proste, publiczne archiwum i sumy kontrolne;
- aktualizacje dzienne i miesięczne;
- brak potrzeby używania sekretów do pobierania danych rynkowych.

Ryzyka i braki:

- są to pary z USDT, a nie USD; powstaje ryzyko bazy stablecoina;
- zmiana jednostki timestampu musi być obsłużona jawnie;
- licencja repozytorium z narzędziami nie może być automatycznie utożsamiona z prawem do
  dowolnej redystrybucji samych danych;
- pojedyncza giełda nadal niesie ryzyko specyficzne dla venue.

## Wniosek roboczy

Do pierwszego testu mechaniki lepiej pasuje **wariant A: Kraken BTC/USD i ETH/USD**, bo nie
wprowadza dodatkowej hipotezy USDT≈USD. Jest to rekomendacja źródła DATA, nie zgoda na
pobranie, nie gotowy model kosztów i nie dowód jakości inwestycyjnej.

Przed pobraniem należy zatwierdzić:

1. venue Kraken i pary BTC/USD oraz ETH/USD;
2. dzienną granicę UTC oraz sposób budowania tygodniowego close;
3. okres badania i jawny podział IS/OOS;
4. zachowanie przy lukach i korektach archiwum;
5. model kosztów niezależny od samego OHLCVT;
6. katalog danych poza Git i budżet miejsca na dysku.

Nie pobrano żadnego archiwum i nie utworzono rekordu DATA.
