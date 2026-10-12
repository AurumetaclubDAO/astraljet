# Kontrakt

Istniejące odczyty budżetu i uwierzytelnienie pozostają. Dodane spendingMode=unlimited,
limit/remaining=null, a dla AI automaticLimit=null. UI sprawdza tryb, nie porównuje null
z kwotą i nie pokazuje procentowego zużycia nieistniejącego pułapu.

AI blocked=false dla legacy overrun. Błędny usage pozostaje uncertain. Nie wolno przyjąć
odpowiedzi jako poprawnie rozliczonej, gdy nie udało się zapisać kosztu.
Rozliczenie ręczne owner-scoped, finite safe integer >=0, z dowodem dla uncertain.

X: INSERT OR IGNORE dla id; ograniczenia adresu, zasobów i rozmiaru nadal aktywne.
Brak auto-doładowania, automatycznych ponowień błędów i zmiany publiczności publikacji.
