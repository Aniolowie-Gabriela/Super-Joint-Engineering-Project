"""Read-only navigation of local EU4 save snapshots."""

from __future__ import annotations

from collections import Counter, OrderedDict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from itertools import islice
import os
from pathlib import Path
import re
import stat
import subprocess
from threading import Event, RLock, Thread, Timer
import zipfile
import zlib

try:
    from compression.zstd import ZstdError
except ImportError:
    _ZSTD_ERRORS = ()
else:
    _ZSTD_ERRORS = (ZstdError,)


MAX_PAGE_SIZE = 50
_MAX_BYTES = 256 * 1024 * 1024
_PREVIEW_BYTES = 128 * 1024
_MAX_DEPTH = 1024
_MAX_BLOCKS = 2_000_000
_TEXT_HEADER = re.compile(rb"(?:\xef\xbb\xbf)?[ \t\r\n]*EU4txt(?=\s|$)")
_BINARY_HEADER = b"EU4bin"
_QUOTED = rb'"(?:[^"\\]++|\\[\s\S])*+"'
_COMMENT = rb"#[^\r\n]*"
_DELIMITER = re.compile(_QUOTED + rb"|" + _COMMENT + rb'|[{}"]|\x00')
_WHITESPACE = re.compile(rb"(?:[ \r\n\t\f\v;]+|" + _COMMENT + rb")*")
_TOKEN = re.compile(_QUOTED + rb"|(?:[^\s;{}\"#<>=!?\x00]++|[!?](?!=))++")
_KEY = re.compile(_TOKEN.pattern + rb"|=(?==)")
_OPERATOR = re.compile(rb"(?:<=|>=|!=|\?=|==|[<>=])")
_ESCAPE = re.compile(rb'\\(["\\])')
_SAVE_NAME = re.compile(r'[^/\\:<>|?*"\x00-\x1f]+\.eu4', re.IGNORECASE)
_METADATA = {"date": "game_date", "player": "player", "campaign_id": "campaign_id"}
_ARCHIVE_SECTIONS = ("meta", "gamestate", "ai")
_ZIP_ERRORS = (zipfile.BadZipFile, EOFError, RuntimeError, zlib.error, *_ZSTD_ERRORS)

Selector = str | int | dict[str, str | int]


