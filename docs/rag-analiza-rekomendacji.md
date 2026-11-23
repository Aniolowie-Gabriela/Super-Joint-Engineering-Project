# Rekomendacje dla RAG EU4 a stan kodu

Materiał wejściowy dla agenta, który przygotuje podsumowanie. Każda rekomendacja z zewnętrznej analizy jest zestawiona z faktycznym kodem. Werdykty wynikają z czytania kodu. Nie uruchamiano żadnych pomiarów.

## 0. Zakres i zastrzeżenia (uwzględnij w podsumowaniu)

- **Wersja kodu:** `origin/main` @ `cf3ffd6` (2026-11-23). Gałąź `feature/elevenlabs-search-server` jest 6 commitów za `main` i ma starszy pipeline. Ścieżki i numery wierszy poniżej dotyczą `main` (`sources/eu4/mechanics/`).
- **Na `main` są dwa pipeline'y w `ask.py`:**
  - **stronicowany** (`_ask_paged`, domyślny, `paged=True`);
  - **starszy** (`paged=False`).

  Część rekomendacji opisuje starszy pipeline i jest już częściowo nieaktualna.
- **Materiał wejściowy jest niekompletny.** Zaczyna się w połowie punktu 6. Brakuje punktów 1–5 i tabeli z „proponowaną kolejnością”. Punktów 1–5 nie oceniono. RRF, reranking, strukturalne embeddingi i routing są oceniane na podstawie wariantów B–E z tabeli benchmarku i zdania końcowego.
- Zewnętrzna analiza sama zaznacza, że jej oceny są szacunkowe. Ten dokument je weryfikuje, ale też nie podaje liczb.

## 1. Jak działa obecny pipeline (`main`, ścieżka domyślna)

1. **Skróty deterministyczne.** Dotyczą tylko krótkich, prostych pytań (`simple_guide_question`, `ask.py:327`). Pytanie musi w całości pasować do wzorca trasy handlowej (`trade_question(..., exact_match=True)`) albo gotowej karty (`guide_context(..., exact_match=True)`).
2. **Wyszukiwanie kandydatów.** `search.context(limit=20)` (`search.py:554`) to **sekwencyjna kaskada**. Każdy etap dopisuje rekordy, dopóki są wolne miejsca, z deduplikacją po `document_id`. Kolejność etapów:
   - stałe mapowania mechanik;
   - progi (`threshold_context`);
   - jawne symbole i słownik (`exact`);
   - zależności (`dependencies`);
   - FTS5/BM25 w rodzinach;
   - **wektory E5, tylko jeśli zostało miejsce** (`search.py:672`, maksymalnie `limit // 3` nowych rekordów);
   - FTS: encje, frazy, słowa.
3. **Kolejność puli.** `_ask_paged.search` układa pulę tak: osobiste źródła, rekordy z wartością liczbową, `direct_mechanic`/`tier_match`, karty, reszta w kolejności kaskady.
4. **Czytanie stronami.** `paged_reader.read_sources` (`paged_reader.py:201`) podaje stronę po 3 rekordy, maksymalnie 5 stron, czyli do 15 rekordów. Gemma czyta **treść** i zwraca JSON:
   - `keep`: wybrane cytaty;
   - `action`: `ready`, `next`, `search` albo `campaign`.

   Na wyjściu wymuszony jest schemat JSON.
5. **Kontrola wartości.** Przy pytaniach „ile kosztuje” i „jak długo” `quantity_match` sprawdza, czy zachowany cytat zawiera wartość z jednostką. Jeśli nie, wymusza dodatkowe wyszukiwanie.
6. **Generowanie odpowiedzi** tylko z zachowanych cytatów. Odpowiedź jest odrzucana (`reading_incomplete`), gdy:
   - brak w niej cytowań;
   - cytuje numer spoza listy źródeł;
   - została ucięta (`ask.py:440–448`).
7. **Diagnostyka.** Przez `diagnostics` zapisywane są kandydaci, strony, decyzje i źródła.

## 2. Ocena rekomendacji

Skala werdyktów:
- **AKTUALNA**: problem istnieje w kodzie `main`;
- **CZĘŚCIOWO ZREALIZOWANA**;
- **NIEAKTUALNA**: dotyczy tylko starszego pipeline'u.

### 2.1 Niezależne wyszukiwanie i fuzja RRF — AKTUALNA, priorytet wysoki

