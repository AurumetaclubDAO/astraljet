# Weryfikacja istniejącego backupu — 13.10.2026

Status: **PASS w zakresie nazw plików, liczby i rozmiarów**.

Odczyt: 2026-10-13 19:03:55 Europe/Warsaw, host `Solyg`, Python 3.12, przed dodaniem dokumentacji dashboardu.

| Parametr | Oryginał | Backup |
|---|---:|---:|
| Katalog | `D:\Astra Jet` | `D:\Astra Jet_backup_20261013-1820` |
| Liczba plików | 1192 | 1192 |
| Suma rozmiarów, bajty | 38 908 833 | 38 908 833 |
| Błędy odczytu metadanych | 0 | 0 |

Wyłączono katalogi o nazwach `.venv`, `.runtime`, `__pycache__` na każdym poziomie. Nie podążano za dowiązaniami symbolicznymi katalogów. Inne katalogi, w tym `.git`, nie były celowo wyłączane.

Porównano również względne ścieżki i rozmiar każdego pliku: brak plików tylko po jednej stronie; brak rozbieżności rozmiarów. Nie odczytywano treści `.env` ani innych plików z sekretami. Nie tworzono kolejnej kopii i nie modyfikowano istniejącego backupu.

Metoda: `os.walk`, `Path.stat().st_size`, zbiory względnych ścieżek i porównanie rozmiarów. Odczyt nie wykonywał kodu aplikacji.

## Granice wyniku

Zgodność metadanych spełnia kontrolę wymaganą w P0. Nie jest porównaniem hashy zawartości, testem odtworzenia ani dowodem spójności aktywnych baz. Wyłączony `.runtime` nie jest objęty tym wynikiem. Późniejsze pliki w `docs/dashboard/` stanowią przyrost po tej kontroli; nie powinny być oczekiwane w wcześniejszym backupie.
