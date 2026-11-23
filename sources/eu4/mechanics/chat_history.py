"""Lokalna historia rozmów oraz migawki odpowiedzi i źródeł."""

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response


SCHEMA = """
CREATE TABLE IF NOT EXISTS chat (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message (
    id INTEGER PRIMARY KEY,
    chat_id TEXT NOT NULL REFERENCES chat(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources TEXT NOT NULL,
    diagnostics TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS message_chat ON message(chat_id, id);
"""


class ChatHistoryError(Exception):
    def __init__(self):
        super().__init__(self.message)


class ChatNotFound(ChatHistoryError):
    status_code = 404
    message = "Ta rozmowa została usunięta. Otwórz nowy czat."


class ChatConflict(ChatHistoryError):
    status_code = 409
    message = "W tej rozmowie pojawiła się nowa wiadomość. Odśwież rozmowę i spróbuj ponownie."


class HistoryUnavailable(ChatHistoryError):
    status_code = 503
    message = "Nie udało się odczytać lub zapisać historii rozmów. Spróbuj ponownie."


def history_path():
    override = os.environ.get("EU4_USER_DATA_DIR")
    if override:
        return Path(override).expanduser() / "chats.sqlite3"
    data = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    base = Path(data).expanduser() if data else Path.home() / ".local" / "share"
    return base / "AtlasEU4" / "chats.sqlite3"


def message_data(row):
    return {**dict(row), "sources": json.loads(row["sources"]),
            "diagnostics": json.loads(row["diagnostics"])}


class ChatHistory:
    def __init__(self, path=None):
        self.path = history_path() if path is None else Path(path)
        self._ready = False
        self._initialize_lock = Lock()

    @contextmanager
    def _connection(self):
        try:
            with self._initialize_lock:
                if not self._ready:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    with closing(sqlite3.connect(self.path)) as db:
                        db.executescript(SCHEMA)
                    self._ready = True
            with closing(sqlite3.connect(self.path)) as db, db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA foreign_keys = ON")
                yield db
        except (OSError, sqlite3.Error, json.JSONDecodeError) as error:
            raise HistoryUnavailable() from error

    def list(self):
        with self._connection() as db:
            return [dict(row) for row in db.execute(
                "SELECT id, title, updated_at FROM chat ORDER BY updated_at DESC, id DESC"
            )]

    def get(self, chat_id):
        with self._connection() as db:
            db.execute("BEGIN")
            chat = db.execute("SELECT id, title, updated_at FROM chat WHERE id = ?", (chat_id,)).fetchone()
            if chat is None:
                raise ChatNotFound()
            rows = db.execute("""
                SELECT id, question, answer, sources, diagnostics, created_at
                FROM message WHERE chat_id = ? ORDER BY id
            """, (chat_id,))
            return {**dict(chat), "messages": [message_data(row) for row in rows]}

    def last_message(self, chat_id):
        with self._connection() as db:
            row = db.execute("""
                SELECT id, question, answer, sources, diagnostics, created_at
                FROM message WHERE chat_id = ? ORDER BY id DESC LIMIT 1
            """, (chat_id,)).fetchone()
            if row is None:
                raise ChatNotFound()
            return message_data(row)

    def append(self, *, chat_id, expected_message_id, question, answer, sources, diagnostics):
        sources_json = json.dumps(sources, ensure_ascii=False)
        diagnostics_json = json.dumps(diagnostics, ensure_ascii=False)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            if chat_id is None:
                chat_id = uuid4().hex
                title = " ".join(question.split())
                if len(title) > 72:
                    title = title[:71].rstrip() + "…"
                db.execute("INSERT INTO chat VALUES (?, ?, ?)", (chat_id, title, now))
            else:
                last = db.execute("""
                    SELECT id FROM message WHERE chat_id = ? ORDER BY id DESC LIMIT 1
                """, (chat_id,)).fetchone()
                if last is None:
                    raise ChatNotFound()
                if last["id"] != expected_message_id:
                    raise ChatConflict()
                db.execute("UPDATE chat SET updated_at = ? WHERE id = ?", (now, chat_id))
            inserted = db.execute("""
                INSERT INTO message (chat_id, question, answer, sources, diagnostics, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (chat_id, question, answer, sources_json, diagnostics_json, now))
        return chat_id, inserted.lastrowid

    def delete(self, chat_id):
        with self._connection() as db:
            db.execute("DELETE FROM chat WHERE id = ?", (chat_id,))


def history_router(history):
    router = APIRouter(prefix="/api/chats")

    @router.get("")
    def chats():
        try:
            return {"items": history.list()}
        except ChatHistoryError as error:
            raise HTTPException(error.status_code, str(error)) from error

    @router.get("/{chat_id}")
    def chat(chat_id: str):
        try:
            return history.get(chat_id)
        except ChatHistoryError as error:
            raise HTTPException(error.status_code, str(error)) from error

    @router.delete("/{chat_id}", status_code=204)
    def delete_chat(chat_id: str):
        try:
            history.delete(chat_id)
        except ChatHistoryError as error:
            raise HTTPException(error.status_code, str(error)) from error
        return Response(status_code=204)

    return router
