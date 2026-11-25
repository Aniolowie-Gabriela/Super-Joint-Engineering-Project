"""Read event observations and the matching scripts from the EU4 installation."""

from __future__ import annotations

import asyncio
from collections import Counter
from itertools import islice
import re
from typing import Annotated, Any
from zipfile import BadZipFile

from pydantic import Field

from saves import SaveError, _Text, _WHITESPACE
from world import MAX_FILE_BYTES, MAX_LINE_CHARS, MAX_PAGE_CHARS, source_path


EventId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")]
Tag = Annotated[str, Field(pattern=r"^[A-Za-z0-9]{3}$")]
Offset = Annotated[int, Field(ge=0, le=MAX_FILE_BYTES)]
EventLimit = Annotated[int, Field(ge=1, le=20)]
LineLimit = Annotated[int, Field(ge=1, le=160)]
EVENT_ID = re.compile(r"[A-Za-z0-9_.-]{1,128}")
COUNTRY_TAG = re.compile(r"[A-Za-z0-9]{3}")
EVENT_KINDS = {"country_event", "province_event"}
IDENTITY_FIELDS = ("pid", "process_start_ms", "session")


def _availability(source, available, **details):
    return {"source": source, "available": available, **details}


def _page(items, offset, limit):
    return {
        "items": items[offset:offset + limit], "total": len(items), "offset": offset,
        "next_offset": offset + limit if offset + limit < len(items) else None,
    }


def _live_events(result, field, offset, limit):
    details = {key: result[key] for key in (
        "tool", "observed_at", "tongs_version", "error_code", "error", "missing",
    ) if key in result}
    events = result.get(field)
    if not result["available"] or not isinstance(events, list):
        details.setdefault("error_code", "events_unavailable")
        return _availability("live", False, **details)
    return _availability("live", True, **details, **_page(events, offset, limit))


async def _read_live(server, tag, offset, limit):
    first = await server.read_live("tongs_state", {})
    closed = _availability("live", False, error_code="live_campaign_unavailable")
    if not first["available"] or first.get("in_game") is not True:
        return {"live_state": first, "active": closed, "queued": closed}

    windows, player = await asyncio.gather(
        server.read_live("tongs_event_list", {}), server.read_live("tongs_player", {}),
    )
    player_tag = player.get("tag") if player["available"] and not player.get("observer") else None
    selected_tag = tag or player_tag
    queued = _availability("live", False, error_code="country_tag_unavailable")
    if isinstance(selected_tag, str) and COUNTRY_TAG.fullmatch(selected_tag):
        country = await server.read_live("tongs_country", {"tag": selected_tag})
        queued = _live_events(country, "pending_events", offset, limit)

    latest = await server.read_live("tongs_state", {})
    if (not latest["available"] or latest.get("in_game") is not True
            or any(first.get(key) != latest.get(key) for key in IDENTITY_FIELDS)):
        changed = _availability("live", False, error_code="live_session_changed")
        return {"live_state": latest, "active": changed, "queued": changed}
    return {
        "live_state": latest, "read_started_game_date": first.get("date"),
        "active": {**_live_events(windows, "events", offset, limit),
                   "scope": "player_interface", "player_tag": player_tag},
        "queued": {**queued, "tag": selected_tag},
    }


def _save_scalar(node, key):
    fields = list(islice(node.children(key), 2))
    return fields[0].value if len(fields) == 1 else None


