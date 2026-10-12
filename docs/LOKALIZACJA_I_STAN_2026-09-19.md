# DEC-15 — główna lokalizacja AstralJet

Status: **zatwierdzone przez Karola w rozmowie 19.09.2026**.

- Budowa całego systemu: `D:\Astra Jet`.
- Repozytorium: `https://github.com/AurumetaclubDAO/astraljet`.
- Dokumentacja: `docs/architektura/START.md`.
- Notion pozostaje miejscem rozmowy o projekcie i przeglądania dokumentacji.

## Co wykonano

Skopiowano kompletną paczkę dokumentacji v0.2 z zachowanymi dokumentami v0.1, bez zmiany ich bajtowej treści. Dla wszystkich 28 załączników ustalono lokalizację na dysku D: istniejące pliki wykorzystano po porównaniu SHA-256, brakujące skopiowano do `materials/inbox`. Oryginałów oraz zastanych folderów nie usuwano i nie przemianowywano. Dokładny duplikat SRC-025 wskazuje ten sam materiał co SRC-020, jeśli dostępna jest jedna identyczna kopia.

Katalog zawiera również dodatkowe, wcześniej nieopracowane DOCX, PDF i grafiki. Ich obecność nie oznacza przeczytania ani uwzględnienia treści w v0.2; nie rozszerzamy deklaracji audytu na te pliki.

## Granice obecnego zapisu

Lokalny Git został przygotowany z `origin` wskazującym docelowy adres i z gałęzią `main` bez własnych commitów. Nie jest to jeszcze sklonowane repozytorium. GitHub w Chrome potwierdza prywatne repo, początkowy commit `8419bc52b1192eae7d65661a8891a1e858a22667`, README i .gitignore. Próby odczytu przez połączenie GitHub oraz lokalny Git zwróciły brak dostępu; GitHub CLI nie jest zalogowane. Nie przesłano plików do repozytorium.

Nie zmieniano kodu dotychczasowej Astry, parametrów, danych runtime ani procesów. Dotychczasowy kod w `C:\Users\karol\Documents\Claude\Projects\Trading\astra_site` nie został jeszcze przeniesiony. Właściwa migracja zachowa jego historię i ustali granice pomiędzy repozytorium rozwojowym, lokalnymi danymi a katalogiem uruchomieniowym.

## Następny krok techniczny

Udostępnić `AurumetaclubDAO/astraljet` połączeniu GitHub w Codex lub zalogować lokalny Git na konto z dostępem. Następnie pobrać istniejące `main`, sprawdzić kolizje i reguły ignorowania plików, a dokumentację dołączyć do istniejącej historii. Nie wykonywać force push ani publikować surowych materiałów automatycznie. Ważne decyzje dotyczące migracji działającej Astry omawiamy z Karolem.
