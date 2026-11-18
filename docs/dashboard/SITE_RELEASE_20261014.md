# Obserwatorium AstralJet na witrynie — 14.10.2026

Nowy panel jest dostępny pod `/observatory` na istniejącej prywatnej witrynie. Strona główna i `/command` zawierają odnośnik. Dotychczasowe moduły pozostają dostępne.

## Dane i dostęp

Sites zachowuje dostęp wyłącznie właściciela. Przeglądarka odczytuje `/api/observatory/summary`; komputer wysyła ograniczony snapshot do `/api/observatory/ingest` przez HTTPS co 45 sekund. Wysyłka wymaga dostępu serwisowego Sites i osobnego sekretu publikatora `ASTRA_OBSERVATORY_PUBLISHER`. Lokalnie poświadczenia są szyfrowane Windows DPAPI dla bieżącego użytkownika, poza repo. Nie są zapisywane w frontendzie, konfiguracji hostingu ani logach.

W R2 zapisujemy jeden najnowszy snapshot i czas odbioru. Nie przesyłamy plików terminala, surowych logów ani kluczy brokera. Ścieżki lokalne są skracane. Konto ograniczone do istniejącego VantageMarkets-Demo. Nie ma endpointu składającego zlecenia ani sterującego botami. Ingest stosuje limit 200 kB, walidację DTO, kontrolę czasu, odrzucanie sekretów oraz warunkowy zapis zapobiegający nadpisaniu przez starszą/równoległą publikację.

Gdy komputer jest wyłączony lub publikator zatrzymany, witryna pokazuje ostatni snapshot z jego rzeczywistym czasem. Po 120 sekundach pojawia się ostrzeżenie braku świeżego odczytu; poszczególne wartości tracą potwierdzenie według własnego TTL. Odświeżenie strony nie odświeża pomiaru.

## Uruchamianie i odwrócenie

Publikator: `D:\Astra Jet\scripts\dashboard_site_start.ps1`. Źródło: lokalny dashboard na 8877. Skrypt nie uruchamia terminala ani handlu. Wysyłka działa w tle na koncie Windows Karola. Stan: `.runtime/dashboard/publisher-status.json`; poświadczenia: `.runtime/dashboard/site-connection.dpapi`. Pliku poświadczeń nie należy kopiować ani publikować.

Wycofanie witryny: opublikować ponownie wcześniejszą wersję 65, zachowując odbiorców. Nowy klucz R2 jest osobny i nie zmienia wcześniejszych danych. Zatrzymanie publikatora nie zatrzymuje botów. Zmiana widoczności witryny na publiczną wymaga wcześniejszego dodania autoryzacji aplikacyjnej do odczytu Obserwatorium — endpoint polega na prywatnej granicy Sites.

## Sprawdzenia przed publikacją

324 testy witryny PASS, w tym 9 nowych testów kontraktu; TypeScript PASS. Cztery testy lokalnego publikatora PASS, w tym DPAPI. Rzeczywisty snapshot lokalnego dashboardu przeszedł schemat chmury. Odbiór po publikacji obejmuje odczyt tego samego identyfikatora snapshotu, blokadę dostępu anonimowego i widok przeglądarkowy.

## Wynik publikacji

- Adres: https://tradebot-astra-pro.solyg.chatgpt.site/observatory
- Wersja Sites: 66, status succeeded, 14.10.2026 08:10 Warszawa.
- Commit: 19f97ba35c6fff8627b9cc708806697e19e65fe7.
- Publikacja: appgdep_6acf1cc9a694819183ad024f9f692c75.
- Odbiór: zgodny snapshot po zapisie i odczycie; anonimowy GET 403; POST bez sekretu publikatora 401. Widok zalogowanego Chrome potwierdzony.
- Publikator działa i otrzymał kolejne ACK. Autostart przy logowaniu: AstralJet-Observatory-Publisher (tylko bieżący użytkownik, bez podniesienia uprawnień). Nie sprawdzano restartu całego Windows.
- Ręczny start/stop: scripts/dashboard_site_start.ps1 i scripts/dashboard_site_stop.ps1. Zatrzymanie procesu nie wyłącza autostartu; do trwałego wyłączenia publikowania należy wyłączyć wskazane zadanie.
- Źródła witryny: .runtime/dashboard-site-20261014, zsynchronizowane z repo Sites. Główny lokalny rdzeń D:\Astra Jet nie był commitowany ani wysyłany.
- Materiały dowodowe: TEST_SITE_20261014.txt, BUILD_SITE_20261014.txt, SITE_ACCEPTANCE_20261014.json.
- Zewnętrzny przegląd Claude z pierwotnego briefu pozostaje niepotwierdzony.
