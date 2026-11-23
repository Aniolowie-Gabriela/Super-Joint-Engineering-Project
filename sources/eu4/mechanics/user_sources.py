"""Trwałe źródła użytkownika, przechowywane niezależnie od bazy gry."""

from contextlib import closing, contextmanager
from datetime import UTC, datetime
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit
from uuid import uuid4

from search import MORPH_END, STOP_WORDS, normalize, open_index


MAX_TITLE = 200
MAX_TEXT = 1_000_000
MAX_URL = 2048
CHUNK_SIZE = 1200
SCHEMA = (
    """CREATE TABLE source (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, text TEXT NOT NULL, url TEXT, updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE chunk (
        id INTEGER PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source(id) ON DELETE CASCADE,
        part INTEGER NOT NULL, text TEXT NOT NULL, UNIQUE(source_id, part)
    )""",
    "CREATE VIRTUAL TABLE source_lookup USING fts5(title, body, tokenize='unicode61 remove_diacritics 2')",
)
GENERIC_QUESTION_WORDS = STOP_WORDS | frozenset(
    " atlas bedzie beda dalej dlaczego dziala dzialaja dzialalo eu4 gram grac gra graczu gry jest jestem "
    "jesli jezeli moze moge moga mozna powiedz robic trzeba warto wiem wiesz wyjasnij zrobic zrobilem "
    "zwieksza zmniejsza wedlug".split()
)


def user_data_dir():
    override = os.environ.get("EU4_USER_DATA_DIR")
    if override:
        return Path(override).expanduser()
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(root).expanduser() / "AtlasEU4"


def clean_source(title, body, url):
    title = title.strip()
    body = body.strip()
    url = url.strip() if url else None
    if not title or len(title) > MAX_TITLE:
        raise ValueError(f"Wpisz tytuł do {MAX_TITLE} znaków.")
    if not body or len(body) > MAX_TEXT:
        raise ValueError("Wpisz tekst źródła o długości do 1 miliona znaków.")
    if url:
        try:
            parsed = urlsplit(url)
            if (len(url) > MAX_URL or parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or any(char.isspace() or ord(char) < 32 for char in url)):
                raise ValueError
        except ValueError:
            raise ValueError("Podaj pełny adres strony zaczynający się od http:// lub https://.") from None
    return title, body, url or None


