"""Sąsiedztwo prowincji na bazowej mapie EU4 1.37.5."""

import asyncio
from collections import defaultdict
import csv
from dataclasses import dataclass
from functools import cached_property
from itertools import chain, pairwise
import os
import re
from struct import iter_unpack, unpack_from
from threading import Lock
from typing import Annotated, Any

from pydantic import Field, StrictInt

from world import decode_lines, safe_stat


MAP_FILES = {
    "definition.csv": 1024 * 1024,
    "default.map": 256 * 1024,
    "climate.txt": 256 * 1024,
    "adjacencies.csv": 256 * 1024,
    "provinces.bmp": 40 * 1024 * 1024,
}
SUPPORTED_VERSIONS = {"1.37.5", "1.37.5.0"}
ProvinceId = Annotated[StrictInt, Field(ge=1)]


def _read_map_file(root, name):
    limit = MAP_FILES[name]
    directory = root / "map"
    path = directory / name
    safe_stat(root, directory=True)
    safe_stat(directory, directory=True)
    before = safe_stat(path, directory=False)
    if before.st_size > limit:
        raise ValueError(f"Plik map/{name} przekracza limit odczytu.")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if not os.path.samestat(before, opened) or opened.st_nlink != 1:
            raise OSError("Plik mapy zmienił się w trakcie otwierania.")
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"Plik map/{name} przekracza limit odczytu.")
    return raw


def _text_lines(root, name):
    lines, _ = decode_lines(_read_map_file(root, name), f"map/{name}")
    return lines


def _integer_groups(lines, names, source):
    text = "\n".join(line.partition("#")[0] for line in lines)
    groups = {}
    for name in names:
        match = re.search(rf"^\s*{name}\s*=\s*\{{([^}}]*)\}}", text, re.MULTILINE)
        if match is None or re.fullmatch(r"[\d\s]*", match[1]) is None:
            raise ValueError(f"Brak obsługiwanej sekcji {name} w map/{source}.")
        groups[name] = set(map(int, match[1].split()))
    return groups


def _definitions(lines, only_random):
    rows = csv.reader(lines, delimiter=";")
    names, colors = {}, {}
    next(rows, None)  # Nagłówek tabeli.
    for row in rows:
        if not row:
            continue
        try:
            province_id = int(row[0])
            rgb = tuple(map(int, row[1:4]))
            name = row[4]
            if province_id < 1 or province_id in names or any(not 0 <= value <= 255 for value in rgb):
                raise ValueError
        except (IndexError, ValueError):
            raise ValueError("Niepoprawny wpis w map/definition.csv.") from None
        if province_id in only_random:
            continue
        names[province_id] = name
        bgr = rgb[::-1]
        # Część definicji RNW współdzieli kolory. Taki kolor wolno pominąć,
        # dopóki nie występuje na bitmapie bazowej.
        colors[bgr] = -1 if bgr in colors else province_id
    if not names:
        raise ValueError("Brak definicji prowincji w map/definition.csv.")
    return names, colors


def _pixel_borders(raw, colors):
    if len(raw) < 54:
        raise ValueError("Niekompletny nagłówek map/provinces.bmp.")
    signature, offset, dib_size, width, height, planes, depth, compression = unpack_from("<2s8xIIiiHHI", raw)
    row_size = width * 3
    stride = (row_size + 3) & ~3
    if (
        signature != b"BM" or dib_size < 40 or offset < 14 + dib_size
        or not (0 < width <= 8192 and 0 < abs(height) <= 8192)
        or (planes, depth, compression) != (1, 24, 0)
        or offset + stride * abs(height) > len(raw)
    ):
        raise ValueError("Mapa prowincji musi być kompletną nieskompresowaną bitmapą 24-bitową.")

    pixels = memoryview(raw)
    borders = defaultdict(set)
    present = set()
    previous = ()
    color_id = colors.get
    for position in range(offset, offset + stride * abs(height), stride):
        row = tuple(color_id(bgr, 0) for bgr in iter_unpack("BBB", pixels[position:position + row_size]))
        present.update(row)
        # Obchód z góry lub z dołu daje te same nieskierowane krawędzie.
        # Skrajne kolumny stykają się na szwie wschód–zachód.
        seam = ((row[-1], row[0]),)
        for first, second in chain(pairwise(row), seam, zip(previous, row)):
            if first != second and first > 0 and second > 0:
                borders[first].add(second)
                borders[second].add(first)
        previous = row
    if -1 in present:
        raise ValueError("Kolor w map/provinces.bmp ma więcej niż jedną definicję prowincji.")
    if 0 in present:
        raise ValueError("Kolor w map/provinces.bmp nie ma definicji prowincji.")
    return present, borders


@dataclass(frozen=True)
class _Connection:
    province_id: int
    type: str
    through: int | None


