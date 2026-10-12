# Weryfikacja — 003-rejestr-sync

## Warunki

- Użyj tymczasowej SQLite i lokalnej D1/in-memory suite; nie wskazuj aktywnego runtime ani MT5.
- Użyj testowego urządzenia tylko ze scopem `registry:sync` i testowego klucza podpisu.

## Scenariusze odbiorowe

1. Utwórz wersjonowany rekord oraz relację w testowym rejestrze, zbuduj batch i prześlij go. Potwierdź, że status odczytowy pokazuje właściciela, registry, hash, wersję, receipt i świeżość.
2. Prześlij identyczny batch 10 razy. Potwierdź jeden zestaw elementów i stabilne ACK.
3. Prześlij ten sam `batch_id` z innym hashem oraz element o tej samej tożsamości i innym hashu. Potwierdź `409` i brak modyfikacji.
4. Sprawdź odrzucenie nieznanego pola, payloadu, sekretu, brakującego hashu, niepoprawnego podpisu, starego czasu i powtórzonego nonce.
5. Zasymuluj timeout po wysłaniu; ponów ten sam batch nowym nonce. Potwierdź odbiór bez duplikatu i przesunięcie cursora dopiero po ACK.
6. Przeskanuj request, receipts i UI: brak tokenów, pełnych baz, ścieżek, brokerów, poleceń i `execution_authorized=true`. Potwierdź brak wywołań jobów/MT5/DEMO/LIVE.

## Dowody

Zachowaj wyniki testów jednostkowych, integracyjnych i kontraktowych oraz zanonimizowany receipt. Nie publikuj tokenu, podpisu, body synchronizacji ani eksportu SQLite.

## Odbiór produkcyjny

24.09.2026 zakończono P001–P004 na osobnym rejestrze `quickstart-2026-09-19`: backup i zachowana historia SQLite, 7 wersji / 6 relacji, sprawdzony ACK i odczyt przez właściciela w panelu. Nie włączono harmonogramu. Polecenia obsługi: [RUNBOOK](../../docs/operations/RUNBOOK.md#podpisana-kopia-metadanych-w-d1--etap-13). Pełne dowody: [Etap 13](../../docs/operations/ETAP_13_2026-09-24.md).
