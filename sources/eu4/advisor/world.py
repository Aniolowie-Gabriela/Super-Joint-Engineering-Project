"""Bieżące odczyty Tongs i tekstowe dane z instalacji EU4."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from importlib.util import find_spec
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from zipfile import BadZipFile, ZipFile


LIVE_TOOLS = frozenset({
    "tongs_state", "tongs_player", "tongs_country", "tongs_province", "tongs_units",
    "tongs_selection", "tongs_cursor", "tongs_event_list", "tongs_ui_find", "tongs_ui_tree",
    "tongs_window", "tongs_frames", "tongs_threads", "tongs_journal",
})
CONTENT_ROOTS = (
    "common", "history", "missions", "events", "decisions", "localisation",
    "customizable_localization", "map", "interface", "gfx", "tutorial", "dlc_metadata",
    "builtin_dlc", "dlc",
)
ROOT_FILES = ("hints", "patchnotes", "eu4_branch.txt", "eu4_rev.txt", "checksum_manifest.txt")
TEXT_SUFFIXES = frozenset({".asset", ".csv", ".dlc", ".gfx", ".gui", ".lua", ".map", ".txt", ".yml", ".yaml"})
DLC_PATH = re.compile(r"(?:builtin_dlc|dlc)/dlc\d{3}_[^/]+/dlc\d{3}\.zip", re.IGNORECASE)
PRIVATE_NAME = re.compile(
    r"(?:api[-_ ]?keys?|credentials?|passwords?|secrets?|tokens?|userdata|private|logs?)(?:[._ -]|$)",
    re.IGNORECASE,
)
INVALID_PATH = re.compile(r'[:<>"|?*\x00-\x1f]')
WINDOWS_DEVICE = re.compile(r"(?:con|prn|aux|nul|(?:com|lpt)[1-9¹²³])(?:\.|$)", re.IGNORECASE)
MAX_FILE_BYTES = 12 * 1024 * 1024
MAX_SCAN_BYTES = 32 * 1024 * 1024
MAX_SCAN_FILES = 2500
MAX_LINE_CHARS = 2000
MAX_PAGE_CHARS = 16000


@dataclass(frozen=True)
class SourceFile:
    path: str
    size: int


def steam_paths():
    if os.name != "nt":
        return
    import winreg

    keys = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
    )
    for hive, key_name, value in keys:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                steam = Path(winreg.QueryValueEx(key, value)[0])
        except OSError:
            continue
        yield steam
        try:
            libraries = (steam / "steamapps/libraryfolders.vdf").read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        for path in re.findall(r'^\s*"path"\s*"((?:[^"\\]|\\.)*)"', libraries, re.MULTILINE):
            yield Path(path.replace("\\\\", "\\"))


def game_location(configured):
    if configured is not None:
        yield Path(configured).expanduser()
        return
    for steam in dict.fromkeys(steam_paths()):
        yield steam / "steamapps/common/Europa Universalis IV"


def game_version(path):
    try:
        settings = path / "launcher-settings.json"
        safe_stat(settings, directory=False)
        with settings.open("rb") as stream:
            data = json.loads(stream.read(65536).decode("utf-8-sig"))
        if data.get("gameId") == "eu4" and isinstance(data.get("rawVersion"), str):
            return data["rawVersion"].removeprefix("v")
    except (OSError, ValueError, AttributeError):
        pass
    return None


def plain_relative(path):
    parts = path.split("/")
    if (
        len(path) > 512 or "!" in path or INVALID_PATH.search(path)
        or any(
            not part or part.startswith(".") or part.endswith((".", " "))
            or PRIVATE_NAME.match(part) or WINDOWS_DEVICE.match(part)
            for part in parts
        )
    ):
        raise ValueError("Użyj względnej ścieżki do pliku gry, zgodnej z wynikiem listowania.")
    return parts


def source_path(value, directory=False):
    value = value.replace("\\", "/")
    if directory:
        if not value:
            return ""
        if value != "/":
            value = value.removesuffix("/")
    archive, separator, member = value.partition("!/")
    parts = plain_relative(archive)
    if separator:
        if not DLC_PATH.fullmatch(archive):
            raise ValueError("Wybierz ścieżkę do tekstowego wpisu z archiwum DLC gry.")
        parts = plain_relative(member)
    if parts[0].casefold() not in CONTENT_ROOTS and (len(parts) != 1 or parts[0].casefold() not in ROOT_FILES):
        raise ValueError("Wybierz katalog lub plik wymieniony w danych instalacji EU4.")
    return value


def text_file(path):
    relative = PurePosixPath(path)
    return (
        len(relative.parts) == 1 and relative.name.casefold() in ROOT_FILES
        or relative.suffix.casefold() in TEXT_SUFFIXES
        or relative.parts[0].casefold() == "dlc_metadata" and relative.suffix.casefold() == ".json"
    )


def safe_stat(path, *, directory):
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise FileNotFoundError(path.name)
    if not directory and info.st_nlink > 1:
        raise FileNotFoundError(path.name)
    return info


def installed_files(root):
    for name in ROOT_FILES:
        try:
            yield SourceFile(name, safe_stat(root / name, directory=False).st_size)
        except OSError:
            pass
    for scope in CONTENT_ROOTS:
        try:
            safe_stat(root / scope, directory=True)
        except OSError:
            continue
        for current, folders, files in os.walk(root / scope):
            folder = Path(current)
            for name in folders[:]:
                try:
                    plain_relative(name)
                    safe_stat(folder / name, directory=True)
                except (OSError, ValueError):
                    folders.remove(name)
            for name in files:
                path = folder / name
                relative = path.relative_to(root).as_posix()
                if not text_file(relative) and not DLC_PATH.fullmatch(relative):
                    continue
                try:
                    plain_relative(relative)
                    yield SourceFile(relative, safe_stat(path, directory=False).st_size)
                except (OSError, ValueError):
                    continue


def archive_files(root, archive):
    with ZipFile(root / archive.path) as package:
        for member in package.infolist():
            if member.is_dir() or "\\" in member.filename or stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1:
                continue
            display_path = f"{archive.path}!/{member.filename}"
            try:
                source_path(display_path)
            except ValueError:
                continue
            if text_file(member.filename):
                yield SourceFile(display_path, member.file_size)


def within(path, directory):
    return not directory or path == directory or path.startswith(directory + "/") or path.startswith(directory + "!/")


def decode_lines(raw, path):
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text, encoding = raw.decode("utf-16"), "utf-16"
    elif b"\x00" in raw:
        raise ValueError("Odczyt jest dostępny dla tekstowych plików gry.")
    else:
        try:
            text, encoding = raw.decode("utf-8-sig"), "utf-8"
        except UnicodeDecodeError:
            polish = "_l_polish." in path.casefold() or raw.lstrip().startswith(b"l_polish:")
            encoding = "cp1250" if polish else "cp1252"
            text = raw.decode(encoding, errors="replace")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines[-1]:
        lines.pop()
    return lines, encoding


def check_range(value, lower, upper, label):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{label} musi być liczbą całkowitą od {lower} do {upper}.")


class WorldSources:
    def __init__(self, game_dir: Path | str | None = None):
        configured = game_dir if game_dir is not None else os.environ.get("EU4_GAME_DIR")
        self.game_dir = None
        self.version = None
        for candidate in game_location(configured):
            try:
                root = candidate.resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            version = game_version(root)
            if version:
                self.game_dir, self.version = root, version
                break

    def status(self) -> dict:
        adapter_installed = find_spec("tongs_mcp") is not None
        return {
            "game_files": {
                "available": self.game_dir is not None, "game_version": self.version,
                "roots": list(CONTENT_ROOTS + ROOT_FILES),
            },
            "live": {"adapter_installed": adapter_installed, "tools": sorted(LIVE_TOOLS) if adapter_installed else []},
        }

    @cached_property
    def inventory(self):
        if self.game_dir is None:
            raise ValueError("Brak dostępu do instalacji EU4. Wskaż katalog gry przez EU4_GAME_DIR lub --game-dir.")
        files = {}
        unavailable = []
        for source in installed_files(self.game_dir):
            try:
                items = archive_files(self.game_dir, source) if DLC_PATH.fullmatch(source.path) else (source,)
                for item in items:
                    files.setdefault(item.path.casefold(), item)
            except (OSError, ValueError, BadZipFile):
                unavailable.append(source.path)
        return dict(sorted(files.items())), unavailable

    def _provenance(self):
        return {"source": "installed_game_files", "game_version": self.version}

    def list_files(self, directory: str = "", query: str = "", offset: int = 0, limit: int = 30) -> dict:
        """Lista ścieżek ze wskazanego katalogu, opcjonalnie filtrowana fragmentem nazwy."""
        check_range(offset, 0, 100000, "Przesunięcie")
        check_range(limit, 1, 100, "Liczba plików")
        if len(query) > 200:
            raise ValueError("Fragment ścieżki może mieć najwyżej 200 znaków.")
        directory = source_path(directory, directory=True).casefold()
        query = query.strip().replace("\\", "/").casefold()
        inventory, unreadable_archives = self.inventory
        matches = [entry for path, entry in inventory.items() if within(path, directory) and query in path]
        page = matches[offset:offset + limit]
        return {
            **self._provenance(), "total": len(matches),
            "files": [{"path": entry.path, "bytes": entry.size} for entry in page],
            "next_offset": offset + len(page) if offset + len(page) < len(matches) else None,
            "unreadable_archives": unreadable_archives,
        }

    def _lines(self, entry):
        if entry.size > MAX_FILE_BYTES:
            raise ValueError("Plik przekracza limit 12 MiB dla odczytu tekstowego.")
        archive, separator, member = entry.path.partition("!/")
        parts = archive.split("/")
        path = self.game_dir
        safe_stat(path, directory=True)
        for part in parts[:-1]:
            path /= part
            safe_stat(path, directory=True)
        path /= parts[-1]
        safe_stat(path, directory=False)
        if separator:
            with ZipFile(path) as package, package.open(member) as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
        else:
            with path.open("rb") as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("Plik przekracza limit 12 MiB dla odczytu tekstowego.")
        return decode_lines(raw, entry.path)

    def read_file(self, path: str, start_line: int = 1, line_count: int = 80) -> dict:
        """Odczyt strony tekstu ze ścieżki zwróconej przez listowanie lub wyszukiwanie."""
        check_range(start_line, 1, MAX_FILE_BYTES, "Pierwszy wiersz")
        check_range(line_count, 1, 160, "Liczba wierszy")
        key = source_path(path).casefold()
        inventory, _ = self.inventory
        entry = inventory.get(key)
        if entry is None:
            raise ValueError("Wybierz dostępny plik tekstowy gry z wyników listowania lub wyszukiwania.")
        try:
            lines, encoding = self._lines(entry)
        except (OSError, BadZipFile, KeyError, RuntimeError):
            raise ValueError("Plik gry jest obecnie niedostępny.") from None
        page = []
        remaining = MAX_PAGE_CHARS
        for number, text in enumerate(lines[start_line - 1:start_line - 1 + line_count], start_line):
            shown = text[:MAX_LINE_CHARS]
            if len(shown) + 1 > remaining:
                break
            page.append({"line": number, "text": shown, "truncated": len(text) > len(shown)})
            remaining -= len(shown) + 1
        next_line = start_line + len(page)
        return {
            **self._provenance(), "path": entry.path, "encoding": encoding, "total_lines": len(lines),
            "lines": page, "next_line": next_line if next_line <= len(lines) else None,
        }

    def search_files(self, query: str, directory: str = "", limit: int = 20,
                     after_path: str | None = None, after_line: int = 0) -> dict:
        """Wyszukiwanie dosłownego tekstu w plikach z numerami znalezionych wierszy."""
        query = query.strip()
        if not 1 <= len(query) <= 200 or any(c in query for c in "\r\n\x00"):
            raise ValueError("Wpisz fragment jednego wiersza od 1 do 200 znaków.")
        check_range(limit, 1, 30, "Liczba dopasowań")
        check_range(after_line, 0, MAX_FILE_BYTES, "Wiersz kontynuacji")
        directory = source_path(directory, directory=True).casefold()
        cursor = source_path(after_path).casefold() if after_path else ""
        if (after_line and not cursor) or (cursor and not within(cursor, directory)):
            raise ValueError("Użyj ścieżki i wiersza kontynuacji z poprzedniej strony wyników.")
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        matches = []
        scanned, scanned_bytes, skipped = 0, 0, 0
        next_page = None
        inventory, unreadable_archives = self.inventory
        for path, entry in inventory.items():
            if not within(path, directory) or path < cursor or (path == cursor and not after_line):
                continue
            if entry.size > MAX_FILE_BYTES:
                skipped += 1
                continue
            if scanned == MAX_SCAN_FILES or scanned_bytes + entry.size > MAX_SCAN_BYTES:
                break
            scanned += 1
            scanned_bytes += entry.size
            next_page = {"after_path": entry.path, "after_line": 0}
            try:
                lines, _ = self._lines(entry)
            except (OSError, ValueError, BadZipFile, KeyError, RuntimeError):
                skipped += 1
                continue
            first = after_line if path == cursor else 0
            for number, line in enumerate(lines[first:], first + 1):
                match = pattern.search(line)
                if match is None:
                    continue
                begin = max(0, match.start() - 150)
                end = min(len(line), match.end() + 150)
                matches.append({
                    "path": entry.path, "line": number, "text": line[begin:end],
                    "truncated": bool(begin or end < len(line)),
                })
                if len(matches) == limit:
                    next_page["after_line"] = number
                    break
            if len(matches) == limit:
                break
        else:
            next_page = None
        return {
            **self._provenance(), "matches": matches, "next": next_page, "files_scanned": scanned,
            "files_skipped": skipped, "unreadable_archives": unreadable_archives,
        }

    @cached_property
    def _live(self):
        try:
            from tongs_mcp.server import build_server
        except ModuleNotFoundError as exc:
            if exc.name != "tongs_mcp":
                raise
            return None
        return build_server()

    async def live_tools(self):
        if self._live is None:
            return []
        return [
            tool for tool in await self._live.list_tools()
            if tool.name in LIVE_TOOLS and tool.annotations
            and tool.annotations.read_only_hint is True and tool.annotations.destructive_hint is False
        ]

    async def call_live(self, name: str, arguments: dict):
        if name not in LIVE_TOOLS:
            raise ValueError("To narzędzie Tongs nie jest dozwolonym odczytem.")
        if self._live is None:
            raise ValueError("Brak lokalnego pakietu tongs_mcp w środowisku serwera.")
        if not any(tool.name == name for tool in await self.live_tools()):
            raise ValueError("Zainstalowany Tongs nie udostępnia tego narzędzia jako odczytu.")
        return await self._live.call_tool(name, arguments)