def _saved_events(saves, tag, save, campaign_id, root_index, offset, limit):
    details = {"live_campaign_match": "unverified"}
    try:
        snapshot, info = saves.snapshot(save=save, campaign_id=campaign_id, root_index=root_index,
                                        require_campaign=True)
        details.update(info)
        tag = tag or info.get("player")
        if not tag or not COUNTRY_TAG.fullmatch(tag):
            raise SaveError("country_tag_unavailable", "Brak tagu gracza w zapisie. Podaj tag państwa.")
        if not info.get("game_date"):
            raise SaveError("save_date_unavailable", "Brak daty rozgrywki w zapisie.")
        queue = snapshot.section(["pending_events"])
        if not queue.container:
            raise SaveError("pending_events_unavailable", "Brak obsługiwanej sekcji kolejki w zapisie.")

        events = []
        unresolved = 0
        for entry in queue.children():
            scopes = list(islice(entry.children("scope"), 2))
            event_id = _save_scalar(entry, "event")
            event_tag = None
            if len(scopes) == 1 and _save_scalar(scopes[0], "scope_is_valid") != "no":
                event_tag = _save_scalar(scopes[0], "country")
            if (entry.key != "event" or not event_id or not EVENT_ID.fullmatch(event_id)
                    or not event_tag or not COUNTRY_TAG.fullmatch(event_tag)):
                unresolved += 1
                continue
            if event_tag.upper() == tag.upper():
                events.append({"id": event_id, "path": ["pending_events", entry.selector]})
        result = {**details, "tag": tag, "unresolved_entries": unresolved}
        # An unsupported record might belong to the country being queried.
        if unresolved and not events:
            return {**result, "available": False, "error_code": "pending_entries_unresolved"}
        return {**result, "available": True, **_page(events, offset, limit)}
    except SaveError as error:
        return {"source": "save", **details, "available": False, "error_code": error.code, "error": str(error)}


def _script_entries(script, start, end):
    """Pair parsed values with the offset of their assignment key."""
    previous = start
    for entry in script.entries(start, end):
        position = _WHITESPACE.match(script.data, previous, end).end()
        previous = entry.end + int(entry.container)
        yield position, entry


def _scalar_fields(script, entry):
    return {item.key: script.scalar(item.start, item.end)
            for item in script.entries(entry.start, entry.end) if not item.container}


def _event_candidates(world, event_id, path):
    inventory, unreadable_archives = world.inventory
    if path is not None:
        path = source_path(path).casefold()
    matches = []
    skipped = 0
    # A script-wide prefilter avoids parsing files without this ID. The parser checks its exact scope.
    identifier = re.escape(event_id)
    space = r"(?:\s|#[^\n]*)*"
    possible = re.compile(rf'(?<![\w.])(?:"id"|id){space}={space}(?:"{identifier}"|{identifier}(?=[\s#}};]|$))')
    for key, entry in inventory.items():
        member = key.rsplit("!/", 1)[-1]
        if not member.startswith("events/") or not member.endswith(".txt") or (path is not None and key != path):
            continue
        try:
            lines, _ = world._lines(entry)
            content = "\n".join(lines)
            if not possible.search(content):
                continue
            script = _Text(content.encode("utf-8"))
            for start, block in _script_entries(script, script.start, len(script.data)):
                if not block.container or block.key not in EVENT_KINDS:
                    continue
                if _scalar_fields(script, block).get("id") == event_id:
                    matches.append((entry.path, script, start, block))
        except (OSError, ValueError, BadZipFile, KeyError, RuntimeError):
            skipped += 1
    return matches, skipped, unreadable_archives


def _line(script, position):
    return script.data.count(b"\n", 0, position) + 1


def _script_page(script, start, end, offset, limit):
    lines = script.data[start:end].decode("utf-8").split("\n")
    first_line = _line(script, start)
    result = []
    remaining = MAX_PAGE_CHARS
    for index, line in enumerate(lines[offset:offset + limit], start=offset):
        preview = line[:MAX_LINE_CHARS]
        if len(preview) + 1 > remaining:
            break
        result.append({"line": first_line + index, "text": preview, "truncated": preview != line})
        remaining -= len(preview) + 1
    next_offset = offset + len(result)
    return {"lines": result, "offset": offset, "next_offset": next_offset if next_offset < len(lines) else None}


def _event_definition(world, event_id, path, start_line, section, occurrence, offset, limit):
    result = {"source": "installed_game_files", "game_version": world.version, "id": event_id, "available": False}
    if world.game_dir is None:
        return {**result, "error_code": "game_files_unavailable"}
    matches, skipped, archives = _event_candidates(world, event_id, path)
    result.update({"files_skipped": skipped, "unreadable_archives": archives})
    if start_line is not None:
        matches = [match for match in matches if _line(match[1], match[2]) == start_line]
    if not matches:
        return {**result, "error_code": "definition_not_found"}
    if len(matches) > 1:
        return {**result, "error_code": "ambiguous_definition", "definitions": [
            {"path": file, "start_line": _line(script, start)} for file, script, start, _ in matches
        ]}

    file, script, start, block = matches[0]
    result.update({"path": file, "kind": block.key, "start_line": _line(script, start),
                   "end_line": _line(script, block.end), "properties": _scalar_fields(script, block)})
    sections = []
    by_key = Counter()
    selected = (start, block.end + 1) if section is None else None
    for position, child in _script_entries(script, block.start, block.end):
        if not child.container or not child.key:
            continue
        current = by_key[child.key]
        entry = {"key": child.key, "occurrence": current,
                 "start_line": _line(script, position), "end_line": _line(script, child.end)}
        by_key[child.key] += 1
        if child.key == "option":
            entry["name_key"] = _scalar_fields(script, child).get("name")
        sections.append(entry)
        if (child.key, current) == (section, occurrence):
            selected = position, child.end + 1
    result["sections"] = sections
    if selected is None:
        return {**result, "error_code": "section_not_found"}
    return {**result, "available": True, **_script_page(script, *selected, offset, limit)}


