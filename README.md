# Lokalny asystent Europa Universalis IV

Zadawaj po polsku pytania o rozgrywkę. Asystent korzysta z naszej wiedzy o EU4 1.37.5.0 i podaje źródła. Gemma działa na twoim komputerze.

## Aplikacja dla gracza na Windows x64

**[Pobierz instalator Atlas EU4 (.exe)](https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project/releases/download/eu4-operator-v0.2.0/Atlas-EU4-Setup-x64.exe)**. Uruchom go, kliknij **Instaluj**, a następnie otwórz **Atlas EU4** z menu Start. Instalacja obejmuje konto bieżącego użytkownika. Aplikację można usunąć z listy zainstalowanych aplikacji Windows.

### Wersja przenośna ZIP

1. [Pobierz paczkę dla Windows](https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project/releases/download/eu4-operator-v0.2.0/Asystent-EU4-Windows-x64.zip) i rozpakuj ją do jednego folderu.
2. Dwukrotnie kliknij **Uruchom-EU4.cmd**. W przeglądarce otworzy się lokalna aplikacja. **Wiedza o grze** zawiera 698 materiałów, które możesz przeszukiwać od pierwszego uruchomienia.
3. W **Czacie** wpisz pytanie, np. „Ile kosztuje warsztat?”. Do pierwszej rozmowy potrzebujesz Gemmy 4 E4B i zgodnej karty z miejscem na cały model. Jeśli brakuje Ollamy, uruchom **Przygotuj-model.cmd** z paczki. Pierwsze pobranie modelu wymaga internetu.

Kliknięcie źródła odpowiedzi otwiera materiał z wersją gry. Po przygotowaniu modelu rozmowa i wyszukiwanie działają lokalnie.

**Własne materiały.** Wybierz **Wiedza o grze → Moje źródła → Dodaj źródło**. Możesz wkleić notatkę, wczytać plik TXT lub Markdown w UTF-8 albo pobrać treść pojedynczej publicznej strony WWW. Sprawdź podgląd i wybierz **Zapisz źródło**. W tym samym miejscu możesz poprawić lub usunąć materiał.

**Historia rozmów.** W widoku **Czat** wybierz tytuł wcześniejszej rozmowy, żeby przeczytać odpowiedzi lub zadać kolejne pytanie. **Nowa rozmowa** zaczyna osobny temat. Rozmowy i własne materiały są zapisywane lokalnie w folderze `%LOCALAPPDATA%\AtlasEU4`.

**Sprawdzenie słabej odpowiedzi.** Przy odpowiedzi otwórz **Jak powstała odpowiedź?**. Najpierw zobacz, czego szukał asystent. Potem sprawdź fragmenty użyte przy odpowiedzi i porównaj je z cytatami. Jeśli w przekazanym fragmencie jest prawidłowa liczba, a w odpowiedzi inna, rozbieżność powstała już po wyborze materiału. W historii możesz otworzyć treść źródła zachowaną w chwili odpowiedzi.

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
