"""Dostęp tylko do odczytu do lokalnej bazy EU4 przez MCP stdio."""

import argparse
import asyncio
from pathlib import Path

from ask import resolve_db_path
from search import context, find_symbol, guide_context, read_record, trace_flag, trade_route


def create_server(db_path: Path):
    if db_path.with_name("semantic").joinpath("manifest.json").is_file():
        # Load native libraries before stdio creates worker threads on Windows.
        try:
            import semantic
        except ImportError:
            pass
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations

    server = FastMCP("EU4 — źródła gry")

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def search_eu4(query: str, limit: int = 4) -> list[dict]:
        """Wyszukaj krótkie fragmenty źródeł EU4. Pełny wpis otworzysz przez read_eu4_record."""
        return await asyncio.to_thread(find_passages, db_path, query, limit)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def read_eu4_record(chunk_id: str) -> dict | None:
        """Odczytaj pełny fragment po identyfikatorze chunk_id z wyników wyszukiwania."""
        return read_record(db_path, chunk_id)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def find_eu4_symbol(symbol: str, family: str | None = None) -> list[dict]:
        """Odczytaj definicję po dokładnym identyfikatorze skryptu i opcjonalnej rodzinie."""
        return find_symbol(db_path, symbol, family)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def trace_eu4_flag(flag: str) -> list[dict]:
        """Pokaż skrypty ustawiające, sprawdzające lub usuwające flagę i dokładny wiersz."""
        return trace_flag(db_path, flag)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def trace_eu4_trade(origin: str, destination: str) -> list[dict]:
        """Pokaż trasę handlu między węzłami po identyfikatorach, np. krakow i english_channel."""
        return trade_route(db_path, origin, destination)

    return server


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
            text += "\n[…] Pełny fragment jest dostępny przez read_eu4_record."
        result.append({**{key: record[key] for key in fields if key in record and record[key]}, "text": text})
    return result


def main():
    parser = argparse.ArgumentParser(description="Udostępnij lokalne źródła EU4 przez MCP.")
    parser.add_argument("--db", metavar="PLIK", help="ścieżka do bazy EU4")
    args = parser.parse_args()
    try:
        server = create_server(resolve_db_path(args.db))
    except FileNotFoundError as exc:
        parser.exit(2, f"{exc}\n")
    except ModuleNotFoundError as exc:
        if exc.name != "mcp":
            raise
        parser.exit(2, "Brakuje pakietu mcp. Zainstaluj go w środowisku Pythona tego projektu.\n")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
