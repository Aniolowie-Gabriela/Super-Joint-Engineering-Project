"""Build an offline EU4 retrieval index from a local, unmodified installation."""

import argparse
import bisect
import collections
import hashlib
import json
import re
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path


MAX_CHARS = 3600
ROOTS = ("common", "decisions", "events", "missions", "history", "map", "customizable_localization")
MAP_FILES = {
    "adjacencies.csv", "area.txt", "climate.txt", "continent.txt", "default.map", "definition.csv",
    "provincegroup.txt", "region.txt", "seasons.txt", "superregion.txt", "terrain.txt", "trade_winds.txt",
}
COSMETIC = {
    "ancestor_personalities", "country_colors", "custom_country_colors", "custom_gui", "dynasty_colors",
    "graphicalculturetype.txt", "insults", "region_colors", "units_display",
}
PARENT_SCOPES = {"potential", "potential_on_load", "allow", "trigger", "required_missions", "available"}
LANGUAGE_LINE = re.compile(r'^\s*([^\s:]+):\d*\s+"(.*)"(?:\s*#.*)?\s*$')
TOKEN = re.compile(
    r'(?P<comment>\#[^\n]*)|(?P<quote>"(?:[^"\\]|\\[\s\S])*")|'
    r'(?P<op>\?=|<=|>=|!=|==|[=<>])|(?P<brace>[{}])|(?P<word>[^\s#"<>{}=?!]+|[?!])'
)
LUA_TOKEN = re.compile(r"--\[(?P<eq>=*)\[[\s\S]*?\](?P=eq)\]|--[^\n]*|"
                       r'"(?:[^"\\]|\\[\s\S])*"|'
                       r"'(?:[^'\\]|\\[\s\S])*'|[{}]")
LUA_ASSIGNMENT = re.compile(r"(?m)^\s*(?P<key>[A-Za-z_][\w.]*)[ \t]*=[ \t]*(?P<value>.+)$")
UI_MECHANIC = re.compile(
    r"(?:SIEGE|REBEL|GOLD_DEPLETE|GOLDDEPLETED|TRADE|BLOCKAD|MANPOWER|FORCELIMIT|"
    r"FAVORS|WAR_TAX|WAR_EXHAUST|AUTONOMY|INSTITUTION|MOTHBALL|FORT|LOAN|BANKRUPT|"
    r"AGGRESSIVE_EXPANSION|COALITION|REVOLT|HEGEMON|NAVAL_ENGAGEMENT|CROWNLAND|DEFENDER_OF_FAITH)"
)


def decode(path):
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        content = raw.decode("utf-16")
        encoding = "utf-16"
    else:
        try:
            content = raw.decode("utf-8-sig")
            encoding = "utf-8"
        except UnicodeDecodeError:
            content = raw.decode("cp1252", errors="replace")
            encoding = "cp1252"
    return content.replace("\r\n", "\n").replace("\r", "\n"), encoding, hashlib.sha256(raw).hexdigest()


@dataclass
class Block:
    key: str
    start: int
    opening: int
    end: int
    children: list = field(default_factory=list)


def blocks(text):
    root = Block("", 0, 0, len(text))
    stack = [root]
    previous = collections.deque(maxlen=3)
    for token in TOKEN.finditer(text):
        kind = token.lastgroup
        if kind == "comment":
            continue
        value = token.group()
        if value == "{":
            header = list(previous)
            left = -2 if len(header) >= 2 and header[-1].lastgroup == "op" else -3
            if len(header) >= -left and header[left + 1].lastgroup == "op":
                key = header[left].group().strip('"')
                start = header[left].start()
            else:
                key, start = "", token.start()
            node = Block(key, start, token.end(), len(text))
            stack[-1].children.append(node)
            stack.append(node)
        elif value == "}":
            if len(stack) == 1:
                raise ValueError("unmatched closing bracket")
            stack.pop().end = token.end()
        previous.append(token)
    if len(stack) != 1:
        raise ValueError("unclosed block")
    return root.children


def between(text, start, end, children):
    """Text directly in this scope, excluding child definitions."""
    parts = []
    for child in children:
        parts.append(text[start:child.start])
        start = child.end
    parts.append(text[start:end])
    return "\n".join(parts)


