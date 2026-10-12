# HEGEMONIKON / SENECA — mapa startowa

Data raportu: **3 października 2026, Europe/Warsaw**. Zakres: dostępna sesja Codex, zapisane projekty, wybrane lokalne aplikacje oraz osiem prób odczytu profilu integracji. Status: **pierwszy etap wykonany; pełna inwentaryzacja finansowa i odbiór przepływów pozostają otwarte**.

## Co wynika z materiału i co wykonano

Przeczytano wszystkie 5 stron `C:\Users\karol\Downloads\HEGEMONIKON_SENECA_Playbook_v1.pdf`. Playbook opisuje wspólny system strategii, marketingu, sprzedaży, eksperymentów i odzyskiwania aktywów. Proponuje rozpoczęcie od realnej mapy stacku przed projektem dashboardu.

Polecenie Karola „go” potraktowano jako rozpoczęcie pracy od sprawdzenia stanu i przygotowania lokalnego pakietu. Prompty, delegowanie i harmonogram zapisane w PDF są materiałem do projektu systemu; nie uruchomiono ich automatycznie. Raport nie ustanawia nowego mandatu handlowego ani nowej architektury Astry.

## Fakty potwierdzone teraz

| Obszar | Wynik | Co ten wynik potwierdza |
|---|---|---|
| Projekty w aplikacji | 24 wpisy: 12 lokalnych, 12 ChatGPT | Projekty zapisane w aplikacji; nie ich stan biznesowy |
| Lokalizacje lokalne | 11 różnych ścieżek po normalizacji wielkości liter | Dwa wpisy AI-Voice-Receptionist-cz wskazują ten sam katalog |
| Git | 6 lokalnych ścieżek znajduje się w repozytorium; 5 ma commit | Jeden projekt dziedziczy repo katalogu nadrzędnego bez pierwszego commita |
| Pluginy Codex | 60 wpisów z `enabled=true` w konfiguracji | Konfigurację; nie skuteczność wszystkich pluginów ani dostęp do ich kont |
| Lokalne serwery MCP | 5 skonfigurowanych | `node_repl`, `GitKraken`, `Memory`, `magic`, `trader-dev`; zdrowia wszystkich nie testowano |
| Narzędzia sesji | 1084 unikalne nazwy | Funkcje udostępnione w tej sesji; jedna funkcja może należeć do kilku pluginów |
| Profile integracji | 6 odczytów udanych, 2 nieudane | Dostęp do danego odczytu profilu; nie pełny przepływ produkcyjny |
| Aplikacje Windows | 10 pasujących wpisów w trzech kluczach Uninstall | Wybraną część aplikacji; pominięto Store/AppX, portable i inne urządzenia |
| Automatyzacje lokalne | Brak katalogu `.codex/automations` | Brak konfiguracji w tej lokalizacji; automatyzacje chmurowe nie zostały wyliczone |

Źródła: odpowiedzi `list_projects`, `list_threads`, katalog narzędzi sesji, odczyty profili, wybrane pola `config.toml`, lokalny Git i rejestr Windows. Dowody oraz identyfikatory znajdują się w `dowody_sesji.json`. Plik jest przeznaczony do użytku wewnętrznego; zawiera identyfikatory kont i ścieżki projektów.

## Konta i plany

| Integracja | Stan odczytu | Plan i ograniczenia ujawnione przez profil | Brakujące dane |
|---|---|---|---|
| GitHub | Profil odczytany: AurumetaclubDAO | Profil nie zwraca abonamentu | Dostęp do konkretnych prywatnych repo i uprawnienia zapisu |
| Google Drive | Profil odczytany | Plan nie został zwrócony | Pojemność, koszt, zakres dostępu do konkretnych plików |
| Figma | Profil odczytany | Jedna zwrócona pozycja: Starter, seat View, rola admin | Praktyczny odbiór edycji, limit operacji i ewentualne inne konta |
| Higgsfield | Profil odczytany | Brak planu i salda w odpowiedzi | Koszt, kredyty, zakres praw do zasobów i publikacji |
| HeyGen | Profil odczytany | `billing_type=subscription`, `plan=free`; pozostałe kredyty `null` | Dostępne kredyty pozostają nieznane, nie zerowe |
| Windsor.ai | Profil odczytany | `plan_id=FREE`, `plan_name=Free`, `is_paid=false` | Limity i dostęp do konkretnych źródeł danych |
| Gmail | Błąd wewnętrzny podczas odczytu | Nieustalony | Ponowny odczyt lub stan połączenia |
| Google Calendar | Błąd wewnętrzny podczas odczytu | Nieustalony | Ponowny odczyt lub stan połączenia |