def _connections(lines, present):
    rows = csv.reader(lines, delimiter=";")
    next(rows, None)  # Nagłówek tabeli.
    connections = defaultdict(set)
    for row in rows:
        if not row:
            continue
        try:
            start, end = map(int, row[:2])
            if start == end == -1:
                break  # Znacznik końca tabeli.
            kind = row[2].strip().casefold()
            through = int(row[3])
            if start == end or not kind or start < 1 or end < 1:
                raise ValueError
        except (IndexError, ValueError):
            raise ValueError("Niepoprawny wpis w map/adjacencies.csv.") from None
        if start in present and end in present:
            through = through if through > 0 else None
            connections[start].add(_Connection(end, kind, through))
            connections[end].add(_Connection(start, kind, through))
    return connections


@dataclass(frozen=True)
class _Index:
    provinces: dict[int, tuple[str, str]]
    borders: dict[int, set[int]]
    connections: dict[int, set[_Connection]]

    def province(self, province_id):
        name, kind = self.provinces[province_id]
        return {"province_id": province_id, "name": name, "kind": kind}

    def describe(self, connection):
        through = None
        if connection.through in self.provinces:
            through = self.province(connection.through)
        elif connection.through is not None:
            through = {"province_id": connection.through}
        return {**self.province(connection.province_id), "type": connection.type, "through": through}


class MapTopology:
    def __init__(self, world):
        self.world = world
        self._index_lock = Lock()

    @cached_property
    def _index(self):
        root = self.world.game_dir
        groups = _integer_groups(
            _text_lines(root, "default.map"), ("sea_starts", "lakes", "only_used_for_random"), "default.map",
        )
        climate = _integer_groups(_text_lines(root, "climate.txt"), ("impassable",), "climate.txt")
        names, colors = _definitions(_text_lines(root, "definition.csv"), groups["only_used_for_random"])
        present, borders = _pixel_borders(_read_map_file(root, "provinces.bmp"), colors)
        kinds = dict.fromkeys(climate["impassable"], "wasteland")
        kinds.update(dict.fromkeys(groups["sea_starts"], "sea"))
        kinds.update(dict.fromkeys(groups["lakes"], "lake"))
        provinces = {province_id: (names[province_id], kinds.get(province_id, "land")) for province_id in present}
        connections = _connections(_text_lines(root, "adjacencies.csv"), present)
        return _Index(provinces, borders, connections)

    def neighbors(self, province_id: int) -> dict[str, Any]:
        result = {
            "source": "installed_game_files", "game_version": self.world.version,
            "scope": "vanilla_map", "available": False,
        }
        if self.world.game_dir is None:
            return {**result, "error_code": "map_unavailable", "error": "Brak dostępu do instalacji EU4."}
        if self.world.version not in SUPPORTED_VERSIONS:
            return {**result, "error_code": "map_version_unsupported", "error": "Odczyt obsługuje mapę EU4 1.37.5."}
        try:
            with self._index_lock:
                index = self._index
        except OSError:
            return {**result, "error_code": "map_unavailable", "error": "Brak dostępu do wymaganych plików mapy EU4."}
        except csv.Error:
            return {**result, "error_code": "map_format_unsupported", "error": "Niepoprawna tabela CSV mapy EU4."}
        except ValueError as exc:
            return {**result, "error_code": "map_format_unsupported", "error": str(exc)}
        if province_id not in index.provinces:
            return {**result, "error_code": "province_not_on_map", "error": "Tej prowincji nie ma na bazowej mapie."}

        connections = sorted(
            index.connections.get(province_id, ()), key=lambda entry: (entry.province_id, entry.type, entry.through or 0),
        )
        blocked = {entry.province_id for entry in connections if entry.type == "impassable"}
        return {
            **result, "available": True, "province": index.province(province_id),
            "neighbors": [
                index.province(other) for other in sorted(index.borders.get(province_id, set()) - blocked)
            ],
            "special_connections": [index.describe(entry) for entry in connections if entry.type != "impassable"],
            "blocked_connections": [index.describe(entry) for entry in connections if entry.type == "impassable"],
            "provenance": [f"map/{name}" for name in MAP_FILES],
            "limitations": [
                "Bazowa mapa bez modów i Losowego Nowego Świata. Styki obejmują szew wschód–zachód.",
                "Przebieg granicy i wpis o przejściu opisują mapę. Dostępność ruchu i kanałów zależy od kampanii.",
                "Nazwy pochodzą z definicji mapy. Właściciela sprawdzisz w eu4_map_provinces.",
            ],
        }


def register_neighbors(server, world, saves, annotations):
    topology = MapTopology(world)

    @server.tool(annotations=annotations)
    async def eu4_map_neighbors(province_id: ProvinceId) -> dict[str, Any]:
        """Sprawdź granice i specjalne połączenia podanej prowincji na bazowej mapie EU4 1.37.5.

        Sąsiedzi stykają się bokami pikseli, także na szwie wschód–zachód. Osobno zwraca cieśniny, połączenia przez jeziora,
        kanały i wyłączenia z pliku mapy. Wynik opisuje geografię bez stanu kampanii.
        """
        return await asyncio.to_thread(topology.neighbors, province_id)