def split_source(body):
    start = 0
    while start < len(body):
        end = min(len(body), start + CHUNK_SIZE)
        if end < len(body):
            for separator in ("\n\n", "\n", " "):
                boundary = body.rfind(separator, start + CHUNK_SIZE * 3 // 4, end)
                if boundary != -1:
                    end = boundary
                    break
        fragment = body[start:end].strip()
        if fragment:
            yield fragment
        start = end


def tokens(value):
    return re.findall(r"[^\W_]+", normalize(value))


def search_words(query, for_chat=False):
    words = []
    for word in tokens(query):
        if for_chat and (len(word) < 3 or word in GENERIC_QUESTION_WORDS):
            continue
        stem = MORPH_END.sub("", word)
        words.append(stem if len(stem) >= 4 else word)
    return list(dict.fromkeys(words))[:24]


def fts_match(words):
    return " OR ".join(f'"{word}"*' for word in words)


def source_record(row):
    return {
        "chunk_id": f"user:{row['source_id']}:{row['part']}",
        "document_id": f"user:{row['source_id']}",
        "user_source_id": row["source_id"],
        "title": row["title"],
        "symbol": row["title"],
        "family": "user_sources",
        "source_type": "user_source",
        "section": f"Fragment {row['part']}",
        "text": row["text"],
        "source_url": row["url"],
        "source_path": row["url"] or "Źródła użytkownika",
        "lines": None,
        "game_version": None,
    }


class UserSources:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else user_data_dir() / "user-sources.sqlite3"

    @contextmanager
    def read(self):
        if not self.path.is_file():
            yield None
            return
        with closing(open_index(self.path)) as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, 1}:
                raise RuntimeError("Zaktualizuj Atlas EU4, aby odczytać własne źródła.")
            yield db if version == 1 else None

    @contextmanager
    def write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                for ddl in SCHEMA:
                    db.execute(ddl)
                db.execute("PRAGMA user_version = 1")
            elif version != 1:
                raise RuntimeError("Zaktualizuj Atlas EU4, aby zapisać własne źródła.")
            yield db

    @staticmethod
    def metadata(db, source_id):
        row = db.execute("""
            SELECT source.*, (SELECT COUNT(*) FROM chunk WHERE source_id = source.id) AS chunks
            FROM source WHERE id = ?
        """, (source_id,)).fetchone()
        return dict(row) if row is not None else None

    def list(self):
        with self.read() as db:
            if db is None:
                return []
            return [dict(row) for row in db.execute("""
                SELECT id, title, url, updated_at,
                       (SELECT COUNT(*) FROM chunk WHERE source_id = source.id) AS chunks
                FROM source ORDER BY updated_at DESC, id
            """)]

    def get(self, source_id):
        with self.read() as db:
            return self.metadata(db, source_id) if db is not None else None

    @staticmethod
    def remove_chunks(db, source_id):
        db.execute("DELETE FROM source_lookup WHERE rowid IN (SELECT id FROM chunk WHERE source_id = ?)", (source_id,))
        db.execute("DELETE FROM chunk WHERE source_id = ?", (source_id,))

    def save(self, title, body, url=None, source_id=None):
        title, body, url = clean_source(title, body, url)
        if source_id is not None and not self.path.is_file():
            return None
        now = datetime.now(UTC).isoformat(timespec="microseconds")
        with self.write() as db:
            if source_id is None:
                source_id = uuid4().hex
                db.execute("INSERT INTO source VALUES (?, ?, ?, ?, ?)", (source_id, title, body, url, now))
            else:
                updated = db.execute("""
                    UPDATE source SET title = ?, text = ?, url = ?, updated_at = ? WHERE id = ?
                """, (title, body, url, now, source_id))
                if not updated.rowcount:
                    return None
                self.remove_chunks(db, source_id)
            for part, fragment in enumerate(split_source(body), 1):
                row = db.execute("INSERT INTO chunk(source_id, part, text) VALUES (?, ?, ?)", (source_id, part, fragment))
                db.execute("INSERT INTO source_lookup(rowid, title, body) VALUES (?, ?, ?)",
                           (row.lastrowid, normalize(title), normalize(fragment)))
            return self.metadata(db, source_id)

    def delete(self, source_id):
        if not self.path.is_file():
            return False
        with self.write() as db:
            self.remove_chunks(db, source_id)
            return bool(db.execute("DELETE FROM source WHERE id = ?", (source_id,)).rowcount)

    def record(self, chunk_id):
        coordinates = re.fullmatch(r"user:([0-9a-f]{32}):(\d{1,8})", chunk_id)
        if coordinates is None:
            return None
        with self.read() as db:
            if db is None:
                return None
            row = db.execute("""
                SELECT chunk.*, source.title, source.url FROM chunk JOIN source ON source.id = chunk.source_id
                WHERE chunk.source_id = ? AND chunk.part = ?
            """, (coordinates[1], int(coordinates[2]))).fetchone()
        return source_record(row) if row is not None else None

    @staticmethod
    def find_chunks(db, match, limit, offset=0):
        if match:
            return db.execute("""
                SELECT chunk.*, source.title, source.url
                FROM source_lookup JOIN chunk ON chunk.id = source_lookup.rowid
                JOIN source ON source.id = chunk.source_id
                WHERE source_lookup MATCH ?
                ORDER BY bm25(source_lookup, 7, 1), chunk.source_id, chunk.part LIMIT ? OFFSET ?
            """, (match, limit, offset))
        return db.execute("""
            SELECT chunk.*, source.title, source.url FROM chunk JOIN source ON source.id = chunk.source_id
            ORDER BY source.updated_at DESC, chunk.source_id, chunk.part LIMIT ? OFFSET ?
        """, (limit, offset))

    def browse(self, query, limit, offset):
        match = fts_match(search_words(query))
        if query and not match:
            return [], 0
        with self.read() as db:
            if db is None:
                return [], 0
            if match:
                count = db.execute("SELECT COUNT(*) FROM source_lookup WHERE source_lookup MATCH ?", (match,)).fetchone()[0]
            else:
                count = db.execute("SELECT COUNT(*) FROM chunk").fetchone()[0]
            items = [source_record(row) for row in self.find_chunks(db, match, limit, offset)]
        return items, count

    def context(self, question, limit=3):
        words = search_words(question, for_chat=True)
        if not words:
            return []
        with self.read() as db:
            if db is None:
                return []
            candidates = self.find_chunks(db, fts_match(words), 32)
            ranked = []
            for row in candidates:
                title = tokens(row["title"])
                text = title + tokens(row["text"])
                matches = sum(any(token.startswith(word) for token in text) for word in words)
                title_matches = sum(any(token.startswith(word) for token in title) for word in words)
                if matches >= min(2, len(words)) or title_matches and len(title) == 1:
                    ranked.append((matches, title_matches, source_record(row)))
            ranked.sort(key=lambda pair: pair[:2], reverse=True)
            return [record for _, _, record in ranked[:limit]]
