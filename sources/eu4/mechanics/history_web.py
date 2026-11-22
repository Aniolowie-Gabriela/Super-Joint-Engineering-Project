"""Okno historii asystenta: mała strona na 127.0.0.1 otwierana jako okno aplikacji.

Serwer działa w wątku pobocznym, więc nie walczy z ikoną w zasobniku ani ze skrótem o główny
wątek. Port jest losowy, a API wymaga tokenu z adresu okna, żeby inne programy na komputerze
nie czytały historii. Strona co sekundę pyta o nowe zdarzenia.
"""

import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import webbrowser

from search import read_record

PAGE = Path(__file__).with_name("ui") / "history.html"


def create_app(history, db_path, token, status):
    from fastapi import Depends, FastAPI, Header, HTTPException, Query
    from fastapi.responses import FileResponse

    def check(x_token: str = Header(default="")):
        if not secrets.compare_digest(x_token, token):
            raise HTTPException(status_code=403, detail="Brak dostępu.")

    app = FastAPI(title="EU4 — historia", docs_url=None, redoc_url=None, openapi_url=None)
    api = [Depends(check)]

    @app.get("/")
    def page():
        return FileResponse(PAGE, headers={"Cache-Control": "no-store"})

    @app.get("/api/sessions", dependencies=api)
    def sessions(q: str = Query(default="", max_length=200)):
        return {"sessions": history.sessions(q), "last_id": history.last_id()}

    @app.get("/api/session/{session_id}", dependencies=api)
    def session(session_id: int):
        return history.session(session_id)

    @app.get("/api/poll", dependencies=api)
    def poll(after: int = 0):
        return {"status": status(), "events": history.since(after)}

    @app.get("/api/logs", dependencies=api)
    def logs():
        return history.logs()

    @app.get("/api/record", dependencies=api)
    def record(chunk_id: str = Query(min_length=1, max_length=200)):
        found = read_record(db_path, chunk_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Nie ma takiego fragmentu.")
        return found

    return app


class HistoryWindow:
    """Uruchamia serwer przy pierwszym otwarciu okna; potem tylko otwiera kolejne okno."""

    def __init__(self, history, db_path, status, log):
        self.history, self.db_path, self.status, self.log = history, db_path, status, log
        self.token = secrets.token_urlsafe(24)
        self.url = None
        self.server = None
        self.lock = threading.Lock()

    def start(self):
        import uvicorn

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        config = uvicorn.Config(create_app(self.history, self.db_path, self.token, self.status),
                                log_level="warning", log_config=None)
        self.server = uvicorn.Server(config)
        threading.Thread(target=self.server.run, kwargs={"sockets": [sock]}, daemon=True).start()
        self.url = f"http://127.0.0.1:{port}/#t={self.token}"
        self.log.info("Okno historii: http://127.0.0.1:%s/", port)

    def open(self, *_):
        try:
            with self.lock:
                if self.server is None:
                    self.start()
            open_app_window(self.url)
        except Exception:
            self.log.exception("Nie udało się otworzyć okna historii")

    def stop(self):
        if self.server is not None:
            self.server.should_exit = True


def find_app_browser():
    """Przeglądarka z trybem --app (okno bez paska adresu). Na Windows Edge jest zawsze."""
    candidates = []
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                     os.environ.get("LOCALAPPDATA")):
            if base:
                candidates += [Path(base) / "Microsoft/Edge/Application/msedge.exe",
                               Path(base) / "Google/Chrome/Application/chrome.exe"]
    found = [str(path) for path in candidates if path.is_file()]
    found += [path for name in ("microsoft-edge", "msedge", "google-chrome", "chromium", "chromium-browser")
              if (path := shutil.which(name))]
    return found[0] if found else None


def open_app_window(url):
    browser = find_app_browser()
    if browser is None:
        webbrowser.open(url)
        return
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.Popen([browser, f"--app={url}", "--window-size=1180,780"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags)
