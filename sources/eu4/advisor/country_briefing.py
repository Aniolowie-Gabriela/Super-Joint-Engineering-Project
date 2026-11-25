"""Read-only strategic briefing from Tongs or one selected EU4 save."""

import asyncio
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Annotated, Any

from pydantic import Field

from saves import SaveError


Tag = Annotated[str, Field(pattern=r"^[A-Za-z0-9]{3}$")]
RootIndex = Annotated[int, Field(ge=0)]
_EXAMPLES = 6
_PROCESS_KEYS = ("pid", "process_start_ms", "session")
_WAR_GOALS = ("take_province", "take_core", "take_capital", "superiority")
_TOPBAR_FIELDS = {
    "treasury": "text_gold",
    "manpower": "text_manpower",
    "sailors": "text_sailors",
    "stability": "text_stability",
}


def register_briefing(server, world, saves, annotations):
    @server.tool(annotations=annotations)
    async def eu4_country_briefing(
        tag: Tag | None = None, campaign_id: str | None = None, save: str | None = None,
        root_index: RootIndex | None = None,
    ) -> dict[str, Any]:
        """Oceń sytuację strategiczną kraju, domyślnie państwa gracza.

        Na żywo odczytuje dyplomację, jednostki i wartości widoczne w pasku gracza.
        Z zapisu odczytuje też budżet, pożyczki i aktywne wojny. Wybierz save lub campaign_id,
        by odczytać konkretny zapis lub kampanię, także przy uruchomionej grze.
        Null oznacza brak wiarygodnego odczytu. W attention są fakty warte sprawdzenia.
        """
        tag = tag.upper() if tag is not None else None
        if any(selector is not None for selector in (save, campaign_id, root_index)):
            return await asyncio.to_thread(_save_briefing, saves, tag, campaign_id, save, root_index)
        live = await _live_briefing(server, tag)
        if live["available"] or live.get("in_game"):
            return live
        saved = await asyncio.to_thread(_save_briefing, saves, tag, None, None, None)
        return {**saved, "live": live}


def _identity(result):
    return tuple(result.get(key) for key in _PROCESS_KEYS)


def _hud_arguments(widget):
    return {"selector": f"topbar//{widget}", "limit": 2}


def _hud_text(result):
    if not result["available"] or result.get("truncated") or result.get("count") != 1:
        return None
    matches = result.get("matches")
    if not isinstance(matches, list) or len(matches) != 1 or not isinstance(matches[0], dict):
        return None
    widget = matches[0]
    value = widget.get("text")
    if widget.get("visible") is True and not widget.get("stale") and isinstance(value, str):
        return value.strip() or None
    return None


async def _live_briefing(server, tag):
    was_in_game = False
    for _ in range(2):
        start = await server.read_live("tongs_state", {})
        if not start["available"] or not start.get("in_game"):
            if was_in_game:
                break
            return {**start, "available": False}
        was_in_game = True
        player = await server.read_live("tongs_player", {"timeout": 3})
        player_tag = player.get("tag") if player["available"] else None
        country_tag = tag or player_tag
        if not country_tag:
            return {**start, "available": False, "error_code": "player_tag_unavailable"}
        hud = _TOPBAR_FIELDS if player_tag == country_tag and player.get("observer") is False else {}
        country_args = {"tag": country_tag, "timeout": 3}
        country, units, *widgets = await asyncio.gather(
            server.read_live("tongs_country", country_args),
            server.read_live("tongs_units", country_args),
            *(server.read_live("tongs_ui_find", _hud_arguments(widget)) for widget in hud.values()),
        )
        end = await server.read_live("tongs_state", {})
        identity = _identity(start)
        if (not end["available"] or not end.get("in_game") or _identity(end) != identity
                or any(
                    result.get(key) is not None and result[key] != value
                    for result in (player, country, units, *widgets)
                    for key, value in zip(_PROCESS_KEYS, identity)
                )):
            continue
        country_data = country if country["available"] and country.get("tag") == country_tag else {}
        unit_data = units.get("units") if units["available"] and units.get("tag") == country_tag else None
        if not country_data and not isinstance(unit_data, list):
            return {**start, "available": False, "error_code": "country_unavailable", "tag": country_tag,
                    "country_error": country.get("error"), "units_error": units.get("error")}
        resources = dict.fromkeys(_TOPBAR_FIELDS)
        resources.update({name: _hud_text(result) for name, result in zip(hud, widgets)})
        return {
            "source": "live", "available": True, "tag": country_tag, "player": player.get("player_tag"),
            "observer": player.get("observer"), "game_date": end.get("date"), "read_started_on": start.get("date"),
            "tongs_version": start.get("tongs_version"), "observed_at": end.get("observed_at"),
            **dict(zip(_PROCESS_KEYS, identity)),
            "country": {name: country_data.get(name) for name in ("exists", "capital", "province_count")},
            "diplomacy": _live_diplomacy(country_data.get("diplomacy"), end.get("date")),
            "military": _live_military(unit_data), "resources_displayed": resources,
            "wars": None, "budget": None,
            "attention": _live_attention(unit_data),
            "details": {
                "country": {"tool": "tongs_country", "tag": country_tag},
                "units": {"tool": "tongs_units", "tag": country_tag},
                "resources_displayed": {
                    name: {"tool": "tongs_ui_find", **_hud_arguments(widget)} for name, widget in hud.items()
                },
            },
        }
    return {"source": "live", "available": False, "in_game": was_in_game, "error_code": "live_session_changed",
            "error": "Gra zmieniła sesję podczas odczytu. Ponów przegląd."}


