# Źródła kontekstu do Europa Universalis IV

Baza dla asystenta rozgrywki w EU4 1.37 bez modów. Lokalne dane gry pochodzą z wydania Steam 1.37.5.0 (Inca). Poradniki i artykuły mogą opisywać inne wersje oraz mieć własne wymagania DLC.

| Źródło | Zawartość |
|---|---|
| [Strategie i odsyłacze do wiki i Reddita](strategies-1.37.json) | Dziewięć polskich notatek o gospodarce na starcie, wojnach i unikaniu koalicji. Każda ma identyfikator, zastosowanie, ograniczenia oraz powiązane źródła. |
| [Poradniki wideo](videos.md) | Linki do filmów, tematy, wersje i dostępność napisów. |
| [Notatki i dane do RAG](video-notes/README.md) | Opracowania sześciu filmów z odsyłaczami do konkretnych minut, osobny przewodnik po Polsce i fragmenty do bezpośredniego indeksowania. |
| [Wspólna paczka do RAG](rag/README.md) | 313 gotowych fragmentów JSONL z kart, notatek i strategii. |
| [Mechaniki z lokalnej instalacji i narzędzie MCP](mechanics/README.md) | Generator indeksu, wyszukiwanie mechanik, klient Gemmy i test odpowiedzi z RAG. |
| [Dane instalacji Steam](game-data.md) | Wersja, zakres zweryfikowanego eksportu lokalnego oraz miejsca, w których gra definiuje reguły i stan startowy. |

## Artykuły przejrzane do lokalnej bazy

- [Trade, rewizja 176001](https://eu4.paradoxwikis.com/index.php?title=Trade&oldid=176001)
- [Land warfare, rewizja 175806](https://eu4.paradoxwikis.com/index.php?title=Land_warfare&oldid=175806)
- [Diplomacy, rewizja 176240](https://eu4.paradoxwikis.com/index.php?title=Diplomacy&oldid=176240)

Dodatkowe rewizje wiki, wątki Reddita i konkretne komentarze są w polu `sources` pliku strategii. Wersja docelowa notatki jest w `game_version`, a wersja podana przez źródło w `reported_game_version`. Przy indeksowaniu zachowaj oba pola oraz odsyłacze do źródeł. Dla twierdzeń zależnych od kampanii, patcha lub DLC podstawą weryfikacji jest lokalna wersja gry i jej zachowanie.

Publiczny katalog zawiera opracowania, metadane i odsyłacze. Pełne lokalne transkrypcje można odtworzyć indywidualnie z napisów wybranych filmów. Lokalny eksport danych można odtworzyć z własnej instalacji EU4 w odpowiedniej wersji.
