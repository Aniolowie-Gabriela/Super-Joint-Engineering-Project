"""Campaign map queries over bounded Tongs reads or one local save."""

import asyncio
from functools import lru_cache, partial
import re
from typing import Annotated, Any, Literal

from pydantic import Field, StrictInt

from saves import SaveError


Offset = Annotated[int, Field(ge=0)]
PageSize = Annotated[int, Field(ge=1, le=20)]
ProvinceId = Annotated[StrictInt, Field(ge=1)]
ProvinceIds = Annotated[list[ProvinceId], Field(min_length=1, max_length=100)]
CountryTag = Annotated[str, Field(pattern=r"^[a-zA-Z0-9]{3}$")]
AreaName = Annotated[str, Field(pattern=r"^[a-zA-Z0-9_]{1,100}$")]
Direction = Literal["incoming", "outgoing", "both"]

AREA_PATH = "map/area.txt"
IDENTITY_FIELDS = ("pid", "process_start_ms", "session")
PROVINCE_FIELDS = ("name", "owner", "controller")
UNIT_FIELDS = ("id", "kind", "name", "location", "mission", "subunits", "strength")
VISIBILITY = {"fog_of_war": "unknown", "on_screen": "unknown"}
_AREA_PATTERN = re.compile(r"(\w+)\s*=\s*\{((?:[^{}]++|\{[^{}]*+\})*)\}")
_AREA_COLOR = re.compile(r"\bcolor\s*=\s*\{[^{}]*\}")


def _error(code, message):
    return {"available": False, "error_code": code, "error": message}


def _read_error(result):
    error = result.get("error")
    code = result.get("error_code")
    if not code and isinstance(error, str) and re.fullmatch(r"[a-z0-9_]+", error):
        code = error
    return _error(code or "live_data_unavailable", result.get("detail") or error or "Odczyt Tongs jest niepełny.")


def _page(total, offset, limit):
    return {"total": total, "offset": offset, "next_offset": offset + limit if offset + limit < total else None}


def _positive_id(value):
    if isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 10:
        value = int(value)
    return value if type(value) is int and value > 0 else None


def _country_tag(value):
    return value.upper() if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9]{3}", value) else None


def _province_row(province_id, data):
    owner, controller = _country_tag(data.get("owner")), _country_tag(data.get("controller"))
    return {"province_id": province_id, "name": data.get("name"), "owner": owner,
            "controller": controller, "occupied": owner != controller if owner and controller else None}


def _occupation_direction(row, tag):
    if row["occupied"]:
        if row["owner"] == tag:
            return "incoming"
        if row["controller"] == tag:
            return "outgoing"
    return None


def _summary(state):
    return {key: state[key] for key in (
        "available", "in_game", "date", "paused", "hour", "observed_at", "tongs_version", *IDENTITY_FIELDS,
    ) if key in state}


async def _live_call(server, name, **kwargs):
    return await server.read_live(name, {**kwargs, "timeout": 3})


async def _live_map(server, read):
    start = await server.read_live("tongs_state", {})
    if not start["available"]:
        return {"source": "live", **_summary(start), **_read_error(start)}
    if not start.get("in_game"):
        return {"source": "live", **_summary(start), **_error("no_active_campaign", "Brak otwartej kampanii w EU4.")}
    for _ in range(2):
        context = {"source": "live", **_summary(start), "visibility": VISIBILITY}
        result = await read()
        end = await server.read_live("tongs_state", {})
        before = tuple(start.get(key) for key in IDENTITY_FIELDS)
        after = tuple(end.get(key) for key in IDENTITY_FIELDS)
        if not end["available"] or not end.get("in_game"):
            break
        if before == after:
            return {**context, **_summary(end), **result, "date_start": start.get("date"),
                    "session_verified": all(value is not None for value in before)}
        start = end
    return {**context, **_error("live_session_changed",
                               "Kampania zmieniła się podczas odczytu. Ponów pytanie po jej załadowaniu.")}


async def _live_province_page(server, ids):
    rows = []
    for province_id in ids:
        result = await _live_call(server, "tongs_province", province_id=province_id)
        if not result["available"]:
            rows.append({"province_id": province_id, **_read_error(result)})
        else:
            rows.append({"available": True, **_province_row(province_id, result),
                         "land": result.get("land"), "wasteland": result.get("wasteland")})
    return rows


