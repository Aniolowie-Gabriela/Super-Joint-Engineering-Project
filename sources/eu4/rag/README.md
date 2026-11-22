# Wspólna paczka wiedzy do RAG

[chunks.jsonl](chunks.jsonl) zawiera 313 gotowych fragmentów po polsku dla EU4 1.37 bez modów. W paczce jest 211 kart mechanik sprawdzonych dla 1.37.5.0, 81 notatek z sześciu filmów, 12 notatek o Polsce opartych na plikach gry i 9 notatek strategicznych. Wersje poszczególnych źródeł są zapisane przy fragmentach.

Każda linia pliku UTF-8 to jeden obiekt JSON. W swoim RAG indeksuj `text`, użyj `chunk_id` jako klucza i zachowaj `title`, `source_type`, `game_version` oraz odsyłacze do cytowania.

| Rodzaj fragmentu | Odsyłacze |
| --- | --- |
| Film | `citation_url`, `start_s` i `end_s` |
| Notatka o Polsce lub karta mechaniki | `game_refs` ze ścieżkami i symbolami w grze |
| Strategia | `sources` z wersjami, adresami i pochodzeniem materiału |

Paczka zawiera wspólne opracowania dostępne z repozytorium. Pełny indeks z regułami, wydarzeniami, historią startową i siecią handlu powstaje z własnej instalacji EU4. [Instrukcja uruchomienia i schemat](../../../docs/eu4-workflow.md)

## Odtwórz eksport

W katalogu repozytorium użyj nowej ścieżki wyjściowej, a potem skopiuj wygenerowany JSONL do paczki.

~~~powershell
python sources/eu4/mechanics/build_index.py --shared-only --output .eu4/rag-export
Copy-Item .eu4/rag-export/chunks.jsonl sources/eu4/rag/chunks.jsonl
~~~
