"""Compare two existing snapshots of the same EU4 campaign."""

from __future__ import annotations

import asyncio
from decimal import Decimal
import re
from typing import Annotated, Any

from pydantic import Field

from country_briefing import _date, _group, _number, _save_budget, _save_wars, _value
from saves import SaveError, SaveProvider, _File, _SAVE_NAME, _ZIP_ERRORS, _stamp, _unstable


RootIndex = Annotated[int, Field(ge=0)]
_PLAYER_TAG = re.compile(r"[A-Z0-9]{3}")
_RESOURCE_KEYS = {
    "treasury_ducats": "treasury",
    "manpower_thousands": "manpower",
    "max_manpower_thousands": "max_manpower",
    "stability": "stability",
    "war_exhaustion": "war_exhaustion",
}


def _find(saves: SaveProvider, name: str, root_index: int | None) -> _File:
    if not _SAVE_NAME.fullmatch(name):
        raise SaveError("invalid_request", "Podaj nazwę pliku .eu4 z listy zapisów.")
    files = [file for file in saves._files(root_index) if file.path.name.casefold() == name.casefold()]
    if len(files) > 1:
        raise SaveError("ambiguous_save", f"Kilka plików ma nazwę {name}. Wskaż indeks katalogu z listy zapisów.")
    if not files:
        raise SaveError("save_not_found", f"Nie znaleziono pliku {name} w katalogach zapisów.")
    return files[0]


def _require_unchanged(file: _File) -> None:
    if _stamp(file.path.stat(follow_symlinks=False)) != file.stamp:
        raise _unstable()


def _load(saves: SaveProvider, file: _File):
    _require_unchanged(file)
    with saves._lock:
        snapshot = saves._snapshot(file)
    info = {**file.info(), **snapshot.metadata, "format": snapshot.format}
    if (_date(info["game_date"]) is None or not (info["campaign_id"] or "").strip()
            or not _PLAYER_TAG.fullmatch(info["player"] or "")):
        raise SaveError(
            "save_identity_unavailable",
            f"W zapisie {info['save']} nie udało się odczytać daty gry, tagu gracza lub identyfikatora kampanii.",
        )
    return snapshot, info


def _same_file(first: _File, second: _File) -> bool:
    return first.path == second.path or (first.stamp[-1] != 0 and first.stamp[-2:] == second.stamp[-2:])


def _metrics(snapshot, tag):
    path = ["countries", tag]
    try:
        country = snapshot.section(path)
    except SaveError as error:
        if error.code != "missing_path":
            raise
        raise SaveError("country_unavailable", "W zapisie brak czytelnej sekcji państwa gracza.") from error
    if not country.container:
        raise SaveError("country_unavailable", "W zapisie brak czytelnej sekcji państwa gracza.")
    fields = _group(country, {"loan", *_RESOURCE_KEYS.values()})
    budget = _save_budget(fields, path)
    wars = _save_wars(snapshot.section().children("active_war"), tag)
    values = {key: _number(_value(fields, field)) for key, field in _RESOURCE_KEYS.items()}
    loans = budget["loans"]
    values.update({
        "loans": loans["count"] if loans is not None else None,
        "debt_ducats": loans["principal"] if loans is not None else None,
        "active_wars": wars["count"] if not wars["unclassified"] else None,
    })
    return values, wars


def _load_after(saves, file, before, *, allow_same_date):
    snapshot, info = _load(saves, file)
    if info["campaign_id"] != before["campaign_id"]:
        raise SaveError("different_campaign", "Wybrane zapisy mają różne identyfikatory kampanii.")
    before_date, after_date = _date(before["game_date"]), _date(info["game_date"])
    if after_date < before_date or (after_date == before_date and not allow_same_date):
        raise SaveError("earlier_save", "Wybrany drugi zapis ma zbyt wczesną datę gry.")
    return info, *_metrics(snapshot, info["player"])


def _latest(saves, root_index, before, before_file):
    before_date = _date(before["game_date"])
    for file in saves._files(root_index):
        if _same_file(before_file, file):
            continue
        try:
            with saves._lock:
                preview = saves._preview(file)
            if preview["campaign_id"] not in (None, before["campaign_id"]):
                continue
            preview_date = _date(preview["game_date"])
            if preview_date is not None and preview_date <= before_date:
                continue
            after, values, wars = _load_after(saves, file, before, allow_same_date=False)
            _require_unchanged(file)
        except (SaveError, OSError, *_ZIP_ERRORS):
            continue
        return file, after, values, wars
    raise SaveError("later_save_not_found", "Brak czytelnego zapisu z późniejszą datą gry i tym samym identyfikatorem kampanii.")


def _compare(saves, before_name, after_name, before_root_index, after_root_index):
    try:
        before_file = _find(saves, before_name, before_root_index)
        snapshot, before = _load(saves, before_file)
        before_values, before_wars = _metrics(snapshot, before["player"])
        if after_name is None:
            after_file, after, after_values, after_wars = _latest(saves, after_root_index, before, before_file)
        else:
            after_file = _find(saves, after_name, after_root_index)
            if _same_file(before_file, after_file):
                raise SaveError("same_save", "Wybierz drugi zapis do porównania.")
            after, after_values, after_wars = _load_after(saves, after_file, before, allow_same_date=True)
        _require_unchanged(before_file)
        _require_unchanged(after_file)
    except (OSError, *_ZIP_ERRORS):
        return _error(SaveError("save_unreadable", "Jeden z plików zapisu jest niedostępny lub nieczytelny."))
    except SaveError as error:
        return _error(error)

    changes = {}
    for key, first in before_values.items():
        last = after_values[key]
        delta = _number(str(Decimal(str(last)) - Decimal(str(first)))) if None not in (first, last) else None
        changes[key] = {"before": first, "after": last, "delta": delta}
    return {
        "source": "save", "available": True, "before": before, "after": after,
        "selection": "named" if after_name is not None else "latest_later_save",
        "same_game_date": _date(before["game_date"]) == _date(after["game_date"]),
        "player_changed": before["player"] != after["player"], "changes": changes,
        "wars": {"before": before_wars, "after": after_wars},
    }


def _error(error: SaveError) -> dict[str, Any]:
    return {"source": "save", "available": False, "error_code": error.code, "error": str(error)}


def register_save_compare(server, saves: SaveProvider, read_only):
    @server.tool(annotations=read_only)
    async def eu4_save_compare(
        before: str,
        after: str | None = None,
        before_root_index: RootIndex | None = None,
        after_root_index: RootIndex | None = None,
    ) -> dict[str, Any]:
        """Porównaj stan gracza z dwóch istniejących zapisów tego samego ID kampanii.

        Podaj nazwy plików .eu4 z eu4_save_list. Przy powtórzonej nazwie wskaż indeks katalogu.
        Bez `after` wybiera ostatnio modyfikowany czytelny zapis z późniejszą datą gry.
        Dwa różne pliki z tą samą datą gry można porównać, podając `after` wprost.
        Wynik podaje źródło, datę i tag gracza dla obu zapisów. `null` oznacza brak wartości lub różnicy.
        """
        return await asyncio.to_thread(_compare, saves, before, after, before_root_index, after_root_index)