Błąd profilu Gmail/Calendar nie dowodzi braku konta lub autoryzacji. Nie odczytywano korespondencji ani wydarzeń. Koszt miesięczny stacku pozostaje **nieustalony**; obecność pluginu nie oznacza opłaconego planu. Nie przypisano wszystkim pozycjom kosztu 0 zł.

## Mapa możliwości do sprawdzenia

Poniższe zastosowania są propozycjami wynikającymi z opisu dostępnych narzędzi. Odbiór wymaga przejścia rzeczywistego wejścia przez przepływ i sprawdzenia końcowego wyniku.

| Potrzeba | Dostępne elementy | Najmniejszy dowód działania |
|---|---|---|
| Strategia i priorytety | Codex/ChatGPT, pliki lokalne, Pages, Notion | Jedna karta decyzji z danymi, wynikiem i właścicielem |
| Marketing | Research web/Exa, Higgsfield, HeyGen, Figma, narzędzia reklamowe | Jeden prawdziwy temat → materiał → zatwierdzona dystrybucja → zapis pomiaru |
| Sprzedaż | Google Contacts, arkusze, Gmail, narzędzia stron i CRM/DB | Jeden zweryfikowany lead → kwalifikacja → zapis CRM; wysyłka wymaga konkretnego zlecenia |
| Kod i produkty | Codex, GitHub, Lovable, Supabase, Vercel, Sites, Render, Replit | Zmiana w wybranym istniejącym repo → właściwy test → działający rezultat |
| Opportunity Radar | Research web/Exa, lokalna karta hipotezy | Sygnał ze źródłem, koszt testu, czas do dowodu i decyzja WATCH/TEST/BUILD/SELL |
| Asset Factory | Repo, pliki lokalne, Drive/Pages | Aktywum z lokalizacją, pochodzeniem, prawami użycia i przykładem ponownego użycia |
| Pomiar i koszty | Windsor.ai, Markifact, arkusze, rejestr faktur | Jeden rzeczywisty rekord kosztu i wynik przypięty do projektu |

Gmail i Calendar wymagają wyjaśnienia błędu profilu przed uzależnieniem od nich operacji. Skonfigurowany Memory MCP nie był odczytywany ani aktualizowany. Dziennik projektu w tym pakiecie nie zmienia pamięci asystenta.

## Nakładanie się i konkretne problemy porządku

1. **Vercel:** trzy włączone wpisy konfiguracji: `vercel@openai-curated`, `vercel@claude-plugins-official`, `vercel-plugin@plugins-cli`. Propozycja: porównać pokrycie jednego istniejącego projektu i wybrać domyślną ścieżkę obsługi. Nie ma jeszcze podstaw do usunięcia którejkolwiek.
2. **Supabase, GitHub, Adobe:** po dwa włączone wpisy konfiguracji. Mogą różnić się zakresem narzędzi, umiejętności lub kont; nakładanie nazw nie dowodzi pełnego duplikatu.
3. **Recepcjonista AI:** trzy fizyczne repozytoria z tym samym remote `SuperAI-maker/ai-voice-receptionist-cz`, różnymi commitami i gałęziami. Katalog główny użytkownika: `codex/project-stabilization`, lokalnie ahead 4. Katalog Documents: `codex/voice-router-pilot`. Katalog Documents/GitHub: `main`, lokalnie ahead 27 / behind 54. Wszystkie mają zmiany śledzonych plików. Dwa zapisane projekty Documents wskazują tę samą fizyczną ścieżkę. Wybór repo roboczego i połączenie zmian wymagają osobnego zakresu; nie łączono historii.
4. **Trading:** zapisany projekt znajduje się pod repo `C:/Users/karol/Documents/Claude/Projects`, które nie ma pierwszego commita. Oznaczenie Git w aplikacji nie oznacza samodzielnego repo Trading.
5. **Automatyzacje:** w widocznej próbce czatów są tytuły dotyczące monitoringu. Sam tytuł nie dowodzi aktywnego harmonogramu; stan chmurowych automatyzacji pozostaje nieustalony.

Wskaźniki ahead/behind dotyczą lokalnie zapisanych referencji `origin`; nie wykonano fetch i nie potwierdzają aktualnego stanu GitHub.

## Relacja z AstralJet