async def _live_provinces(server, ids, tag, world_scope, direction, offset, limit):
    capital = None
    panel = None
    if world_scope or direction == "outgoing":
        return _error("scope_unavailable_live", "Tongs odczytuje prowincje po ID. Ten zakres wymaga zapisu.")
    if direction and tag is None:
        player = await _live_call(server, "tongs_player")
        tag = _country_tag(player.get("tag"))
        if not player["available"] or tag is None:
            return _read_error(player)
    if tag is not None:
        country = await _live_call(server, "tongs_country", tag=tag)
        if not country["available"] or not isinstance(country.get("provinces"), list):
            return _read_error(country)
        ids = sorted({ident for entry in country["provinces"] if (ident := _positive_id(entry)) is not None})
        capital = _positive_id(country.get("capital"))
    if ids is None:
        selection = await _live_call(server, "tongs_selection")
        if not selection["available"]:
            return _read_error(selection)
        view = selection.get("view") or {}
        opened = _positive_id(view.get("province")) if view.get("visible") is True else None
        if opened is None:
            return _error("province_panel_closed", "Otwórz panel prowincji lub podaj jej ID, obszar albo tag.")
        ids = [opened]
        panel = {"visible": True, "province_id": opened}
    rows = await _live_province_page(server, ids[offset:offset + limit])
    missing = [row["province_id"] for row in rows if not row["available"]]
    if rows and len(rows) == len(missing):
        return {**_error(rows[0]["error_code"], rows[0]["error"]), "missing_province_ids": missing}
    result = {
        "available": True, "tag": tag, "capital": capital, "panel": panel,
        "items": rows, "missing_province_ids": missing, **_page(len(ids), offset, limit),
    }
    if direction:
        result["items"] = [
            {**row, "direction": "incoming"} for row in rows if row.get("owner") == tag and row.get("occupied")
        ]
        result["page_by"] = "owned_provinces"
        result["checked_provinces"] = len(rows) - len(missing)
        result["unknown_control_province_ids"] = [
            row["province_id"] for row in rows if row["available"] and row["occupied"] is None
        ]
        result["directions_covered"] = ["incoming"]
        if direction == "both":
            result["outgoing_unavailable_live"] = True
    return result


async def _live_units(server, tag, kind, offset, limit):
    result = await _live_call(server, "tongs_units", **({"tag": tag} if tag else {}))
    if not result["available"] or not isinstance(result.get("units"), list):
        return _read_error(result)
    items = [unit for unit in result["units"] if kind is None or unit.get("kind") == kind]
    page = [{field: unit.get(field) for field in UNIT_FIELDS} for unit in items[offset:offset + limit]]
    locations = [_positive_id(unit["location"]) for unit in page]
    provinces = await _live_province_page(server, list(dict.fromkeys(loc for loc in locations if loc is not None)))
    names = {row["province_id"]: row.get("name") for row in provinces}
    for unit, location in zip(page, locations):
        unit["location"] = location
        unit["province_name"] = names.get(location)
    return {"available": True, "tag": _country_tag(result.get("tag")) or tag,
            "items": page, **_page(len(items), offset, limit)}


def _require_block(node):
    if not node.container:
        raise SaveError("invalid_map_data", "Oczekiwana sekcja mapy w zapisie nie jest blokiem.")
    return node


def _saved_province_nodes(snapshot, wanted=None):
    for node in _require_block(snapshot.section(["provinces"])).children():
        province_id = _positive_id((node.key or "").removeprefix("-"))
        if province_id and node.container and (wanted is None or province_id in wanted):
            yield province_id, node


def _saved_province_fields(node):
    fields = {}
    for entry in node.children():
        if entry.key in PROVINCE_FIELDS and entry.key not in fields:
            nested_tag = entry.container and entry.key in ("owner", "controller")
            fields[entry.key] = next((child.value for child in entry.children("tag")), None) if nested_tag else entry.value
            if len(fields) == len(PROVINCE_FIELDS):
                break
    return fields


def _saved_tag(tag, info):
    tag = tag or _country_tag(info["player"])
    if tag is None:
        raise SaveError("missing_player_tag", "W zapisie brakuje tagu gracza. Podaj tag państwa.")
    return tag


