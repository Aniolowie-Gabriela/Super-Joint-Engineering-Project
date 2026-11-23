"""Lokalny panel asystenta EU4 i przegląd jego źródeł."""

import argparse
from contextlib import asynccontextmanager, closing
from http.client import HTTPConnection, HTTPException as ClientHTTPException
import json
import os
from pathlib import Path
import re
import sqlite3
from threading import Lock, Thread
from time import sleep
import webbrowser

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from ask import DEFAULT_MODEL, DEFAULT_NUM_CTX, DEFAULT_URL, _loopback_address, ask, resolve_db_path
from search import lexical_query, open_index, read_record


ASSETS = Path(__file__).with_name("web_ui")
DEFAULT_PORT = 8765
PAGE_SIZE = 20
MODEL_MESSAGES = {
    "ready": "Gemma 4 E4B jest gotowa.",
    "runtime_unavailable": "Uruchom Ollamę. Jeśli jej brakuje, otwórz Przygotuj-model.cmd.",
    "model_missing": "Pobierz Gemmę 4 E4B. Model zajmuje kilka gigabajtów.",
    "model_installed": "Gemma 4 E4B jest pobrana. Wczytaj ją na kartę graficzną.",
    "downloading": "Pobieram Gemmę 4 E4B.",
    "loading": "Wczytuję Gemmę 4 E4B na kartę graficzną.",
    "gpu_required": "Gemma 4 E4B wymaga wolnej pamięci na karcie graficznej. Zwolnij pamięć GPU i spróbuj ponownie.",
}
OFFLOAD_UNVERIFIED = "Sprawdź w logu llama.cpp, czy wszystkie warstwy modelu są na GPU, i ponownie uruchom panel."
BUSY_STATES = {"downloading", "loading"}


class ChatRequest(BaseModel):
    question: str = Field(max_length=1200)
    previous_question: str | None = Field(default=None, max_length=1200)
    previous_answer: str | None = Field(default=None, max_length=12000)


def status_data(state, message=None):
    return {
        "model_ready": state == "ready",
        "model_state": state,
        "message": message or MODEL_MESSAGES[state],
    }


