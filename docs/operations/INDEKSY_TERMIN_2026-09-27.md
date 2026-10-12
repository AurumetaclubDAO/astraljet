# Przedłużenie turnusu indeksowego — 27.09.2026

Dyspozycja Karola: zakończyć istniejący turnus indeksowy **02.10.2026 o 23:00,
Europe/Warsaw**. Odpowiada to `2026-10-02T21:00:00Z` (UTC+02:00).

- Runda: `8490d396-047e-4c18-8b73-265e33ab8330`, `ALL_INDICES`, VantageMarkets-Demo.
- Start zachowany: `2026-09-14T10:04:55.122267Z`.
- Poprzedni koniec: `2026-09-28T10:04:55.122267Z`.
- Jedyna zmiana pola stanu: `endsAt`.
- Bez resetu ksiąg, wyników, transakcji, parametrów ryzyka lub procesów.
- Krypto: runda `3265dcb2-5bea-4ab7-b966-317094f60bbe`; koniec
  `2026-10-07T20:10:06.210114Z` pozostaje bez zmian.

## Wykonanie i weryfikacja

Łącznik nie udostępnia funkcji zmiany terminu. Wykonano kontrolowaną transakcję
w istniejącej lokalnej SQLite, po świeżym potwierdzeniu rachunku DEMO i ID rundy.
Przed każdą zmianą wykonano spójną kopię SQLite. Parametry strategii i księgi
zostały zachowane; zmiana oraz zgoda Karola zapisana w dzienniku.

Pierwszy zapis o 21:12:27 UTC został nadpisany starszym snapshotem trwającego
cyklu. Weryfikacja wykryła to przed ogłoszeniem powodzenia. Powtórny zapis
o 21:15:31 UTC zabezpieczono dwoma tymczasowymi triggerami: dotyczą wyłącznie
tej rundy DEMO i odtworzenia dokładnie poprzedniej daty końca. Wszystkie inne
pola aktualizuje nadal istniejący wykonawca. Triggery usunięto po potwierdzeniu
kolejnych świeżych cykli; końcowa kontrola wykazała zero tych triggerów.

Odczyty wykonawcy o 21:16:11 i 21:17:35 UTC potwierdzają nową datę, `RUNNING`,
brak błędu i `executionEnabled=true`. Zabezpieczenie zdjęto przy potwierdzonym
odczycie 21:17:54 UTC. Kolejny zapis o 21:20:57 UTC nadal zawiera prawidłową
datę po usunięciu ochrony; reguły i start zgodne z kopią sprzed zmiany.

Panel po odświeżeniu pokazuje brak aktualnego odczytu; nie potwierdzono w nim
nowej daty. To ograniczenie odbioru UI, nie cofnięcie potwierdzonej zmiany
w rzeczywistym wykonawcy. Nie publikowano zmian frontendu w tym zadaniu.

Kopie poza repozytorium:

- `C:\Users\karol\AppData\Local\AstraMT5\recovery\index_deadline_20260927_before.sqlite3`
- `C:\Users\karol\AppData\Local\AstraMT5\recovery\index_deadline_20260927_before_guard.sqlite3`

Test narzędzia utrzymaniowego: jedna grupa z sześcioma scenariuszami,
w tym odmowa LIVE, obcego ID, zakończonego turnusu, innego zakresu i innej daty.
Sprawdzono kopię, niezmienność innych pól, wpis dziennika, ochronę przed
starszym snapshotem oraz usunięcie ochrony po potwierdzeniu.

Nie wysyłano ręcznych zleceń ani nie restartowano MT5/łącznika. Zmiana terminu
przedłuża działanie już aktywnego automatu DEMO na dotychczasowych warunkach.
