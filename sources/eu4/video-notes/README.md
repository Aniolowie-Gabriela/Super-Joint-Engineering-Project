# EU4 1.37 — notatki strategiczne i dane do RAG

Opracowania po polsku dla rozgrywki jednoosobowej bez modów. Poradniki przejrzano na podstawie sześciu transkrypcji. Najważniejsze warunki wybranych wydarzeń, misji i decyzji porównano ze skryptami instalacji Steam 1.37.5.0. Wiele decyzji zależy od włączonych DLC i stanu konkretnego zapisu.

| Jeśli pytasz o… | Opracowanie | Wersja podana przez źródło |
|---|---|---|
| Start Węgier, Mołdawię, wojny bałkańskie, unie i Rzeszę | [Węgry](wegry-1.37.md) | 1.37, Winds of Change |
| Niepodległość Holandii, wcześniejsze formowanie, kanał La Manche, kolonie i VOC | [Holandia i Niderlandy](holandia-1.37.md) | 1.37, Winds of Change |
| Konstantynopol, kolejkę frontów, ejalety i podbój świata | [Osmanowie](osmanowie-1.37.md) | 1.37, Winds of Change |
| Technologię wojskową, front i tył armii, morale oraz odsiecz | [Armia](armia-skol.md) | Niepodana |
| Towary, produkcję, budynki i inwestycje kompanii | [Handel](handel-budgetmonk.md) | Sprzed 1.37 |
| Agresywną ekspansję, podatność na koalicje i rozejmy | [Koalicje](koalicje-florryworry-1.md) | Sprzed 1.37 |
| Otwarcie Polską, wybór władcy, Litwę, Prusy i Rzeczpospolitą | [Polska](polska-1.37.5.md) | Pliki gry 1.37.5.0 |

Węgierski film pokazuje też [wojnę o unię z Polską i Litwą](wegry-1.37.md#t3254) z perspektywy Węgier. Do odpowiedzi o otwarciu samą Polską użyj przede wszystkim notatek z plików gry.

## Indeksowanie i cytowanie

Wczytaj [`chunks.jsonl`](chunks.jsonl) jako UTF-8. Jedna linia to samodzielny fragment. Indeksuj razem `title`, `text`, `caveat` i `tags`. Jeśli chcesz mieszać te dane z innymi materiałami, użyj `chunk_id` do deduplikacji. Pliki Markdown przedstawiają tę samą treść w postaci do czytania.

| Pola | Przeznaczenie |
|---|---|
| `chunk_id`, `document_id`, `notes_path` | Klucz fragmentu, grupowanie po materiale i odsyłacz do sekcji. Ścieżka jest względna wobec katalogu z JSONL. |
| `game_version`, `reported_game_version`, `source_version_status`, `source_version_label`, `version_evidence` | Wersja docelowa bazy, wersja podana przez materiał lub dokładny build plików oraz podstawa przypisania. Statusy to `reported`, `unknown`, `predates_target` i `local_build`. |
| `source_type`, `source_country`, `evidence_kind`, `verification` | Rodzaj źródła, kraj materiału, przykład kampanii lub mechanika i zakres kontroli. `source_country` opisuje główny kraj materiału. |
| `source_url`, `citation_url`, `start_s`, `end_s`, `timestamp` | Film oraz początek i koniec ustępu w napisach. Cytuj link do początku wraz z pełnym zakresem czasu. |
| `game_data_version`, `game_refs` | Build oraz ścieżki i identyfikatory do sprawdzenia w instalacji. Przy notatkach bez źródła wideo cytuj te referencje. |

Przy pytaniu o obowiązujący próg lub konkretną nagrodę korzystaj najpierw z mechaniki potwierdzonej w odpowiednim buildzie. Przy pytaniu o plan kampanii zestaw przykład z sytuacją gracza i jego DLC. `transcript_and_partial_game_file_check` oznacza, że plik gry potwierdza element wskazany w `game_refs`. Żaden status nie oznacza symulacji kampanii, sprawdzenia w interfejsie ani pełnej zgodności całego filmu z 1.37.5.0.

W tych materiałach najlepiej udokumentowano trzy kampanie i polskie otwarcie, wojny lądowe, handel oraz ryzyko koalicji. Węższe przykłady obejmują kolonizację oraz instytucje i zarządzanie rozwojem. Religia, ekonomia stanów i dyplomacja wielkich mocarstw pojawiają się tylko w kontekście wybranych decyzji. Pytania o pełne mechaniki tych systemów wymagają dodatkowych źródeł.

Warunki drzewa misji sprawdzaj w plikach odpowiedniego kraju. Producent opisuje rozbudowane drzewa Węgier i Niderlandów, osmańskie ejalety, dekadencję i kryzys oraz rozbudowane misje Polski i Litwy w opisach DLC. [Winds of Change](https://store.steampowered.com/app/2854750/Expansion_Europa_Universalis_IV_Winds_of_Change/), [Domination](https://store.steampowered.com/app/2223660/Europa_Universalis_IV_Domination/), [Lions of the North](https://www.paradoxinteractive.com/games/europa-universalis-iv/add-ons/europa-universalis-iv-lions-of-the-north)
