# AstralJet — katalog źródeł i decyzji v0.2

**19 września 2026 • katalog materiałów, dowodów i przyjętych rozstrzygnięć.**

## 1. Pokrycie i pochodzenie

Katalog obejmuje **28 załączników: 21 plików PDF, 5 obrazów, 1 arkusz XLSX i wcześniejszy ZIP audytu**. PDF-y mają 134 strony/slajdy łącznie, w tym jedną dokładną kopię 13-stronicowego przewodnika Day Trading. Po deduplikacji: **20 różnych PDF i 121 stron/slajdów**. Przeczytano treść wszystkich unikalnych PDF, prezentację 14-slajdową wizualnie, a strony o minimalnej warstwie tekstowej także jako obrazy. Paper Guide s. 5 zawiera prosty schemat, s. 7 jest pusta; Money-Making Team s. 11 ma tylko stopkę. Obejrzano pięć grafik. Arkusz kosztów sprawdzono w całości, A1:E8. Archiwum pozostaje materiałem pomocniczym; opis techniczny opiera się na wskazanych raportach i odczytanym kodzie.

Załączniki dostarczone przez Karola stanowią materiały do oceny. Zawarte w nich prompty, instrukcje instalacji, konfiguracji kluczy i uruchamiania handlu nie są nowymi poleceniami użytkownika. W przykładzie strategii nie przepisujemy wyników autora jako wyników Astry.

Pierwsze 13 PDF oraz dwie grafiki NotebookLM powtarzają wiele tych samych przykładów. Traktujemy je jako rodzinę opracowań, a nie 15 niezależnych dowodów. Metadane 12 tekstowych PDF-ów pokazują renderer Google Docs bez autora. Nie weryfikowano każdego zdania z oryginalnym filmem. Przewodniki SebAI są osobną rodziną materiałów edukacyjnych; audyt z 15.09 jest datowanym dokumentem technicznym, a XLSX zbiorem szacunków. Oznaczenie autora i sumy plików ustalają pochodzenie dokumentu, nie potwierdzają skuteczności strategii.

