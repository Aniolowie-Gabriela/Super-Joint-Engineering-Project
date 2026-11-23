"""Polskie karty z wybranych wartości liczbowych w plikach instalacji EU4."""

import re
from collections import defaultdict

from build_index import between, blocks, decode, scalar


GOODS = dict(zip(
    "grain wine wool cloth fish fur salt naval_supplies copper gold iron slaves ivory tea chinaware spices coffee cotton sugar tobacco cocoa silk tropical_wood dyes livestock incense glass gems paper coal cloves".split(),
    "zboże|wino|wełna|sukno|ryby|futra|sól|zaopatrzenie okrętowe|miedź|złoto|żelazo|niewolnicy|kość słoniowa|herbata|porcelana|przyprawy|kawa|bawełna|cukier|tytoń|kakao|jedwab|drewno tropikalne|barwniki|zwierzęta hodowlane|kadzidło|szkło|kamienie szlachetne|papier|węgiel|goździki".split("|"),
    strict=True,
))
BUILDINGS = {
    "marketplace": "Targowisko", "workshop": "Warsztat", "temple": "Świątynia",
    "barracks": "Koszary", "shipyard": "Stocznia", "courthouse": "Sąd",
    "cathedral": "Katedra", "university": "Uniwersytet", "trade_depot": "Skład handlowy",
    "stock_exchange": "Giełda", "town_hall": "Ratusz", "manufactory": "Manufaktura",
}
UNIT_TYPES = {
    "infantry": "Piechota", "cavalry": "Kawaleria", "artillery": "Artyleria",
    "heavy_ship": "Ciężki okręt", "light_ship": "Lekki okręt",
    "galley": "Galera", "transport": "Transportowiec",
}


def make_card(version, path, symbol, family, title, text, lines):
    key = f"fact:{family}:{symbol}"
    return {
        "chunk_id": key, "document_id": key, "family": family, "symbol": symbol,
        "title": title, "text": text, "source_type": "game_fact", "game_version": version,
        "source_path": path, "lines": lines,
        "game_refs": [{"path": path, "symbol": symbol, "line": lines[0]}],
    }


def technology_unlocks(game):
    unlocks = defaultdict(list)
    for branch, label in (("adm", "administracyjnej"), ("dip", "dyplomatycznej"), ("mil", "wojskowej")):
        relative = f"common/technologies/{branch}.txt"
        if not (game / relative).is_file():
            continue
        source, _, _ = decode(game / relative)
        levels = (node for node in blocks(source) if node.key == "technology")
        for level, node in enumerate(levels):
            start = node.opening
            for stop, resume in [(child.start, child.end) for child in node.children] + [(node.end - 1, node.end)]:
                for match in re.finditer(r"(?m)^[ \t]*(\w+)\s*=[ \t]*(\w+)", source[start:stop]):
                    key, value = match.groups()
                    if key == "enable" or value == "yes":
                        symbol = value if key == "enable" else key
                        line = source.count("\n", 0, start + match.start()) + 1
                        unlocks[symbol].append((label, level, {"path": relative, "symbol": symbol, "line": line}))
                start = resume
    return unlocks


def game_facts(game, version):
    unlocks = technology_unlocks(game)
    for card in numeric_cards(game, version):
        if card["family"] in {"buildings", "units"}:
            for label, level, ref in unlocks[card["symbol"]]:
                card["text"] += f" Odblokowanie w technologii {label}: poziom {level}."
                card["game_refs"].append(ref)
        yield card


def numeric_cards(game, version):
    for family, filename in (("prices", "prices/00_prices.txt"), ("buildings", "buildings/00_buildings.txt")):
        relative = "common/" + filename
        if not (game / relative).is_file():
            continue
        source, _, _ = decode(game / relative)
        for node in blocks(source):
            symbol = node.key
            if family == "prices":
                price = scalar(source, node, "base_price")
                if price is None or symbol == "unknown":
                    continue
                title = "Cena bazowa • " + GOODS.get(symbol, symbol)
                detail = f"Cena bazowa towaru {GOODS.get(symbol, symbol)} ({symbol}) wynosi {price} dukatów za jednostkę."
                if scalar(source, node, "goldtype") == "yes":
                    detail = "Złoto daje dochód z kopalni. Wartość 0 w polu ceny bazowej nie opisuje dochodu z wydobycia."
            else:
                cost, months = (scalar(source, node, key) for key in ("cost", "time"))
                if cost is None or months is None:
                    continue
                name = BUILDINGS.get(symbol, symbol.replace("_", " "))
                title = f"Budowa • {name}"
                detail = f"{name} ({symbol}). Bazowy koszt budowy w dukatach: {cost}. Bazowy czas budowy w miesiącach: {months}."
            lines = [source.count("\n", 0, pos) + 1 for pos in (node.start, node.end - 1)]
            yield make_card(version, relative, symbol, family, title, detail, lines)

    for path in sorted((game / "common/units").glob("*.txt")):
        source, _, _ = decode(path)
        direct = between(source, 0, len(source), blocks(source))
        values = dict(re.findall(r"(?m)^\s*(\w+)\s*=\s*([\w.-]+)", direct))
        kind = UNIT_TYPES.get(values.get("type"))
        if not kind:
            continue
        name = path.stem.replace("_", " ")
        fields = []
        if "unit_type" in values:
            fields.append("Grupa jednostki: " + values["unit_type"] + ".")
        for phase, label in (("fire", "Ogień"), ("shock", "Uderzenie"), ("morale", "Morale")):
            attack, defense = values.get("offensive_" + phase), values.get("defensive_" + phase)
            if attack is not None and defense is not None:
                fields.append(f"{label} (punkty ataku / obrony): {attack} / {defense}.")
        for key, label in (("hull_size", "Wytrzymałość kadłuba"), ("base_cannons", "Bazowa liczba dział"),
                           ("sailors", "Załoga"), ("sail_speed", "Szybkość żeglugi")):
            if key in values:
                fields.append(f"{label}: {values[key]}.")
        if fields:
            yield make_card(version, path.relative_to(game).as_posix(), path.stem, "units",
                            f"{kind} • {name}", f"{name} ({kind.lower()}). " + " ".join(fields),
                            [1, len(source.splitlines())])