`D:\Astra Jet` pozostaje zatwierdzonym katalogiem Astry. Sprawdzony Git: gałąź `main`, HEAD `c14945af80633d86c1f8ad3bb342af8cea92f9d4`, lokalnie ahead 1 względem `origin/main`, zmieniony `.gitignore` i liczne istniejące pliki nieśledzone. Nie wykonano push ani stage.

HEGEMONIKON obejmuje wiele projektów. Z tego raportu nie wynika decyzja o przekształceniu panelu handlowego Astry w globalny system biznesowy. Przed wyborem dashboardu należy porównać istniejące centrum i wymagania przekrojowe. Rozdział ASTRA Pro / Wykonawca oraz zasady DEMO/LIVE pozostają obowiązującym kontekstem pracy. Bieżącej telemetrii MT5 i strategii nie audytowano.

## Proponowane trzy wyniki następnego sprintu

To propozycje do wyboru priorytetu, nie zlecenia automatycznej publikacji lub wysyłki.

| Tor | Wynik | Dlaczego teraz | Definicja DONE |
|---|---|---|---|
| MONEY | Wybrać jedną ofertę i jeden rynek dla pierwszego testu sprzedaży | Stack sam nie wskazuje najwyższej wartości biznesowej | Oferta, cena, odbiorca, istniejący materiał, sygnał potrzeby i metryka wyniku zapisane w karcie |
| BUILD | Uzupełnić koszt i limit 10 narzędzi używanych w wybranym przepływie | Teraz nie ma podstaw do oceny duplikatów finansowych | Plan, miesięczny koszt, kredyty/limity, konto oraz datowany dowód dla każdej pozycji |
| DISTRIBUTE | Wybrać jeden istniejący materiał i przygotować pakiet dystrybucji | Pozwala testować marketing na realnym aktywie | Źródło, CTA, kanał, pomiar i gotowy pakiet; publikacja rozliczona osobno |

Pierwszy ruch na 10 minut: wskazać jedną ofertę do MONEY i wpisać jej fakty do karty sprintu. Dziś nie kupować kolejnego narzędzia na podstawie samej luki w konfiguracji; najpierw sprawdzić istniejący przepływ.

## Plan pracy po mapie startowej

Harmonogram 14 dni z PDF pozostaje propozycją kolejności. Obecny pakiet daje część dowodów dla dni 1–3; nie jest odbiorem dni 1–2 w pełnym zakresie, bo brakuje kosztów, pozostałych kont i części automatyzacji.

| Następny etap | Warunek wejścia | Wynik do odbioru |
|---|---|---|
| Dokończenie inventory i kosztów | Konkretne konta/plany lub faktury | Pokrycie stacku z datą, brakami i kosztami |
| Capability map | Jeden wybrany proces biznesowy | Mapa narzędzi, potwierdzone duplikaty, rekomendacje KEEP/TEST/REMOVE/UPGRADE |
| Wybór Command Center | Projekty, KPI i model danych ustalone | Konkretny projekt wykorzystania istniejącego centrum lub uzasadniona alternatywa |
| Marketing i Sales MVP | Oferta, ICP, kanał i miernik ustalone | Jeden kompletny przepływ z realnym wynikiem i dowodem |
| Asset Factory i Radar | Pierwszy zakończony sprint | Rejestr aktywów i jedna hipoteza z kryterium testu |
| Automatyzacje i stress test | Ręczny przepływ działa, zakres harmonogramu wybrany | Test powtórzeń, awarii, kosztu, końcowego wyniku i powiadomień |

## Pakiet

- `dowody_sesji.json` — sprawdzone odczyty, zakres i identyfikatory; materiał wewnętrzny.
- `projekty.csv` — wszystkie 24 wpisy aplikacji, zachowane oryginalne nazwy.
- `repozytoria.csv` — 11 lokalnych ścieżek po deduplikacji, stan Git.
- `pluginy.csv` — 60 wpisów konfiguracji pluginów.
- `narzedzia.csv` — katalog funkcji z powiązaniami do pluginów; powiązań jest więcej niż unikalnych funkcji.
- `aplikacje.csv` — wybrane wpisy Windows.
- `karty_narzedzi.csv` — plan, koszt, limity, dowód i proponowany status przeglądu grup narzędzi.
- `KARTA_SPRINTU.md` — szablon wyniku MONEY / BUILD / DISTRIBUTE i odzyskiwania aktywów.

Nie uruchomiono marketingu, wysyłek, płatnych generacji, nowych harmonogramów, instalacji, publikacji ani zmian wykonawców. Pakiet nie potwierdza sprzedaży, przychodu, wartości aktywów ani ukończenia całego systemu v1.