def _date(value):
    if isinstance(value, str):
        parts = value.split(".")
        if len(parts) == 3 and all(part.isascii() and part.isdecimal() and len(part) <= 5 for part in parts):
            return tuple(map(int, parts))
    return None


def _relation_current(start, end, date):
    if start is None and end is None:
        return True
    today = _date(date)
    start_date, end_date = _date(start), _date(end)
    if today is None or (start is not None and start_date is None) or (end is not None and end_date is None):
        return None
    return (start_date is None or start_date <= today) and (end_date is None or end_date >= today)


def _live_diplomacy(data, date):
    if not isinstance(data, dict):
        return None
    result = {}
    for key in ("alliance", "royal_marriage", "guarantee", "dependency"):
        relations = data.get(key)
        if not isinstance(relations, list):
            result[key] = None
            continue
        items = []
        complete = True
        for relation in relations:
            if not isinstance(relation, dict) or not relation.get("first") or not relation.get("second"):
                complete = False
                continue
            in_effect = _relation_current(relation.get("start"), relation.get("end"), date)
            if in_effect is not False:
                items.append({**relation, "in_effect": in_effect})
            complete &= in_effect is not None
        result[key] = {"count": len(items), "complete": complete, "examples": items[:_EXAMPLES]}
    for key in ("rivals", "subjects"):
        items = data.get(key)
        result[key] = {"count": len(items), "examples": items[:_EXAMPLES]} if isinstance(items, list) else None
    result["overlord"] = data.get("overlord")
    result["overlord_known"] = "overlord" in data
    return result


def _live_military(items):
    if not isinstance(items, list) or any(
        not isinstance(item, dict) or item.get("kind") not in ("army", "navy") for item in items
    ):
        return None
    result = {}
    for kind, quantity in (("army", "regiments"), ("navy", "ships")):
        group = [item for item in items if item["kind"] == kind]
        counts = [item.get("subunits") for item in group]
        result[kind] = {
            "formations": len(group),
            quantity: sum(counts) if all(type(count) is int and count >= 0 for count in counts) else None,
            "examples": [
                {key: unit.get(key) for key in ("name", "location", "mission", "subunits", "strength")}
                for unit in group[:_EXAMPLES]
            ],
        }
    return result


def _live_attention(items):
    if not isinstance(items, list):
        return []
    missions = defaultdict(int)
    for item in items:
        if isinstance(item, dict) and item.get("mission") in ("siege", "drill"):
            missions[item["mission"]] += 1
    return [{"topic": "units", "missions": dict(missions)}] if missions else []


def _group(node, keys):
    result = defaultdict(list)
    for child in node.children():
        if child.key in keys:
            result[child.key].append(child)
    return result


def _single(fields, key):
    matches = fields.get(key, ())
    return matches[0] if len(matches) == 1 else None


def _value(fields, key):
    match = _single(fields, key)
    return match.value if match is not None else None


def _decimal(value):
    if value:
        try:
            number = Decimal(value)
            if number.is_finite() and isfinite(float(number)):
                return number
        except InvalidOperation:
            pass
    return None