def _saved_provinces(snapshot, info, ids, tag, direction, offset, limit):
    capital = None
    if direction:
        tag = _saved_tag(tag, info)
    if tag:
        country = _require_block(snapshot.section(["countries", tag]))
        capital = next((_positive_id(entry.value) for entry in country.children("capital")), None)
    if ids is not None:
        wanted = ids[offset:offset + limit]
        nodes = dict(_saved_province_nodes(snapshot, set(wanted))) if wanted else {}
        items = [_province_row(n, _saved_province_fields(nodes[n])) for n in wanted if n in nodes]
        return {"tag": tag, "capital": capital, "items": items,
                "missing_province_ids": [n for n in wanted if n not in nodes], **_page(len(ids), offset, limit)}
    count = unknown_control = 0
    items = []
    for n, node in _saved_province_nodes(snapshot):
        row = _province_row(n, _saved_province_fields(node)) if tag else None
        if direction:
            if not row["controller"] and row["owner"] == tag:
                unknown_control += 1
            match = _occupation_direction(row, tag)
            if match is None or direction not in (match, "both"):
                continue
            row["direction"] = match
        elif tag and row["owner"] != tag:
            continue
        if offset <= count < offset + limit:
            items.append(row if tag else _province_row(n, _saved_province_fields(node)))
        count += 1
    result = {"tag": tag, "capital": capital, "items": items, **_page(count, offset, limit)}
    if direction:
        result["page_by"] = "matches"
        result["directions_covered"] = ["incoming", "outgoing"] if direction == "both" else [direction]
        result["unknown_control_owned_count"] = unknown_control
    return result


def _saved_unit(node):
    fields = {}
    subunits = 0
    for entry in node.children():
        if entry.key in ("name", "location"):
            fields[entry.key] = entry.value
        elif entry.container and entry.key == ("regiment" if node.key == "army" else "ship"):
            subunits += 1
    return {"kind": node.key, "name": fields.get("name"), "location": _positive_id(fields.get("location")),
            "subunits": subunits}


def _saved_units(snapshot, info, tag, kind, offset, limit):
    tag = _saved_tag(tag, info)
    country = _require_block(snapshot.section(["countries", tag]))
    units = [node for node in country.children() if node.container and node.key in ("army", "navy")
             and (kind is None or node.key == kind)]
    items = [_saved_unit(node) for node in units[offset:offset + limit]]
    locations = {unit["location"] for unit in items if unit["location"] is not None}
    names = {}
    if locations:
        try:
            names = {n: next((item.value for item in node.children("name")), None)
                     for n, node in _saved_province_nodes(snapshot, locations)}
        except SaveError as error:
            if error.code != "missing_path":
                raise
    for unit in items:
        unit["province_name"] = names.get(unit["location"])
    return {"tag": tag, "items": items, **_page(len(units), offset, limit)}


def _from_save(saves, read, selection):
    context = {"source": "save", "live_campaign_match": "unverified", "visibility": VISIBILITY}
    try:
        snapshot, info = saves.snapshot(**selection, require_campaign=True)
        context.update(info)
        return {**context, "available": True, **read(snapshot, info)}
    except SaveError as error:
        return {**context, **_error(error.code, str(error))}


async def _query(server, saves, live_read, save_read, selection):
    explicit = any(value is not None for value in selection.values())
    if explicit:
        if save_read is None:
            return {"source": "save", **_error("save_scope_required",
                    "Plik zapisu nie wskazuje, który panel jest otwarty. Podaj ID prowincji, obszar, tag lub scope.")}
        return await asyncio.to_thread(_from_save, saves, save_read, selection)
    live = await _live_map(server, live_read)
    if save_read is None or live["available"]:
        return live
    if live.get("error_code") in ("unknown_province", "unknown_country"):
        return live
    if live.get("in_game"):
        return {**live, "fallback_requires_save": True}
    return {**await asyncio.to_thread(_from_save, saves, save_read, selection), "live": live}


def _read_areas(world):
    lines = []
    start = 1
    while start is not None:
        page = world.read_file(AREA_PATH, start_line=start, line_count=160)
        for row in page["lines"]:
            if row["truncated"]:
                raise ValueError("Definicja obszaru przekracza dostępny odczyt tekstowy.")
            lines.append(row["text"].split("#", 1)[0])
        start = page["next_line"]
    areas = {}
    for name, block in _AREA_PATTERN.findall("\n".join(lines)):
        words = _AREA_COLOR.sub("", block).split()
        if all(_positive_id(word) for word in words):
            areas[name.casefold()] = list(dict.fromkeys(map(int, words)))
    return areas, page["game_version"]