class ModelRuntime:
    def __init__(self):
        self.llama = os.environ.get("EU4_LLM_BACKEND") == "llama.cpp"
        self.url = os.environ.get("EU4_MODEL_URL") or DEFAULT_URL
        if self.llama and not os.environ.get("EU4_MODEL_URL"):
            raise ValueError("Podaj lokalny adres llama.cpp w EU4_MODEL_URL.")
        self.host, self.port = _loopback_address(self.url)
        self.model = os.environ.get("EU4_MODEL", DEFAULT_MODEL) if self.llama else DEFAULT_MODEL
        try:
            self.num_ctx = int(os.environ.get("EU4_NUM_CTX", str(DEFAULT_NUM_CTX)))
            if self.num_ctx < 2048:
                raise ValueError
        except ValueError:
            raise ValueError("Ustaw EU4_NUM_CTX na liczbę całkowitą co najmniej 2048.") from None
        # Tę deklarację ustawia operator po sprawdzeniu pełnego offloadu w logu llama.cpp.
        self.strict = os.environ.get("EU4_GPU_STRICT") == "1"
        self.job = None
        self.failure = None
        self.state_lock = Lock()
        self.generation_lock = Lock()

    def request(self, route, payload=None, timeout=3, on_line=None):
        method = "GET" if payload is None else "POST"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        connection = HTTPConnection(self.host, self.port, timeout=timeout)
        try:
            connection.request(method, route, body=body, headers={"Content-Type": "application/json"})
            with connection.getresponse() as response:
                if on_line is not None and response.status == 200:
                    for line in response:
                        on_line(json.loads(line))
                    return response.status, {}
                data = json.load(response)
                if not isinstance(data, dict):
                    raise ValueError("Nieprawidłowy format odpowiedzi.")
                return response.status, data
        finally:
            connection.close()

    def active_model(self):
        code, data = self.request("/api/ps")
        if code != 200 or not isinstance(data.get("models"), list):
            raise ValueError("Nie udało się odczytać listy modeli.")
        return self.find_model(data)

    def find_model(self, data):
        return next((
            entry for entry in data["models"]
            if isinstance(entry, dict) and self.model in (entry.get("name"), entry.get("model"))
        ), None)

    @staticmethod
    def all_gpu(model):
        if model is None:
            return False
        size = model.get("size")
        return type(size) is int and size > 0 and model.get("size_vram") == size

    def inspect(self):
        try:
            if self.llama:
                code, data = self.request("/health")
                error = data.get("error")
                if code == 503 and isinstance(error, dict) and error.get("message") == "Loading model":
                    return status_data("loading")
                if code != 200 or data.get("status") != "ok":
                    raise ValueError("Model jest niedostępny.")
                if not self.strict:
                    return status_data("gpu_required", OFFLOAD_UNVERIFIED)
                return status_data("ready")

            active = self.active_model()
            if active is not None:
                return status_data("ready" if self.all_gpu(active) else "gpu_required")
            code, data = self.request("/api/tags")
            if code != 200 or not isinstance(data.get("models"), list):
                raise ValueError("Nie udało się odczytać listy modeli.")
            return status_data("model_installed" if self.find_model(data) is not None else "model_missing")
        except (OSError, ClientHTTPException, ValueError):
            if self.llama:
                return status_data("runtime_unavailable", "Uruchom lokalny serwer llama.cpp z Gemmą 4 E4B.")
            return status_data("runtime_unavailable")

    def status(self):
        with self.state_lock:
            if self.job is not None:
                return self.job
        observed = self.inspect()
        with self.state_lock:
            if self.job is not None:
                return self.job
            if self.failure and observed["model_state"] in {"model_installed", "model_missing"}:
                return self.failure
        return observed

    def start(self, *, only_installed=False):
        current = self.inspect()
        state = current["model_state"]
        with self.state_lock:
            if self.job is not None:
                return self.job
            if self.llama or state in {"ready", "runtime_unavailable"}:
                return current
            if only_installed and state != "model_installed":
                return current
            phase = "downloading" if state == "model_missing" else "loading"
            self.job = status_data(phase)
            self.failure = None
            progress = self.job
            Thread(target=self.prepare, args=(phase,), daemon=True).start()
            return progress

    def load(self):
        options = {"num_ctx": self.num_ctx}
        if self.strict:
            options["draft_num_predict"] = 0
        code, data = self.request(
            "/api/generate",
            {"model": self.model, "prompt": "", "stream": False, "keep_alive": "30m", "options": options},
            timeout=180,
        )
        if code != 200 or data.get("error"):
            raise RuntimeError("Nie udało się wczytać modelu. Sprawdź wolną pamięć GPU i spróbuj ponownie.")
        return self.all_gpu(self.active_model())

    def download(self):
        finished = False

        def update(event):
            nonlocal finished
            if event.get("error"):
                raise RuntimeError("Nie udało się pobrać modelu. Sprawdź połączenie z internetem i wolne miejsce.")
            finished = event.get("status") == "success"
            total, completed = event.get("total"), event.get("completed")
            if type(total) is int and total > 0 and type(completed) is int:
                percent = min(100, max(0, completed * 100 // total))
                with self.state_lock:
                    self.job = status_data("downloading", f"Pobieram pliki Gemmy 4 E4B. Ukończono {percent}% bieżącego pliku.")

        code, _ = self.request(
            "/api/pull", {"model": self.model, "stream": True}, timeout=180, on_line=update,
        )
        if code != 200 or not finished:
            raise RuntimeError("Nie udało się pobrać modelu. Sprawdź połączenie z internetem i wolne miejsce.")

    def prepare(self, phase):
        failure = None
        try:
            with self.generation_lock:
                if phase == "downloading":
                    self.download()
                    with self.state_lock:
                        self.job = status_data("loading")
                if not self.load():
                    failure = status_data("gpu_required")
        except RuntimeError as error:
            failure = status_data("error", str(error))
        except (OSError, ClientHTTPException, ValueError):
            failure = status_data("error", "Przygotowanie modelu zostało przerwane. Sprawdź Ollamę i spróbuj ponownie.")
        finally:
            with self.state_lock:
                self.failure = failure
                self.job = None

    def answer(self, question, database, follow_up):
        current = self.status()
        if current["model_state"] not in {"ready", "model_installed"}:
            raise HTTPException(503, current["message"])
        with self.generation_lock:
            if not self.llama and not self.load():
                raise HTTPException(503, MODEL_MESSAGES["gpu_required"])
            result = ask(
                question, database, model=self.model, url=self.url, think=True,
                detailed=True if follow_up else None,
            )
            if not self.llama and not self.all_gpu(self.active_model()):
                raise HTTPException(503, MODEL_MESSAGES["gpu_required"])
        return {"answer": result["answer"], "sources": result["sources"]}


def chat_question(payload):
    question = payload.question.strip()
    if not question:
        raise ValueError("Wpisz pytanie o EU4.")
    previous = (payload.previous_question or "").strip()
    if not previous:
        return question, False
    intro = "\n\nPoprzednia rozmowa, tylko do wyjaśnienia odniesień w aktualnym pytaniu:\n"
    available = 1200 - len(question) - len(intro)
    if available < 40:
        return question, False
    previous = "Pytanie: " + previous[:min(300, available // 2)]
    answer = re.sub(r"\[\s*\d+[\d,\s]*\]", "", payload.previous_answer or "").strip()
    history = previous + ("\nOdpowiedź: " + answer if answer else "")
    return question + intro + history[:available], True


def knowledge_items(database, query, offset):
    params = (PAGE_SIZE + 1, offset)
    with closing(open_index(database)) as db:
        if query:
            match = lexical_query(query)
            if not match:
                words = re.findall(r"[^\W_]+", query.casefold())[:24]
                match = " OR ".join(f'"{part}"*' for part in words)
            rows = db.execute("""
                SELECT record.json FROM lookup JOIN record ON lookup.rowid = record.id
                WHERE lookup MATCH ?
                ORDER BY bm25(lookup, 10, 6, 1, 1), record.id LIMIT ? OFFSET ?
            """, (match, *params)) if match else ()
        else:
            rows = db.execute("SELECT json FROM record ORDER BY id LIMIT ? OFFSET ?", params)
        items = [json.loads(row[0]) for row in rows]
    return {"items": items[:PAGE_SIZE], "more": len(items) > PAGE_SIZE}


def choose_database(explicit):
    if explicit or os.environ.get("EU4_RAG_DB"):
        return resolve_db_path(explicit)
    data = Path(__file__).resolve().parents[3] / ".eu4"
    for kind in ("game", "shared"):
        candidate = data / kind / "knowledge.sqlite3"
        if candidate.is_file():
            return candidate
    return resolve_db_path()


def knowledge_status(database):
    fallback = "Czat wyszukuje źródła po słowach."
    try:
        from semantic import complete_index, index_paths
    except (ImportError, OSError):
        return f"{fallback} Aby włączyć wyszukiwanie według znaczenia, otwórz Przygotuj-wyszukiwanie.cmd."
    if not complete_index(*index_paths(database)):
        return f"{fallback} Brakuje plików do wyszukiwania według znaczenia."
    return None


def create_app(database, port=DEFAULT_PORT, runtime=None):
    model = ModelRuntime() if runtime is None else runtime
    knowledge_message = knowledge_status(database)

    @asynccontextmanager
    async def lifespan(_app):
        if not model.llama:
            Thread(target=lambda: model.start(only_installed=True), daemon=True).start()
        yield

    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, lifespan=lifespan)
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    if port == 80:
        hosts.update({"127.0.0.1", "localhost"})

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        host_values = request.headers.getlist("host")
        origin = request.headers.getlist("origin")
        if len(host_values) != 1 or (host := host_values[0].lower()) not in hosts:
            return JSONResponse({"detail": "Otwórz panel pod jego lokalnym adresem."}, status_code=403)
        allowed_origins = {f"http://{host}"}
        if port == 80 and host.endswith(":80"):
            allowed_origins.add(f"http://{host[:-3]}")
        cross_site = request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}
        if (origin and (len(origin) != 1 or origin[0] not in allowed_origins)
                or cross_site and request.method != "GET"):
            return JSONResponse({"detail": "Wyślij żądanie z lokalnego panelu EU4."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _error):
        message = "Sprawdź wpisane dane i spróbuj ponownie."
        if request.url.path == "/api/chat":
            message = "Wpisz pytanie o EU4 o długości do 1200 znaków."
        return JSONResponse({"detail": message}, status_code=422)

    @app.get("/")
    def index():
        return FileResponse(ASSETS / "index.html")

    @app.get("/assets/style.css")
    def stylesheet():
        return FileResponse(ASSETS / "style.css", media_type="text/css")

    @app.get("/assets/app.js")
    def javascript():
        return FileResponse(ASSETS / "app.js", media_type="text/javascript")

    @app.get("/api/status")
    def status():
        current = model.status()
        if knowledge_message:
            return {**current, "knowledge_message": knowledge_message}
        return current

    @app.post("/api/model")
    def prepare_model():
        current = model.start()
        state = current["model_state"]
        if state == "ready":
            return {"message": current["message"]}
        if state in BUSY_STATES:
            return JSONResponse({"message": current["message"]}, status_code=202)
        raise HTTPException(503, current["message"])

    @app.post("/api/chat")
    def chat(payload: ChatRequest):
        try:
            question, follow_up = chat_question(payload)
            return model.answer(question, database, follow_up)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except sqlite3.Error as error:
            raise HTTPException(503, "Nie udało się odczytać bazy wiedzy EU4.") from error
        except RuntimeError as error:
            detail = str(error)
            if model.llama:
                detail = detail.replace("Ollama", "Serwer llama.cpp").replace("z Ollamą", "z serwerem llama.cpp")
            raise HTTPException(502, detail) from error
        except (OSError, ClientHTTPException) as error:
            raise HTTPException(503, "Utracono połączenie z lokalnym modelem. Spróbuj ponownie.") from error

    @app.get("/api/knowledge")
    def knowledge(q: str = Query(default="", max_length=1200), offset: int = Query(default=0, ge=0, le=2**31-1)):
        try:
            return knowledge_items(database, q.strip(), offset)
        except sqlite3.Error as error:
            raise HTTPException(503, "Nie udało się odczytać bazy wiedzy EU4.") from error

    @app.get("/api/record")
    def record(id: str = Query(min_length=1, max_length=2048)):
        try:
            item = read_record(database, id)
        except sqlite3.Error as error:
            raise HTTPException(503, "Nie udało się odczytać bazy wiedzy EU4.") from error
        if item is None:
            raise HTTPException(404, "Tego źródła nie ma w bieżącej bazie wiedzy.")
        return item

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="ścieżka do bazy wiedzy EU4")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="lokalny port panelu")
    parser.add_argument("--no-browser", action="store_true", help="uruchom panel bez otwierania przeglądarki")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Wybierz port od 1 do 65535.")
    if os.environ.get("EU4_LLM_BACKEND") != "llama.cpp":
        # ask.py i wczytywanie używają tych samych opcji, z wyłączonym modelem szkicującym.
        os.environ["EU4_GPU_STRICT"] = "1"
    try:
        app = create_app(choose_database(args.db), args.port)
    except (OSError, ValueError) as error:
        parser.exit(2, f"{error}\n")
    host = "127.0.0.1"
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=args.port, proxy_headers=False))

    def open_panel():
        while not server.started and not server.should_exit:
            sleep(0.05)
        if server.started:
            webbrowser.open(f"http://{host}:{args.port}/")

    if not args.no_browser:
        Thread(target=open_panel, daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
