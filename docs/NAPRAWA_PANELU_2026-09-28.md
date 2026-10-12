# Naprawa podglądu AstralJet — 28.09.2026

## Wynik i zakres

Wdrożono prywatne wydanie Sites **65**, potwierdzone statusem `succeeded`
28.09.2026 o 09:09 czasu Warszawy. Adres: https://tradebot-astra-pro.solyg.chatgpt.site.

Naprawa dotyczy odczytu Command Center i widoku turnusów. Nie jest wdrożeniem
całej architektury AJ-00–AJ-18 ani potwierdzeniem rentowności strategii.
Nie zmieniono reguł, kapitału, limitów ryzyka, mandatu DEMO ani uprawnień witryny.
Nie uruchamiano LIVE, nie resetowano ksiąg i nie wznawiano zablokowanych zadań AI.

## Potwierdzone przyczyny

1. Telemetria zatrzymała się po przedłużeniu turnusu indeksowego. Dwa historyczne
   zdarzenia `INDEX_DEADLINE_EXTENDED` miały pole `authorization` zawierające
   notatkę decyzji Karola. Rekurencyjna ochrona sekretów odrzucała cały pakiet
   HTTP 400. Dodano wąską zgodność dla tej konkretnej treści, rodzaju zdarzenia
   i ścieżki: notatka jest publikowana jako `decisionNote`. Inne pola
   `authorization`, hasła, tokeny i zagnieżdżone sekrety nadal są odrzucane.
   Oryginalny dziennik SQLite pozostał bez zmian. Lokalny skrypt przedłużenia
   zapisuje odtąd `decisionNote`; nie wykonano ponownie przedłużenia.
2. `/api/astra/command` zwracał 503, ponieważ dwa złożone identyfikatory zadań
   przekraczały limit 160 znaków kontraktu odczytu. Log diagnostyczny potwierdził
   `jobs.0.id` i `jobs.1.id / too_big`. Osobny limit identyfikatora wynosi teraz
   512 znaków; nazwy/statusy nadal mają dotychczasowe ograniczenia. Identyfikatory
   nie są obcinane i żadne zadanie w bazie nie zostało zmienione.
3. Licznik dni był ograniczony do 14 mimo późniejszego terminu końca.
   Teraz wylicza długość z potwierdzonego początku i końca rundy.
4. Ujednolicono formatowanie dat raportu i panelu do `Europe/Warsaw`.
   Po wdrożeniu w sprawdzonych widokach `/command` i `/contest` konsola
   przeglądarki nie pokazała wcześniejszego błędu React 418.
5. Brak świeżych danych DEMO nie jest już prezentowany jako zero aktywnych testów.

## Publikacja

- Projekt: `appgprj_6aa11e91b0a481918f829269eea5b400`.
- Checkout witryny: `D:\Astra Jet\.runtime\command-center-release-20260920`.
- Commity naprawy: `9538c6a4767d59cf0c5097006bbbffd0ab19c27d`,
  `bfbbe94407af8179bcc93dcd67a1bcd365cd211f`.
- Oba commity wysłane bez force push; zdalny HEAD potwierdzony.
- Wydanie końcowe: `appgprj_6aa11e91b0a481918f829269eea5b400~appgver_55cb1323f0788191a2937705a9e73a53`.
- Deployment: `appgdep_6aba12814ba88191af597fecabebba4e`.
- Pakiet: `D:\Astra Jet\.runtime\panel-recovery-v65-20260928.tar`.
- Pakiet zbudowano z eksportu dokładnego commita. Cztery wcześniejsze lokalne
  zmiany diagnostyki cytatów pozostawiono niewdrożone i nietknięte.
- Dostęp pozostaje prywatny, wyłącznie dla właściciela. Sekretów nie zapisano
  w repozytorium ani archiwum; poświadczenie Git przekazano tylko w pamięci.

## Weryfikacja

- **315/315 testów Node** na dokładnym kodzie wydania 65.
- `npx tsc --noEmit`: sukces; `npm run build`: sukces.
- Test skryptu przedłużenia: **1/1**.
- Testy regresji obejmują: ochronę sekretów, niezmienność oryginalnego dziennika,
  kompatybilność historycznej notatki, przedłużenie terminu, pełne złożone ID,
  zachowanie autoryzacji i odczyt bez mutacji.
- Lint zmienionych modułów poza `contest-desk.tsx` bez błędów; ten starszy
  komponent nadal ma niezależne uwagi dotyczące efektu React i nawigacji `<a>`.
  Nie raportujemy czystego lint całego repozytorium.
- Po publikacji logi produkcyjne potwierdziły HTTP 200 dla
  `GET /api/astra/command`, `GET /api/astra/discovery`,
  `GET /api/mt5/telemetry` i cyklicznych `POST /api/mt5/telemetry`.
- Przeglądarka: „Rejestr aktualny”, 24 karty strategii, świeża telemetria,
  sześć ksiąg ze statusem „Test w toku”. To różne liczniki: karty nie są botami.

## Rzeczywisty stan DEMO przy odbiorze, 09:11–09:12 Warszawa

Oba wykonawcy były uruchomione przed naprawą i pozostają uruchomione.
Nie restartowano MT5 ani workera badawczego. Zatrzymano tylko pomocniczy
serwer developerski uruchomiony do tej diagnozy.

| Turnus | Status | Księgi | Otwarte / zamknięte | Termin końca (Warszawa) |
| --- | --- | --- | --- | --- |
| Indeksy | RUNNING, executionEnabled=true | ORB15, Noise Area, ORB15 retest | 0 / 40 | 02.10.2026, 23:00 |
| Krypto | RUNNING, executionEnabled=true | Momentum M15, Trend H1, Relative Momentum | 1 / 13 | 07.10.2026, 22:10 |

Oba odczyty: `terminalAlgoTrading=true`, `unresolved=0`, `foreignPositions=0`,
`pendingOrders=0`, brak błędu, żaden book nie ma `halted` ani `dayHalted`.
UI pokazuje indeksy: dzień 14/19; krypto: dzień 5/14; oba „DEMO aktywne”.
Aktywność skanera nie oznacza obowiązku zawarcia transakcji: wykonanie nadal
wymaga aktualnego sygnału, danych i spełnienia istniejących reguł.

Dowody wizualne:

- `D:\Astra Jet\.runtime\browser-diagnostics-20260928\command-center-fixed.png`
- `D:\Astra Jet\.runtime\browser-diagnostics-20260928\turnusy-demo-fixed.png`

Stan pozycji i wyniki mogą zmienić się po tym odczycie. Pozostałe blokady badań
nie zostały uznane za rozwiązane przez samą naprawę panelu.
