# Zapytaj Gemmę o EU4

Po zbudowaniu bazy i uruchomieniu Ollamy wpisz pytanie. Odpowiedź zawiera numerowane źródła.

```powershell
python sources/eu4/mechanics/ask.py "Po co mi kupcy?"
```

Klient domyślnie korzysta z `gemma4:e4b`, włączonego rozumowania i kontekstu 4096. Przeszukuje bazę przed każdym pytaniem. Na krótkie pytanie odpowiada zwięźle i podpowiada, co zrobić w grze. Gdy potrzebujesz rozpiski, podaj polecenie „policz” lub dodaj przełącznik `--detailed`. Te same źródła można podłączyć w innej aplikacji przez MCP.

W próbie na Radeonie RX 7600S użyto `llama-server` dołączonego do Ollamy, z Gemmą E4B, wszystkimi wagami na GPU i oddzielnym budżetem 256 tokenów rozumowania. Backend należy wskazać w PowerShell przez `$env:EU4_LLM_BACKEND = 'llama.cpp'`, a adres lokalnego serwera przez `--url`. Wersja klienta z tym backendem umie rozszerzyć wyszukiwanie o angielskie nazwy gry.

## Zbuduj bazę ze swojej instalacji

```powershell
python sources/eu4/mechanics/build_index.py --game-dir "D:/Gry/Steam/steamapps/common/Europa Universalis IV" --output "outputs/eu4-gameplay/mechanics"
```

Uruchom skrypt w Pythonie 3.10 lub nowszym z SQLite FTS5. Ścieżkę instalacji można zmienić. W wybranym folderze pojawią się `knowledge.sqlite3` do wyszukiwania, `chunks.jsonl` do dowolnego indeksu RAG i `coverage.json` ze stanem pokrycia. Przy odświeżaniu użyj nowego folderu, żeby zachować poprzedni wynik. Inną lokalizację podaj klientowi przez `--db` lub `EU4_RAG_DB`.

Indeks przechowuje m.in. stałe bitew i dyplomacji, misje, wydarzenia, religie, instytucje, technologie, poddanych i handel. Zawiera również dane historyczne, sieć handlu i wybrane dane mapy. Każdy fragment lokalnych danych ma wersję, ścieżkę i zakres wierszy. Duże reguły zachowują identyfikator i warunki nadrzędne. Najważniejsze z nich uzupełniają [polskie karty mechanik](rules.json) z odsyłaczami do skryptów 1.37.5.0. Indeks dołącza [notatki z filmów](../video-notes/README.md) i [strategie z wiki i Reddita](../strategies-1.37.json).

Przez `--wiki-jsonl` możesz dołączyć wcześniej zapisane lokalne artykuły wiki. Skrypt odczytuje wyłącznie wskazany plik. W artykułach pozostają identyfikatory rewizji i odsyłacze.

Wyszukiwanie tekstowe SQL FTS5 uzupełnia słownik polskich nazw i identyfikatorów ze skryptów. Przy pytaniach o wynik konkretnej kampanii potrzebny jest opis stanu gry lub zapis. Historia prowincji opisuje stan z danych gry. Sieć handlu pochodzi z definicji węzłów, a sąsiedztwo lądowe wszystkich prowincji wymaga odczytu mapy rastrowej.

### Włącz wyszukiwanie po znaczeniu

Zainstaluj biblioteki z [pliku wymagań](requirements.txt). Umieść pliki `tokenizer.json` oraz `onnx/model_int8.onnx` z eksportu modelu E5 w katalogu `embedding-model` obok bazy z nazwami `tokenizer.json` i `model_int8.onnx`. Zbuduj wektory raz po każdej przebudowie bazy.

```powershell
python -m pip install -r sources/eu4/mechanics/requirements.txt
python sources/eu4/mechanics/semantic.py --db outputs/eu4-gameplay/mechanics/knowledge.sqlite3 --model-dir outputs/eu4-gameplay/mechanics/embedding-model --output outputs/eu4-gameplay/mechanics/semantic
```

