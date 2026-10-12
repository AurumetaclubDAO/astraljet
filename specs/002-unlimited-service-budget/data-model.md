# Model danych

Polityka: spendingMode=unlimited; limit, automaticLimit, remaining=null.
Stary kontrakt liczbowy można wyświetlić, lecz brak polityki nie jest zgodą unlimited.
Used zawiera dotychczasowe rozliczenia i rezerwacje; reserved i byStatus je rozdzielają.
Wartości księgi: nieujemne bezpieczne całkowite micro-USD, bez sztywnego pułapu biznesowego.

AI: reserved → settled / uncertain / rejected. Znany koszt ponad rezerwację jest
settled z reservationExceeded=true. Legacy overrun widoczny, ale nie blokuje nowych
wywołań; potwierdzenie idempotentne, bez ponownego naliczenia.
Uncertain: kwota plus dowód, brak nie oznacza zero.

X: jedno id partii rezerwuje tylko raz. Kwota i niepewna inna partia nie blokują nowej.
Brak migracji tabel, usuwania wpisów lub zmian właścicieli.
