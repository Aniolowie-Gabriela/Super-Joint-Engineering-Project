# Atlas EU4 2.0 preview · Pierwszy wieczór z Polską

Na tej gałęzi jest pierwsze demo głosowego doradcy dla Windows x64. Podczas kampanii Polską przytrzymaj **F8**, powiedz **„Co teraz?”** i puść klawisz. Luna ogląda okno EU4. Gdy rozpozna skarbiec, Atlas otacza go ramką i czyta krótką wskazówkę po polsku.

1. [Pobierz Atlas-Polska.exe dla Windows x64](https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project/releases/download/atlas-2.0.0-preview.1/Atlas-Polska.exe). Uruchom aplikację, wpisz swój klucz API OpenAI i kliknij **Włącz doradcę**. Aplikacja może też pobrać klucz ze zmiennej `OPENAI_API_KEY`.
2. Uruchom EU4 w trybie okienkowym bez ramek, wybierz Polskę i wejdź na mapę kampanii. Pozostaw Atlas w tle.
3. Przytrzymaj **F8** na czas pytania. Ramka pojawia się nad grą. Ostatnie pytanie, odpowiedź lub komunikat błędu odczytasz również w oknie Atlasu.

**Wymagania.** Windows 10 (wersja 2004 lub nowsza) albo Windows 11, mikrofon, internet i konto API z dostępem do modeli `gpt-transcribe` i `gpt-6-luna`. Do odsłuchu służy zainstalowany polski głos Windows SAPI. Jeśli brakuje głosu, odpowiedź pozostaje w oknie aplikacji. Koszt wywołań API ponosi właściciel klucza.

**Dane.** Atlas zbiera dźwięk podczas przytrzymania klawisza (do 20 s) i pobiera pojedynczy obraz aktywnego okna EU4 przy rozpoczęciu pytania. Wysyła nagranie do transkrypcji, a rozpoznane pytanie i obraz do Luny. Do kontroli aktualności oznaczenia porównuje dalsze klatki lokalnie. Wpisany klucz, obraz i nagranie są przechowywane przez aplikację w pamięci. Demo koncentruje się na wskazaniu skarbca; odczyt zapisów kampanii, otwieranie zakładek i poprzedni panel RAG stanowią osobne funkcje.

### Zbuduj demo ze źródeł

Na Windows x64 z .NET SDK 8 w katalogu repozytorium:

```powershell
dotnet publish tools/atlas2/Atlas2.csproj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:EnableCompressionInSingleFile=true -p:DebugType=None -o outputs/atlas2
.\outputs\atlas2\Atlas-Polska.exe
```

## Atlas EU4 0.3 · Lokalny asystent

Zadawaj po polsku pytania o rozgrywkę. Asystent korzysta z naszej wiedzy o EU4 1.37.5.0 i podaje źródła. Gemma działa na twoim komputerze.

## Aplikacja dla gracza na Windows x64

**[Pobierz instalator Atlas EU4 (.exe)](https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project/releases/download/eu4-operator-v0.3.0/Atlas-EU4-Setup-x64.exe)**. Uruchom go, kliknij **Instaluj**, a następnie otwórz **Atlas EU4** z menu Start. Instalacja obejmuje konto bieżącego użytkownika. Aplikację można usunąć z listy zainstalowanych aplikacji Windows.

### Wersja przenośna ZIP

1. [Pobierz paczkę dla Windows](https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project/releases/download/eu4-operator-v0.3.0/Asystent-EU4-Windows-x64.zip) i rozpakuj ją do jednego folderu.
2. Dwukrotnie kliknij **Uruchom-EU4.cmd**. W przeglądarce otworzy się lokalna aplikacja. **Wiedza o grze** zawiera 698 materiałów, które możesz przeszukiwać od pierwszego uruchomienia.
3. W **Czacie** wpisz pytanie, np. „Ile kosztuje warsztat?”. Do pierwszej rozmowy potrzebujesz Gemmy 4 E4B i zgodnej karty z miejscem na cały model. Jeśli brakuje Ollamy, uruchom **Przygotuj-model.cmd** z paczki. Pierwsze pobranie modelu wymaga internetu.

Kliknięcie źródła odpowiedzi otwiera materiał z wersją gry. Po przygotowaniu modelu rozmowa i wyszukiwanie działają lokalnie.

**Własne materiały.** Wybierz **Wiedza o grze → Moje źródła → Dodaj źródło**. Możesz wkleić notatkę, wczytać plik TXT lub Markdown w UTF-8 albo pobrać treść pojedynczej publicznej strony WWW. Sprawdź podgląd i wybierz **Zapisz źródło**. W tym samym miejscu możesz poprawić lub usunąć materiał.

