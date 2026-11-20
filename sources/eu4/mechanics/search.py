"""Read-only retrieval for the EU4 assistant, CLI and MCP server."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import unicodedata

from interpret import COUNTRY_TAG, annotations

MECHANIC_LOOKUPS = (
    (r"wojen.*budzet|budzet.*wojen|(?:bilans|skarb|deficyt).*(?:utrzym|fort|wojn)", ("wartime-budget",)),
    (r"(?<![a-z])(?:zwykl[aey].{0,25}pozycz|bankow.{0,24}pozycz|pozycz.{0,24}bankow|pozycz.{0,70}(?:odset|inflac)|bank loan)",
     ("ordinary-bank-loans",)),
    (r"mothball|uspion.*fort|fort.*uspi|utrzymani.*fort", ("wartime-budget",)),
    (r"g[oó]r(?:ach|y|sk)|mountain|(?<![a-z])(?:rzek|przepraw)|river crossing|strait crossing",
     ("combat-terrain-and-crossings",)),
    (r"reparac|war reparations", ("war-reparations",)),
    (r"wojenn.*podat|podat.*wojenn|war taxes", ("war-taxes",)),
    (r"(?:osobn|oddzieln|odrebn).{0,12}pok[oó]j|separate peace|separat.*pok", ("coalition-separate-peace",)),
    (r"prestiz|prestige", ("prestige",)),
    (r"(?:zbier|pobier|collect).{0,95}(?:kupc|handl|wezl|wez|merchant|trade|node)|(?:home node|glown.*miast.*handl)|(?:po co|do czego|jak uzyw|what.*for).*(?:kupc|merchant)",
     ("collecting-and-steering-trade",)),
    (r"ochron.*handl|chron.*handl|protect trade|lekk.*okr", ("trade-protection-and-power",)),
    (r"warsztat|workshop|textile manufact|manufaktur.*wlokien|towar.*efektywnosc produkcj",
     ("workshops-and-manufactories",)),
    (r"jagiell|kazimierz|flavor_pol\.18", ("pol-casimir-election-effects",)),
    (r"(?:warszaw|warsaw|mazowsz|mazovi).*(?:stolic|capital)|(?:stolic|capital).*(?:warszaw|warsaw)",
     ("pol-move-capital-warsaw",)),
    (r"(?:liczeb|liczba|tysi[eę]c|manpower).*(?:wygr|zwyci|atak|bitw)|przed.*(?:bitw|atak)|battle.*(?:win|advantage)",
     ("war-before-declaration",)),
    (r"(?:(?:po co|co daj|jak dzial|how.*work).*(?:fortun|fort[yua]|zamk|fort\b))",
     ("war-terrain-forts",)),
    (r"(?:po co|co daj|jak dzial|what is).*(?:koalicj|agresywn.*ekspansj|\bae\b)",
     ("koalicja-czlonkostwo-i-ofensywa", "coalition-eligibility")),
    (r"\bdoradc|\badvisor", ("advisors-and-monarch-points",)),
    (r"\bmorale\b|dyscyplin|discipline|military tactics|taktyk.*wojsk",
     ("battle-morale-and-discipline",)),
    (r"zasob.*ludz|\bmanpower\b|brak.*rekrut|rezerwa.*wojsk", ("HINT_MANPOWER_TEXT",)),
    (r"\binflacj|\binflation", ("inflation-and-spending",)),
    (r"\brozejm|\btruce", ("rozejmy-czas-i-zwloka-ai",)),
)

GLOSSARY = (
    (r"renesans|renaissance", ("renaissance", "institution_events.2", "EMBRACE_INSTITUTION_COST")),
    (r"global.*hand|global trade", ("global_trade",)),
    (r"pozyczk.*mieszcz|dlug.*mieszcz|burgher.*loan|indebted.*burgher", (
        "estate_burghers_indebted_to_burghers", "MEE_Byzantine_Events.21", "BASE_INTERESTS")),
    (r"bankruct|bankrupt", (
        "BANKRUPTCY_DURATION", "bankruptcy", "BANKRUPTCY_BUILDING_DESTRUCTION_THRESHOLD",
        "BANKRUPTCY_PROVINCE_DEVASTATION_GAIN")),
    (r"nadmiern.*ekspansj|overextension", (
        "over_extension", "OVEREXTENSION_THRESHOLD", "on_overextension_pulse", "overextension.1")),
    (r"efektywnosc administr|administrative efficiency|absolutyzm|absolutism", (
        "adm:17", "adm:23", "adm:27", "absolutism", "ab_adm_efficiency")),
    (r"rekonkwist|reconquest|odzysk.*rdze", ("take_core", "cb_core")),
    (r"wasal.*aneks|aneks.*wasal|integracj|wzgl.dn.*sil.*(?:uni|wasal)|\bannex|\bintegrat", (
        "INTEGRATE_VASSAL_MIN_YEARS", "INTEGRATE_UNION_MIN_YEARS", "vassal", "personal_union", "default")),
    (r"dziedzictw.*burgund|sukcesj.*burgund|burgund.*inherit", (
        "burgundian_inheritance_start_effect", "incidents_bur_inheritance.1000",
        "incidents_bur_inheritance.1", "on_monarch_death")),
    (r"protestantyzm|reformacj|reformation", (
        "2001", "can_have_center_of_reformation_trigger", "protestant", "MAX_CHRISTIAN_RELIGIOUS_CENTERS")),
    (r"dekadenc|decadence|ottoman power struggle|walk.*wladz.*osman", (
        "tur_disaster_ottoman_power_struggle", "ottoman_decadence_mechanic", "ottoman_government")),
    (r"mozdzier|dzial.*urban|guns of urban|artyl.*urban", ("tur_guns_of_urban",)),
    (r"township|brokers.*exchange", ("townships", "brokers_exchange", "governor_general_mansion")),
    (r"hormuz|ormuz", ("hormuz", "basra", "aleppo", "constantinople")),
    (r"aleksandri|alexandria", ("alexandria", "navy_tradition")),
    (r"koalicj|coalition|agresywn.*ekspansj", (
        "AE_COALITION_THRESHOLD", "MIN_DAYS_AFTER_TRUCE_ENDS", "DIPLOMATIC_ACTION_COALITION_MIN_SCORE",
        "WARDEC_COBELLI_FOR_COALITION")),
    (r"rozejm|truce", ("TRUCE_YEARS", "SCALED_TRUCE_YEARS", "MIN_DAYS_AFTER_TRUCE_ENDS")),
    (r"jagiell|kazimierz", ("flavor_pol.18", "flavor_lit.16", "flavor_pol.20")),
    (r"lubelski|cesj.*rusi|cession.*ruthenia", (
        "pol_annexed_ruthenia_opinion_modifier", "flavor_pol.32", "pol_commonwealth")),
    (r"rzeczpospolit|commonwealth|negocjacj.*lubel", ("pol_commonwealth", "flavor_pol.32", "commonwealth_enforced")),
    (r"konfederacj.*prus|prussian confederation", (
        "prussian_confederation_disaster", "pol_prussia_confederation", "flavor_teu.1", "flavor_teu.3")),
    (r"\bformowa.*niderland|utworze.*niderland|je maintiendrai", ("NED_unification_of_low_countries", "netherlands_nation")),
    (r"\bvoc\b|ostindische compagnie", ("establish_voc", "NED_founding_the_voc", "commercial_enterprise")),
    (r"husari|hussar", ("POL_ideas", "PLC_ideas", "CREATE_HUSSARS_MIL_COST")),
    (r"promow.*kultur|akceptowan.*kultur|culture promot", (
        "CULTURE_MIN_DEVELOPMENT_TO_PROMOTE", "PS_ADD_ACCEPTED_CULTURE")),
    (r"izolacj.*japon|japon.*izolacj|shinto.*isolation", ("closed_doors_isolation",)),
    (r"szerokosc.*walk|combat width|szerok.*front", ("BASE_COMBAT_WIDTH", "mil:2", "mil:5")),
    (r"\bgaler|galley", ("GALLEY_BONUS_INLAND_SEA", "GALLEY_BONUS_COASTAL_SEA", "GALLEY_DICE_MALLUS_HIGH_SEA")),
    (r"przyslug|favors?.*(?:call|ally)|call to arms", ("CALL_TO_ARMS_COST",)),
    (r"czarn.*flag|hoist.*black flag|pirack.*republ|pirate republic", ("become_pirates_decision",)),
    (r"kastylijsk.*domow|castili.*civil war|castile.*civil war", ("castilian_civil_war",)),
    (r"angielsk.*domow|english.*civil war", ("english_civil_war",)),
    (r"dwor i kraj|court and country", (
        "court_and_country_events.100", "central_authority_asserted", "crushed_local_authority")),
    (r"manufaktur.*instytucj|instytucj.*manufaktur|manufactories.*institution", ("manufactories",)),
    (r"centrum handl|centr.*handl|centers? of trade|trade cent(?:er|re)", (
        "world_port", "world_trade_center")),
    (r"cesarsk.*elekc|elekcj.*cesarz|cesarz.*elekc|wybor.*cesarz|cesarz.*glos|imperial election",
     ("HRE_VOTE_ALLIANCE",)),
    (r"koptyjsk.*blogoslaw|coptic.*bless", ("promote_territorial_rights", "will_of_the_martyrs")),
    (r"partykular|particularist", ("particularist_rebels",)),
    (r"hegemon.*morsk|morsk.*hegemon|naval hegemon", ("naval_hegemon",)),
    (r"konflikt.*handl|trade conflict", ("cb_trade_conflict",)),
    (r"blokad.*port|blokuj.*port|blockad.*port", ("blockaded",)),
    (r"(?:zlota|zloto).*(wyczer|wyczerp)|wyczer.*(?:zlota|zloto)|gold mine deplet", (
        "GOLD_DEPLETE_CHANCE", "GOLD_MINE_DEPLETION_CHANCE")),
    (r"utworz.*wloch|utworze.*wloch|form.*wloch|italian unification|form italy", ("italian_nation",)),
)
FAMILY_CUES = (
    (r"monument|wielki.*projekt|great project|pozio[mou].{0,8}(?:iii|3)", "great_projects"),
    (r"katastrof|disaster|wojn.*domow|civil war", "disasters"),
    (r"najemn|mercenar|guard", "mercenary_companies"),
    (r"osobist.*bostw|personal deit", "personal_deities"),
    (r"\bpolityk|polic|wspoln.*ide", "policies"),
    (r"zakon.*rycer|holy order", "holy_orders"),
    (r"reform[aey].*rzad|government reform|ustroj", "government_reforms"),
    (r"kto.*kontrol|kto.*posiad|wlasciciel.*prow|w 1444|1444 r", "history"),
    (r"kupiec|kupca|wezel|wezla|trade node|merchant", "tradenodes"),
    (r"osiagnieci|achievement", "common"),
    (r"przywodca.*cech|cech.*(?:monarch|wladc)|(?:monarch|wladc).*cech|ruler trait", "ruler_personalities"),
    (r"towar|produkuj|produkcj|trading in|trade good", "tradegoods"),
    (r"budynek|budynk|manufakt.*(?:staw|budow)|building", "buildings"),
    (r"blogoslawienst|blessing", "church_aspects"),
    (r"instytucj|institution", "institutions"),
    (r"formuj|formowanie|utworz|utworze|unification", "decisions"),
    (r"okna|interfejs|podpowiedz|gdzie.*sprawdzi|tooltip", "game_tooltips"),
)
STOP_WORDS = frozenset(
    "a albo and bez by czy co do dla dwie for go he how i ile it ja jak jaka jaki jakie "
    "jakiego której który które ktore kiedy lecza lub me mi moje moim na nad nie o od one or oraz "
    "po pod przez przy sie sa sam tak tego to the then ten tych u w we what when which with za ze z".split()
)
IDENTIFIER = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:[_.][A-Za-z0-9]+)+\b")
TITLE_WORDS = re.compile(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{3,}(?:[- ][A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,})*\b")
TITLE_STOP = frozenset("bez czy dlc gram jakie kiedy mam moje skad swoj twoj po przy trakcie trwa wybralem zaczynam".split())
MORPH_END = re.compile(r"(?:owego|owej|owych|ami|ach|em|om|ie|[aeyęąu])$")


def open_index(path):
    return sqlite3.connect(Path(path).expanduser().resolve().as_uri() + "?mode=ro", uri=True)


def normalize(value):
    plain = unicodedata.normalize("NFKD", value.casefold().replace("ł", "l"))
    return "".join(char for char in plain if not unicodedata.combining(char))


def lexical_query(question):
    tokens = re.findall(r"[\w]+", question.casefold())
    distinctive = [word for word in tokens if len(word) > 2 and normalize(word) not in STOP_WORDS]
    return " OR ".join(f'"{token}"*' for token in dict.fromkeys(distinctive[:24]))


def phrase_query(phrases):
    terms = [" ".join(re.findall(r"[\w]+", phrase)) for phrase in phrases]
    return " OR ".join(f'"{term}"' for term in dict.fromkeys(terms) if term)


def entity_query(question):
    words = []
    for match in TITLE_WORDS.finditer(question):
        term = normalize(match.group())
        if term in TITLE_STOP:
            continue
        if len(term) >= 5 and " " not in term:
            stem = MORPH_END.sub("", term)
            if len(stem) >= 4 and stem != term:
                words.append(f'"{stem}"*')
                if "j" in stem:
                    words.append(f'"{stem.replace("j", "y")}"*')
        words.append(f'"{term.replace("-", " ")}"')
    return "{title symbol} : (" + " OR ".join(dict.fromkeys(words)) + ")" if words else ""


def explicit_symbols(question):
    hints = []
    plain = normalize(question)
    for pattern, symbols in GLOSSARY:
        match = re.search(pattern, plain)
        if match:
            hints.append((match.start(), symbols))
    named = list(IDENTIFIER.findall(question))
    known = [symbol for _, symbols in sorted(hints, key=lambda item: item[0]) for symbol in symbols]
    return list(dict.fromkeys(named + known))


def exact(db, symbol):
    return db.execute("""
        SELECT record.json FROM record
        WHERE record.symbol = ? OR record.id IN (SELECT record_id FROM alias WHERE symbol = ?)
        ORDER BY record.id LIMIT 32
    """, (symbol, symbol)).fetchall()


def importance(record, question):
    text = record["text"]
    score = int(len(text.strip()) > len(record["symbol"]) + 6)
    tokens = set(re.findall(r"[\w]+", normalize(question))) - STOP_WORDS
    haystack = normalize(record["title"] + " " + record.get("section", "") + " " + text)
    score += sum(term in haystack for term in tokens if len(term) > 3)
    preferences = preferred_sections(question)
    score += sum(12 if key == "tier_3" else 7 for key in preferences if re.search(rf"\b{key}\s*=", text))
    return score


def preferred_sections(question):
    question = normalize(question)
    result = []
    if re.search(r"pozio[mou].{0,6}(?:iii|3)\b|najwyzs|tier 3", question):
        result.append("tier_3")
    if re.search(r"zakoncz|sie konczy|can end|zatrzym", question):
        result.append("can_end")
    if re.search(r"(?:(?:zmien|musz).{0,24}religi|religio.*(?:wymag|zmien))", question):
        result.append("can_use_modifiers_trigger")
    return result


def by_id(db, chunk_id):
    result = db.execute("SELECT json FROM record WHERE chunk_id = ?", (chunk_id,)).fetchone()
    return json.loads(result[0]) if result else None


def related(db, record, limit=6):
    identifiers = list(dict.fromkeys(IDENTIFIER.findall(record["text"] + " " + record.get("parent_conditions", ""))))
    identifiers = [key for key in identifiers if key != record["symbol"]][:160]
    links = []
    if not identifiers:
        return links
    placeholders = ",".join("?" for _ in identifiers)
    rows = db.execute(f"SELECT symbol,json FROM record WHERE symbol IN ({placeholders}) ORDER BY id", identifiers)
    seen = set()
    for name, payload in rows:
        if name in seen:
            continue
        ref = json.loads(payload)
        if ref["document_id"] == record["document_id"] or len(ref["text"]) < len(name) + 6:
            continue
        seen.add(name)
        links.append({"chunk_id": ref["chunk_id"], "symbol": ref["symbol"], "source_path": ref["source_path"]})
        if len(links) == limit:
            break
    return links


def for_context(db, record):
    result = dict(record)
    result["related"] = related(db, record)
    if "notes_path" not in record:
        siblings = db.execute(
            "SELECT json FROM record WHERE document_id = ? AND chunk_id != ? ORDER BY id LIMIT 8",
            (record["document_id"], record["chunk_id"]),
        )
        result["other_sections"] = [
            {key: item[key] for key in ("chunk_id", "section", "lines")}
            for item in (json.loads(row[0]) for row in siblings)
        ]
    conditions = record.get("parent_conditions")
    if conditions:
        result["text"] = "Warunki nadrzędne:\n" + conditions + "\n\nFragment:\n" + record["text"]
    checked = record.get("game_refs")
    if checked and record["source_type"] == "youtube":
        evidence = "\n".join(f"{item['path']} / {item['locator']}: {item['reason']}" for item in checked)
        result["text"] += "\nSprawdzono w danych " + record["game_data_version"] + ":\n" + evidence
    values = annotations(record)
    if values:
        result["text"] = ("Odczyt wartości. Zakres wynika z bloku źródłowego:\n- " + "\n- ".join(values)
                          + "\n\n" + result["text"])
    if record["source_type"] == "game_history":
        tags = list(dict.fromkeys(COUNTRY_TAG.findall(record["text"])))[:4]
        tag_sources = []
        for tag in tags:
            row = db.execute("SELECT json FROM record WHERE symbol = ? AND family = 'country_tags' LIMIT 1",
                             (tag,)).fetchone()
            if row:
                ref = json.loads(row[0])
                result["text"] += f"\nOdczyt znacznika kraju w pliku {ref['source_path']}: {ref['text']}"
                tag_sources.append({"path": ref["source_path"], "line": ref["lines"][0], "symbol": tag})
        if tag_sources:
            result["game_refs"] = tag_sources
    return result


def read_record(db_path, chunk_id):
    if not isinstance(chunk_id, str) or not chunk_id:
        raise ValueError("Wybierz źródło zwrócone przez wyszukiwanie.")
    with closing(open_index(db_path)) as db:
        record = by_id(db, chunk_id)
        return for_context(db, record) if record else None


def find_symbol(db_path, symbol, family=None):
    """Find exact symbol records, optionally limited to one game-data family."""
    if not re.fullmatch(r"[\w.:-]{1,120}", symbol):
        raise ValueError("Podaj identyfikator reguły widoczny w wynikach wyszukiwania.")
    with closing(open_index(db_path)) as db:
        matches = [json.loads(item[0]) for item in exact(db, symbol)]
        return [for_context(db, record) for record in matches
                if family is None or record["family"] == family][:12]


def trace_flag(db_path, flag):
    """List literal flag references, distinguished by operation and owning scope."""
    if not re.fullmatch(r"[a-zA-Z0-9_]{1,120}", flag):
        raise ValueError("Podaj dokładną nazwę flagi ze skryptu gry.")
    actions = {"set": "ustawia", "has": "sprawdza", "clr": "usuwa", "had": "sprawdza historię"}
    pattern = re.compile(
        rf"\b(set|has|clr|had)_(country|global|province|ruler|heir|consort)_flag"
        rf"\s*=\s*(?:\{{\s*flag\s*=\s*)?\"?{re.escape(flag)}\"?(?![\w.])"
    )
    references = {}
    with closing(open_index(db_path)) as db:
        rows = db.execute("""
            SELECT record.json FROM lookup JOIN record ON lookup.rowid = record.id
            WHERE lookup MATCH ? AND record.family NOT IN ('strategy_notes','checked_rules')
            ORDER BY record.id LIMIT 500
        """, (f'body : "{flag}"',))
        for row in rows:
            record = json.loads(row[0])
            # Recognize authored commands on non-comment lines.
            text = re.sub(r"(?m)^[ \t]*#[^\n]*", "", record["text"])
            for match in pattern.finditer(text):
                line = record["lines"][0] + text.count("\n", 0, match.start())
                key = record["source_path"], line, match[1]
                references[key] = {
                    "operation": actions[match[1]], "scope": match[2], "flag": flag,
                    "source_path": record["source_path"], "line": line, "chunk_id": record["chunk_id"],
                    "entity": record["symbol"], "section": record.get("section") or None,
                    "game_version": record["game_version"],
                }
    return list(references.values())


def dependencies(db, record, question):
    """Follow named links and check which technology unlocks a selected definition."""
    family = record["family"]
    text = record["text"]
    for symbol in dict.fromkeys(re.findall(
        r"\b(?:war_goal|copy_from|id)\s*=\s*([a-zA-Z_][\w.]+)", text
    )):
        if symbol == record["symbol"]:
            continue
        candidates = (json.loads(row[0]) for row in exact(db, symbol))
        match = next((item for item in candidates if "notes_path" not in item and item["text"].strip()), None)
        if match:
            yield match

    if family not in {"buildings", "units"} or not re.search(r"technolog|tech|odblokow", normalize(question)):
        return
    symbol = record["symbol"]
    if not re.fullmatch(r"\w+", symbol):
        return
    rows = db.execute("""
        SELECT record.json FROM lookup JOIN record ON lookup.rowid = record.id
        WHERE lookup MATCH ? AND record.family = 'technologies' LIMIT 30
    """, (f'body : "{symbol}"',))
    for row in rows:
        technology = json.loads(row[0])
        if re.search(rf"\b(?:{symbol}\s*=\s*yes|enable\s*=\s*{symbol})\b", technology["text"]):
            yield technology


def threshold_context(db, question):
    """Select the exact intervals in small game-defined tier tables."""
    normalized = re.sub(r"^\s*eu4 [\d.]+ bez modow[. ]*", "", normalize(question))
    if re.search(r"ziem.{0,15}koron|crown land|crownland", normalized):
        family = "estate_crown_land"
        examples = re.findall(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*%", normalized)
    elif re.search(r"obronc.{0,5} wiar|defender of the faith", normalized):
        family = "defender_of_faith"
        examples = re.findall(r"(?<![\d.])\b(\d{1,3})\b", normalized)
    else:
        return []
    values = list(dict.fromkeys(float(item.replace(",", ".")) for item in examples))[:4]
    if not values:
        return []
    results = []
    rows = db.execute("SELECT json FROM record WHERE family = ? ORDER BY id", (family,))
    for row in rows:
        record = json.loads(row[0])
        lower = re.search(r"\brange_from\s*=\s*(-?\d+(?:\.\d+)?)", record["text"])
        upper = re.search(r"\brange_to\s*=\s*(-?\d+(?:\.\d+)?)", record["text"])
        if not lower and not upper:
            continue
        start = float(lower[1]) if lower else 0.0
        finish = float(upper[1]) if upper else float("inf")
        applies = [value for value in values if start <= value < finish]
        if applies:
            result = dict(record)
            result["tier_match"] = True
            result["text"] = (
                f"Dane {', '.join(f'{value:g}' for value in applies)} należą do tego przedziału "
                f"(od {start:g} włącznie do {finish:g} wyłącznie).\n\n" + record["text"]
            )
            results.append(result)
    return results


def context(db_path, question, limit=6, extra_terms=()):
    question = question.strip()
    if not question or len(question) > 1200:
        raise ValueError("Wpisz pytanie o EU4 o długości do 1200 znaków.")
    if not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("Liczba źródeł musi wynosić od 1 do 20.")
    candidates = []
    picked = set()
    normalized = normalize(question)
    asks_for_both = bool(re.search(r"warunk|wymag|trigger|requirements?", normalized)
                         and re.search(r"nagrod|skut|efekt|effect|reward", normalized))
    preferences = preferred_sections(question)
    families = [family for pattern, family in FAMILY_CUES if re.search(pattern, normalized)]

    def choose(record):
        doc = record["document_id"]
        if doc not in picked and len(candidates) < limit:
            candidates.append(record)
            picked.add(doc)

    def choose_complement(chunks, first):
        missing = [key for key in preferences if not re.search(rf"\b{key}\s*=", first["text"])]
        if asks_for_both and "effect =" not in first["text"]:
            missing.append("effect")
        if not missing or len(candidates) >= limit:
            return
        supplement = next(
            (item for item in chunks if item["document_id"] == first["document_id"]
             and item["chunk_id"] != first["chunk_id"]
             and any(re.search(rf"\b{key}\s*=", item["text"]) for key in missing)), None,
        )
        if supplement:
            candidates.append(supplement)

    with closing(open_index(db_path)) as db:
        primary_symbols = list(dict.fromkeys(
            symbol for pattern, group in MECHANIC_LOOKUPS if re.search(pattern, normalized)
            for symbol in group
        ))
        for symbol in primary_symbols[:min(3, limit)]:
            matches = [json.loads(row[0]) for row in exact(db, symbol)]
            exact_entry = next((item for item in matches if item["symbol"] == symbol), None)
            if exact_entry:
                choose({**exact_entry, "direct_mechanic": True})
        for entry in threshold_context(db, question)[:limit]:
            choose(entry)
        symbols = explicit_symbols(question)
        inferred = [normalize(term).replace(" ", "_") for term in extra_terms]
        named = [symbol for symbol in inferred if len(symbol) >= 4][:5]
        # English Gamedata IDs often use the singular and drop a possessive apostrophe.
        named.extend(token for symbol in tuple(named) for token in symbol.split("_") if len(token) >= 5)
        named = list(dict.fromkeys(re.sub(r"['’]s(?=_|$)", "", name) for name in named))
        if "mercenary_companies" in families:
            named = [f"merc_{symbol}" for symbol in named] + named
        if "ruler_personalities" in families:
            named = [f"{symbol}_personality" for symbol in named] + named
        symbols = list(dict.fromkeys(symbols + named))
        for symbol in symbols:
            if len(candidates) >= max(1, limit - 2):
                break
            matches = [json.loads(row[0]) for row in exact(db, symbol)]
            if matches:
                matches.sort(key=lambda record: (
                    record["source_type"] == "checked_game_rule", importance(record, question),
                    record["family"] in families,
                ), reverse=True)
                first = next((record for record in matches if record["document_id"] not in picked), None)
                if first:
                    choose(first)
                    choose_complement(matches, first)
            if len(candidates) >= max(1, limit - 2):
                break
        for parent in candidates[:5]:
            for dependency in dependencies(db, parent, question):
                choose({**dependency, "linked_from": parent["symbol"]})
                if len(candidates) >= max(1, limit - 1):
                    break

        def find(query, remaining, family=None):
            if not query or len(candidates) >= remaining:
                return
            rows = db.execute("""
                SELECT record.json FROM lookup JOIN record ON lookup.rowid = record.id
                WHERE lookup MATCH ? AND (? IS NULL OR record.family = ?)
                ORDER BY bm25(lookup, 8, 5, 0.5, 1) LIMIT ?
            """, (query, family, family, limit * 16))
            for row in rows:
                record = json.loads(row[0])
                if record["document_id"] in picked:
                    continue
                related_chunks = db.execute("SELECT json FROM record WHERE document_id = ? ORDER BY id LIMIT 16",
                                            (record["document_id"],))
                sections = [json.loads(item[0]) for item in related_chunks]
                if len(sections) > 1:
                    record = max(sections, key=lambda item: importance(item, question))
                choose(record)
                choose_complement(sections, record)
                if len(candidates) >= remaining:
                    break
        if len(candidates) < limit:
            topic = entity_query(question) or phrase_query(extra_terms) or lexical_query(question)
            for family in families[:2]:
                find(topic, min(len(candidates) + 1, max(1, limit - 2)), family)
        if len(candidates) < limit:
            embed = Path(db_path).resolve().parent / "semantic/manifest.json"
            if embed.is_file():
                try:
                    from semantic import neighbors
                except ImportError:
                    neighbors = None
                if neighbors:
                    expanded = neighbors(db_path, question, extra_terms)
                    ranked = []
                    for row_id, rating in expanded:
                        row = db.execute("SELECT json FROM record WHERE id = ?", (row_id,)).fetchone()
                        if row:
                            record = json.loads(row[0])
                            ranked.append((rating + (0.025 if record["family"] in families else 0), record))
                    semantic_limit = min(limit, len(candidates) + max(1, limit // 3))
                    for _, record in sorted(ranked, key=lambda item: item[0], reverse=True):
                        choose(record)
                        if len(candidates) >= semantic_limit:
                            break
        find(entity_query(question), min(len(candidates) + 2, limit))
        find(phrase_query(extra_terms), max(1, limit - 1))
        lexical_limit = min(limit, len(candidates) + 2) if len(candidates) >= 2 and symbols else limit
        find(lexical_query(question), lexical_limit)
        return [for_context(db, record) for record in candidates]


def main():
    parser = argparse.ArgumentParser(description="Znajdź lokalne źródła do pytania o EU4.")
    parser.add_argument("question")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--limit", default=6, type=int)
    args = parser.parse_args()
    try:
        result = context(args.db, args.question, args.limit)
    except (sqlite3.Error, OSError, ValueError) as error:
        parser.exit(2, f"Nie można wyszukać źródeł. {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
