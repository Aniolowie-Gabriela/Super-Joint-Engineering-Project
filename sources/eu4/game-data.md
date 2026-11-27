# Dane z instalacji Europa Universalis IV

Lokalny eksport powstał 20 listopada 2026 r. z wydania Steam EU4 1.37.5.0 (Inca, suma kontrolna gry `491d`, kompilacja Steam `15918133`). Obejmuje 8 684 pliki. Każdy wpis w archiwum sprawdzono względem pliku źródłowego za pomocą SHA-256. Dalsze sprawdzanie działania reguł wymaga uruchomienia gry z odpowiednimi DLC.

| Ścieżka wewnątrz instalacji | Co można sprawdzić |
|---|---|
| `common/defines.lua` | Stałe AI i rozgrywki, np. `AE_COALITION_THRESHOLD` ustawione na `-50` w tym wydaniu. Warunki członkostwa w koalicji mają także inne składowe. |
| `common/tradenodes/`, `common/tradegoods/`, `common/buildings/` | Sieć handlowa, towary i budynki. |
| `common/ideas/`, `common/units/`, `common/technologies/` | Idee, typy jednostek i technologie. |
| `history/countries/`, `history/provinces/`, `history/diplomacy/` | Stan startowy państw, prowincji i dyplomacji. |
| `missions/`, `events/`, `decisions/` | Misje, wydarzenia i decyzje wraz z warunkami, w tym `has_dlc`. |
| `localisation/`, `customizable_localization/` | Powiązania identyfikatorów z tekstem wyświetlanym w grze. |
| `map/` | Prowincje, teren i specjalne połączenia. `adjacencies.csv` opisuje specjalne krawędzie. Granice lądowe trzeba wyprowadzić z mapy prowincji. |
| `hints/`, `tutorial/`, `patchnotes` | Podpowiedzi, samouczek i zmiany między wydaniami. |
| `dlc_metadata/`, `builtin_dlc/` | Metadane i deskryptory dodatków. |

Lokalne archiwum `eu4-game-sources-1.37.5.0.zip` zawiera plik `source-manifest.json` z wersją, względnymi ścieżkami i indywidualnymi sumami kontrolnymi. SHA-256 archiwum to `71294efc69b7e110636299b0a78cf1772f927f7d9857c424e2213fef1644e341`.

Przy przetwarzaniu zachowaj identyfikatory, warunki DLC i daty. Pliki mają różne kodowania, m.in. UTF-8 z BOM i Windows-1252. Pliki lokalizacji z rozszerzeniem `.yml` używają składni Paradox.