def _number(value):
    number = _decimal(value)
    return float(number) if number is not None else None


def _array(node):
    if node is None or not node.container:
        return None
    items = list(node.children())
    if any(item.key is not None or item.container for item in items):
        return None
    return [item.value for item in items]


def _save_budget(fields, path):
    ledger = _single(fields, "ledger")
    recurring_keys = ("last_months_recurring_income", "last_months_recurring_expenses")
    monthly = _group(ledger, {"lastmonthincome", "lastmonthexpense", *recurring_keys}) if ledger else {}
    income = _decimal(_value(monthly, "lastmonthincome"))
    expense = _decimal(_value(monthly, "lastmonthexpense"))
    budget = {
        "last_month_income": float(income) if income is not None else None,
        "last_month_expense": float(expense) if expense is not None else None,
        "last_month_balance": _number(str(income - expense)) if None not in (income, expense) else None,
        **{key: _number(_value(monthly, key)) for key in recurring_keys},
        "loans": None,
    }
    loans = fields["loan"]
    if any(not loan.container for loan in loans):
        return budget
    terms = ("amount", "interest", "expiry_date", "lender")
    examples = []
    total = Decimal(0)
    for loan in loans:
        values = _group(loan, terms)
        amount = _decimal(_value(values, "amount"))
        total = total + amount if None not in (total, amount) else None
        if len(examples) < _EXAMPLES:
            examples.append({
                "amount": float(amount) if amount is not None else None,
                "interest": _number(_value(values, "interest")), "expiry_date": _value(values, "expiry_date"),
                "lender": _value(values, "lender"), "path": [*path, loan.selector],
            })
    budget["loans"] = {"count": len(loans), "principal": _number(str(total)), "examples": examples}
    return budget


def _save_diplomacy(section, tag, date):
    if section is None or not section.container:
        return None
    kinds = ("alliance", "royal_marriage", "guarantee", "dependency")
    relations = _group(section, kinds)
    result = {}
    subjects, overlords = [], []
    for kind in kinds:
        items = []
        complete = True
        for entry in relations[kind]:
            fields = _group(entry, {"first", "second", "subject_type", "start_date", "end_date"})
            first, second = _value(fields, "first"), _value(fields, "second")
            if first is None or second is None:
                complete = False
                continue
            if tag not in (first, second):
                continue
            start, end = _value(fields, "start_date"), _value(fields, "end_date")
            in_effect = _relation_current(start, end, date)
            if in_effect is False:
                continue
            complete &= in_effect is not None
            relation = {"first": first, "second": second, "start_date": start, "end_date": end,
                        "in_effect": in_effect, "path": ["diplomacy", entry.selector]}
            if kind == "dependency":
                relation["subject_type"] = _value(fields, "subject_type")
                if in_effect:
                    if first == tag:
                        subjects.append(second)
                    else:
                        overlords.append(first)
            items.append(relation)
        result[kind] = {"count": len(items), "complete": complete, "examples": items[:_EXAMPLES]}
    for key, tags in (("subjects", subjects), ("overlords", overlords)):
        result[key] = {"count": len(tags), "complete": result["dependency"]["complete"], "examples": tags[:_EXAMPLES]}
    return result


def _save_military(fields, path):
    result = {}
    for kind, subunit, quantity in (("army", "regiment", "regiments"), ("navy", "ship", "ships")):
        forces = fields[kind]
        if any(not force.container for force in forces):
            result[kind] = None
            continue
        counts = []
        examples = []
        for force in forces:
            info = _group(force, {"name", "location", subunit})
            count = len(info[subunit]) if all(item.container for item in info[subunit]) else None
            counts.append(count)
            if len(examples) < _EXAMPLES:
                examples.append({"name": _value(info, "name"), "location": _number(_value(info, "location")),
                                 quantity: count, "path": [*path, force.selector]})
        result[kind] = {"formations": len(forces), quantity: sum(counts) if None not in counts else None,
                        "examples": examples}
    return result


