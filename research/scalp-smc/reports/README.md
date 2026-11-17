# Scalp-SMC: badanie, runda 1 (14.11.2026, Europe/Warsaw)
To jest BADANIE, nie dowód skuteczności. Konto MT5 LIVE (numer w dokumentacji prywatnej) było używane tylko do odczytu: symbols_get, symbol_info, symbol_info_tick, copy_rates_range, copy_ticks_range. Żadnych zleceń, zmian SL/TP ani logowania.

## Lokalizacja
E:\Astra Jet\research\scalp-smc\ — folder D:\Astra Jet nie istnieje, Astra Jet jest na E:.
- scripts\collect_mt5.py: kolektor przyrostowy (tiki per dzień, M1 per miesiąc), raport w reports\data_inventory.json
- scripts\srvtime.py: czas serwera na UTC (UTC+2 zimą, UTC+3 w czasie DST w USA; ZAŁOŻENIE)
- scripts\smc_features.py: detektory SMC na M1 bez lookahead
- scripts\build_dataset.py: cechy tickowe, etykiety triple-barrier, features\*.parquet
- scripts\train_wf.py: walk-forward na XGBoost GPU, wyniki w reports\wf_results.json
- scripts\ollama_describe.py: opis po polsku z lokalnego modelu (nie służy do predykcji), wynik w reports\ollama_opis.md
- .venv: osobne środowisko. Parquet zapisuje fastparquet, bo Smart App Control blokuje pyarrow._fs.

## Uruchamianie (PowerShell)
cd "E:\Astra Jet\research\scalp-smc"
.\.venv\Scripts\python.exe scripts\collect_mt5.py --symbols "ETHUSD,XAUUSD+" --days 120
.\.venv\Scripts\python.exe scripts\build_dataset.py --tick-days 30
.\.venv\Scripts\python.exe scripts\train_wf.py --folds 4 --device cuda

## Propozycja harmonogramu (NIE jest ustawiony)
Kolektor uruchamiany codziennie o 23:30 Europe/Warsaw w Harmonogramie zadań Windows, jako użytkownik karol, tylko gdy terminal działa. Przebieg przyrostowy trwa ok. 10 s. Dodatkowo w sobotę o 09:00 jako dobicie tygodnia.
Terminal trzyma tiki XAUUSD+ tylko z ok. 8 dni, więc bez codziennego zbierania ta historia przepada.
