"""Dostęp tylko do odczytu do lokalnej bazy EU4 przez MCP stdio."""

import argparse
import asyncio
from pathlib import Path

from ask import resolve_db_path
from search import context, find_symbol, read_record, trace_flag


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
    async def search_eu4(query: str, limit: int = 6) -> list[dict]:
        """Wyszukaj fragmenty w bazie wiedzy o EU4. Podaj pytanie lub temat."""
        return await asyncio.to_thread(context, db_path, query, limit)

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

    return server


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