- **Fakt:** `context()` nie łączy wyników. Pierwszy etap, który znajdzie rekord, zajmuje miejsce. Wektory działają jako uzupełnienie: uruchamiają się tylko przy wolnych miejscach i dodają najwyżej ok. 1/3 limitu. Wynik BM25 i podobieństwo wektorowe nigdy nie są porównywane.
- **Dlaczego to ważne właśnie tu:** czytnik stronicowany zobaczy najwyżej 15 rekordów, w kolejności puli. Trafny rekord z wektorów albo z dalszej części BM25 może nie trafić na żadną stronę.
- **Wdrożenie:** każdy retriever działa niezależnie ze swoim top-k:
  - dokładne symbole;
  - FTS5 BM25;
  - E5;
  - FTS na terminach z rozszerzenia zapytania.

  Wyniki łączy RRF (`1/(k+rank)`, k≈60). Rekordy deterministyczne (`direct_mechanic`, `tier_match`, wartości dla pytań „ile”) zostają przypięte na górze, tak jak dziś. Nie trzeba nowej bazy. Dochodzi koszt jednego zapytania wektorowego na pytanie, które i tak często jest liczone.

### 2.2 Reranking analizujący treść — CZĘŚCIOWO ZREALIZOWANA

- **Teza z analizy jest prawdziwa dla starszego pipeline'u.** `rank_sources` (`ask.py:153`) sortuje wyłącznie po `title | symbol | family | section`, bez treści, i działa tylko przy llama.cpp.
- **Na ścieżce domyślnej** Gemma czyta treść cytatów (`read_sources`). To jest jednak filtr sekwencyjny, nie reranking: model nie zmienia kolejności puli, tylko decyduje, czy czytać dalej. Kolejność nadal wynika z kaskady.
- **Wdrożenie:** reranker na treści **przed** stronicowaniem, na ok. 30–40 kandydatach z RRF. Może to być mały wielojęzyczny cross-encoder w ONNX na CPU, jak obecne E5. Dzięki temu na pierwszych stronach znajdą się trafniejsze rekordy i skróci się czytanie. Każda strona to osobne wywołanie Gemmy, więc to także zysk czasowy.

### 2.3 Strukturalne embeddingi — AKTUALNA, priorytet średni

- **Fakt:** `semantic.passage` (`semantic.py:72`) koduje tytuł, symbol, rodzinę, sekcję i **pierwsze 560 znaków** surowego skryptu. W długich regułach warunki i efekty z dalszej części nie trafiają do wektora.
- Pole `parent_conditions` nie jest kodowane.
- Deterministyczne odczyty wartości z `interpret.annotations` nie są kodowane.
- Rodziny `history`, `map` i `country_tags` są wyłączone z wektorów.
- **Wdrożenie:** passage zbudowany z polskiej nazwy, warunków nadrzędnych, odczytanych efektów (`annotations`) i lokalizacji, zamiast surowego skryptu. Ewentualnie kilka wektorów na rekord. Wymaga przebudowy wektorów, a `reuse_prefix` nie zadziała przy zmianie formatu.

### 2.4 Routing pytań (adaptive RAG) — CZĘŚCIOWO ZREALIZOWANA

Routing już istnieje i opiera się na wyrażeniach regularnych:
- `detailed` (liczba słów i słowa kluczowe);
- `simple_guide_question`;
- dokładne wzorce kart i tras;
- `threshold_context`;
- `quantities`;
- akcja `campaign` w czytniku.

Brakuje dwóch rzeczy:
- pomiaru trafności routingu;
- osobnej ścieżki dla pytań wieloczęściowych. Dziś obsługuje je ten sam czytnik z limitem 5 stron.

Rekomendacja w praktyce sprowadza się do tego, żeby **zmierzyć routing i ujednolicić go**, a nie budować go od zera.

### 2.5 Deterministyczna weryfikacja odpowiedzi — CZĘŚCIOWO ZREALIZOWANA

| Postulat | Stan na `main` |
|---|---|
| Czy każde `[N]` istnieje w kontekście | **Zrobione** na ścieżce domyślnej (`ask.py:440–448`). W starszym pipeline'ie tylko raportowane w `evaluate.grade`. |
| Odczyt wartości i operatorów z danych strukturalnych | **Częściowo.** `interpret.annotations` odczytuje wartości do kontekstu. `quantity_match` sprawdza obecność wartości z jednostką w cytacie. Brak sprawdzenia, czy liczby i znaki **w odpowiedzi** występują w cytowanym fragmencie. Operatory i negacje (`NOT`, `>=`/`<`, zakres `limit` w `effect`) nie są weryfikowane. |
| Oznaczanie odpowiedzi jako niepotwierdzonej | **Częściowo.** Jest `reading_incomplete` i komunikat o braku podstaw. Nie ma oznaczenia na poziomie pojedynczego zdania lub liczby. |
| Drugi przebieg Gemmy to nie dowód | **Zgodne z `main`.** `check_answer` działa tylko w starszym pipeline'ie i tylko na llama.cpp. Ścieżka domyślna go nie używa. |

