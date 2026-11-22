"""Historia asystenta głosowego: pytania, odpowiedzi, źródła wysłane agentowi i ostrzeżenia.

Wszystko trafia do jednej tabeli zdarzeń, w kolejności, w jakiej się wydarzyło:
  user    — transkrypcja pytania gracza
  agent   — odpowiedź agenta
  search  — wyszukiwanie agenta; text = zapytanie, data = dokładnie ten JSON, który dostał agent
  record  — pełny fragment przeczytany przez agenta; text = chunk_id, data = JSON dla agenta
  log     — ostrzeżenia i błędy aplikacji
Rozmowa (session_id) to jedno połączenie z agentem. Logi spoza rozmowy mają session_id NULL.
"""

from datetime import datetime
import json
import sqlite3
import threading

KINDS = ("user", "agent", "search", "record", "log")


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


class History:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Zapisy przychodzą z wątków SDK ElevenLabs i logowania, odczyty z serwera okna.
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                session_id INTEGER,
                kind TEXT NOT NULL,
                text TEXT NOT NULL DEFAULT '',
                data TEXT,
                at TEXT NOT NULL)""")
            self.db.execute("CREATE INDEX IF NOT EXISTS events_session ON events(session_id, id)")

    def close(self):
        with self.lock:
            self.db.close()

    def new_session(self):
        """Numer następnej rozmowy. Rozmowa bez zdarzeń nie zajmuje numeru, więc nie ma pustych wpisów."""
        with self.lock:
            return self.db.execute("SELECT COALESCE(MAX(session_id), 0) + 1 FROM events").fetchone()[0]

    def add(self, session_id, kind, text, data=None):
        if kind not in KINDS:
            raise ValueError(f"Nieznany rodzaj zdarzenia: {kind}")
        if data is not None and not isinstance(data, str):
            data = json.dumps(data, ensure_ascii=False)
        with self.lock:
            cursor = self.db.execute(
                "INSERT INTO events (session_id, kind, text, data, at) VALUES (?, ?, ?, ?, ?)",
                (session_id, kind, text or "", data, now()))
            return cursor.lastrowid

    def last_id(self):
        with self.lock:
            return self.db.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()[0]

    def sessions(self, query=None, limit=200):
        """Rozmowy od najnowszej; query szuka w pytaniach, odpowiedziach i zapytaniach agenta."""
        where, params = "session_id IS NOT NULL", []
        if query and query.strip():
            pattern = "%" + query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where += """ AND session_id IN (SELECT session_id FROM events
                         WHERE kind IN ('user', 'agent', 'search') AND text LIKE ? ESCAPE '\\')"""
            params.append(pattern)
        sql = f"""SELECT session_id AS id, MIN(at) AS started, MAX(at) AS ended,
                         SUM(kind = 'user') AS questions, SUM(kind = 'search') AS searches,
                         SUM(kind = 'log') AS warnings,
                         (SELECT text FROM events f WHERE f.session_id = e.session_id AND f.kind = 'user'
                          ORDER BY f.id LIMIT 1) AS title
                  FROM events e WHERE {where}
                  GROUP BY session_id ORDER BY session_id DESC LIMIT ?"""
        with self.lock:
            return [dict(row) for row in self.db.execute(sql, (*params, limit))]

    def session(self, session_id):
        return self._events("WHERE session_id = ? ORDER BY id", (session_id,))

    def since(self, after_id, limit=500):
        return self._events("WHERE id > ? ORDER BY id LIMIT ?", (after_id, limit))

    def logs(self, limit=300):
        return self._events("WHERE kind = 'log' ORDER BY id DESC LIMIT ?", (limit,))

    def _events(self, tail, params):
        with self.lock:
            rows = [dict(row) for row in self.db.execute(f"SELECT * FROM events {tail}", params)]
        for row in rows:
            if row["data"] is not None:
                try:
                    row["data"] = json.loads(row["data"])
                except ValueError:
                    pass
        return rows
