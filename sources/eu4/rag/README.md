# Wspólna paczka wiedzy do RAG

[chunks.jsonl](chunks.jsonl) zawiera 698 fragmentów po polsku dla EU4 1.37 bez modów. Z lokalnej instalacji 1.37.5.0 pochodzą 31 kart cen bazowych, 25 kart kosztów i czasu budowy oraz 329 kart jednostek lądowych i okrętów. Przy budynkach i jednostkach podano poziom technologii, jeśli pliki technologii jawnie wskazują odblokowanie. W paczce jest także 211 kart mechanik, 81 notatek z sześciu filmów, 12 notatek o Polsce i 9 notatek strategicznych. Wersje poszczególnych źródeł są zapisane przy fragmentach.

Każda linia pliku UTF-8 to jeden obiekt JSON. W swoim RAG indeksuj `text`, użyj `chunk_id` jako klucza i zachowaj `title`, `source_type`, `game_version` oraz odsyłacze do cytowania.

| Rodzaj fragmentu | Odsyłacze |
| --- | --- |
| Film | `citation_url`, `start_s` i `end_s` |
| Fakt z instalacji gry | `source_type=game_fact`, ścieżka, wiersze i `game_refs` dla powiązanych definicji |
| Notatka o Polsce lub karta mechaniki | `game_refs` ze ścieżkami i symbolami w grze |
| Strategia | `sources` z wersjami, adresami i pochodzeniem materiału |

Paczka zawiera wspólne opracowania dostępne z repozytorium. Pełny indeks z regułami, wydarzeniami, historią startową i siecią handlu powstaje z własnej instalacji EU4. [Instrukcja uruchomienia i schemat](../../../docs/eu4-workflow.md)

## Odtwórz eksport

Do użycia paczki wystarczy zwykły setup lub budowa z opcją `--shared-only`. Na komputerze z już przygotowaną starszą bazą poniższe polecenie tworzy nowy indeks SQLite, który można wskazać przez `--db`. Użyj nowego folderu wyjściowego.

~~~powershell
python sources/eu4/mechanics/build_index.py --shared-only --output .eu4/rag-export
~~~

Aby ponownie wyciągnąć fakty z oryginalnych plików, wskaż instalację EU4 1.37.5.0 i skopiuj wynik do paczki.

~~~powershell
python sources/eu4/mechanics/build_index.py --shared-only --facts-game-dir "D:/Steam/steamapps/common/Europa Universalis IV" --output .eu4/rag-from-game
Copy-Item .eu4/rag-from-game/chunks.jsonl sources/eu4/rag/chunks.jsonl
~~~
