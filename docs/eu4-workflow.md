# Jak działa lokalny asystent EU4

Po sklonowaniu repozytorium możesz korzystać z naszych kart mechanik, notatek z poradników i strategii. Wspólną wiedzę z Git instalator zamienia na lokalną bazę SQLite i indeks wyszukiwania. Wpisanie folderu własnego EU4 dodaje reguły, stan startowy z historii gry, dokładne numery wierszy i sieć handlu. Karty zweryfikowano dla **EU4 1.37.5.0 bez modów**. Własna instalacja pozwala odczytać dane w jej rzeczywistej wersji.

~~~mermaid
flowchart LR
    R["GitHub<br/>Nasze karty, strategie i notatki"] --> P["Przygotuj-EU4"]
    G["Twoja instalacja EU4<br/>opcjonalnie"] --> P
    P --> B["Lokalna wiedza<br/>SQLite + indeks wyszukiwania"]
    Q["Zapytaj-EU4<br/>Twoje pytanie"] --> S["Wyszukiwanie źródeł"]
    B --> S
    S --> K["Sprawdzona karta dla prostego pytania"]
    S --> M["Gemma czyta do 3 nowych fragmentów"]
    M --> E["Zachowuje przydatne fragmenty ze źródłami"]
    E -->|"kolejna strona lub inne zapytanie, łącznie do 5 stron"| S
    E -->|"wystarczające dowody, brak nowych notatek lub koniec limitu"| F["Odpowiedź z zachowanych fragmentów"]
    E -->|"potrzebne dane z kampanii"| F
    K --> A["Odpowiedź po polsku + źródła"]
    F --> A
    B --> C["MCP<br/>źródła dla innych aplikacji"]
~~~

W aplikacji „strona” oznacza partię wyników z lokalnej bazy. Po zmianie zapytania Atlas może znaleźć kolejne materiały ze wspólnej bazy i z własnych notatek gracza. Każda przeczytana strona zużywa jeden z pięciu kroków. Kolejne wywołanie modelu dostaje wybrane wcześniej dowody i nową stronę. Pozwala to pracować w domyślnym oknie 4096 tokenów. Gdy brakuje informacji o stanie kampanii, Atlas może poprosić o konkretną informację. W panelu **Jak powstała odpowiedź?** można porównać odczytane fragmenty z tymi zachowanymi do odpowiedzi.

## Którą wiedzę możesz udostępnić

Wspólna wersja powstaje z tych samych opracowań dla każdej osoby, która uruchomi przygotowanie z tego samego commitu. Do uruchomienia tej wersji wystarczy repozytorium, Python i lokalna Ollama. Pełną wersję każdy może zbudować z folderu własnej gry. Jeżeli masz już gotową bazę i chcesz jej użyć z tym kodem, wskaż plik SQLite przez `--db`. Do wyszukiwania wektorowego zachowaj obok niego katalogi `semantic/` i `embedding-model/`.

Komputer pobiera zależności, Gemmę i model wyszukiwania przy przygotowaniu. Pytania trafiają do Gemmy przez `localhost`. Asystent korzysta z treści pytania oraz przygotowanych źródeł, więc opisz stan swojej kampanii w treści pytania.

## Polecenia równoważne launcherom

Uruchom Ollamę przed wykonaniem poleceń. Dane i środowisko Pythona powstają w ignorowanym przez Git katalogu `.eu4/`. Ponowne przygotowanie może dokończyć przerwane pobranie lub budowę indeksu. Zmienioną wersję własnej gry możesz zindeksować do nowego katalogu poleceniem z dokumentacji mechanik. [Dokumentacja mechanik](../sources/eu4/mechanics/README.md)

~~~powershell
# Wspólna wiedza z repozytorium
python eu4.py setup

# Pełne źródła z twojej instalacji, zamiast poprzedniego polecenia
python eu4.py setup --game-dir "C:/Twoja biblioteka/steamapps/common/Europa Universalis IV"

# Rozmowa lub jedno pytanie
python eu4.py ask
python eu4.py ask "Po co mi kupcy?"

# Istniejąca baza
python eu4.py ask --db "C:/Dane/EU4/knowledge.sqlite3" "Jak zacząć Polską?"
~~~

Domyślnie asystent otworzy pełną bazę, jeśli została przygotowana, a w przeciwnym razie wspólną. Po przygotowaniu możesz podłączyć tę samą bazę w aplikacji z obsługą MCP. Wybierz odpowiednią ścieżkę `.eu4/game/knowledge.sqlite3` lub `.eu4/shared/knowledge.sqlite3` i użyj Pythona z `.eu4/.venv/Scripts/python.exe`. [Konfiguracja MCP i narzędzia](../sources/eu4/mechanics/README.md#podłącz-źródła-w-aplikacji-obsługującej-mcp)

## Odtwórz próbę

Próba kampanii Polską używa lokalnej bazy z plikami gry, kartami, indeksowaniem wektorowym i punktowo zebranymi artykułami oraz Gemmy 4 E4B na lokalnym backendzie llama.cpp. Zapis zachowuje wszystkie odpowiedzi i wskazane źródła. [Próba kampanii Polską](eu4-polska-demo.md)

Wcześniejsza próba prostych pytań używała przygotowanej w ten sam sposób pełnej bazy. Poniższe polecenie uruchamia jej 25 pytań. Wynik ocenia się według klucza z pliku. Raport zapisuje odpowiedzi, źródła, czasy i sumy kontrolne kodu oraz danych. Zakres danych oraz backend wpływają na odpowiedzi. [25 pytań z kluczem](eu4-benchmark-questions.json)

~~~powershell
.\.eu4\.venv\Scripts\python.exe sources/eu4/mechanics/evaluate.py --db .eu4/game/knowledge.sqlite3 --url http://127.0.0.1:11434 --questions docs/eu4-benchmark-questions.json --output wyniki-eu4.json
~~~

### Backend użyty podczas próby na Radeonie

Skrypt uruchamia serwer używający GPU ROCm, z kontekstem 4096 i budżetem 256 tokenów rozumowania. Potrzebuje PowerShell 7, instalacji Ollamy z dołączonym serwerem llama.cpp i bibliotekami ROCm oraz pobranej Gemmy 4 E4B. Jeśli modele Ollamy są na innej ścieżce, użyj parametru `-ModelsDirectory`. [Skrypt ROCm](../tools/Start-Gemma-ROCm.ps1)

W pierwszym terminalu uruchom serwer i pozostaw okno otwarte na czas rozmowy.

~~~powershell
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File ./tools/Start-Gemma-ROCm.ps1
~~~

W drugim terminalu zadaj pytanie. Tych samych zmiennych i adresu możesz użyć przy uruchamianiu testu.

~~~powershell
$env:EU4_LLM_BACKEND = 'llama.cpp'
python eu4.py ask --url http://127.0.0.1:11437 "Po co mi kupcy?"
~~~

Modele używane przy przygotowaniu to [Gemma 4 E4B z biblioteki Ollamy](https://ollama.com/library/gemma4:e4b) oraz [multilingual E5 small, eksport ONNX](https://huggingface.co/Xenova/multilingual-e5-small/commit/761b726dd34fb83930e26aab4e9ac3899aa1fa78).
