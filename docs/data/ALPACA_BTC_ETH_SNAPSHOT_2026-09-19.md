# Snapshot BTC/ETH z Alpaca — 2026-09-19

**Stan:** pobrany i zarejestrowany jako `blocked`  
**Zastosowanie:** wyłącznie lokalne badania AstralJet  
**Wykonanie zleceń:** nie uruchomiono

## Wynik

Adapter pobrał historyczne świece dzienne z oficjalnego endpointu Alpaca Market Data:

- endpoint: `GET https://data.alpaca.markets/v1beta3/crypto/us/bars`;
- lokalizacja danych: `us` — Alpaca US;
- źródłowe symbole: `BTC/USD`, `ETH/USD`;
- znormalizowane instrumenty: `BTCUSD`, `ETHUSD`;
- żądany początek: `2015-01-01T00:00:00Z`;
- faktyczny okres zwrócony przez Alpaca: `2021-01-01T00:00:00Z`–`2026-09-18T00:00:00Z`;
- liczba wierszy: 4174, po 2087 na instrument;
- strony API: 1;
- wiersze z `volume=0`: 0;
- hash CSV SHA-256: `5012CA5FA52653633438853CEBEC8AE98C6DA5253B7C987A836E475FFE42CEFF`;
- hash kanonicznej odpowiedzi API SHA-256:
  `D32278B738176C3CE44721F2A3ACA71D05D2EE7F15520A28095AB87CF61AC91A`;
- rekord: `DATA-1e44487b0074425f959c2758c497c046`;
- wynik kontroli: `unknown_cost_model`.

Plik CSV i metadane znajdują się w `.runtime/data/`, który jest ignorowany przez Git.
Metadane nie zawierają klucza ani sekretu Alpaca.

## Zabezpieczenia adaptera

- klucze są czytane z jawnie wskazanego, ignorowanego pliku `.env`;
- sekret nie występuje w `repr`, wyniku CLI ani metadanych;
- poświadczenia mogą być wysłane tylko do `https://data.alpaca.markets/v1beta3`;
- przekierowania HTTP są blokowane, aby nagłówki nie trafiły do innej domeny;
- obsługiwane jest stronicowanie `next_page_token` i wykrywanie powtórzonego tokenu;
- duplikaty świec, brak żądanego symbolu i niespójne OHLC blokują snapshot;
- bieżąca, potencjalnie niezamknięta świeca `1Day` blokuje snapshot;
- zapis CSV i metadanych jest atomowy.

Pierwsze pobranie obejmujące `2026-09-19T00:00:00Z` zostało świadomie odrzucone z procesu
badawczego jako potencjalnie niezamknięte. Następnie pobrano zamknięty zakres od 2023 r.,
a na końcu szerszy zakres z początkiem żądanym w 2015 r. Alpaca zwróciła wspólną historię
obu instrumentów od 2021 r.; to szerszy snapshot i jego rekord są aktualnym kandydatem DATA.

## Dlaczego DATA pozostaje zablokowane

Sam poprawny OHLCV nie definiuje kosztów wykonania. Przed zamrożeniem EXP Karol musi
zatwierdzić konserwatywny model obejmujący co najmniej fee, spread i slippage. Trzeba także
zaakceptować użycie danych wyłącznie do prywatnego, lokalnego badania; prawa do
redystrybucji nie zostały potwierdzone.

Alpaca informuje, że przy braku transakcji świeca krypto może wykorzystywać midpoint
kwotowań i mieć wolumen zero. W tym snapshocie nie stwierdzono wierszy z zerowym wolumenem,
ale ograniczenie pozostaje częścią proweniencji.

## Odtworzenie odczytu

```powershell
$env:PYTHONPATH='src'
python -m astraljet.cli --state-dir .runtime/state data fetch-alpaca `
  --env-file .env `
  --output .runtime/data/alpaca_crypto_us_full_2015-01-01_2026-09-19.csv `
  --start 2015-01-01T00:00:00Z `
  --end 2026-09-18T23:59:59Z `
  --symbols BTC/USD,ETH/USD `
  --timeframe 1Day `
  --location us `
  --limit 10000
```

Źródła:

- https://docs.alpaca.markets/us/reference/cryptobars-1
- https://docs.alpaca.markets/us/docs/historical-crypto-data-1
