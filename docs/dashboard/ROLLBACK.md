# Zatrzymanie i wycofanie dashboardu

1. Uruchom `D:\Astra Jet\stop_dashboard.bat`. Skrypt sprawdza tożsamość zapisanego procesu. Nie używaj zbiorczego zatrzymywania Pythona lub terminala MT5.
2. Potwierdź brak nasłuchu 8877. Jeżeli należy już do innego procesu, nie zatrzymuj go.
3. Zachowaj `docs/dashboard` i ewentualne lokalne logi `.runtime/dashboard`, jeśli potrzebny jest dalszy audyt.
4. Aby wycofać kod, odłącz tylko dodane pliki: `src/astraljet/dashboard`, `tests/dashboard`, `dashboard_config.toml`, `requirements-dashboard.in`, `requirements-dashboard.lock`, `start_dashboard.bat`, `stop_dashboard.bat`, `scripts/dashboard_start.ps1`, `scripts/dashboard_stop.ps1`, `scripts/dashboard_browser_check.py`, `scripts/dashboard_regression.py`.
5. Izolowane środowisko `.runtime/dashboard-venv` i zasoby `.runtime/dashboard` można usunąć po upewnieniu się, że nie działa dashboard i nie są potrzebne jego dowody. Przed usunięciem zweryfikować pełne ścieżki wewnątrz `D:\Astra Jet`.

Nie cofaj całego katalogu z backupu na działający projekt. Backup `D:\Astra Jet_backup_20261013-1820` ma potwierdzoną zgodność nazw i rozmiarów sprzed prac; nie obejmuje `.runtime` i nie jest potwierdzeniem spójności aktywnych baz. Dashboard nie migruje baz, więc wyłączenie nowego modułu nie wymaga odtwarzania baz.

Nie zmieniaj `.env`, `EXECUTE_ORDERS`, portu 8876, starego UI, TQ-Common, runnerów, zadań Harmonogramu ani pliku KILL_SWITCH. Kod i konfiguracja tych elementów nie zostały zmienione przez implementację dashboardu. Raport Notion jest dokumentacją, a nie sterowaniem runtime.