**Historia rozmów.** W widoku **Czat** wybierz tytuł wcześniejszej rozmowy, żeby przeczytać odpowiedzi lub zadać kolejne pytanie. **Nowa rozmowa** zaczyna osobny temat. Rozmowy i własne materiały są zapisywane lokalnie w folderze `%LOCALAPPDATA%\AtlasEU4`.

**Sprawdzenie słabej odpowiedzi.** Przy odpowiedzi otwórz **Jak powstała odpowiedź?**. W wersji 0.3.0 przy pytaniach wymagających wyszukiwania zobaczysz kolejne strony notatek, zachowane dowody i powód zakończenia poszukiwań. Atlas może przeczytać do pięciu stron po trzy fragmenty i zmienić zapytanie, gdy brakuje konkretnej reguły. Porównaj zachowany tekst z tym, co podaje odpowiedź. Jeśli w przekazanym fragmencie jest prawidłowa liczba, a w odpowiedzi inna, rozbieżność powstała już po wyborze materiału. W historii możesz otworzyć treść źródła zachowaną w chwili odpowiedzi.

**Próba dla operatora.** W widoku **Wiedza o grze** wyszukaj „warsztat” i otwórz „Budowa • Warsztat”. Karta powinna pokazać 100 dukatów, 12 miesięcy i technologię administracyjną 6. W **Czacie** zapytaj „Ile kosztuje warsztat?”, a potem „A ile trwa jego budowa?”. Kliknij numer źródła i porównaj odpowiedź z kartą.

Paczka korzysta ze wspólnej bazy. Aby wskazać własny pełny indeks, ustaw w środowisku `EU4_RAG_DB` na ścieżkę do pliku `knowledge.sqlite3`. Katalogi `embedding-model` i `semantic` umieść obok tego pliku. Pełny indeks można zbudować z lokalnej instalacji EU4 przez `eu4.py setup --game-dir`. [Budowanie indeksu](docs/eu4-workflow.md)

## Zbuduj paczkę Windows z repozytorium

Na stanowisku budującym wydanie użyj Windows x64 i CPythona 3.14 x64. Polecenia uruchom w katalogu repozytorium. Pierwsze polecenie przygotowuje wspólną bazę i wektory.

~~~powershell
python eu4.py setup --no-model
.\.eu4\.venv\Scripts\python.exe -m pip install -r sources/eu4/mechanics/requirements-web.txt
.\.eu4\.venv\Scripts\python.exe tools/build-portable.py --data .eu4/shared --output outputs/Asystent-EU4-Windows-x64.zip
~~~

Instalator EXE buduje Inno Setup 6.7.4 z tej samej paczki. W PowerShellu z poleceniem ISCC dostępnym w PATH wykonaj:

~~~powershell
Expand-Archive outputs/Asystent-EU4-Windows-x64.zip outputs/installer-input
$payload = (Resolve-Path outputs/installer-input/Asystent-EU4).Path
$output = (Resolve-Path outputs).Path
ISCC "/DPayloadDir=$payload" "/O$output" tools/Atlas-EU4.iss
~~~

## Uruchom wersję wiersza poleceń ze źródeł

1. Zainstaluj Python 3.12 lub nowszy oraz Ollamę. Otwórz Ollamę. [Python](https://www.python.org/downloads/) · [Ollama dla Windows](https://docs.ollama.com/windows)
2. Pobierz repozytorium przez **Code → Download ZIP** i rozpakuj je lub użyj polecenia poniżej.
3. Otwórz [Przygotuj-EU4.cmd](Przygotuj-EU4.cmd). Naciśnij Enter, aby użyć wspólnej wiedzy. Jeśli chcesz dołączyć reguły i historię z własnej instalacji gry, wpisz jej folder. Przy pierwszym uruchomieniu pobierane są zależności i modele.
4. Otwórz [Zapytaj-EU4.cmd](Zapytaj-EU4.cmd) i wpisz pytanie, np. „Po co mi kupcy?”.

~~~powershell
git clone https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project.git
cd Super-Joint-Engineering-Project
~~~

[Schemat działania i odtwarzanie testu](docs/eu4-workflow.md) · [Przykładowa rozmowa o kampanii Polską](docs/eu4-polska-demo.md) · [Materiały do bazy](sources/eu4/README.md)

## Agent skills

[taf4you2/agent-skills](https://github.com/taf4you2/agent-skills) is included as a Git submodule in `agent-skills/`.

To use the agent skills, clone the project with the submodule:

```bash
git clone --recurse-submodules https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project.git
```

For an existing checkout, fetch the pinned version:

```bash
git submodule update --init --recursive
```

To update to the latest upstream `main`, then record the new version:

```bash
git submodule update --remote agent-skills
git add agent-skills
git commit -m "chore: update agent-skills submodule"
```

See [the agent-skills README](agent-skills/README.md) for skill descriptions and setup instructions.
