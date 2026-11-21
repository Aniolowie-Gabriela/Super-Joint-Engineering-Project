"""Serwer HTTP z wyszukiwaniem źródeł EU4 dla zewnętrznego agenta (np. ElevenLabs).

Nie używa żadnego modelu językowego. Zwraca fragmenty źródeł, a odpowiedź
układa agent po stronie wywołującej. Wymaga tokenu w zmiennej SEARCH_API_TOKEN.
"""

import argparse
import hmac
import os
from pathlib import Path

from ask import resolve_db_path
from mcp_server import find_passages
from search import find_symbol, read_record, trace_flag, trade_route

MAX_QUERY = 1200


def create_app(db_path: Path, token: str):
    if len(token) < 24:
        raise ValueError("SEARCH_API_TOKEN musi mieć co najmniej 24 znaki.")
    if db_path.with_name("semantic").joinpath("manifest.json").is_file():
        try:
            import semantic  # noqa: F401  (ładuje biblioteki natywne przed wątkami)
        except ImportError:
            pass
    from fastapi import Depends, FastAPI, Header, HTTPException
    from pydantic import BaseModel, Field

    def authorize(authorization: str = Header(default="")):
        scheme, _, given = authorization.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(given.encode(), token.encode()):
            raise HTTPException(status_code=401, detail="Brak lub błędny token.")

    class SearchRequest(BaseModel):
        query: str = Field(min_length=1, max_length=MAX_QUERY, description="Pytanie gracza po polsku")
        limit: int = Field(default=4, ge=1, le=8)

    class RecordRequest(BaseModel):
        chunk_id: str = Field(min_length=1, max_length=200)

    class TradeRequest(BaseModel):
        origin: str = Field(min_length=1, max_length=80, description="np. krakow")
        destination: str = Field(min_length=1, max_length=80, description="np. english_channel")

    app = FastAPI(title="EU4 — wyszukiwanie źródeł", docs_url=None, redoc_url=None)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/search", dependencies=[Depends(authorize)], operation_id="search_eu4")
    def search(body: SearchRequest) -> list[dict]:
        """Wyszukaj fragmenty źródeł o Europa Universalis IV 1.37. Odpowiadaj tylko na ich podstawie."""
        try:
            return find_passages(db_path, body.query, body.limit)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None

    @app.post("/record", dependencies=[Depends(authorize)], operation_id="read_eu4_record")
    def record(body: RecordRequest) -> dict:
        """Odczytaj pełny fragment po chunk_id z wyników wyszukiwania."""
        found = read_record(db_path, body.chunk_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Nie ma takiego fragmentu.")
        return found

    @app.post("/trade", dependencies=[Depends(authorize)], operation_id="trace_eu4_trade")
    def trade(body: TradeRequest) -> list[dict]:
        """Pokaż trasę handlu między węzłami po identyfikatorach."""
        return trade_route(db_path, body.origin, body.destination)

    return app


def build_app():
    """Fabryka dla uvicorn: uvicorn --factory server:build_app."""
    token = os.environ.get("SEARCH_API_TOKEN", "")
    return create_app(resolve_db_path(), token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", metavar="PLIK", help="ścieżka do bazy EU4 (albo EU4_RAG_DB)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    import uvicorn

    app = create_app(resolve_db_path(args.db), os.environ.get("SEARCH_API_TOKEN", ""))
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