class SaveError(ValueError):
    """A user-facing save access error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _invalid(detail: str) -> SaveError:
    return SaveError("invalid_save", detail)


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


@dataclass(frozen=True, slots=True)
class _Entry:
    key: str | None
    start: int
    end: int
    container: bool
    operator: str | None = None
    tag: str | None = None


class _Text:
    """An immutable byte buffer with a compact index of matching braces."""

    def __init__(self, data: bytes, *, header_required: bool = False, partial: bool = False):
        header = _TEXT_HEADER.match(data)
        if header_required and header is None:
            raise _invalid("Oczekiwano tekstowego nagłówka EU4txt.")
        self.data = data
        self.start = header.end() if header else 0
        self.braces: dict[int, int] = {}
        stack: list[int] = []
        for match in _DELIMITER.finditer(data, self.start):
            char = data[match.start()]
            if char == ord("{"):
                stack.append(match.start())
                if len(stack) > _MAX_DEPTH:
                    raise _invalid("Zapis przekracza obsługiwaną głębokość zagnieżdżenia.")
            elif char == ord("}"):
                if not stack:
                    raise _invalid("Zapis zawiera nadmiarowy nawias zamykający.")
                if len(self.braces) >= _MAX_BLOCKS:
                    raise SaveError("save_too_large", "Zapis przekracza limit dwóch milionów bloków.")
                self.braces[stack.pop()] = match.start()
            elif char == 0 or (char == ord('"') and match.end() - match.start() == 1):
                if not partial:
                    raise _invalid("Zapis zawiera niekompletną wartość tekstową.")
                break
        if stack and not partial:
            raise _invalid("Zapis kończy się przed zamknięciem wszystkich bloków.")

    def scalar(self, start: int, end: int) -> str:
        raw = self.data[start:end]
        if raw.startswith(b'"'):
            raw = _ESCAPE.sub(rb"\1", raw[1:-1])
        return _decode(raw)

    def entries(self, start: int, end: int) -> Iterator[_Entry]:
        data = self.data
        cursor = _WHITESPACE.match(data, start, end).end()
        while cursor < end:
            key = operator = tag = None
            value_at = cursor
            if data[cursor] != ord("{"):
                token = _KEY.match(data, cursor, end)
                if token is None:
                    raise _invalid(f"Nieprawidłowy element zapisu przy bajcie {cursor}.")
                operator_at = _WHITESPACE.match(data, token.end(), end).end()
                assignment = _OPERATOR.match(data, operator_at, end)
                if assignment:
                    key = self.scalar(cursor, token.end())
                    operator = assignment.group().decode("ascii")
                    value_at = _WHITESPACE.match(data, assignment.end(), end).end()
                    token = _TOKEN.match(data, value_at, end)
                    if token and data[value_at] != ord('"'):
                        tag_end = _WHITESPACE.match(data, token.end(), end).end()
                        if tag_end < end and data[tag_end] == ord("{"):
                            tag = self.scalar(value_at, token.end())
                            value_at = tag_end
            else:
                token = None

            if value_at < end and data[value_at] == ord("{"):
                close = self.braces.get(value_at)
                if close is None or close >= end:
                    raise _invalid("Zapis zawiera niekompletny blok.")
                yield _Entry(key, value_at + 1, close, True, operator, tag)
                cursor = close + 1
            elif token is not None:
                yield _Entry(key, value_at, token.end(), False, operator)
                cursor = token.end()
            else:
                raise _invalid(f"Brak wartości przy bajcie {value_at}.")
            cursor = _WHITESPACE.match(data, cursor, end).end()


_Node = tuple[_Text, _Entry]


class _Snapshot:
    def __init__(self, parts: Sequence[_Text], format_name: str):
        self.format = format_name
        self.parts = parts
        prefix = list(islice(self._root(), 1025))
        self._root_cache = prefix if len(prefix) <= 1024 else None
        self.metadata = _metadata(iter(prefix))

    def _root(self) -> Iterator[_Node]:
        for part in self.parts:
            for entry in part.entries(part.start, len(part.data)):
                yield part, entry

    def children(self, node: _Node | None) -> Iterator[_Node]:
        if node is None:
            return self._root() if self._root_cache is None else iter(self._root_cache)
        part, entry = node
        return ((part, child) for child in part.entries(entry.start, entry.end))

    def section(self, path: Sequence[Selector] = ()) -> SaveNode:
        return SaveNode(self, _path(self, path), path[-1] if path else None)


def _metadata(entries: Iterator[_Node]) -> dict:
    result = dict.fromkeys(_METADATA.values())
    try:
        for part, entry in entries:
            name = _METADATA.get(entry.key)
            if name and not entry.container and result[name] is None:
                result[name] = part.scalar(entry.start, entry.end) or None
            if all(result.values()):
                break
    except SaveError:
        # A bounded metadata probe can end in the middle of a later entry.
        pass
    return result


@dataclass(frozen=True, slots=True)
class _File:
    path: Path
    root_index: int
    stamp: tuple[int, int, int, int, int]

    def info(self) -> dict:
        return {
            "source": "save",
            "save": self.path.name,
            "root_index": self.root_index,
            "modified_at": datetime.fromtimestamp(self.stamp[0] / 1e9, timezone.utc).isoformat(),
            "size_bytes": self.stamp[2],
        }


def _stamp(info: os.stat_result) -> tuple[int, int, int, int, int]:
    changed = info.st_birthtime_ns if os.name == "nt" else info.st_ctime_ns
    return (info.st_mtime_ns, changed, info.st_size, info.st_dev, info.st_ino)


def _unstable() -> SaveError:
    return SaveError("save_changing", "Zapis zmienił się podczas odczytu. Spróbuj ponownie po zakończeniu zapisywania.")


def _copy(file: _File, size: int | None = None) -> bytes:
    try:
        with file.path.open("rb") as handle:
            if _stamp(os.fstat(handle.fileno())) != file.stamp:
                raise _unstable()
            count = file.stamp[2] if size is None else min(size, file.stamp[2])
            data = handle.read(count + 1)
            if len(data) < count or _stamp(os.fstat(handle.fileno())) != file.stamp:
                raise _unstable()
        if _stamp(file.path.stat(follow_symlinks=False)) != file.stamp:
            raise _unstable()
    except OSError as error:
        raise SaveError("save_unreadable", "Nie udało się otworzyć lub odczytać zapisu.") from error
    return data[:count]


def _archive_parts(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    for info in archive.infolist():
        if info.filename in _ARCHIVE_SECTIONS:
            if info.filename in members or info.flag_bits & 1:
                raise _invalid("Zapis ZIP ma powtórzone lub zaszyfrowane sekcje EU4.")
            members[info.filename] = info
    if "gamestate" not in members:
        raise _invalid("Zapis ZIP nie zawiera sekcji gamestate.")
    if sum(info.file_size for info in members.values()) > _MAX_BYTES:
        raise SaveError("save_too_large", "Rozpakowany zapis przekracza limit 256 MiB.")
    return members


def _archive_read(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int | None = None) -> bytes:
    size = info.file_size if limit is None else min(info.file_size, limit)
    try:
        with archive.open(info) as member:
            body = member.read(size)
    except NotImplementedError as error:
        if info.compress_type == 93:
            reason = "Odczyt zapisu ZIP z kompresją Zstandard wymaga Pythona 3.14 lub nowszego."
        else:
            reason = f"Python nie obsługuje metody kompresji ZIP {info.compress_type} użytej w tym zapisie."
        raise SaveError("unsupported_zip_compression", reason) from error
    except _ZIP_ERRORS as error:
        raise _invalid(f"Nie udało się rozpakować sekcji {info.filename} zapisu EU4.") from error
    if len(body) != size:
        raise _invalid(f"Sekcja {info.filename} jest krótsza niż deklaruje archiwum zapisu.")
    return body


def _archive_for_rakaly(
    original: bytes, archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo],
    binary_name: str, binary_body: bytes,
) -> bytes:
    if any(section not in members for section in _ARCHIVE_SECTIONS):
        raise _invalid("Binarny zapis ZIP musi zawierać sekcje meta, gamestate i ai.")
    methods = {info.compress_type for info in members.values()}
    if methods == {zipfile.ZIP_DEFLATED} and len(archive.infolist()) == len(members):
        return original

    # The Windows Rakaly build accepts Deflate, including for archives with mixed original methods.
    # Python verifies sizes and CRCs while reading the original members.
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1) as compatible:
        for section in _ARCHIVE_SECTIONS:
            body = binary_body if section == binary_name else _archive_read(archive, members[section])
            if not body.startswith(_BINARY_HEADER):
                raise _invalid(f"Sekcja {section} binarnego zapisu ZIP nie ma nagłówka EU4bin.")
            compatible.writestr(section, body)
    return buffer.getvalue()


def _pagination(offset: int, limit: int) -> None:
    if type(offset) is not int or not 0 <= offset <= _MAX_BYTES or type(limit) is not int or not 1 <= limit <= MAX_PAGE_SIZE:
        raise SaveError("invalid_request", f"Offset musi być nieujemny, a limit mieścić się w zakresie 1–{MAX_PAGE_SIZE}.")


def _page(items: list, offset: int, limit: int) -> dict:
    return {
        "items": items[:limit],
        "offset": offset,
        "next_offset": offset + limit if len(items) > limit else None,
    }


def _entries_with_positions(entries: Iterator[_Node]) -> Iterator[tuple[Selector, _Node]]:
    counts: Counter[str] = Counter()
    for index, node in enumerate(entries):
        key = node[1].key
        if key is None or len(key) > 128:
            yield index, node
        else:
            occurrence = counts[key]
            counts[key] += 1
            yield {"key": key, "occurrence": occurrence}, node


def _path(snapshot: _Snapshot, path: Sequence[Selector]) -> _Node | None:
    if not isinstance(path, Sequence) or isinstance(path, (str, bytes)) or len(path) > _MAX_DEPTH:
        raise SaveError("invalid_request", "Podaj ścieżkę jako listę elementów zapisu.")
    current = None
    for position, segment in enumerate(path):
        if current and not current[1].container:
            raise SaveError("invalid_path", f"Element na pozycji {position - 1} jest wartością prostą.")
        children = snapshot.children(current)
        if type(segment) is int and 0 <= segment <= _MAX_BYTES:
            current = next(islice(children, segment, None), None)
        elif isinstance(segment, str):
            matches = islice((node for node in children if node[1].key == segment), 2)
            current = next(matches, None)
            if next(matches, None) is not None:
                raise SaveError("ambiguous_path", "Klucz się powtarza. Podaj obiekt z polami key i occurrence.")
        elif isinstance(segment, dict) and set(segment) == {"key", "occurrence"}:
            key, occurrence = segment["key"], segment["occurrence"]
            if not isinstance(key, str) or type(occurrence) is not int or not 0 <= occurrence <= _MAX_BYTES:
                raise SaveError("invalid_request", "Wskaźnik wymaga tekstowego key i nieujemnego occurrence.")
            current = next(islice((node for node in children if node[1].key == key), occurrence, None), None)
        else:
            raise SaveError("invalid_request", "Wskaźnik ścieżki musi być kluczem, pozycją lub obiektem key i occurrence.")
        if current is None:
            raise SaveError("missing_path", f"Brak elementu ścieżki na pozycji {position}.")
    return current


def _item(selector: Selector, node: _Node) -> dict:
    part, entry = node
    result = {"selector": selector, "kind": "container" if entry.container else "scalar"}
    if entry.key is not None:
        result["key"] = entry.key[:128]
    if entry.operator and entry.operator != "=":
        result["operator"] = entry.operator
    if entry.tag:
        result["tag"] = entry.tag[:128]
    if not entry.container:
        value = part.scalar(entry.start, entry.end)
        result["value"] = value[:256]
        if len(value) > 256:
            result["value_truncated"] = True
    return result


@dataclass(frozen=True, slots=True)
class SaveNode:
    """An entry in a pinned save, with lazy scalar and child access."""

    _snapshot: _Snapshot
    _node: _Node | None
    selector: Selector | None

    @property
    def key(self) -> str | None:
        return self._node[1].key if self._node else None

    @property
    def container(self) -> bool:
        return self._node is None or self._node[1].container

    @property
    def value(self) -> str | None:
        if self.container:
            return None
        part, entry = self._node
        return part.scalar(entry.start, entry.end)

    def children(self, key: str | None = None) -> Iterator[SaveNode]:
        if self.container:
            entries = _entries_with_positions(self._snapshot.children(self._node))
            for selector, node in entries:
                if key is None or node[1].key == key:
                    yield SaveNode(self._snapshot, node, selector)


class SaveProvider:
    """Read configured directories only. Paths and the converter are configured by the host."""

    def __init__(self, roots: Sequence[Path], rakaly: Path | None = None):
        self.roots = tuple(dict.fromkeys(Path(root).expanduser().resolve() for root in roots))
        self.rakaly = Path(rakaly).expanduser().resolve() if rakaly is not None else None
        self._lock = RLock()
        self._cached: tuple[_File, _Snapshot] | None = None
        self._previews: OrderedDict[_File, dict] = OrderedDict()

    def _files(self, root_index: int | None = None) -> list[_File]:
        if root_index is not None and (type(root_index) is not int or not 0 <= root_index < len(self.roots)):
            raise SaveError("invalid_request", "Podaj root_index z listy zapisów.")
        files = []
        for index, root in enumerate(self.roots):
            if root_index is not None and index != root_index:
                continue
            try:
                for path in root.iterdir():
                    if not _SAVE_NAME.fullmatch(path.name):
                        continue
                    try:
                        info = path.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if stat.S_ISREG(info.st_mode) and path.resolve() == path:
                        files.append(_File(path, index, _stamp(info)))
            except OSError:
                continue
        return sorted(files, key=lambda file: (-file.stamp[0], file.root_index, file.path.name.casefold()))

    def _preview(self, file: _File) -> dict:
        if file in self._previews:
            self._previews.move_to_end(file)
            return self._previews[file]
        preview = _copy(file, _PREVIEW_BYTES)
        result = dict.fromkeys(_METADATA.values())
        part = None
        if preview.startswith(b"PK"):
            with file.path.open("rb") as handle, zipfile.ZipFile(handle) as archive:
                member = _archive_parts(archive).get("meta")
                if member:
                    preview = _archive_read(archive, member, _PREVIEW_BYTES)
                if _stamp(os.fstat(handle.fileno())) != file.stamp:
                    raise _unstable()
            if (
                member and member.file_size <= _PREVIEW_BYTES and preview.startswith(_BINARY_HEADER)
                and self.rakaly is not None and self.rakaly.is_file()
            ):
                part = self._melt(preview, max_bytes=_PREVIEW_BYTES, timeout=3)
        if _TEXT_HEADER.match(preview):
            part = _Text(preview, partial=True)
        if part is not None:
            result = _metadata((part, entry) for entry in part.entries(part.start, len(part.data)))
        self._remember(file, result)
        return result

    def _remember(self, file: _File, metadata: dict) -> None:
        self._previews[file] = metadata
        self._previews.move_to_end(file)
        while len(self._previews) > 128:
            self._previews.popitem(last=False)

    def _melt(self, data: bytes, *, max_bytes: int = _MAX_BYTES, timeout: int = 40) -> _Text:
        if self.rakaly is None or not self.rakaly.is_file():
            raise SaveError("converter_required", "Zapis binarny EU4 wymaga lokalnego konwertera Rakaly.")
        command = [str(self.rakaly), "melt", "--format", "eu4", "--to-stdout", "--retain", "--unknown-key", "error"]
        try:
            with subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ) as process:
                expired = Event()

                def send_input():
                    try:
                        with process.stdin:
                            process.stdin.write(data)
                    except (BrokenPipeError, OSError):
                        pass

                def stop_conversion():
                    expired.set()
                    process.kill()

                writer = Thread(target=send_input, daemon=True)
                timer = Timer(timeout, stop_conversion)
                writer.start()
                timer.start()
                try:
                    plain = process.stdout.read(max_bytes + 1)
                    if len(plain) > max_bytes:
                        process.kill()
                        raise SaveError("save_too_large", "Wynik konwersji przekracza limit rozmiaru.")
                    if process.wait() != 0:
                        if expired.is_set():
                            raise SaveError("converter_timeout", "Rakaly nie zakończył odczytu w limicie czasu.")
                        raise SaveError("converter_failed", "Rakaly nie odczytał zapisu. Sprawdź zgodność wersji zapisu i konwertera.")
                finally:
                    timer.cancel()
                    if process.poll() is None:
                        process.kill()
                    writer.join()
        except OSError as error:
            raise SaveError("converter_failed", "Nie udało się uruchomić lokalnego Rakaly.") from error
        return _Text(plain, header_required=True)

    def _snapshot(self, file: _File) -> _Snapshot:
        if self._cached and self._cached[0] == file:
            return self._cached[1]
        if file.stamp[2] > _MAX_BYTES:
            raise SaveError("save_too_large", "Zapis przekracza limit 256 MiB.")
        data = _copy(file)
        if _TEXT_HEADER.match(data):
            parts, format_name = [_Text(data)], "text"
        elif data.startswith(_BINARY_HEADER):
            parts, format_name = [self._melt(data)], "binary"
        else:
            try:
                with zipfile.ZipFile(BytesIO(data)) as archive:
                    members = _archive_parts(archive)
                    parts = []
                    for name in _ARCHIVE_SECTIONS:
                        if name not in members:
                            continue
                        body = _archive_read(archive, members[name])
                        if body.startswith(_BINARY_HEADER):
                            compatible = _archive_for_rakaly(data, archive, members, name, body)
                            parts, format_name = [self._melt(compatible)], "zip-binary"
                            break
                        parts.append(_Text(body))
                    else:
                        format_name = "zip-text"
            except _ZIP_ERRORS as error:
                raise _invalid("Nie udało się odczytać archiwum zapisu EU4.") from error
        snapshot = _Snapshot(parts, format_name)
        self._cached = file, snapshot
        self._remember(file, snapshot.metadata)
        return snapshot

    def _select(
        self, save: str | None, root_index: int | None, campaign_id: str | None, require_campaign: bool,
    ) -> tuple[_Snapshot, dict]:
        if save is not None and (not isinstance(save, str) or not _SAVE_NAME.fullmatch(save)):
            raise SaveError("invalid_request", "Podaj nazwę pliku .eu4 z listy zapisów.")
        if campaign_id is not None and (not isinstance(campaign_id, str) or not campaign_id):
            raise SaveError("invalid_request", "Podaj niepusty identyfikator kampanii z zapisu.")
        files = self._files(root_index)
        if save is not None:
            files = [file for file in files if file.path.name.casefold() == save.casefold()]
            if len(files) > 1:
                raise SaveError("ambiguous_save", "Kilka plików ma tę nazwę. Wybierz także root_index.")
            selection = "named"
        elif campaign_id is not None:
            selection = "campaign"
        elif require_campaign and len(files) > 1:
            campaign_id = self._single_campaign(files)
            selection = "single_campaign"
        elif require_campaign:
            selection = "only_save"
        else:
            selection = "latest_by_mtime"
        skipped = 0
        first_error = None
        for file in files:
            try:
                if campaign_id is not None:
                    known_campaign = self._preview(file)["campaign_id"]
                    if known_campaign is not None and known_campaign != campaign_id:
                        continue
                snapshot = self._snapshot(file)
            except (SaveError, OSError, *_ZIP_ERRORS) as error:
                if not isinstance(error, SaveError):
                    error = _invalid("Podczas próby odczytu zapis był niedostępny lub uszkodzony.")
                if save is not None or (campaign_id is None and error.code not in {
                    "save_changing", "save_unreadable", "invalid_save",
                }):
                    raise error
                first_error = first_error or error
                skipped += 1
                continue
            if campaign_id is not None and snapshot.metadata["campaign_id"] != campaign_id:
                continue
            return snapshot, {
                **file.info(), **snapshot.metadata, "format": snapshot.format,
                "selection": selection, "unreadable_newer_saves": skipped,
            }
        if first_error is not None:
            raise first_error
        raise SaveError("save_not_found", "Brak pasującego zapisu w skonfigurowanych katalogach.")

    def _single_campaign(self, files: Sequence[_File]) -> str:
        common_id = None
        for file in files:
            try:
                campaign_id = self._preview(file)["campaign_id"]
            except (SaveError, OSError, *_ZIP_ERRORS):
                campaign_id = None
            if not campaign_id or (common_id is not None and common_id != campaign_id):
                raise SaveError(
                    "selection_required",
                    "Zapisów nie udało się przypisać do jednej kampanii. Wybierz nazwę pliku lub identyfikator kampanii.",
                )
            common_id = campaign_id
        return common_id

    def list_saves(self, *, offset: int = 0, limit: int = 30) -> dict:
        """List names and available metadata without reading full saves."""
        _pagination(offset, limit)
        with self._lock:
            files = self._files()
            items = []
            for file in files[offset:offset + limit + 1]:
                item = file.info()
                try:
                    item.update(self._preview(file))
                except (SaveError, OSError, *_ZIP_ERRORS):
                    item["metadata_unavailable"] = True
                items.append(item)
            return {"source": "save", "total": len(files), **_page(items, offset, limit)}

    def status(
        self, save: str | None = None, *, root_index: int | None = None,
        campaign_id: str | None = None, require_campaign: bool = False,
    ) -> dict:
        with self._lock:
            try:
                _, info = self._select(save, root_index, campaign_id, require_campaign)
            except SaveError as error:
                return {"source": "save", "available": False, "error_code": error.code, "error": str(error)}
            return {"available": True, **info}

    def snapshot(
        self, *, save: str | None = None, root_index: int | None = None,
        campaign_id: str | None = None, require_campaign: bool = False,
    ) -> tuple[_Snapshot, dict]:
        """Pin one selected snapshot for several reads without holding the provider lock."""
        with self._lock:
            return self._select(save, root_index, campaign_id, require_campaign)

    def read(self, path: Sequence[Selector] | None = None, *, save: str | None = None,
             root_index: int | None = None, campaign_id: str | None = None, require_campaign: bool = False,
             offset: int = 0, limit: int = 30) -> dict:
        _pagination(offset, limit)
        path = [] if path is None else path
        with self._lock:
            snapshot, info = self._select(save, root_index, campaign_id, require_campaign)
            node = _path(snapshot, path)
            if node and not node[1].container:
                part, entry = node
                value = part.scalar(entry.start, entry.end)
                end = offset + 4096
                return {
                    **info, "path": path, "kind": "scalar", "value": value[offset:end],
                    "offset": offset, "next_offset": end if end < len(value) else None,
                    "total_characters": len(value),
                }
            children = _entries_with_positions(snapshot.children(node))
            items = [_item(selector, item) for selector, item in islice(children, offset, offset + limit + 1)]
            return {**info, "path": path, "kind": "container", **_page(items, offset, limit)}

    def find(self, key: str, *, path: Sequence[Selector] | None = None, save: str | None = None,
             root_index: int | None = None, campaign_id: str | None = None, exact: bool = False,
             require_campaign: bool = False, offset: int = 0, limit: int = 30) -> dict:
        _pagination(offset, limit)
        if not isinstance(key, str) or not 1 <= len(key) <= 256:
            raise SaveError("invalid_request", "Podaj szukany klucz o długości od 1 do 256 znaków.")
        path = [] if path is None else path
        needle = key.casefold()
        prefilter = None
        if needle.isascii():
            # Non-ASCII characters and escapes can change the spelling after decoding.
            prefilter = re.compile(re.escape(needle.encode("ascii")) + rb"|[\x80-\xff\\]", re.IGNORECASE)
        with self._lock:
            snapshot, info = self._select(save, root_index, campaign_id, require_campaign)
            root = _path(snapshot, path)
            if root and not root[1].container:
                return {**info, "path": path, **_page([], offset, limit)}
            stack = [enumerate(snapshot.children(root))]
            trail: list[int] = []
            matches = []
            skipped = 0
            while stack and len(matches) <= limit:
                step = next(stack[-1], None)
                if step is None:
                    stack.pop()
                    if trail:
                        trail.pop()
                    continue
                index, node = step
                part, entry = node
                if entry.key is not None:
                    label = entry.key.casefold()
                    is_match = label == needle if exact else needle in label
                    if is_match:
                        if skipped < offset:
                            skipped += 1
                        else:
                            matches.append({**_item(index, node), "path": [*path, *trail, index]})
                if entry.container and (prefilter is None or prefilter.search(part.data, entry.start, entry.end)):
                    trail.append(index)
                    stack.append(enumerate(snapshot.children(node)))
            return {**info, "path": path, **_page(matches, offset, limit)}
