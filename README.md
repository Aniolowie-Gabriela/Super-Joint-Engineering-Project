# EU4 Campaign Harness

Lokalny serwer MCP dla Europy Universalis IV. Klient czatu może odczytać stan kampanii, porównać zapisy, otworzyć zakładkę państwa oraz pokazać graczowi widoczny element kursorem. Serwer komunikuje się przez standardowe wejście i wyjście (stdio). Można go podłączyć do klienta MCP niezależnie od Atlasa.

## Uruchomienie na Windows

1. Zainstaluj Git i Pythona 3.14. W folderze repozytorium utwórz środowisko i zainstaluj zależności:

   ```powershell
   py -3.14 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. Do połączenia z działającą grą potrzebne są EU4 1.37.5, Anvil i wtyczka Tongs 0.37.0. W ustawieniach Tongs włącz **Open the pipe**. Wystarczy `enabled = true` oraz `input = false`; weryfikowana nawigacja po oknie korzysta z Windows. Po instalacji wtyczki uruchom ponownie grę. [Instalacja Anvil](https://anvil.happydwarf.dev/docs/install/) · [Tongs](https://github.com/happy-dwarf-team/tongs/tree/v0.37.0)

3. W kliencie MCP dodaj serwer stdio o nazwie `eu4_campaign`. Jako `command` podaj pełną ścieżkę do `.venv\Scripts\python.exe`; w `args` umieść osobno `-B` oraz pełną ścieżkę do `sources\eu4\advisor\server.py`. W PowerShell poniższe polecenia wypisują obie ścieżki:

   ```powershell
   (Resolve-Path .\.venv\Scripts\python.exe).Path
   (Resolve-Path .\sources\eu4\advisor\server.py).Path
   ```

Serwer szuka instalacji Steam i folderów zapisów gracza. Możesz wskazać własne ścieżki przez `--game-dir` i powtarzalny `--save-dir`. Opcjonalny `--rakaly` wskazuje lokalny program do dekodowania binarnych zapisów Ironman. Odczyt ZIP z kompresją Zstandard wymaga Pythona 3.14 lub nowszego. Opcjonalny `--db` włącza wyszukiwanie mechanik w istniejącym indeksie SQLite projektu. [Rakaly](https://github.com/rakaly/cli/releases)

Do zrzutów okna potrzebujesz Windows 10 2004 lub nowszego i SDK .NET 8. Po pobraniu gałęzi przygotuj obsługę obrazu z głównego katalogu:

```powershell
dotnet build sources/eu4/advisor/capture -c Release
```

## Co można zrobić

| Polecenie gracza | Narzędzia MCP |
| --- | --- |
| „Spójrz na mój ekran. Co oznacza ta ikona?” | `eu4_ui_screenshot` zwraca jedną aktualną klatkę okna gry jako obraz JPEG. Klient musi przekazywać obrazy MCP do modelu obsługującego obraz. |
| „Jakim krajem gram i jaki jest dzień?” | `eu4_campaign_state`, `tongs_player` |
| „Kto kontroluje prowincje przy mojej armii?” | `eu4_map_units`, `eu4_map_neighbors`, `eu4_map_provinces`, `eu4_map_occupations` |
| „Z kim walczę i jakie mam rezerwy?” | `eu4_country_briefing`; przy danych z zapisu klient podaje plik i datę. |
| „Jakie wydarzenie mam teraz na ekranie i co robią jego opcje?” | `eu4_campaign_events`, `eu4_event_definition` |
| „Co zmieniło się pomiędzy dwoma zapisami?” | `eu4_save_list`, `eu4_save_compare`. Szczegółowe pola odczytują `eu4_save_find` i `eu4_save_read`. |
| „Pokaż, gdzie zaciąga się pożyczkę” | `eu4_ui_open_tab` otwiera `economy`; `eu4_ui_point` wskazuje `countryeconomyview/take_loan`. Wybór opcji pozostaje po stronie gracza. |

Zrzut obejmuje obszar gry w rozdzielczości okna, razem z mapą, otwartymi panelami i widocznymi podpowiedziami. Możesz mieć czat przed grą. Przy zminimalizowanej grze przywróć okno. Każde wywołanie pobiera jedną klatkę do pamięci i działa także po F9. Nazwy, teksty i położenie elementów UI są nadal dostępne przez `tongs_ui_tree`, `tongs_ui_find` i `tongs_cursor`. Pozostałe odczyty i opisy parametrów klient otrzymuje przez MCP `tools/list`.

## Sterowanie myszą

Podczas oprowadzania możesz przesuwać mysz. **F9 oddaje sterowanie graczowi**, również między wskazaniami. Po przejęciu nadal można zadawać pytania o kampanię. Aby wrócić do nawigacji, powiedz Lunie „wznów sterowanie”; klient wywołuje `eu4_ui_resume` na tę prośbę. Utrata aktywnego okna lub przytrzymany przycisk może zablokować konkretną czynność. Kliknięcie zakładki wymaga potwierdzenia, że pod kursorem znajduje się właściwy przycisk EU4.

Pierwsza operacja nawigacji rezerwuje F9 jako skrót Windows do końca sesji serwera. W jednej sesji pulpitu może z niego korzystać jeden klient sterujący. Jeśli skrót jest zajęty przez inny program lub klienta, harness informuje o konflikcie. Same odczyty nie rezerwują klawisza.

## Testy

Z głównego folderu repozytorium:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s sources/eu4/advisor -p "test_*.py"
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py"
```