def scalar(text, block, key):
    direct = between(text, block.opening, block.end - 1, block.children)
    match = re.search(rf"(?m)^\s*{key}\s*=\s*([^\s#}}]+)", direct)
    return match[1].strip('"') if match else None


def scope_excerpt(text, block, further=()):
    keys = PARENT_SCOPES | set(further)
    snippets = [text[child.start:child.end].strip() for child in block.children if child.key in keys]
    return "\n".join(snippets)[:2200]


def bounded_parts(text, start, end, children):
    """Partition a large block at direct child boundaries, or lines inside a huge child."""
    if end - start <= MAX_CHARS:
        yield start, end, ""
        return
    cursor = start
    spans = []
    for child in children:
        if child.start > cursor:
            spans.append((cursor, child.start, "", []))
        spans.append((child.start, child.end, child.key, child.children))
        cursor = child.end
    if cursor < end:
        spans.append((cursor, end, "", []))
    if len(spans) > 1:
        group_start, group_end, group_key = spans[0][:3]
        for part_start, part_end, part_key, _ in spans[1:]:
            if part_end - group_start > MAX_CHARS:
                yield from split_part(text, group_start, group_end, group_key, spans)
                group_start, group_key = part_start, part_key
            group_end = part_end
        yield from split_part(text, group_start, group_end, group_key, spans)
        return
    while end - start > MAX_CHARS:
        cut = text.rfind("\n", start + MAX_CHARS // 2, start + MAX_CHARS + 1)
        cut = cut + 1 if cut >= 0 else start + MAX_CHARS
        yield start, cut, ""
        start = cut
    if start < end:
        yield start, end, ""


def split_part(text, start, end, name, spans):
    if end - start <= MAX_CHARS:
        yield start, end, name
        return
    children = next((children for left, right, _, children in spans if (left, right) == (start, end)), [])
    for left, right, subkey in bounded_parts(text, start, end, children):
        names = "/".join(part for part in (name, subkey) if part)
        yield left, right, names


def definitions(text, family, stem, roots):
    if family == "events":
        for root in roots:
            name = scalar(text, root, "id")
            if name:
                yield root, name, root.key, "", scalar(text, root, "title")
        return
    if family in {"missions", "decisions"}:
        for root in roots:
            prefix = scope_excerpt(text, root, ("has_country_shield",))
            if shield := scalar(text, root, "has_country_shield"):
                prefix = f"has_country_shield = {shield}\n{prefix}".strip()
            for node in root.children:
                if node.key and node.key not in PARENT_SCOPES and node.key != "has_country_shield":
                    yield node, node.key, root.key, prefix, None
        return
    if family == "technologies":
        level = 0
        for root in roots:
            name = f"{stem}:{level}" if root.key == "technology" else f"{stem}:{root.key}"
            yield root, name, "technology", "", None
            level += root.key == "technology"
        return
    if family in {"religions", "cultures", "ages"}:
        excluded = {"flag_emblem_index_range", "male_names", "female_names", "dynasty_names"}
        for root in roots:
            if family == "ages":
                # The main record keeps years, eligibility and ability/objective definitions.
                yield root, root.key, "", "", None
                for section in root.children:
                    if section.key in {"abilities", "objectives"}:
                        for item in section.children:
                            yield item, item.key, f"{root.key}/{section.key}", scope_excerpt(text, root), None
                continue
            group = scope_excerpt(text, root)
            for node in root.children:
                if node.key and node.key not in excluded:
                    yield node, node.key, root.key, group, None
        return
    if family == "units":
        # Each file is a unit definition, even if its only block is a trigger.
        return
    for root in roots:
        if root.key:
            name = scalar(text, root, "key") if family == "estate_crown_land" else None
            yield root, name or root.key, "", "", scalar(text, root, "localization")


def lua_definitions(text, relative):
    if relative != "common/defines.lua":
        for match in LUA_ASSIGNMENT.finditer(text):
            key = match["key"]
            if key.startswith("NDefines."):
                yield key, match.start("key"), match.end(), relative.removeprefix("common/defines/").removesuffix(".lua")
        return
    tokens = list(LUA_TOKEN.finditer(text))
    braces = {token.start(): token.group() for token in tokens if token.group() in {"{", "}"}}
    group = ""
    depth = 0
    offset = 0
    pending = None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        match = re.match(r"([\w.]+)\s*=", stripped)
        if match and depth == 1:
            group = match[1]
        if match and depth == 2:
            pending = (f"NDefines.{group}.{match[1]}", offset + len(line) - len(stripped))
        for index in range(offset, offset + len(line)):
            if braces.get(index) == "{":
                depth += 1
            elif braces.get(index) == "}":
                depth -= 1
        offset += len(line)
        if pending and depth == 2:
            yield pending[0], pending[1], offset, group
            pending = None


def sources(game):
    for root in ROOTS:
        for path in sorted((game / root).rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(game)
            if any(part in COSMETIC for part in relative.parts):
                continue
            if root == "map" and path.name not in MAP_FILES:
                continue
            if path.suffix in {".lua", ".txt", ".csv", ".map"}:
                yield path, relative.as_posix()
    filename = game / "patchnotes/1.37 Patchnotes.txt"
    if filename.is_file():
        yield filename, filename.relative_to(game).as_posix()


def localization(game):
    labels = {}
    count = 0
    for path in sorted((game / "localisation").rglob("*_l_english.yml")):
        count += 1
        relative = path.relative_to(game).as_posix()
        for line, text in enumerate(decode(path)[0].splitlines(), start=1):
            match = LANGUAGE_LINE.match(text)
            if match:
                labels[match[1]] = (match[2].replace(r"\n", " "), relative, line)
    return labels, count


def file_records(path, relative, version, labels):
    text, encoding, sha256 = decode(path)
    category = relative.split("/")
    family = category[1] if category[0] == "common" and len(category) > 2 else category[0]
    newline_offsets = [-1, *[m.start() for m in re.finditer("\n", text)]]
    if not text.strip():
        return
    if path.suffix == ".lua":
        for key, start, end, scope in lua_definitions(text, relative):
            yield make_record(text, start, end, relative, family, key.split(".")[-1], scope, "",
                              "", version, labels, None, encoding, sha256, newline_offsets, "engine_parameter")
        return
    kind = "game_script"
    if category[0] in {"history", "map", "patchnotes"}:
        kind = {"history": "game_history", "map": "game_map", "patchnotes": "patch_notes"}[category[0]]
    parsed = []
    if path.suffix in {".txt", ".map"} and kind != "patch_notes":
        roots = blocks(text)
        if kind != "game_history":
            parsed = list(definitions(text, family, path.stem, roots))
    if family == "country_tags":
        for match in re.finditer(r'(?m)^\s*([A-Z0-9]{3})\s*=\s*"[^"\n]+"', text):
            yield make_record(text, match.start(1), match.end(), relative, family, match[1], "", "",
                              "", version, labels, None, encoding, sha256, newline_offsets, kind)
        return
    if not parsed:
        roots = roots if path.suffix in {".txt", ".map"} and kind != "patch_notes" else []
        parsed = [(Block(path.stem, 0, 0, len(text), roots), path.stem, "", "", None)]
    for block, symbol, scope, inherited, title_key in parsed:
        parent_rules = ""
        if block.end - block.start > MAX_CHARS:
            parent_rules = scope_excerpt(text, block)
        context = "\n".join(part for part in (inherited, parent_rules) if part)
        for start, end, section in bounded_parts(text, block.start, block.end, block.children):
            if text[start:end].strip():
                yield make_record(text, start, end, relative, family, symbol, scope, section, context,
                                  version, labels, title_key, encoding, sha256, newline_offsets, kind)


def make_record(text, start, end, relative, family, symbol, scope, section, context,
                version, labels, title_key, encoding, sha256, newline_offsets, kind):
    excerpt = text[start:end]
    trim = len(excerpt) - len(excerpt.lstrip())
    start_line = bisect.bisect_left(newline_offsets, start + trim)
    end_line = bisect.bisect_left(newline_offsets, end - 1)
    label = next((labels[key] for key in (title_key, symbol, symbol.upper(), symbol + "_title") if key in labels), None)
    title = label[0] if label and label[0].strip() else symbol
    record = {
        "chunk_id": f"game:{relative}:{symbol}:{start}",
        "document_id": f"game:{relative}:{symbol}",
        "title": title,
        "symbol": symbol,
        "scope": scope,
        "section": section,
        "family": family,
        "text": excerpt.strip(),
        "parent_conditions": context,
        "source_path": relative,
        "lines": [start_line, end_line],
        "source_type": kind,
        "game_version": version,
        "source_sha256": sha256,
        "encoding": encoding,
    }
    if label:
        record["label_ref"] = [label[1], label[2]]
    return record


def note_records(path):
    if path is None:
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        note = json.loads(line)
        note["family"] = "strategy_notes"
        note["symbol"] = note["source_id"]
        note["source_path"] = "video-notes/" + note["notes_path"]
        note["lines"] = None
        note["text"] = note["text"] + "\nWarunki i ograniczenia: " + note["caveat"]
        yield note


def rule_records(path, game, version):
    if path is None or not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["game_version"] != version:
        return
    for rule in data["rules"]:
        refs = []
        for ref in rule["refs"]:
            source = Path(ref["path"])
            if source.is_absolute() or ".." in source.parts:
                raise ValueError(f"Nieprawidłowa ścieżka źródła dla {rule['id']}.")
            if game is None:
                refs.append(ref)
                continue
            text, _, _ = decode(game / source)
            marker = re.escape(ref["symbol"])
            found = re.search(
                rf"(?m)^[ \t]*(?:{marker}[ \t]*[=:]|id[ \t]*=[ \t]*{marker}(?=[ \t#}}]|$))", text
            )
            if found is None:
                found = re.search(marker, text)
            if found:
                line = text.count("\n", 0, found.start()) + 1
            else:
                generated = file_records(game / source, source.as_posix(), version, {})
                line = next((item["lines"][0] for item in generated if item["symbol"] == ref["symbol"]), None)
            if line is None:
                raise ValueError(f"Brak symbolu {ref['symbol']} w {ref['path']}.")
            refs.append({**ref, "line": line})
        if not refs or not rule["symbols"]:
            raise ValueError(f"Uzupełnij źródła i symbole w {rule['id']}.")
        patterns = rule.get("patterns", [])
        for pattern in patterns:
            re.compile(pattern)
        chunk_id = f"rule:{rule['id']}"
        yield {
            "chunk_id": chunk_id,
            "document_id": chunk_id,
            "title": rule["title"],
            "symbol": rule["id"],
            "aliases": rule["symbols"],
            **({"question_patterns": patterns} if patterns else {}),
            "scope": "",
            "section": "",
            "family": "checked_rules",
            "text": rule["text"],
            "source_path": refs[0]["path"],
            "lines": [refs[0]["line"]] * 2 if game is not None else None,
            "source_type": "checked_game_rule",
            "game_version": version,
            "game_refs": refs,
        }


def strategy_records(path):
    if path is None or not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    for note in payload["notes"]:
        links = [payload["sources"][key] for key in note["sources"]]
        text = "\n".join([note["when"], *note["steps"], note["reason"], note["limitations"]])
        key = f"strategy:{note['id']}"
        yield {
            "chunk_id": key, "document_id": key, "title": note["title"], "symbol": note["id"],
            "scope": note["topic"], "section": "", "family": "strategy_notes",
            "text": text, "tags": [note["topic"]], "source_path": path.name, "lines": None,
            "source_type": "curated_strategy", "game_version": note["game_version"], "sources": links,
            "source_url": links[0].get("revision_url") or links[0]["url"],
        }


def wiki_records(path, version):
    if path is None:
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if "pageid" not in item or not item.get("source_url", "").startswith("https://eu4.paradoxwikis.com/"):
                continue
            source = item["source_url"]
            body = item["text"]
            for start, end, _ in bounded_parts(body, 0, len(body), []):
                yield {
                    "chunk_id": f"wiki:{item['chunk_id']}:{start}",
                    "document_id": f"wiki:{item['chunk_id']}",
                    "title": item["title"], "symbol": item["title"], "scope": "",
                    "section": item.get("heading") or "", "family": "wiki",
                    "text": "Artykuł wiki ma sekcje z różnymi wersjami. Sprawdź wartości w plikach gry.\n"
                            + body[start:end].strip(),
                    "source_path": source, "source_url": source, "lines": None,
                    "source_type": "wiki", "game_version": version, "reported_game_version": None,
                    "revision_id": item.get("revid"), "license": item.get("license"),
                }


def tooltip_records(labels, version):
    for symbol, (label, path, line) in labels.items():
        if not re.fullmatch(r"[A-Z0-9_]+", symbol) or not 45 <= len(label) <= 650:
            continue
        if not UI_MECHANIC.search(symbol):
            continue
        clean = re.sub(r"§[A-Za-z!]", "", label)
        key = f"tooltip:{symbol}"
        yield {
            "chunk_id": key, "document_id": key, "title": symbol.replace("_", " ").title(),
            "symbol": symbol, "scope": "english_ui", "section": "", "family": "game_tooltips",
            "text": clean + ("\nPola oznaczone znakami $ uzupełnia gra w bieżącym zapisie." if "$" in clean else ""),
            "source_path": path, "lines": [line, line], "source_type": "game_tooltip",
            "game_version": version,
        }


def schema(db):
    db.executescript("""
        CREATE TABLE record (
            id INTEGER PRIMARY KEY, chunk_id TEXT NOT NULL UNIQUE,
            symbol TEXT NOT NULL COLLATE NOCASE, document_id TEXT NOT NULL,
            family TEXT NOT NULL, json TEXT NOT NULL
        );
        CREATE INDEX record_symbol ON record(symbol);
        CREATE INDEX record_document ON record(document_id);
        CREATE INDEX record_family ON record(family);
        CREATE TABLE alias (symbol TEXT NOT NULL COLLATE NOCASE, record_id INTEGER NOT NULL,
                            PRIMARY KEY(symbol, record_id));
        CREATE TABLE guide_pattern (pattern TEXT NOT NULL, record_id INTEGER NOT NULL,
                                    PRIMARY KEY(record_id, pattern));
        CREATE VIRTUAL TABLE lookup USING fts5(
            title, symbol, location, body, tokenize='unicode61 remove_diacritics 2'
        );
    """)


def indexing_row(record):
    return (
        record["title"],
        record["symbol"] + " " + record["symbol"].replace("_", " "),
        record["family"].replace("_", " ") + " " + record["source_path"].replace("/", " "),
        record["text"] + "\n" + record.get("parent_conditions", "") + "\n" + " ".join(record.get("tags", [])),
    )


def insert(db, handle, record):
    payload = json.dumps(record, ensure_ascii=False)
    row = db.execute(
        "INSERT INTO record(chunk_id, symbol, document_id, family, json) VALUES (?, ?, ?, ?, ?)",
        (record["chunk_id"], record["symbol"], record["document_id"], record["family"], payload),
    )
    db.execute("INSERT INTO lookup(rowid, title, symbol, location, body) VALUES (?, ?, ?, ?, ?)",
               (row.lastrowid, *indexing_row(record)))
    db.executemany("INSERT OR IGNORE INTO alias VALUES (?, ?)",
                   ((symbol, row.lastrowid) for symbol in record.get("aliases", ())))
    for pattern in record.get("question_patterns", ()):
        db.execute("INSERT INTO guide_pattern VALUES (?, ?)", (pattern, row.lastrowid))
    handle.write(payload + "\n")


def fact_records(game, version):
    if game is not None:
        from game_facts import game_facts
        yield from game_facts(game, version)
        return
    bundle = Path(__file__).resolve().parents[1] / "rag/chunks.jsonl"
    with bundle.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if item["source_type"] == "game_fact" and item["game_version"] == version:
                yield item


def build(game, output, notes, rules=None, strategies=None, wiki=None, facts_game=None):
    if game is None:
        if rules is None or not rules.is_file():
            raise ValueError("Brakuje pliku wspólnych kart mechanik.")
        version = json.loads(rules.read_text(encoding="utf-8"))["game_version"]
        labels, label_files = {}, 0
    else:
        settings = json.loads((game / "launcher-settings.json").read_text(encoding="utf-8-sig"))
        if settings["gameId"] != "eu4":
            raise ValueError("Wskaż katalog instalacji Europa Universalis IV.")
        version = settings["rawVersion"].removeprefix("v")
        labels, label_files = localization(game)
    if output.exists():
        raise ValueError("Folder wyników już istnieje. Wybierz nowy folder, żeby zachować poprzednią bazę.")
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "game_version": version,
        "scope": "local_installation_without_mods" if game is not None else "shared_guides",
        "files_per_family": collections.Counter(),
        "chunks_per_family": collections.Counter(),
        "empty_or_no_records": [],
        "structure_errors": [],
        "english_labels": len(labels),
        "label_files": label_files,
    }
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        staging = Path(temp) / "index"
        staging.mkdir()
        with closing(sqlite3.connect(staging / "knowledge.sqlite3")) as db, (staging / "chunks.jsonl").open(
            "w", encoding="utf-8", newline="\n"
        ) as handle:
            schema(db)
            for path, relative in sources(game) if game is not None else ():
                try:
                    records = list(file_records(path, relative, version, labels))
                except ValueError as error:
                    summary["structure_errors"].append({"path": relative, "reason": str(error)})
                    continue
                if not records:
                    summary["empty_or_no_records"].append(relative)
                    continue
                summary["files_per_family"][records[0]["family"]] += 1
                for record in records:
                    insert(db, handle, record)
                    summary["chunks_per_family"][record["family"]] += 1
            for record in note_records(notes):
                insert(db, handle, record)
                summary["chunks_per_family"][record["family"]] += 1
            for extra in (rule_records(rules, game, version), strategy_records(strategies), wiki_records(wiki, version),
                          tooltip_records(labels, version), fact_records(game or facts_game, version)):
                for record in extra:
                    insert(db, handle, record)
                    summary["chunks_per_family"][record["family"]] += 1
            db.commit()
        summary["files"] = sum(summary["files_per_family"].values())
        summary["chunks"] = sum(summary["chunks_per_family"].values())
        (staging / "coverage.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
        staging.rename(output)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Przygotuj lokalne źródła rozgrywki w EU4.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--game-dir", type=Path, help="Katalog instalacji Europa Universalis IV")
    source.add_argument("--shared-only", action="store_true", help="Zbuduj bazę z opracowań z repozytorium")
    parser.add_argument("--output", required=True, type=Path, help="Nowy folder dla lokalnej bazy")
    parser.add_argument("--facts-game-dir", type=Path, help="Odtwórz wspólne karty faktów z danej instalacji")
    parser.add_argument("--notes", type=Path, default=Path(__file__).resolve().parent.parent / "video-notes/chunks.jsonl")
    parser.add_argument("--rules", type=Path, default=Path(__file__).resolve().with_name("rules.json"))
    parser.add_argument("--strategies", type=Path, default=Path(__file__).resolve().parents[1] / "strategies-1.37.json")
    parser.add_argument("--wiki-jsonl", type=Path, help="opcjonalne wcześniej pobrane artykuły z lokalnego JSONL")
    args = parser.parse_args()
    try:
        if args.facts_game_dir:
            if not args.shared_only:
                raise ValueError("Opcja --facts-game-dir wymaga --shared-only.")
            settings = json.loads((args.facts_game_dir / "launcher-settings.json").read_text(encoding="utf-8-sig"))
            expected = json.loads(args.rules.read_text(encoding="utf-8"))["game_version"]
            if settings["gameId"] != "eu4" or settings["rawVersion"].removeprefix("v") != expected:
                raise ValueError(f"Wybierz instalację EU4 {expected}.")
        coverage = build(args.game_dir, args.output, args.notes, args.rules, args.strategies, args.wiki_jsonl,
                         args.facts_game_dir)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Nie udało się zbudować bazy. {error}\n")
    print(f"Gotowe. Zapisano {coverage['chunks']} fragmentów z {coverage['files']} plików EU4 {coverage['game_version']}.")
    if coverage["structure_errors"]:
        print(f"Pliki wymagające sprawdzenia: {len(coverage['structure_errors'])}. Ich lista jest w coverage.json.")


if __name__ == "__main__":
    main()
