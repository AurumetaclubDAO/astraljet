# Walidacja

W katalogu istniejącej witryny, Node >=22.13:

```powershell
node --experimental-strip-types --test tests/*.test.mjs
npx tsc --noEmit
npm run build
```

Testy używają atrap transportu; bez kluczy i płatnych wywołań. Oczekiwane: ponad 25/20
USD AI i 5 USD X nie blokuje nowego zadania; niepewność zostaje, powtórzenie partii X
nie wysyła drugiego żądania. Kontrolne sumy z SQLite zgodne z odczytem budżetu.

Po prywatnej publikacji: odczytać Command Center, czat/budżet i X bez uruchamiania analizy.
Oczekiwane spendingMode=unlimited, limit=null, remaining=null i tekst „bez pułapu”.
Stare blocked mogą pozostać: nie wszystkie historyczne przyczyny były kwotowe.