def register_map(server, world, saves, annotations):
    @lru_cache(maxsize=1)
    def areas():
        return _read_areas(world)

    @server.tool(annotations=annotations)
    async def eu4_map_provinces(
        province_ids: ProvinceIds | None = None, area: AreaName | None = None,
        tag: CountryTag | None = None, scope: Literal["world"] | None = None,
        offset: Offset = 0, limit: PageSize = 10, campaign_id: str | None = None,
        save: str | None = None, root_index: Offset | None = None,
    ) -> dict[str, Any]:
        """Sprawdź właściciela i kontrolującego prowincje oraz stolicę wybranego państwa.

        Wybierz jeden zakres: province_ids (ID prowincji), area (np. leinster_area z map/area.txt),
        tag (własne prowincje państwa) lub scope="world" (mapa z zapisu, stronami). Bez zakresu
        sprawdza otwarty panel prowincji na żywo. Zasięg obszaru pochodzi z instalacji.
        Mapa kampanii nie określa mgły wojny ani widoczności na ekranie.
        Podaj save lub campaign_id, by celowo odczytać wybrany zapis.
        root_index ogranicza wybór do wskazanego folderu. Przy stronicowaniu używaj tej samej nazwy pliku.
        """
        ranges = sum(value is not None for value in (province_ids, area, tag, scope))
        if ranges > 1:
            return _error("ambiguous_map_scope", "Wybierz jeden zakres: ID, obszar, państwo albo całą mapę.")
        area_info = {}
        ids = list(dict.fromkeys(province_ids)) if province_ids is not None else None
        if area is not None:
            try:
                known, version = await asyncio.to_thread(areas)
                ids = known[area.casefold()]
            except KeyError:
                return _error("unknown_area", "Podaj klucz obszaru z map/area.txt w instalacji gry.")
            except (OSError, ValueError) as error:
                return _error("area_unavailable", str(error))
            area_info = {"area_definition": {"name": area.casefold(), "source": "installed_game_files",
                         "path": AREA_PATH, "game_version": version, "campaign_membership_verified": False}}
        tag = _country_tag(tag)
        live_read = partial(_live_provinces, server, ids, tag, scope == "world", None, offset, limit)
        save_read = partial(_saved_provinces, ids=ids, tag=tag, direction=None, offset=offset, limit=limit)
        selection = {"campaign_id": campaign_id, "save": save, "root_index": root_index}
        result = await _query(server, saves, live_read, save_read if ranges else None, selection)
        return {**result, **area_info}

    @server.tool(annotations=annotations)
    async def eu4_map_occupations(
        tag: CountryTag | None = None, direction: Direction = "incoming", offset: Offset = 0,
        limit: PageSize = 10, campaign_id: str | None = None, save: str | None = None,
        root_index: Offset | None = None,
    ) -> dict[str, Any]:
        """Sprawdź okupacje państwa (domyślnie gracza).

        incoming: kto kontroluje jego własne prowincje. outgoing: które cudze prowincje kontroluje.
        both: oba kierunki. Na żywo Tongs pozwala stronicować własne prowincje przy incoming;
        brak wyniku na stronie to brak potwierdzonej okupacji na tej stronie. Cudzą prowincję
        sprawdzisz na żywo po ID w eu4_map_provinces. Pełny wykaz outgoing wymaga zapisu.
        Podaj save lub campaign_id, by celowo odczytać wybrany zapis.
        root_index ogranicza wybór do wskazanego folderu.
        Użyj next_offset, a przy zmianie źródła zacznij od pierwszej strony.
        """
        tag = _country_tag(tag)
        live_read = partial(_live_provinces, server, None, tag, False, direction, offset, limit)
        save_read = partial(_saved_provinces, ids=None, tag=tag, direction=direction, offset=offset, limit=limit)
        selection = {"campaign_id": campaign_id, "save": save, "root_index": root_index}
        return await _query(server, saves, live_read, save_read, selection)

    @server.tool(annotations=annotations)
    async def eu4_map_units(
        tag: CountryTag | None = None, kind: Literal["army", "navy"] | None = None,
        offset: Offset = 0, limit: PageSize = 10, campaign_id: str | None = None,
        save: str | None = None, root_index: Offset | None = None,
    ) -> dict[str, Any]:
        """Znajdź położenie armii i flot gracza lub państwa wskazanego przez tag.

        kind zawęża do armii (army) lub flot (navy). Zwraca bieżącą prowincję jednostki
        lub położenie w dniu zapisu. To dane kampanii. Widoczność przez mgłę wojny
        i położenie jednostek na ekranie pozostają nieustalone.
        Podaj save lub campaign_id, by celowo odczytać wybrany zapis.
        root_index ogranicza wybór do wskazanego folderu.
        """
        tag = _country_tag(tag)
        live_read = partial(_live_units, server, tag, kind, offset, limit)
        save_read = partial(_saved_units, tag=tag, kind=kind, offset=offset, limit=limit)
        selection = {"campaign_id": campaign_id, "save": save, "root_index": root_index}
        return await _query(server, saves, live_read, save_read, selection)
