# Command Center AstralJet — publikacja 20.09.2026

## Wynik

Główny panel istniejącej Astry opublikowany przez Sites, bez tworzenia nowego projektu. Adres: https://tradebot-astra-pro.solyg.chatgpt.site/command. Strona główna bez `view` otwiera ten sam panel; dotychczasowe adresy `/?view=...` zachowują swoje moduły.

- Wersja Sites: **50**.
- Projekt: `appgprj_6aa11e91b0a481918f829269eea5b400`.
- Zapisana wersja: `appgprj_6aa11e91b0a481918f829269eea5b400~appgver_f62a3392d37481918fb605c0f3c0eaf7`.
- Udana publikacja: `appgdep_6aaf2c9b3700819183540387f6357ba2`, status **succeeded**, 20.09.2026 00:45:39 UTC.
- Źródło: `53c97d1f0c62ccc4779d872ca3d3dd200b4523a2`, zwykły commit i push istniejącej historii do repo źródłowego Sites, bez force push. Nie jest to push do GitHub AurumetaclubDAO/astraljet.
- Dostęp sprawdzony po publikacji: nadal wyłącznie właściciel, bez grup, dodatkowych edytorów i gości. Nie zmieniano poświadczeń ani ustawień dostępu.

## Zrobione

- Ciemny panel operacyjny: pięć liczników rejestru, przebieg procesu, kolejka, Decision Inbox, blokady, ostatnie zmiany, granice połączeń i datowana informacja o etapie 05.
- Pełna nawigacja 14 obszarów, wyszukiwarka modułów, mobilny panel nawigacyjny. Istniejące laboratorium, strategie i materiały pozostają pod dotychczasowymi adresami.
- Odczyt `GET /api/astra/command` z `astra_discovery` i `astra_jobs`: filtrowanie właściciela z sesji, wyłącznie SELECT, walidacja odpowiedzi, brak surowych payloadów i sekretów. Pełne liczniki, szczegóły maks. 12 rekordów każdej sekcji.
- Brak danych, błąd, brak logowania i nieaktualna migawka mają osobne stany. Błąd nie jest zerowym wynikiem. Zapis running nie jest potwierdzeniem działającego workera; wygasły lease otrzymuje ostrzeżenie.
- Podłączono odczytowy widok pochodzenia z etapu 02. Import lokalnego snapshotu pozostaje wyłącznie w pamięci przeglądarki, bez scalenia rejestrów i bez uploadu.
- Role AJ-00–AJ-18 oznaczone jako odpowiedzialności, nie uruchomione procesy. Funkcje bez telemetrii i danych nie mają atrap wykresów, pozycji, wyników lub aktywnych przycisków.

## Sprawdzenie

- **33/33** testy JS/TS: panel, API, renderowanie, izolacja właściciela, inbox, brak danych, limity widoku, nawigacja i pochodzenie.
- TypeScript całej aplikacji; lint plików panelu bez błędów.
- Czysty checkout publikowanego commita: powtórzenie 33 testów, TypeScript i poprawna kompilacja produkcyjna.
- Przeglądarka lokalna: desktop, 390 px, mobilna nawigacja do Risk Center i nieaktywny kill switch. Bez dodawania przykładowych rekordów do baz.
- Rdzeń Python ponownie: **115/115 testów**, 13,519 s; wyłącznie testy mechaniki, nie dowód rentowności.
- Na stronie produkcyjnej potwierdzono bramkę logowania. Pełny widok danych zalogowanego właściciela wymaga sesji Karola; nie obchodzono uwierzytelnienia ani nie generowano tokenu bypass.

## Publikacja i ograniczenia

Pierwsza próba zdalnej kompilacji (`appgdep_6aaf2beb603881918dc0721d615bc029`) zakończyła się komunikatem o niespójności package.json i lockfile. Lokalne `npm ci --dry-run` i `npm install --package-lock-only --ignore-scripts` nie potwierdziły błędu i nie zmieniły zależności. Nie przedstawiamy przyczyny błędu chmurowego jako rozpoznanej.

Lokalny helper pakowania Sites nie był dostępny w zainstalowanych plikach. Zbudowano i sprawdzono archiwum wyłącznie z `dist/client`, `dist/server` oraz `.openai/hosting.json` czystego checkoutu tego samego, już przesłanego commita. Sites zaakceptował archiwum dla wersji 50 i druga publikacja się powiodła. Bez pakowania źródeł roboczych, .env, baz lub sekretów.

Archiwum lokalne: `.runtime/command-center-53c97d1.tar`, SHA-256 `B2CCCAB5B8C21B3592A25FA4E0A5F5CE54C287EA02ECECBA7F6F6914242FBD61`.

Nie opublikowano roboczych zmian etapu 03 w `discovery`, `worker` i `discovery-store`; pozostają lokalne. Nowy panel i pochodzenie są odczytowe. Nie zmieniono działających procesów MT5, reguł, ryzyka, budżetu, kluczy, danych rynkowych ani baz Pythona. Osobny checkout w `.runtime/command-center-release-20260920` służył weryfikacji pakietu, nie jest migracją runtime.

## Dalej

Po zalogowaniu sprawdzić odczyt własnego rejestru w produkcji. Kolejny etap silnika pozostaje osobnym zadaniem: adapter wiążący model etapu 05 z konkretnym zamrożonym EXP, wersjami reguł i rzeczywistymi danymi historycznymi. Wymagane ustalenia protokołu BTC/ETH nie zostały tym panelem zatwierdzone. Zleceń DEMO nie uruchomiono.