def register_events(server, world, saves, annotations):
    @server.tool(annotations=annotations)
    async def eu4_campaign_events(tag: Tag | None = None, campaign_id: str | None = None,
                                  save: str | None = None, root_index: Offset | None = None,
                                  offset: Offset = 0, limit: EventLimit = 10) -> dict[str, Any]:
        """Odczytaj otwarte okna gracza i zdarzenia oczekujące na wybór państwa.

        `active` pochodzi z interfejsu gracza. `queued` dotyczy państwa `tag` albo gracza i może obejmować
        te same zdarzenia, co widać po `pending_id`. Data `auto_select` dotyczy automatycznego wyboru opcji.
        Podaj `save`, `campaign_id` lub `root_index`, aby skierować odczyt do zapisu. Wtedy `queued` zawiera
        datowany odczyt sekcji `pending_events`, a widoczność okien pozostaje nieznana. Gdy nie ma dostępu
        do bieżącej kampanii, `saved_queued` podaje odrębny odczyt dostępnego zapisu z nazwą i datą.
        Obie listy można stronicować. Do skutków opcji użyj eu4_event_definition z identyfikatorem zdarzenia.
        Przypisz opcję do sekcji `option` po zerowym `option_index`, jeżeli odczytano go i pasuje definicja gry.
        `number` to pozycja w oknie, gdzie część opcji może być pominięta.
        """
        tag = tag.upper() if tag else None
        if save is not None or campaign_id is not None or root_index is not None:
            queued = await asyncio.to_thread(_saved_events, saves, tag, save, campaign_id, root_index, offset, limit)
            return {
                "active": _availability("save", False, error_code="event_windows_not_recorded"), "queued": queued,
            }
        result = await _read_live(server, tag, offset, limit)
        if result["queued"].get("error_code") == "live_campaign_unavailable":
            result["saved_queued"] = await asyncio.to_thread(
                _saved_events, saves, tag, save, campaign_id, root_index, offset, limit,
            )
        return result

    @server.tool(annotations=annotations)
    async def eu4_event_definition(event_id: EventId, path: str | None = None,
                                   start_line: Annotated[int, Field(ge=1)] | None = None,
                                   section: Annotated[str, Field(min_length=1, max_length=128)] | None = None,
                                   occurrence: Offset = 0, offset: Offset = 0, limit: LineLimit = 100) -> dict[str, Any]:
        """Odczytaj źródłową definicję zdarzenia po pełnym ID (np. flavor_pol.18 lub 1021).

        Zwraca warunki `trigger`, `is_triggered_only`, `fire_only_once`, bazę i modyfikatory
        `mean_time_to_happen`, efekty `immediate` i powtarzające się `option` w kolejności w skrypcie.
        `section` wybiera blok, np. `option`, i jego `occurrence` liczone od zera. `offset` i `next_offset`
        są liczone w wierszach w obrębie wybranego bloku lub całej definicji. Przy kontynuacji podaj `path`
        z odpowiedzi. Przy wielu definicjach wybierz `path` i ewentualnie `start_line` nagłówka zdarzenia.
        `ai_chance` dotyczy wyboru opcji przez AI. `mean_time_to_happen` określa parametr losowania.
        Wydarzenia wywoływane przez inne skrypty można prześledzić przez eu4_game_search po pełnym ID.
        Tekst w grze i dostępność widocznych opcji odczytaj z eu4_campaign_events.
        """
        return await asyncio.to_thread(_event_definition, world, event_id, path, start_line,
                                       section, occurrence, offset, limit)