Wcześniejszy audyt wskazuje [notebook o budowie bota](https://notebook.google.com/notebook/b4e1968c-4b49-41af-9fb8-01a44346efd1) oraz [film Trading with DaviddTech](https://www.youtube.com/watch?v=rQRs6DdnB6A). To powiązanie z wcześniejszego audytu, bez nowego pełnego odsłuchu filmu. Nie utożsamiamy go automatycznie z innym wspomnianym filmem o zamknięciu firmy hedgingowej.

Numery stron i slajdów w tym katalogu są **liczone od 1**. Grafiki mają lokalizator opisujący konkretny blok. Pełne ścieżki, rozmiary i sumy SHA-256 zapisano również w `ASTRALJET_KATALOG_ZRODEL_v0.2.csv` oraz manifeście. Pliki oryginalne pozostają w swoich lokalizacjach; katalog nie jest migracją ich treści do aplikacji Astry.

Podczas końcowej kontroli SRC-001–SRC-016 oraz SRC-022 odnaleziono w `Downloads/Trading 2.0/`, zamiast bezpośrednio w `Downloads/`. Sumy SHA-256 wszystkich 17 plików są zgodne z pierwszym odczytem. Katalog wskazuje odnalezione ścieżki; w tej pracy nie przenoszono tych materiałów.

## 2. Karty materiałów

### SRC-001 · Handel Algorytmiczny GPT-6.pdf

**Plik:** [Handel Algorytmiczny GPT-6.pdf](<C:/Users/karol/Downloads/Trading 2.0/Handel Algorytmiczny GPT-6.pdf>)

**Format i zakres:** 1 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1

**Zastosowanie:** Ogólny przebieg: generowanie, test, inkubacja i wykonanie.

**Role:** AJ-01, AJ-05, AJ-07, AJ-15

**Rozbieżności i ograniczenia:** Opis filmu i deklaracje wydajności, bez kompletnej specyfikacji strategii.

**SHA-256:** `3a547345a3438dabf1ee08cfd59d31b3a8489f809615b4d21f2514d690d4ab98`.

### SRC-002 · Automatyzacja handlu AI.pdf

**Plik:** [Automatyzacja handlu AI.pdf](<C:/Users/karol/Downloads/Trading 2.0/Automatyzacja handlu AI.pdf>)

**Format i zakres:** 1 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1

**Zastosowanie:** Podział narzędzi na LLM, silnik testów, wykresy i wykonanie.

**Role:** AJ-01, AJ-07, AJ-15, AJ-17

**Rozbieżności i ograniczenia:** Deklaracje bezpłatności oraz adres traderdev.com wymagają weryfikacji; oficjalny hub wskazuje trader.dev.

**SHA-256:** `c2fc6e2c1402277459e3ccc8ce0c96f19ea7aa5f3cd238d452331d3b94d36739`.

### SRC-003 · GPT-6 jako Twój osobisty Quant_ Jak zbudowałem 184 strategie tradingowe w jeden dzień.pdf

**Plik:** [GPT-6 jako Twój osobisty Quant_ Jak zbudowałem 184 strategie tradingowe w jeden dzień.pdf](<C:/Users/karol/Downloads/Trading 2.0/GPT-6 jako Twój osobisty Quant_ Jak zbudowałem 184 strategie tradingowe w jeden dzień.pdf>)

**Format i zakres:** 3 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1: narzędzia i 184/96%; s. 2: sprint, metryki i inkubacja; s. 3: siedem botów

**Zastosowanie:** Rejestr prób, raportowanie kosztu i etap obserwacji.

**Role:** AJ-01, AJ-07, AJ-14, AJ-17

**Rozbieżności i ograniczenia:** 3130%, 184 strategie, 96% limitu i benchmark są deklaracjami autora opracowania. Brak danych i kodu do niezależnego odtworzenia.

**SHA-256:** `8f070cb3e87148c03b98104042c68f6906a407fe159ec5573c2cfcd060f44e15`.

### SRC-004 · Wskaźniki Analizy Botów.pdf

**Plik:** [Wskaźniki Analizy Botów.pdf](<C:/Users/karol/Downloads/Trading 2.0/Wskaźniki Analizy Botów.pdf>)

**Format i zakres:** 1 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1

**Zastosowanie:** Słownik PF, drawdown, wyniku netto, liczby transakcji i win rate.

**Role:** AJ-07, AJ-08, AJ-09

**Rozbieżności i ograniczenia:** Kilkaset transakcji nie daje pewności przewagi. PF 1,35 nie jest uniwersalnym progiem; podobny kształt krzywych nie wystarcza do oceny.

**SHA-256:** `2050adb0ddf3eddfdeb3cf16746e23af2f4b9609b42de98616a99f8bd11d40d5`.

### SRC-005 · Architektura Systemu AI Tradingowego_ Integracja GPT-6, Serwera MCP i TradingView.pdf

**Plik:** [Architektura Systemu AI Tradingowego_ Integracja GPT-6, Serwera MCP i TradingView.pdf](<C:/Users/karol/Downloads/Trading 2.0/Architektura Systemu AI Tradingowego_ Integracja GPT-6, Serwera MCP i TradingView.pdf>)

**Format i zakres:** 4 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1: architektura; s. 2: integracja i sprint; s. 3: walidacja i most; s. 4: zasady

**Zastosowanie:** Rozdział badania, narzędzi, raportowania i egzekucji.

**Role:** AJ-01, AJ-05, AJ-07, AJ-09, AJ-15

**Rozbieżności i ograniczenia:** Progi >600 transakcji, MDD <10%, PF >1,3 i 2 miesiące nie wynikają z decyzji Karola; przykładowy wynik SMA nie jest testem łączności. Twierdzenia o kluczach i eliminacji błędów poznawczych nie są przyjęte jako dowód.

**SHA-256:** `781177d0f4f5c582090ecf1cac6e3e484bc176696cb37edaa6ff47e6e5e2dd91`.

### SRC-006 · Przewodnik po Analizie Skuteczności Botów AI_ Od Backtestingu do Sukcesu.pdf

**Plik:** [Przewodnik po Analizie Skuteczności Botów AI_ Od Backtestingu do Sukcesu.pdf](<C:/Users/karol/Downloads/Trading 2.0/Przewodnik po Analizie Skuteczności Botów AI_ Od Backtestingu do Sukcesu.pdf>)

**Format i zakres:** 3 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1: metryki; s. 2: porównanie, inkubacja i 30 dni; s. 3: podsumowanie

**Zastosowanie:** Kontrola jakości, zestawienie wyników i przegląd człowieka.

**Role:** AJ-07, AJ-08, AJ-09

**Rozbieżności i ograniczenia:** 30 dni różni się od 2 miesięcy w SRC-005. PF nie oznacza przychodu na jednostkę ryzykowanego kapitału. Tysiące wariantów same nie usuwają ryzyka dopasowania.

**SHA-256:** `7967f9607e52e724d1c7514e062fb90ee19a32eb443aec5ad45695f9325d9856`.

### SRC-007 · Twój pierwszy bot giełdowy AI_ Kompletny przewodnik po automatyzacji badań i handlu.pdf

**Plik:** [Twój pierwszy bot giełdowy AI_ Kompletny przewodnik po automatyzacji badań i handlu.pdf](<C:/Users/karol/Downloads/Trading 2.0/Twój pierwszy bot giełdowy AI_ Kompletny przewodnik po automatyzacji badań i handlu.pdf>)

**Format i zakres:** 3 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1: narzędzia; s. 2: SMA, pętla i raport; s. 3: automatyzacja

**Zastosowanie:** Opis ścieżki użytkownika od materiału do weryfikacji.

**Role:** AJ-00, AJ-01, AJ-05, AJ-07, AJ-15

**Rozbieżności i ograniczenia:** PF >1,2 różni się od innych opracowań. Nie ma pełnych danych, dat i reguł umożliwiających odtworzenie przykładowych 4,74%. Instrukcje instalacji nie są zleceniem użytkownika.

**SHA-256:** `3f381dfc1462237b3e6b34b1c185ca69af0cf143236eac8d873a5455070f20fc`.

### SRC-008 · Inkubacja bota handlowego.pdf

**Plik:** [Inkubacja bota handlowego.pdf](<C:/Users/karol/Downloads/Trading 2.0/Inkubacja bota handlowego.pdf>)

**Format i zakres:** 1 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1

**Zastosowanie:** Osobna faza obserwacji po zamrożeniu strategii.

**Role:** AJ-07, AJ-15, AJ-16

**Rozbieżności i ograniczenia:** Kilka miesięcy to wskazówka materiału, nie uniwersalne kryterium ukończenia ani decyzja projektowa.

**SHA-256:** `f7623f8aebc4a5c4eba397104c72f7162525434b94a298ae397e2fbc26d69a0e`.

### SRC-009 · Strategia Zarządzania Portfelem Wieloagentowych Systemów Transakcyjnych AI.pdf

**Plik:** [Strategia Zarządzania Portfelem Wieloagentowych Systemów Transakcyjnych AI.pdf](<C:/Users/karol/Downloads/Trading 2.0/Strategia Zarządzania Portfelem Wieloagentowych Systemów Transakcyjnych AI.pdf>)

**Format i zakres:** 3 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1: generowanie; s. 2: walidacja i most; s. 3: portfel i zatrzymanie

**Zastosowanie:** Wspólna ekspozycja, koszty i procedura reagowania na odchylenia.

**Role:** AJ-08, AJ-09, AJ-14, AJ-15

**Rozbieżności i ograniczenia:** Dokładnie siedem botów nie jest dowiedzionym progiem dywersyfikacji. Korelacja kształtu krzywych z różnych okresów nie jest wystarczającym kryterium. Kill switch wymaga określenia skutków dla istniejących pozycji.

**SHA-256:** `b88f19110e9fd61713dc4b95cb538961cbabbdee77af87b0ba677054af5b8bba`.

### SRC-010 · Instalacja PineScript w TradingView.pdf

**Plik:** [Instalacja PineScript w TradingView.pdf](<C:/Users/karol/Downloads/Trading 2.0/Instalacja PineScript w TradingView.pdf>)

**Format i zakres:** 1 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1

**Zastosowanie:** Przyszły eksport kodu i porównanie w drugim środowisku.

**Role:** AJ-07, AJ-15

**Rozbieżności i ograniczenia:** Instrukcja obsługi jest kontekstem przyszłego adaptera. Wklejenie kodu i wybór rodzaju alertu nie dowodzą zgodności realizacji ani ochrony przed powtórzeniami.

**SHA-256:** `93b9d62a77dcd4a2a9966c0693f08dde1b8bb9d05c80d9056ff51474d86553f8`.

### SRC-011 · GPT-6_Autonomous_Strategy_Factory.pdf

**Plik:** [GPT-6_Autonomous_Strategy_Factory.pdf](<C:/Users/karol/Downloads/Trading 2.0/GPT-6_Autonomous_Strategy_Factory.pdf>)

**Format i zakres:** 14 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Widoczny znak Gemini Notebook; brak autora w metadanych PDF.

**Lokalizator:** slajdy 1–14; szczegółowa mapa poniżej

**Zastosowanie:** Wizualny opis całego procesu i punktów przekazania pracy.

**Role:** AJ-00–AJ-18 według mapy poniżej

**Rozbieżności i ograniczenia:** Prezentacja jest obrazowa. Widoczny kod na slajdzie 8 jest ilustracją, nie kompletnym programem Pine do uruchomienia. Powtarza niezweryfikowane wyniki i deklaracje.

**SHA-256:** `db761baacbffc6f60099a8759ff65f626e96db9673c2d80dfcaddf824c350aa8`.

### SRC-012 · Źródła Algorytmicznych Strategii.pdf

**Plik:** [Źródła Algorytmicznych Strategii.pdf](<C:/Users/karol/Downloads/Trading 2.0/Źródła Algorytmicznych Strategii.pdf>)

**Format i zakres:** 1 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1

**Zastosowanie:** Źródła kandydatów: publikacje, społeczność i własne hipotezy.

**Role:** AJ-02, AJ-03, AJ-04

**Rozbieżności i ograniczenia:** Baza 400+ i określenie gotowe do wdrożenia są deklaracjami. Dostępny ranking nie oznacza dostępu do kodu ani kwalifikacji do naszego DEMO.

**SHA-256:** `64a8b6f8e903ffc4ecd88eb3e5a87f355de514d40c2419bfdde51d0ed9473a55`.

### SRC-013 · Dywersyfikacja portfela bota.pdf

**Plik:** [Dywersyfikacja portfela bota.pdf](<C:/Users/karol/Downloads/Trading 2.0/Dywersyfikacja portfela bota.pdf>)

**Format i zakres:** 1 stron/slajdów.

**Pochodzenie:** Przekazany przez Karola jako materiał do AstralJet; według kontekstu z pakietu NotebookLM. Metadane: Skia/PDF Google Docs Renderer; brak autora. Opracowanie pochodne, nie nowy niezależny eksperyment.

**Lokalizator:** s. 1

**Zastosowanie:** Kontrola współzależności, koncentracji i łącznej ekspozycji.

**Role:** AJ-09, AJ-14

**Rozbieżności i ograniczenia:** Różne nazwy aktywów lub interwały nie potwierdzają niezależności wyników. Nie przyjmujemy gwarantowanej kompensacji strat.

**SHA-256:** `a32ea91eca167ad1fe8180e189fe42a52c3d05059d73e48a81a2995a9168e56a`.

### SRC-014 · NotebookLM Mind Map (2).png

**Plik:** [NotebookLM Mind Map (2).png](<C:/Users/karol/Downloads/Trading 2.0/NotebookLM Mind Map (2).png>)

**Format i zakres:** Grafika.

**Pochodzenie:** Załącznik użytkownika; mapa koncepcji, nie dowód działania systemu.

**Lokalizator:** Gałęzie Required Tools, AI Strategy Research Loop, Validation and Testing, TradingView Integration, Live Automation Setup, Performance and Results.

**Zastosowanie:** Mapa etapów i zależności; AJ-01, AJ-07, AJ-15, AJ-17.

**Role:** Mapa etapów i zależności; AJ-01, AJ-07, AJ-15, AJ-17.

**Rozbieżności i ograniczenia:** Mapa inspirowana tym samym materiałem; gałąź Live nie jest zgodą na uruchomienie rachunku realnego.

**SHA-256:** `ebba8f69d85bfdd9bd0ae8e49290de0ba54cdba02bcd92508879c21ed86afd5f`.

### SRC-015 · Budowa_bota_handlowego_AI.png

**Plik:** [Budowa_bota_handlowego_AI.png](<C:/Users/karol/Downloads/Trading 2.0/Budowa_bota_handlowego_AI.png>)

**Format i zakres:** Grafika.

**Pochodzenie:** Załącznik użytkownika; mapa koncepcji, nie dowód działania systemu.

**Lokalizator:** Góra: narzędzia i sprint; dół: inkubacja, most, portfel.

**Zastosowanie:** Czytelny schemat procesu; AJ-01, AJ-07, AJ-14, AJ-15.

**Role:** Czytelny schemat procesu; AJ-01, AJ-07, AJ-14, AJ-15.

**Rozbieżności i ograniczenia:** 184/13/96% to ilustracja deklaracji, nie nasz benchmark. Znak Gemini Notebook wskazuje opracowanie.

**SHA-256:** `139b2c9a2d25e6d86141ddb639d84613cea4c89dc4388ec543457a345f50414c`.

### SRC-016 · ChatGPT Image 19 wrz 2026, 14_13_48.png

**Plik:** [ChatGPT Image 19 wrz 2026, 14_13_48.png](<C:/Users/karol/Downloads/Trading 2.0/ChatGPT Image 19 wrz 2026, 14_13_48.png>)

**Format i zakres:** Grafika.

**Pochodzenie:** Załącznik użytkownika; mapa koncepcji, nie dowód działania systemu.

**Lokalizator:** Cały schemat: Ty, AI Chat, Trading Office, analitycy, ryzyko, krytyk, rynki.

**Zastosowanie:** Źródłowa wizja AstralJet i 19 ról AJ-00–AJ-18.

**Role:** Źródłowa wizja AstralJet i 19 ról AJ-00–AJ-18.

**Rozbieżności i ograniczenia:** Grafika koncepcyjna przekazana przez Karola; strzałki S.M. Promo do rynków nie oznaczają uprawnienia do transakcji.

**SHA-256:** `27eefc177d400f0cd18ba766825cf5e0ebd38df0f90fde3a62248db90349c926`.

### SRC-017 · 1-Photo-1.jpg

**Plik:** [1-Photo-1.jpg](<C:/Users/karol/Documents/Codex/2026-09-19/openai-developers-plugin-openai-developers-openai-3/.codex-remote-attachments/01a0b995-b7b5-7d20-82f7-0b06ece0c226/7587d357-0685-4db4-8898-23e691dc529a/1-Photo-1.jpg>)

**Format i zakres:** Grafika.

**Pochodzenie:** Załącznik użytkownika; mapa koncepcji, nie dowód działania systemu.

**Lokalizator:** Pełny wcześniejszy schemat Trading Office ASTRA JET.

**Zastosowanie:** Powtórzona wizja całości i relacja W.M. / inne projekty.

**Role:** Powtórzona wizja całości i relacja W.M. / inne projekty.

**Rozbieżności i ograniczenia:** Inna wersja obrazu tej samej koncepcji; nie niezależne potwierdzenie wdrożenia.

**SHA-256:** `72dc53e576573692d958b507c2c6f145bd78e960827a2bda93482e837e89800c`.

### SRC-018 · 2-Photo-2.jpg

**Plik:** [2-Photo-2.jpg](<C:/Users/karol/Documents/Codex/2026-09-19/openai-developers-plugin-openai-developers-openai-3/.codex-remote-attachments/01a0b995-b7b5-7d20-82f7-0b06ece0c226/7587d357-0685-4db4-8898-23e691dc529a/2-Photo-2.jpg>)

**Format i zakres:** Grafika.

**Pochodzenie:** Załącznik użytkownika; mapa koncepcji, nie dowód działania systemu.

**Lokalizator:** Dwa bloki: Badanie strategii oraz Testowanie strategii.

**Zastosowanie:** Bezpośrednia podstawa zakresu ASTRA Pro — AJ-05 i AJ-07.

**Role:** Bezpośrednia podstawa zakresu ASTRA Pro — AJ-05 i AJ-07.

**Rozbieżności i ograniczenia:** Zbliżenie wcześniejszego schematu. Nie opisuje funkcji składania zleceń przez laboratorium.

**SHA-256:** `48e8831613677d9bae0045cb4192be94fcd7c035b6b9843fb41d9775818b3e55`.

### SRC-019 · AURUM_ASTRA_2026-09-19.zip

**Plik:** [AURUM_ASTRA_2026-09-19.zip](<C:/Users/karol/Documents/Codex/2026-09-19/openai-developers-plugin-openai-developers-openai-3/outputs/AURUM_ASTRA_2026-09-19.zip>)

**Format i zakres:** ZIP — 15 wpisów.

**Pochodzenie:** Wcześniejszy pakiet AURUM / ASTRA wskazany przez Karola.

**Lokalizator:** Archiwum wcześniejszego audytu; odpowiadające pliki robocze w outputs/AURUM_ASTRA.

**Zastosowanie:** Kontekst zastanego systemu i wcześniejsze katalogi. Do stanu z 15:06 używamy późniejszego raportu E-09.

**Role:** AJ-00, AJ-01, AJ-16, AJ-17

**Rozbieżności i ograniczenia:** Datowany audyt częściowy. Sam ZIP nie jest nowym audytem całej historii. Sprawdzono obecność i listę archiwum, a treść raportów odczytano z rozpakowanego katalogu.

**SHA-256:** `6c35f86c6ef06396890d8351dbd412a423946b2d6450cd12165ea10706f05f72`.

### SRC-020 · SebAIAIDayTradingDeskAstraGuide.pdf

**Plik:** [SebAIAIDayTradingDeskAstraGuide.pdf](<C:/Users/karol/Downloads/SebAIAIDayTradingDeskAstraGuide.pdf>)

**Format i zakres:** 13 stron/slajdów.

**Pochodzenie:** Przewodnik przekazany przez Karola; oznaczenia autora/marki SebAI lub @seb.ai w materiale. Nie potwierdzano tożsamości autora ani niezależnie wszystkich deklaracji. Osobna rodzina materiałów od opracowań NotebookLM.

**Lokalizator:** s. 1–2: granice i sześć ról; s. 3–8: karty analityków; s. 9–11: orkiestracja i opcjonalny dashboard; s. 12: fikcyjny przykład XYZ; s. 13: weryfikacja danych.

**Zastosowanie:** Wzorzec wejść, wyjść i przekazania analizy między AJ-10, AJ-12, AJ-07, AJ-09 i AJ-05; wspólny raport dla AJ-00.

**Role:** AJ-00, AJ-01, AJ-05, AJ-06, AJ-07, AJ-09, AJ-10, AJ-12

**Rozbieżności i ograniczenia:** Skanowanie instrumentów z dostarczonej tabeli nie jest wyszukiwaniem strategii przez Scouta. Przykład XYZ jest fikcyjny. Sześć kroków i przykład 1% nie są obowiązkowym przebiegiem każdej strategii. Instrukcja budowy nowego dashboardu nie zmienia zakresu v0.2.

**SHA-256:** `ee1391de12bd9091d25e827dc3c5b1b1891b19db2d8f6ae0006eef56f64ad6e3`.

### SRC-021 · AIMoneyMakingTeam.pdf

**Plik:** [AIMoneyMakingTeam.pdf](<C:/Users/karol/Downloads/AIMoneyMakingTeam.pdf>)

**Format i zakres:** 13 stron/slajdów.

**Pochodzenie:** Przewodnik przekazany przez Karola; oznaczenia autora/marki SebAI lub @seb.ai w materiale. Nie potwierdzano tożsamości autora ani niezależnie wszystkich deklaracji. Osobna rodzina materiałów od opracowań NotebookLM.

**Lokalizator:** s. 2–3: brief i łańcuch pracy; s. 4–9: research, produkt, leady, treści, reklamy, sprzedaż; s. 10 i 12: Operations; s. 11: sama stopka; s. 13: lista kontrolna.

**Zastosowanie:** Operations jako inspiracja tablicy zadań AJ-01/AJ-16. Treści wyłącznie jako materiał dla AJ-18 po osobnym zleceniu. Pozostałe funkcje biznesowe w katalogu pobocznym.

**Role:** AJ-00, AJ-01, AJ-16, AJ-18; funkcje sprzedażowe poza zakresem AstralJet

**Rozbieżności i ograniczenia:** Siedmiu agentów biznesowych nie dopisujemy do 19 ról tradingowych. Przykłady klientów i wyników są ilustracyjne. Liczba opinii konkurenta nie potwierdza płatnego popytu na ofertę Karola. Nie wysyłamy wiadomości ani nie uruchamiamy reklam.

**SHA-256:** `fbadcb03fb61f91dc21ee7d9d05eabd12bc316e176dcdba31dc8669019373959`.

### SRC-022 · Audyt_Astry_2026-09-15.pdf

**Plik:** [Audyt_Astry_2026-09-15.pdf](<C:/Users/karol/Downloads/Trading 2.0/Audyt_Astry_2026-09-15.pdf>)

**Format i zakres:** 13 stron/slajdów.

**Pochodzenie:** Dokument podpisany jako ponowny audyt Claude, 15.09.2026; przekazany przez Karola. Dokumentacja historyczna, nie nowy odczyt.

**Lokalizator:** s. 1–6: podsumowanie i stan 15.09; s. 7: koszty oraz brak niezależnej próby; s. 8: UNCERTAIN i nieporównywalna runda; s. 9–10: uruchomienie, stan i wersje; s. 11: ocena krypto i autorstwo zdarzeń; s. 12–13: naprawy i metoda.

**Zastosowanie:** Historyczny punkt odniesienia dla AJ-08/AJ-09/AJ-15/AJ-16/AJ-17; wymagania odtwarzalności, porównywalności i rozliczenia operacji.

**Role:** AJ-06, AJ-07, AJ-08, AJ-09, AJ-15, AJ-16, AJ-17

**Rozbieżności i ograniczenia:** Audyt Claude: 15.09.2026, stan 20:35, aktualizacja 21:15 czasu polskiego. Nie jest bieżącym stanem 19.09. Liczba 785 testów i dawne wyniki nie były tu ponownie sprawdzane. Progi t > 2 i przykład 30 transakcji są zaleceniami autora audytu, nie zatwierdzonymi kryteriami v0.2. Polecenia naprawcze i usuwania plików nie są wykonywane.

**SHA-256:** `de39f064a880ad983c9447966449fda0521b8ad585679686fbf6492ea4401cdc`.

### SRC-023 · Claude-x-TradingView-OS.pdf

**Plik:** [Claude-x-TradingView-OS.pdf](<C:/Users/karol/Downloads/Claude-x-TradingView-OS.pdf>)

**Format i zakres:** 8 stron/slajdów.

**Pochodzenie:** Przewodnik przekazany przez Karola; oznaczenia autora/marki SebAI lub @seb.ai w materiale. Nie potwierdzano tożsamości autora ani niezależnie wszystkich deklaracji. Osobna rodzina materiałów od opracowań NotebookLM.

**Lokalizator:** s. 1–4: desktop i połączenie; s. 5: prompty i ograniczenia; s. 6: przykładowy plan; s. 7: rutyna; s. 8: zakończenie.

**Zastosowanie:** Możliwy podgląd wykresów AJ-10, raport dzienny AJ-00 i przyszły adapter. Porównanie z lokalnym mostem E-13.

**Role:** AJ-00, AJ-10, AJ-17

**Rozbieżności i ograniczenia:** Polecenia instalacji są dla macOS; nie kopiujemy ich do Windows. Most CDP do TradingView różni się od TradingKit. Przykładowe 1% ryzyka i R/R 1:2 nie są polityką Astry. Odczyt wykresu nie zastępuje backtestu.

**SHA-256:** `27d2028daa5aa8987c6893a5ece98a4daf041894d1fa3623b51c4b13543fd2e6`.

### SRC-024 · SebAI-10K-ChatGPT-Paper-Trading-Guide.pdf

**Plik:** [SebAI-10K-ChatGPT-Paper-Trading-Guide.pdf](<C:/Users/karol/Downloads/SebAI-10K-ChatGPT-Paper-Trading-Guide.pdf>)

**Format i zakres:** 21 stron/slajdów.

**Pochodzenie:** Przewodnik przekazany przez Karola; oznaczenia autora/marki SebAI lub @seb.ai w materiale. Nie potwierdzano tożsamości autora ani niezależnie wszystkich deklaracji. Osobna rodzina materiałów od opracowań NotebookLM.

**Lokalizator:** s. 1–4: cel i źródła; s. 5: schemat dane–badanie–pomysł; s. 6–10: reguły, sizing i karta; s. 7: pusta strona; s. 11–15: przeglądy i dziennik; s. 16–20: projekt, alerty, dashboard, cykl; s. 21: zakończenie.

**Zastosowanie:** Szablon karty hipotetycznej transakcji, dziennika, przeglądu tygodniowego i oceny jakości procesu. Pomoc dla specyfikacji inkubacji.

**Role:** AJ-00, AJ-05, AJ-07, AJ-09, AJ-15, AJ-16

**Rozbieżności i ograniczenia:** 10 000 USD, 30 dni i 1% to przykład edukacyjny, nie plan rachunku Karola. Ręczny dziennik paper nie dowodzi działania ciągłego wykonawcy. Dashboard może zawierać mock; taki zapis musi być oznaczony. Nie tworzymy nowego projektu ChatGPT ani nowej aplikacji na podstawie promptu z PDF.

**SHA-256:** `aaaa19ef3217d23773b1e2adfc63895a9a6189294a62c517e3a75a28aa1c1458`.

### SRC-025 · SebAIAIDayTradingDeskAstraGuide (1).pdf

**Plik:** [SebAIAIDayTradingDeskAstraGuide (1).pdf](<C:/Users/karol/Downloads/SebAIAIDayTradingDeskAstraGuide (1).pdf>)

**Format i zakres:** 13 stron/slajdów.

**Pochodzenie:** Przewodnik przekazany przez Karola; oznaczenia autora/marki SebAI lub @seb.ai w materiale. Nie potwierdzano tożsamości autora ani niezależnie wszystkich deklaracji. Osobna rodzina materiałów od opracowań NotebookLM.

**Lokalizator:** Całość: s. 1–13, identyczna z SRC-020.

**Zastosowanie:** Alias pliku SRC-020; wspólna karta wiedzy i te same odwołania do stron.

**Role:** Jak SRC-020

**Rozbieżności i ograniczenia:** Dokładny duplikat bajtowy SRC-020, potwierdzony SHA-256. Nie zwiększa liczby niezależnych materiałów ani dowodów.

**SHA-256:** `ee1391de12bd9091d25e827dc3c5b1b1891b19db2d8f6ae0006eef56f64ad6e3`.

### SRC-026 · SebAIAICryptoTraderAstraGuide.pdf

**Plik:** [SebAIAICryptoTraderAstraGuide.pdf](<C:/Users/karol/Downloads/SebAIAICryptoTraderAstraGuide.pdf>)

**Format i zakres:** 12 stron/slajdów.

**Pochodzenie:** Przewodnik przekazany przez Karola; oznaczenia autora/marki SebAI lub @seb.ai w materiale. Nie potwierdzano tożsamości autora ani niezależnie wszystkich deklaracji. Osobna rodzina materiałów od opracowań NotebookLM.

**Lokalizator:** s. 1–2: zakres i przygotowanie; s. 3–6: Scan, Technicals, Research, Risk; s. 7–8: plan i master prompt; s. 9–10: alert i dashboard; s. 11–12: przykład i zasady.

**Zastosowanie:** Wzorzec analizy danych krypto: źródło i czas, jawne braki, rozdzielenie faktu od opinii i ryzyka. Raport przekazywany AJ-05.

**Role:** AJ-00, AJ-05, AJ-06, AJ-09, AJ-10, AJ-11, AJ-12

**Rozbieżności i ograniczenia:** Cztery prompty i plan nie są automatem składającym zlecenia. Ranking dostarczonych monet nie oznacza skanu całego rynku. Dane on-chain wymagają źródła; przykłady 5000 USD i 1% nie są parametrami Astry.

**SHA-256:** `0e7e5fba7b2b3286ad5daec54dc5d3a361619fa662c710202596ccb7392c1dfb`.

### SRC-027 · SebAIAIHedgeFund8AnalystsGuide.pdf

**Plik:** [SebAIAIHedgeFund8AnalystsGuide.pdf](<C:/Users/karol/Downloads/SebAIAIHedgeFund8AnalystsGuide.pdf>)

**Format i zakres:** 4 stron/slajdów.

**Pochodzenie:** Przewodnik przekazany przez Karola; oznaczenia autora/marki SebAI lub @seb.ai w materiale. Nie potwierdzano tożsamości autora ani niezależnie wszystkich deklaracji. Osobna rodzina materiałów od opracowań NotebookLM.

**Lokalizator:** s. 1: kolejność ośmiu ról; s. 2: wyniki i memo; s. 3: prompty i tryb próbny; s. 4: jakość danych i domknięcie.

**Zastosowanie:** Wspólny pakiet źródeł, oddzielne raporty analityków, krytyka ryzyka i memo dla Karola. Mapa do istniejących ról w strukturze v0.2.

**Role:** AJ-00, AJ-01, AJ-05, AJ-07, AJ-09, AJ-11, AJ-12, AJ-13, AJ-14

**Rozbieżności i ograniczenia:** Execution Planner przygotowuje plan, nie realizuje zlecenia. Sektor należy do AJ-11; nie tworzymy dodatkowego bota. Przykładowe 100 000 USD i 2% oraz identyfikatory modeli nie są zatwierdzoną konfiguracją.

**SHA-256:** `b660970f649db4cc4d7375d9ba5e9305a3c32e6f4dad3ca41800cdf7bdbf7a1f`.

### SRC-028 · Vantage_Broker_Koszty_i_Spready.xlsx

**Plik:** [Vantage_Broker_Koszty_i_Spready.xlsx](<C:/Users/karol/Downloads/Vantage_Broker_Koszty_i_Spready.xlsx>)

**Format i zakres:** XLSX — 1 arkusz, 7 wierszy danych.

**Pochodzenie:** Arkusz przekazany przez Karola; metadane openpyxl, utworzenie i modyfikacja 10.09.2026 19:15:05 bez wskazania strefy. Brak autora/taryfy w komórkach. Data pliku nie jest datą rynkowej obowiązywalności kosztów.

**Lokalizator:** Arkusz 'Koszty i Spready', A1:E8; siedem klas aktywów w wierszach 2–8. Szczegóły kontroli poniżej.

**Zastosowanie:** Lista pytań do profilu kosztów DATA; materiał do LAB-06 i prób kosztowych LAB-10. Bez kopiowania liczb do konfiguracji.

**Role:** AJ-06, AJ-07, AJ-09

**Rozbieżności i ograniczenia:** Szacunki bez źródeł taryfy, podmiotu brokera, serwera, daty kwotowania i pełnej konwencji naliczania. Jednostki i koszt jednej strony/pełnego obrotu wymagają uzgodnienia. Brak potwierdzenia zgodności z rachunkiem Astry.

**SHA-256:** `b2bc35e88accb3a49177971c59ebffd3e591a4d5717fa7b96de312f1096264d9`.

### Mapa prezentacji SRC-011

| Slajd | Treść | Zastosowanie w AstralJet |
|---|---|---|
| 1 | Autonomiczna fabryka strategii | Cel procesu, bez deklaracji istniejącego wdrożenia |
| 2 | Porównanie 1 i 184 strategii | Rejestr twierdzeń autora; nie kryterium odbioru |
| 3 | Mózg, symulator, walidator, most, broker | Rozdzielenie koordynacji, testów i wykonania |
| 4 | Work Tab, MCP i aktywacja | Lista możliwych integracji do późniejszego sprawdzenia |
| 5 | SMA 20/50, BTC/USDT i przykładowe wyniki | EX-001 w Lab; wynik autora nie staje się oczekiwanym wynikiem testu łączności |
| 6 | Ośmiogodzinny cykl i limity | Potrzeba trwałego postępu, limitu kosztu i historii prób |
| 7 | Inkubacja | Osobny etap i jednoznaczne wskazanie rodzaju dowodu |
| 8 | Wykres MNTUSDT i 3130% | Rozdzielenie ilustracji, kodu oraz odtwarzalnego raportu |
| 9 | Trigger Trade | Przyszły adapter wykonawczy poza Lab |
| 10 | Alert i webhook | Wymagania późniejszej integracji, bez jej uruchamiania |
| 11 | Ranking modeli | Kontekst autora; nie wybór modelu na podstawie niezweryfikowanych liczb |
| 12 | Siedem botów i kapitał | Wspólna ekspozycja, koszty i zależność strategii; brak magicznej liczby |
| 13 | Lista wdrożeniowa | Etapy przekazania pracy z jawnymi decyzjami |
| 14 | Narzędzia i zasoby | Katalog integracji i źródeł, nie zgoda na instalację |

## 3. Rozbieżności i sposób ich obsługi

| ID | Twierdzenie / problem | Gdzie występuje | Rozstrzygnięcie v0.2 |
|---|---|---|---|
| R-01 | 184 strategie, 13 konkurenta, 96% pozostałego limitu | SRC-003 s. 1; SRC-005 s. 2; SRC-011 slajdy 2, 6 | Deklaracje źródła. Potrzebne logi, definicja unikalnej strategii, konfiguracja modeli i rozliczenia. Nie utożsamiamy limitu konta z liczbą zużytych tokenów |
| R-02 | 3130% i 695/około 700 transakcji dowodzą przewagi | SRC-003 s. 2; SRC-006 s. 2; SRC-011 slajd 8 | Brak odtwarzalnego kodu, danych, dat, sizingu i pełnych kosztów w pakiecie; nie jest to wynik Astry |
| R-03 | PF >1,2, >1,3 albo minimum 1,35 | SRC-007 s. 2; SRC-005 s. 3; SRC-009 s. 2 | Brak wspólnego progu. Kryterium konkretnego EXP ustalamy przed jego oceną |
| R-04 | 30 dni, minimum 2 miesiące albo kilka miesięcy inkubacji | SRC-006 s. 2; SRC-005 s. 3; SRC-008 s. 1 | To różne zalecenia źródłowe. Zakres obserwacji, liczba zdarzeń i warunki rynku wymagają planu; upływ czasu nie powoduje awansu |
| R-05 | Minimum 600 transakcji albo kilkaset daje pewność | SRC-005 s. 3; SRC-004 s. 1 | Wielkość i zależność próby oraz liczba wariantów muszą być jawne. Sama liczba nie jest dowodem |
| R-06 | Dokładnie siedem botów gwarantuje wygładzenie wyników | SRC-009 s. 3; SRC-013 s. 1; SRC-011 slajd 12 | AJ-14 ocenia wspólne straty, ekspozycję i koszty. Siedem strategii nie oznacza siedmiu niezależnych zakładów ani siedmiu ról AI |
| R-07 | Różowa krzywa ma pokrywać się z zieloną | SRC-003 s. 2; SRC-006 s. 2; SRC-009 s. 1–2 | Odrębne tryby testu. Na wspólnym okresie porównujemy sygnały/realizacje; między okresami właściwości wyników i ograniczenia |
| R-08 | Test SMA ma zwrócić dokładnie 4,74%, 38%, 1,5 i 5,81% | SRC-005 s. 2; SRC-007 s. 2; SRC-011 slajd 5 | Bez kompletnego eksperymentu tych liczb nie da się odtworzyć. Łączność sprawdza poprawna odpowiedź narzędzia; wynik finansowy wymaga osobnej walidacji |
| R-09 | PF 1,5 oznacza przychód 1,50 na każdą ryzykowaną złotówkę | SRC-006 s. 1 | PF jest ilorazem sum dodatnich i ujemnych wyników przy określonym sposobie ujęcia kosztów. Nie jest stopą zwrotu z ryzykowanego kapitału |
| R-10 | Dużo optymalizacji usuwa błędy poznawcze i przypadek | SRC-005 s. 2; SRC-006 s. 1 | Zachowujemy pełną historię prób, ograniczony plan strojenia i odrębną ocenę poza strojeniem |
| R-11 | Nieprzechowywanie kluczy gwarantuje pełne bezpieczeństwo | SRC-005 s. 3; SRC-007 s. 3; SRC-011 slajd 9 | Nie przyjmujemy gwarancji. Przed integracją potrzebny jest aktualny opis przepływu i przechowywania uprawnień; patrz W-04 |
| R-12 | Fill orders only zapobiega powtórzeniu transakcji | SRC-006 s. 2; SRC-010 s. 1 | Wybór typu alertu nie zastępuje identyfikatora zlecenia, rejestru stanu i uzgodnienia niepewnej realizacji |
| R-13 | traderdev.com, TradingKit i lokalny TradingView MCP to ten sam silnik | SRC-002 s. 1; SRC-005 s. 2; E-13 | Oficjalny hub wskazuje trader.dev. Lokalny most to inne narzędzie. Wybór integracji odroczony |
| R-14 | TradingView jest ostatecznym potwierdzeniem rzeczywistego wykonania | SRC-005 s. 3; SRC-007 s. 2 | To dodatkowy model symulacji; wymagane uzgodnienie danych i założeń. Nie zastępuje zapisu brokera |

## 4. Zewnętrzne źródła weryfikacyjne

Odczyty: 19.09.2026. Twierdzenia usługodawcy opisują jego usługę, a nie niezależny audyt jej jakości. Poniżej tylko ustalenia potrzebne do dokumentacji.

- **W-01 — [AI Trading Arena](https://aitradingarena.com/):** w sekcji pipeline forward oznacza ponowny test na późniejszych danych. Sekcja caveats przyznaje wysoką korelację wielu strategii; koszt tokenów jest samoopisem agentów, bez niezależnego audytu. Nie kopiujemy jej progów kwalifikacji do Astry.
- **W-02 — [TradingView: Strategies](https://www.tradingview.com/pine-script-docs/concepts/strategies/):** sekcje Broker emulator oraz Commission opisują model realizacji i konfigurowane koszty. To podstawa oznaczania ograniczeń przy porównaniu dwóch silników.
- **W-03 — [TradingKit](https://tradingkit.com/):** oficjalny hub odsyła do [trader.dev](https://trader.dev/) jako serwera MCP. Nie potwierdzono tu szczegółów API, uprawnień konta ani warunków bezpłatności.
- **W-04 — [repozytorium autora Trigger Trade](https://github.com/daviddme/trigger-trade-skills/blob/main/README.md):** opisuje szyfrowanie kluczy po stronie serwera i ostrzega, że wygenerowane pliki nadają możliwość handlu ich posiadaczowi. Nie dowodzi to samo w sobie przechowywania ani nieprzechowywania kluczy. Zakres przyszłej integracji wymaga osobnego sprawdzenia.
- **W-05 — [TradingView: webhook alerts](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/):** webhook wysyła żądanie HTTP; dokumentacja wskazuje możliwość niedostarczenia. Przyszły wykonawca potrzebuje potwierdzenia i uzgodnienia stanu, nie tylko wysyłki alertu.
- **W-06 — [The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf):** praca metodologiczna o ryzyku wyboru najlepszego wariantu spośród wielu prób. Uzasadnia zachowanie historii selekcji; nie dostarcza uniwersalnego progu rentowności dla projektu.

## 5. Dowody stanu zastanego

Odczyt statyczny: **2026-09-19T14:51:54+00:00**. Repo HEAD: `5073f653d35a2d01ff92ab2e4f854f33f213fa23`. Zmiany lokalne zastane w repo pozostawiono. Nie wykonywano odświeżenia runtime ani płatnego badania. Hash identyfikuje przeczytany plik, nie dowodzi prawdziwości wszystkich jego twierdzeń. Same pliki README nie zastępują testu działania.

### E-01

**Źródło:** Bieżąca rozmowa i zatwierdzony plan.

**Miejsce / treść:** Rozmowa z Karolem: polecenie wdrożenia planu v0.2 i trzy odpowiedzi z fazy planowania.

**Co potwierdza i czego nie potwierdza:** Potwierdza: rozwijamy obecną Astrę; najpierw dokumentacja; Lab bada i ocenia, Wykonawca osobno.

### E-02

**Źródło:** [ASTRALJET_STRUKTURA_v0.1.md](<C:/Users/karol/Documents/Codex/2026-09-19/openai-developers-plugin-openai-developers-openai-3/outputs/AstralJet/ASTRALJET_STRUKTURA_v0.1.md>)

**Miejsce / treść:** 19 kart i źródłowe obrazy SRC-016–SRC-018.

**Co potwierdza i czego nie potwierdza:** Dowód projektu ról, nie ich kompletnego wdrożenia.

**SHA-256:** `dbe078b8aadfe3aa6a7f6298145c526e64ab7de581175dd7173662ea07946208`.

### E-03

**Źródło:** [README.md](<C:/Users/karol/Documents/Claude/Projects/Trading/astra_site/research/discovery/README.md>)

**Miejsce / treść:** Sekcje: kolejka turniejów, Portfel strategii i czytanie całych materiałów, X: radar i badania.

**Co potwierdza i czego nie potwierdza:** Opis zastanego zachowania i limitów, nie test uruchomionego procesu.

**SHA-256:** `2d26c338831c4c4f3b7a29907bd32b68bf94d3ac0be4f71ddc36402e48f012bf`.

### E-04

**Źródło:** [discovery-store.ts](<C:/Users/karol/Documents/Claude/Projects/Trading/astra_site/lib/discovery-store.ts>)

**Miejsce / treść:** DiscoveryRecord, enqueue, jobs; research/discovery/worker.py: run_job, main.

**Co potwierdza i czego nie potwierdza:** Kod rejestru i kolejki; istnienie funkcji nie dowodzi kompletności wdrożenia.

**SHA-256:** `e480e4f24c6adf9573f7e6f35f70520bf9ec6fa46f03be03f5363eb8763267b4`.

### E-05

**Źródło:** [discovery.ts](<C:/Users/karol/Documents/Claude/Projects/Trading/astra_site/lib/discovery.ts>)

**Miejsce / treść:** strategySpec, validateCitations, adapterIds; worker.py: ingest i extract_bytes.

**Co potwierdza i czego nie potwierdza:** Schemat reguł i mechanizm sprawdzania cytatów; import obrazowego PDF wymaga osobnej ścieżki.

**SHA-256:** `0219e1119795cf11c3ad5ef52c698d159d9a0f36609e969adc41e96cfad9f8f3`.

### E-06

**Źródło:** [research_models.py](<C:/Users/karol/Documents/Claude/Projects/Trading/astra_site/research/discovery/research_models.py>)

**Miejsce / treść:** generate_research_signals i modele regułowe.

**Co potwierdza i czego nie potwierdza:** Istnieją wybrane implementacje; nie dowodzi to uniwersalnego generatora lub modułu ML.

**SHA-256:** `b09eb71215ec495f861466c7dbd8676d41f556d58882c78d97493eda668e6dba`.

### E-07

**Źródło:** [adapter.py](<C:/Users/karol/Documents/Claude/Projects/Trading/astra_site/research/discovery/adapter.py>)

**Miejsce / treść:** collect oraz obliczenia bazowe/stresowe, hashe i raporty; bez uruchamiania.

**Co potwierdza i czego nie potwierdza:** Adapter badawczy, dane MT5 i ograniczenia historycznej niezależności.

**SHA-256:** `e2667ad66b972f292e550d4632f999fb42f343d0adc4667154ca63e63f3bb0c7`.

### E-08

**Źródło:** [execution.py](<C:/Users/karol/Documents/Claude/Projects/Trading/astra_site/research/mt5_connector/contest_lab/astra_lab/execution.py>)

**Miejsce / treść:** Silnik księgi; sąsiednie daily_replay.py, pair_replay.py i katalog tests.

**Co potwierdza i czego nie potwierdza:** Kod testów i diagnostyki, nie nowy pomiar skuteczności strategii.

**SHA-256:** `d3b284a59c85049b500df91afa2fdf6ad1e3fbc1e6a039b92620475780b4442e`.

### E-09

**Źródło:** [13_AUR001_POSTEP.md](<C:/Users/karol/Documents/Codex/2026-09-19/openai-developers-plugin-openai-developers-openai-3/outputs/AURUM_ASTRA/13_AUR001_POSTEP.md>)

**Miejsce / treść:** Raport z 19.09.2026, odczyty 15:03–15:06 Europe/Warsaw.

**Co potwierdza i czego nie potwierdza:** Historycznie potwierdzone wykonanie DEMO i uzgodnienie 64 zapisów; pełna historia pozostaje niepotwierdzona.

**SHA-256:** `6008c9bafb11de17f09d3a2646c8d81acd4beb208cc43b43a180dbd77207e1fc`.

### E-10

**Źródło:** [astra_monitor.py](<C:/Users/karol/Documents/Claude/Projects/Trading/astra_site/research/mt5_connector/astra_monitor.py>)

**Miejsce / treść:** Kod monitora; astra_demo_round.py, astra_crypto_round.py i astra_oil_round.py jako sąsiedni kod wykonawców.

**Co potwierdza i czego nie potwierdza:** Istnienie kodu wykonania i monitorowania. Bieżącego stanu procesu nie sprawdzano w etapie dokumentacji.

**SHA-256:** `03591ea067efee8fe1865e942100fd81bb9f3ef5543b955005617febfdfaf5a5`.

### E-11

**Źródło:** [01_AUDYT_2026-09-19.md](<C:/Users/karol/Documents/Codex/2026-09-19/openai-developers-plugin-openai-developers-openai-3/outputs/AURUM_ASTRA/01_AUDYT_2026-09-19.md>)

**Miejsce / treść:** Katalogi i blokady importów oraz kolejki z pierwszego audytu.

**Co potwierdza i czego nie potwierdza:** Dane historyczne; nie deklarujemy usunięcia dawnych błędów.

**SHA-256:** `fda067d919860ded0e2fb9d2473ac1392551eac5e970d4d9d17eddeba3bec292`.

### E-12

**Źródło:** [README.md](<C:/Users/karol/Documents/Claude/Projects/Trading/astra_site/research/research_cli/README.md>)

**Miejsce / treść:** Opis ról badawczych i materiałów SEB.

**Co potwierdza i czego nie potwierdza:** Punkt odniesienia dla analityków; brak potwierdzenia kompletnego automatycznego wdrożenia.

**SHA-256:** `b2f4b076345ec476a7d318188490ac0fa8ed423a9559da33c408a842a95e5dbd`.

### E-13

**Źródło:** [README.md](<C:/Users/karol/tradingview-mcp/README.md>)

**Miejsce / treść:** How It Works, What This Tool Does Not Do, Prerequisites.

**Co potwierdza i czego nie potwierdza:** Lokalny most do aplikacji TradingView; odrębny od TradingKit / trader.dev.

**SHA-256:** `9e05e20adc349e2c3ab9d8a48d428624dfe00ea9a52422d6ec976ff9a1dc17a4`.

## 6. Rejestr decyzji

| ID | Status | Decyzja | Właściciel i podstawa |
|---|---|---|---|
| DEC-01 | ZATWIERDZONA | Rozwijamy obecną Astrę | Karol, odpowiedź w planowaniu i polecenie wdrożenia |
| DEC-02 | ZATWIERDZONA | Pierwszy etap to dokumentacja Markdown | Karol; bez wdrażania kodu produktu |
| DEC-03 | ZATWIERDZONA | ASTRA Pro bada i ocenia; Wykonawca jest osobno | Karol, odpowiedź „Badania i ocena” |
| DEC-04 | ZATWIERDZONA | Zachowujemy 19 kart AJ-00–AJ-18 i rozwijamy 12 zadań Lab | Zatwierdzony plan v0.2 |
| DEC-05 | ZATWIERDZONA | Dotychczasowe wersje pozostają; indeks wskazuje v0.2 | Zatwierdzony plan v0.2 |
| DEC-06 | ZATWIERDZONA | Drobne poprawki samodzielnie; ważne decyzje wspólnie | Karol, zasady współpracy |
| DEC-07 | PRZYJĘTA W SPECYFIKACJI | Oddzielne tryby testu, stan techniczny i ocena strategii; zmiana reguł tworzy nową wersję | Realizacja zatwierdzonego planu; nie migracja bazy |
| DEC-08 | PRZYJĘTA W SPECYFIKACJI | Liczby i progi z materiałów nie są automatycznymi kryteriami Astry | Zatwierdzony plan v0.2 |
| DEC-09 | ODROCZONA | Pierwsza strategia i wierna replikacja albo własna adaptacja | Karol po propozycji AJ-05; blokuje właściwy eksperyment, nie dokumentację |
| DEC-10 | ODROCZONA | Instrument, miejsce obrotu, dane i model kosztów | Karol z AJ-05/AJ-06 przed zamrożeniem planu |
| DEC-11 | ODROCZONA | Okresy, warianty, kryteria, budżet eksperymentu i tolerancja odtworzenia | Karol z AJ-07/AJ-08/AJ-17 przed testem |
| DEC-12 | ODROCZONA | Tryb, wersja, limity i procedura zatrzymania pierwszej nowej inkubacji | Karol z AJ-09/AJ-15 przed uruchomieniem |
| DEC-13 | ODROCZONA | TradingKit / TradingView / Trigger Trade lub inne adaptery | Osobna ocena funkcji, kosztu i przepływu danych; brak instalacji w v0.2 |
| DEC-14 | POZA ETAPEM | Handel realny, wybór brokera realnego i alokacja kapitału | Wymaga osobnego zlecenia; dokumentacja niczego nie uruchamia |

DEC-09–DEC-14 są świadomie odroczone do właściwych etapów. Wykonawca dokumentacji nie ma ich zgadywać. Przykład SMA w Lab nie rozstrzyga żadnej z nich. Upływ daty zapisanej w starszym repo nie oznacza zgody na realny kapitał.

## 7. Utrzymanie dokumentacji

### Porównanie audytu z 15.09 z późniejszym rozpoznaniem

SRC-022 przedstawia stan na 15.09 o 20:35 z aktualizacją 21:15. E-09 jest późniejszym, węższym odczytem 19.09 o 15:03–15:06. Nie przenosimy automatycznie statusu „naprawione” pomiędzy tymi datami i zakresami.

| Zagadnienie i miejsce w SRC-022 | Co wnosi późniejsze E-09 | Wniosek dla dokumentacji |
|---|---|---|
| K-1, s. 7: brak wykazanej przewagi, wielokrotnie użyte 36 miesięcy | Uzgodnienie zapisów DEMO; brak nowego testu przewagi | Stan metodologiczny pozostaje otwarty; księgowanie nie dowodzi rentowności |
| K-2, s. 8: UNCERTAIN bez poprawnego wyjścia | Bieżące rundy nie zgłaszały nierozliczonych prób w chwili odczytu | Brak incydentu nie dowodzi naprawy gałęzi błędu; potrzebny osobny odbiór mechanizmu |
| W-1, s. 8: inne ryzyko, instrumenty i sizing niż w Lab | Dostępne zapisy DEMO zgodne księgowo | Nie potwierdzono porównywalności z dawnym badaniem; wymagamy zgodności STRAT/DATA/EXP/kodu |
| W-5, s. 9: stary autostart i dwa łączniki | Zidentyfikowano bieżący launcher i interpreter; 19 lokalnych modułów zgodnych | To nie audyt autostartu ani próba wyłącznego portu; nie zamykamy historycznego ustalenia |
| W-6, s. 9: zależność ścieżki stanu od sposobu startu | Bieżące ścieżki oraz zapis dostępne; odtwarzalność instalacji pozostaje otwarta | Wymagamy jawnej lokalizacji stanu i próby odtworzenia w przyszłym wdrożeniu |
| Ś-6, s. 10: przerwa po restarcie Windows | Punktowy odczyt działającego procesu | Brak dowodu ciągłości i działania strażnika; nie deklarujemy usunięcia problemu |
| Ś-7, s. 10: zmiany kodu w rundzie | Hashe krypto i ropy zgodne; analogicznego hasha indeksów brak w raporcie | Zamrożenie ma obejmować każdą badaną serię; wdrożenie tej zasady w indeksach niepotwierdzone |
| Ś-8, s. 11: mała próba krypto, koszty jako założenia | Więcej zapisów, ale nadal mała próbka; pełna historia niepotwierdzona | Osobno jakość danych, poprawność wykonania i ocena strategii |
| N-5, s. 11: brak autora akcji | Wcześniejsze LITE nadal bez rozstrzygniętego przypisania; nie dowodzi tego samego błędu | EVENT musi wskazywać autora/proces; pełne przypisanie historyczne pozostaje zadaniem audytu |
| Pozostałe: testy, Telegram, repo, kopie, instrukcje | E-09 nie odbiera wszystkich dawnych napraw | 785 testów to wynik historycznego audytu. Nie uruchamiano ich ani zaleceń usuwania/konfiguracji w v0.2 |

Zalecenia audytu dotyczące `t > 2`, liczby transakcji, wyłączania restartów systemu i konkretnych parametrów rund zachowujemy jako treść źródła. Wymagania jakości dokumentacji nie są zgodą na wykonanie tych operacji.

### Arkusz Vantage — co jest znane i czego brakuje

SRC-028 ma jeden widoczny arkusz `Koszty i Spready`, siedem wierszy danych, bez formuł, komentarzy, odnośników źródłowych, nazwanych zakresów ani zewnętrznych łączy. W nagłówku C1 jest gwiazdka bez objaśnienia w arkuszu. Poniższe liczby są **wartościami z pliku, nie zweryfikowaną taryfą Vantage**.

| Komórki | Wartości/konwencja z arkusza | Ograniczenie zastosowania |
|---|---|---|
| B2:E3 | Forex: szacunkowo 12/7 USD i 87,5/43,5 USD za lot; E2 wspomina 6 USD prowizji za pełny obrót | Potrzebne symbol, waluta rachunku, spread z czasem i osobno prowizja; ustalić, co zawiera suma |
| B4:E5 | Złoto: 20/9 USD przy 100 oz; ropa: 30/15 USD przy 1000 baryłek | Potwierdzić mnożnik i specyfikację konkretnego symbolu; nie przenosić wprost między kontraktami |
| B6:E6 | Indeks: 1,5/0,8 USD przy mnożniku 1 USD | Ogólna nazwa S&P500 nie identyfikuje symbolu ani warunków danego rachunku |
| B7:E7 | Jedna akcja; 6/6 USD; opis minimum 6 USD za jedną stronę | Minimum za zlecenie nie jest stałym kosztem każdej akcji; rozdzielić koszt wejścia i wyjścia |
| B8:E8 | BTC: koszt „zmienny”; opis swapu codziennie | Brak liczbowego profilu spreadu, prowizji i finansowania; nie podstawiać zera |

DATA dla właściwego testu musi zawierać: dostawcę i dokładny symbol, rachunek/serwer/podmiot właściwy dla dowodu kosztu, walutę, wielkość kontraktu, tick size/value, jednostki spreadu, prowizję jednej strony lub pełnego obrotu, minima, finansowanie i moment naliczenia, poślizg/model realizacji, datę obowiązywania oraz źródło weryfikacji. W eksporcie dokumentów wystarczy identyfikator środowiska bez danych dostępowych. Założenie i zweryfikowany koszt to oddzielne statusy. Rozbieżności między SRC-022 a SRC-028 rozstrzygamy dla konkretnego symbolu i okresu, nie przez wybór niższej liczby.

### Dodatkowe rozbieżności nowych materiałów

| ID | Treść materiału | Rozstrzygnięcie v0.2 |
|---|---|---|
| R-15 | SRC-020 i SRC-026: desk badawczy bez zleceń | Zgodne z granicą Lab; nie usuwa istniejącego osobnego Wykonawcy DEMO |
| R-16 | SRC-020: Market Scanner; SRC-027: Execution Planner | Scanner analizuje instrumenty, Scout poszukuje strategii; plan wykonania nie jest wykonaniem zlecenia |
| R-17 | SRC-023–SRC-027: 1%, 2%, 10 000/100 000 USD, 30 dni i R/R 1:2 | Przykładowe parametry. Nie aktualizują polityki ryzyka, budżetu ani terminu inkubacji Astry |
| R-18 | SRC-021: siedmiu agentów biznesowych i zatrzymanie po każdym kroku | Inspiracja organizacji; brak zmiany priorytetów i zasad współpracy Karola. Marketing i sprzedaż nie sterują strategiami |
| R-19 | Przewodniki: nazwy modeli, plany subskrypcji i instrukcje instalacji | Twierdzenia źródłowe; wybór technologii wymaga osobnej weryfikacji przed wdrożeniem. Nie wdrażamy nowego stosu z promptu |
| R-20 | SRC-024: ręczny paper trading i projekt dashboardu z mockiem | Nie jest dowodem działającej ciągłej symulacji. Mock i edukacyjny zapis muszą być jednoznacznie oznaczone |
| R-21 | SRC-025 powtarza SRC-020 | Jeden materiał wiedzy, dwie ścieżki pliku, identyczny hash |
| R-22 | SRC-022 i SRC-028: koszty oraz historyczne parametry | Datowane źródła do weryfikacji; brak automatycznej podmiany wartości w Astra Pro |

## 8. Aktualizacja i następne decyzje

Po istotnej decyzji aktualizujemy odpowiednie karty, wpis DEC i tabelę zależności. Stan techniczny otrzymuje datowany dowód. Materiał zmieniony przez autora dostaje nową wersję; poprzedni hash i wynik badania pozostają. Katalog nie przenosi prywatnych kluczy ani danych dostępowych.

Aktualny punkt wejścia: [START](START.md). Pełne zakresy: [struktura AstralJet](ASTRALJET_STRUKTURA_v0.2.md) i [ASTRA Pro Trading Lab](ASTRA_PRO_TRADING_LAB_v0.2.md).