def _save_wars(wars, tag):
    items = []
    unclassified = 0
    for war in wars:
        fields = _group(war, {"name", "attackers", "defenders", "history", *_WAR_GOALS})
        attackers = _array(_single(fields, "attackers"))
        defenders = _array(_single(fields, "defenders"))
        if attackers is None or defenders is None:
            unclassified += 1
        if tag not in (attackers or []) and tag not in (defenders or []):
            continue
        candidates = [node for key in _WAR_GOALS if (node := _single(fields, key)) is not None]
        goal = candidates[0] if len(candidates) == 1 else None
        if goal is None and (history := _single(fields, "history")) is not None:
            goal = _single(_group(history, {"war_goal"}), "war_goal")
        goal_fields = _group(goal, {"type", "casus_belli", "province"}) if goal else {}
        items.append({
            "name": _value(fields, "name"),
            "side": "attacker" if tag in (attackers or []) else "defender",
            "attackers": attackers, "defenders": defenders,
            "goal": {key: _value(goal_fields, key) for key in ("type", "casus_belli", "province")} if goal_fields else None,
            "path": [war.selector],
        })
    return {"count": len(items), "unclassified": unclassified, "examples": items[:_EXAMPLES]}


def _save_attention(wars, budget, resources):
    attention = []
    if wars["count"]:
        attention.append({"topic": "active_wars", "count": wars["count"]})
    balance = budget["last_month_balance"]
    if balance is not None and balance < 0:
        attention.append({"topic": "last_month_deficit", "ducats": -balance})
    loans = budget["loans"]
    if loans and loans["count"]:
        attention.append({"topic": "loans", "count": loans["count"], "principal": loans["principal"]})
    manpower, maximum = resources["manpower_thousands"], resources["max_manpower_thousands"]
    if manpower is not None and maximum and manpower < maximum / 3:
        attention.append({"topic": "low_manpower", "percent_of_maximum": round(100 * manpower / maximum, 1)})
    if resources["stability"] is not None and resources["stability"] < 0:
        attention.append({"topic": "negative_stability", "value": resources["stability"]})
    return attention


def _save_briefing(saves, tag, campaign_id, save, root_index):
    info = {"source": "save", "live_campaign_match": "unverified"}
    try:
        snapshot, metadata = saves.snapshot(save=save, campaign_id=campaign_id, root_index=root_index,
                                            require_campaign=True)
        info.update(metadata)
        tag = tag or info.get("player")
        if not tag:
            raise SaveError("player_tag_unavailable", "Zapis nie zawiera tagu gracza. Wskaż kraj przez tag.")
        path = ["countries", tag]
        country = snapshot.section(path)
        if not country.container:
            raise SaveError("country_unavailable", "W zapisie brak czytelnej sekcji tego kraju.")
        resources = {
            "treasury": "treasury", "manpower_thousands": "manpower", "max_manpower_thousands": "max_manpower",
            "sailors": "sailors", "stability": "stability", "prestige": "prestige", "war_exhaustion": "war_exhaustion",
        }
        fields = _group(country, set(resources.values()) | {
            "capital", "owned_provinces", "ledger", "loan", "army", "navy", "technology",
        })
        roots = _group(snapshot.section(), {"diplomacy", "active_war"})
        budget = _save_budget(fields, path)
        wars = _save_wars(roots["active_war"], tag)
        owned = _array(_single(fields, "owned_provinces"))
        technology = _single(fields, "technology")
        tech = _group(technology, {"adm_tech", "dip_tech", "mil_tech"}) if technology else {}
        resources = {name: _number(_value(fields, key)) for name, key in resources.items()}
        return {
            **info, "available": True, "tag": tag,
            "country": {"capital": _number(_value(fields, "capital")),
                        "province_count": len(owned) if owned is not None else None,
                        "technology": {key: _number(_value(tech, key)) for key in ("adm_tech", "dip_tech", "mil_tech")}},
            "resources": resources, "budget": budget,
            "diplomacy": _save_diplomacy(_single(roots, "diplomacy"), tag, info["game_date"]),
            "military": _save_military(fields, path), "wars": wars,
            "attention": _save_attention(wars, budget, resources),
            "details": {
                "tool": "eu4_save_read", "save": info["save"], "root_index": info["root_index"],
                "country_path": path, "ledger_path": [*path, "ledger"], "diplomacy_path": ["diplomacy"],
                "wars_find": {"tool": "eu4_save_find", "key": "active_war", "exact": True},
            },
        }
    except SaveError as error:
        return {**info, "available": False, "tag": tag, "error_code": error.code, "error": str(error)}
