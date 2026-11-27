"""Demo w przeglądarce: rozmowa z agentem ElevenLabs, źródła EU4 szukane na tym komputerze.

Przeglądarka obsługuje mikrofon i głośnik, a ten serwer (tylko 127.0.0.1) daje jej
jednorazowy podpisany adres rozmowy i przeszukuje lokalną bazę na prośbę agenta.
Klucz API zostaje na serwerze. Konfiguracja jak dla voice.py: ELEVENLABS_API_KEY
i ELEVENLABS_AGENT_ID w .env.
"""

import argparse
import os
from pathlib import Path
import threading
import webbrowser

from ask import prepared_db_path
from mcp_server import find_passages
from search import read_record
from voice import ROOT, load_env_file, make_elevenlabs_client

PAGE = Path(__file__).with_name("demo") / "index.html"


def create_app(db_path, api_key, agent_id):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse
    from pydantic import BaseModel, Field

    client = make_elevenlabs_client(api_key) if api_key and agent_id else None
    app = FastAPI(title="EU4 — demo głosowe", docs_url=None, redoc_url=None, openapi_url=None)

    class SearchRequest(BaseModel):
        query: str = Field(min_length=1, max_length=1200)
        limit: int = Field(default=4, ge=1, le=8)

    class RecordRequest(BaseModel):
        chunk_id: str = Field(min_length=1, max_length=200)

    @app.get("/")
    def page():
        return FileResponse(PAGE, headers={"Cache-Control": "no-store"})

    @app.post("/api/session")
    def session():
        if client is None:
            raise HTTPException(
                status_code=503,
                detail="Ustaw ELEVENLABS_API_KEY i ELEVENLABS_AGENT_ID w pliku .env i uruchom demo ponownie.",
            )
        try:
            signed = client.conversational_ai.conversations.get_signed_url(agent_id=agent_id)
        except Exception as error:  # błąd ElevenLabs pokazujemy na stronie
            raise HTTPException(status_code=502, detail=f"ElevenLabs: {error}") from None
        return {"signedUrl": signed.signed_url}

    @app.post("/api/search")
    def search(body: SearchRequest):
        return find_passages(db_path, body.query, body.limit)

    @app.post("/api/record")
    def record(body: RecordRequest):
        found = read_record(db_path, body.chunk_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Nie ma takiego fragmentu.")
        return found

    return app


def main():
    load_env_file(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", metavar="PLIK", help="ścieżka do bazy EU4 (albo EU4_RAG_DB)")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--no-browser", action="store_true", help="nie otwieraj przeglądarki")
    args = parser.parse_args()
    api_key, agent_id = os.environ.get("ELEVENLABS_API_KEY"), os.environ.get("ELEVENLABS_AGENT_ID")
    try:
        db_path = prepared_db_path(args.db)
    except FileNotFoundError as exc:
        parser.exit(2, f"{exc} Najpierw uruchom: python eu4.py setup --voice\n")
    if db_path.with_name("semantic").joinpath("manifest.json").is_file():
        try:
            import semantic  # noqa: F401  (ładuje biblioteki natywne przed wątkami)
        except ImportError:
            pass
    print("Ładuję indeks…", flush=True)
    find_passages(db_path, "kupcy", 1)  # pierwsze wyszukiwanie ładuje model; agent nie czeka

    import uvicorn

    url = f"http://127.0.0.1:{args.port}/"
    print(f"Demo: {url}  (Ctrl+C kończy)", flush=True)
    if not api_key or not agent_id:
        print("Do rozmowy dodaj ELEVENLABS_API_KEY i ELEVENLABS_AGENT_ID w .env i uruchom demo ponownie.", flush=True)
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, (url,)).start()
    uvicorn.run(create_app(db_path, api_key, agent_id), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
