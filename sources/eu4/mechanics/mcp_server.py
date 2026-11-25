"""Fragmenty źródeł mechaniki zwracane przez serwer kampanii."""

from search import context, guide_context


def find_passages(db_path, query, limit):
    query = query.strip()
    if not query or len(query) > 1200 or not 1 <= limit <= 8:
        raise ValueError("Wpisz pytanie do 1200 znaków i wybierz od 1 do 8 fragmentów.")
    guides = guide_context(db_path, query)
    matches = context(db_path, query, limit)
    guide_ids = {item["chunk_id"] for item in guides}
    records = guides + [item for item in matches if item["chunk_id"] not in guide_ids]
    fields = ("chunk_id", "title", "symbol", "source_type", "game_version", "source_path", "source_url",
              "citation_url", "lines", "game_refs", "parent_conditions")
    result = []
    for record in records[:limit]:
        text = record["text"]
        if len(text) > 1100:
            text = text[:1080].rsplit("\n", 1)[0] or text[:1080]
            text += "\n[…] Pełny fragment jest dostępny przez eu4_mechanics_read."
        result.append({**{key: record[key] for key in fields if key in record and record[key]}, "text": text})
    return result