**Następny krok:** deterministyczna kontrola liczb. Dla każdej liczby i znaku w zdaniu z `[N]` sprawdzić, czy występuje w cytacie N lub w jego `annotations`. Jeśli nie, oznaczyć zdanie albo odrzucić odpowiedź.

### 2.6 Zrównanie Ollamy i llama.cpp — W DUŻEJ MIERZE NIEAKTUALNA

- Na ścieżce domyślnej `completion()` (`ask.py:268`) obsługuje oba backendy, także schemat JSON: `format` w Ollamie, `response_format` w llama.cpp. To już pełni rolę proponowanej abstrakcji `LLMBackend`.
- **Pozostałe różnice:**
  - temperatura generowania: 0 w Ollamie, 0.4 w llama.cpp;
  - `num_ctx` nie jest przekazywane do llama.cpp, bo zależy od ustawień serwera.
- **Asymetria w starszym pipeline'ie zostaje:** `search_terms`, `rank_sources`, `find_guide` i `check_answer` działają tylko z llama.cpp.
- **Decyzja do podjęcia:** usunąć starszy pipeline albo przenieść go na `completion()`. Lepsze to pierwsze, bo zmniejsza liczbę wariantów do testowania.

### 2.7 Benchmark przed dalszym rozwojem — AKTUALNA, priorytet najwyższy

Stan obecny:
- `evaluate.py` ma 7 wbudowanych przypadków ocenianych wzorcami regex: 6 faktów i 1 pytanie o kampanię.
- `docs/eu4-benchmark-questions.json` ma 25 pytań, po 5 w kategoriach eco, war, trade, diplo i pol. Każde ma oczekiwane źródła w formacie `ścieżka:wiersze`.
- Tryb `--questions` tylko zapisuje odpowiedzi. **Nie liczy Recall@k ani MRR.**
- 44 z 54 oczekiwanych źródeł to pliki `localisation/`. Zestaw słabo testuje skrypty z warunkami.

Wnioski:
- **Metryki wyszukiwania (Recall@5, MRR) da się liczyć bez Gemmy**, bezpośrednio na `search.context()` albo na puli z `_ask_paged.search`. Wystarczy porównać `source_path` i `lines` rekordów z oczekiwanymi źródłami. To szybkie i deterministyczne, a pokrywa warianty B–D z tabeli bez kosztu generowania.
- Wariant A („obecny pipeline”) trzeba przypiąć do konkretnej ścieżki, stronicowanej albo starszej, i konkretnego backendu. Inaczej wyniki nie będą porównywalne.
- Dla czytnika stronicowanego warto mierzyć także recall puli w obrębie pierwszych 15 rekordów, bo tylko tyle model zobaczy.
- Zestaw trzeba rozszerzyć do 100–150 pytań, z naciskiem na skrypty: warunki, progi, negacje, zagnieżdżone `limit`/`if`. Zgodnie z analizą potrzebne są też grupy kontrolne: mylące nazwy, negacja, progi, brak danych kampanii.

## 3. Proponowana kolejność dla `main`

1. **Benchmark wyszukiwania bez LLM.** Recall@5/@15, MRR na 25 pytaniach, potem rozszerzenie zestawu. Bez tego nie da się ocenić kroków 2–4.
2. **RRF** w miejsce kaskady w `search.context()`, z zachowaniem przypiętych rekordów deterministycznych.
3. **Reranker na treści** przed `read_sources`.
4. **Kontrola liczb i znaków** w odpowiedzi względem cytatów.
5. **Strukturalne passage** dla E5 i przebudowa wektorów.
6. **Usunięcie starszego pipeline'u** (`paged=False`) albo przeniesienie go na `completion()`.

Kroki 2 i 3 pokrywają się z dwiema zmianami, które zewnętrzna analiza wskazuje jako najważniejsze. Kod to potwierdza, a czytnik stronicowany zwiększa ich wagę, bo widzi tylko ograniczoną liczbę rekordów.

## 4. Otwarte kwestie

- Punkty 1–5 analizy nie zostały dostarczone i nie są tu ocenione.
- Gałąź `feature/elevenlabs-search-server` nie zawiera zmian z `main`. Decyzja o scaleniu należy do zespołu, przed pracą nad RAG na tej gałęzi.
- Nie zweryfikowano, czy wszystkie oczekiwane źródła z `eu4-benchmark-questions.json` (głównie lokalizacja) są obecne jako rekordy w bazie współdzielonej `data/knowledge.sqlite3`.