Klient szuka po polsku i angielsku. Wektory reguł są liczone lokalnie na CPU, a dane historyczne wyszukiwane tekstowo. Gemma porządkuje kandydatów przed przygotowaniem cytowanej odpowiedzi. [Model multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small), [eksport INT8](https://huggingface.co/Xenova/multilingual-e5-small/tree/main/onnx)

## Podłącz źródła w aplikacji obsługującej MCP

W środowisku Pythona używanym przez hosta zainstaluj oficjalne SDK przez `python -m pip install mcp==1.30.0`. W konfiguracji hosta wskaż Python jako `command` oraz bezwzględne ścieżki do skryptu i bazy jako `args`.

```json
{
  "mcpServers": {
    "eu4": {
      "command": "C:/sciezka/do/python.exe",
      "args": ["D:/projekt/sources/eu4/mechanics/mcp_server.py", "--db", "D:/dane/knowledge.sqlite3"]
    }
  }
}
```

- `search_eu4(query, limit)` zwraca trafienia z tekstem i danymi źródła.
- `read_eu4_record(chunk_id)` otwiera wskazany fragment. `related` pokazuje odsyłacze po symbolach, a `other_sections` pozostałe fragmenty tej samej reguły.
- `find_eu4_symbol(symbol, family)` odczytuje definicję po identyfikatorze i rodzinie danych.
- `trace_eu4_flag(flag)` odróżnia zapis flagi, sprawdzenie i usunięcie, podając zakres, plik i wiersz.

Narzędzie korzysta z lokalnego pliku w trybie odczytu. Klient Gemmy przesyła kontekst do lokalnego modelu wyłącznie przez localhost. Wersja gry, warunki DLC i zakres dowodu pozostają widoczne w zwracanych danych. [Dokumentacja MCP](https://modelcontextprotocol.io/docs/learn/architecture), [Gemma 4 E4B](https://ollama.com/library/gemma4%3Ae4b)

## Porównaj odpowiedzi

```powershell
python sources/eu4/mechanics/evaluate.py --db outputs/eu4-gameplay/mechanics/knowledge.sqlite3 --url http://127.0.0.1:11434 --output wyniki-eu4.json
```

Test wykorzystuje sześć pytań z odpowiedzią sprawdzalną w plikach gry i jedno pytanie wymagające danych z kampanii. Każde pytanie jest wysyłane do tej samej Gemmy z kontekstem i bez niego. Dopasowanie wzorców wspiera ręczną ocenę odpowiedzi, kolejności warunków i zgodności cytowań.

W publicznym repozytorium jest kod i nasze opracowania. Baza z treścią plików instalacji powstaje lokalnie.

## Sprawdzone rozwiązania pokrewne

- `eu4-kb` rozwiązuje dwa oddzielne problemy. Tłumaczy skrypty i lokalizację gry na czytelne reguły, potem łączy wyszukiwanie wektorowe z BM25. Nasz indeks zachowuje surowy fragment i dołącza sprawdzone karty oraz odczyty jednostek i modyfikatorów. [Architektura eu4-kb](https://github.com/torisu233/eu4-kb#architecture)
- `eu4-indexer` udostępnia dokładny odczyt typu i klucza oraz graf odwołań. Nasze narzędzie śladu flagi rozróżnia ustawienie, sprawdzanie i usunięcie. Można tak prześledzić misję Je Maintiendrai, flagę `ned_ignore_tech_requirement_netherlands` i decyzję formowania. [eu4-indexer v0.4.0](https://github.com/Golden-Pigeon/eu4-indexer/releases/tag/v0.4.0)
- PlanRAG używa m.in. problemu lokowania kupców w EU4, aby odróżnić reguły mechaniki od danych koniecznych do decyzji w konkretnej sytuacji. W naszej bazie statyczna sieć handlu nie zna dochodu w zapisie kampanii. [PlanRAG, przykład EU4](https://openreview.net/pdf?id=4sajV6NEnWE)
