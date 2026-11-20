"""CPU-only multilingual retrieval, built from the local SQLite corpus."""

import argparse
from contextlib import closing
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


FAMILY_NAMES = {
    "centers_of_trade": "coastal and inland center of trade upgrade effects",
    "tradegoods": "trade good production bonus, trading in national bonus",
    "ruler_personalities": "ruler personality trait, monarch bonus",
    "leader_personalities": "military leader personality trait",
    "religious_reforms": "religious reform, coptic blessing, religion effects",
    "personal_deities": "religion personal deity, Hindu god bonus modifier",
    "great_projects": "monument great project, use requirements, tiers and effects",
    "decisions": "country decision, formable nation formation requirements and effects",
    "disasters": "disaster start conditions, progress and end",
    "institutions": "institution spawn location and how to embrace",
    "tradenodes": "trade node routes, transfer trade",
    "peace_treaties": "peace treaty demand conditions and effects",
    "buildings": "province and state buildings, manufactories",
    "policies": "policy combination of two completed idea groups",
    "country_tags": "country name, game tag",
    "technologies": "technology level unlock modifiers",
    "mercenary_companies": "mercenary companies eligibility and bonuses",
    "game_tooltips": "English game interface mechanics tooltip and player guidance",
}
SPACE = re.compile(r"\s+")


class Encoder:
    def __init__(self, model_dir):
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=96)
        # XLM-R token ID 1 is the padding token.
        self.tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        options = ort.SessionOptions()
        options.intra_op_num_threads = min(6, os.cpu_count() or 1)
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_dir / "model_int8.onnx"), options,
                                            providers=["CPUExecutionProvider"])
        self.inputs = {entry.name for entry in self.session.get_inputs()}

    def encode(self, texts):
        batch = self.tokenizer.encode_batch(texts)
        mask = np.array([item.attention_mask for item in batch], dtype=np.int64)
        values = {
            "input_ids": np.array([item.ids for item in batch], dtype=np.int64),
            "attention_mask": mask,
            "token_type_ids": np.array([item.type_ids for item in batch], dtype=np.int64),
        }
        hidden = self.session.run(None, {key: values[key] for key in self.inputs})[0]
        vectors = (hidden * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1)[:, None]
        vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
        return vectors.astype(np.float32)


def db_connection(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def passage(record):
    family = record["family"]
    heading = FAMILY_NAMES.get(family, family.replace("_", " "))
    name = record["symbol"].replace("_", " ")
    section = record.get("section") or ""
    text = record["text"]
    # Give names and scope priority within the transformer token window.
    sample = SPACE.sub(" ", text.replace("_", " ")).strip()[:560]
    return f"passage: {record['title']}. {name}. {heading}. {section}. {sample}"


def reuse_prefix(old_db_path, new_db, matrix, ids, where):
    """Reuse embeddings only when all prior indexed rows are still byte-identical."""
    old_dir = old_db_path.resolve().parent / "semantic"
    old_ids = np.load(old_dir / "ids.npy", allow_pickle=False)
    old_matrix = np.load(old_dir / "vectors.npy", mmap_mode="r", allow_pickle=False)
    if len(old_ids) == 0 or len(old_ids) > len(ids) or len(old_matrix) != len(old_ids):
        raise ValueError("Poprzedni indeks wektorów nie pasuje do nowej bazy.")
    last_id = int(old_ids[-1])
    with closing(db_connection(old_db_path)) as old_db:
        old = old_db.execute(f"SELECT id,json FROM record {where} ORDER BY id")
        new = new_db.execute(
            f"SELECT id,json FROM record {where} {'AND' if where else 'WHERE'} id <= ? ORDER BY id", (last_id,)
        )
        for one, two in zip(old, new, strict=True):
            if one != two:
                raise ValueError("Zmieniono treść istniejącego wpisu. Zbuduj wektory ponownie.")
    count = len(old_ids)
    ids[:count], matrix[:count] = old_ids, old_matrix
    return count, last_id


def build(db_path, model_dir, output, batch_size=64, include_history=False, reuse_from=None):
    if output.exists():
        raise ValueError(f"Folder {output} już istnieje.")
    encoder = Encoder(model_dir)
    where = "" if include_history else "WHERE family NOT IN ('history','map','country_tags')"
    with closing(db_connection(db_path)) as db, tempfile.TemporaryDirectory(dir=output.parent) as scratch:
        count = db.execute(f"SELECT count(*) FROM record {where}").fetchone()[0]
        staging = Path(scratch) / "semantic"
        staging.mkdir()
        ids = np.empty(count, dtype=np.int64)
        matrix = np.lib.format.open_memmap(staging / "vectors.npy", mode="w+", dtype=np.float16, shape=(count, 384))
        done, last_id = (reuse_prefix(reuse_from, db, matrix, ids, where) if reuse_from else (0, 0))
        cursor = db.execute(
            f"SELECT id,json FROM record {where} {'AND' if where else 'WHERE'} id > ? ORDER BY id", (last_id,)
        )
        while batch := cursor.fetchmany(batch_size):
            texts = [passage(json.loads(row[1])) for row in batch]
            size = len(batch)
            matrix[done:done + size] = encoder.encode(texts)
            ids[done:done + size] = [row[0] for row in batch]
            done += size
            if done % (batch_size * 10) == 0 or done == count:
                print(f"Zapisano {done}/{count} wektorów.", flush=True)
        matrix.flush()
        del matrix
        np.save(staging / "ids.npy", ids, allow_pickle=False)
        marker = {"records": db.execute("SELECT count(*) FROM record").fetchone()[0],
                  "pages": db.execute("PRAGMA page_count").fetchone()[0], "vectors": count}
        (staging / "manifest.json").write_text(json.dumps(marker) + "\n", encoding="utf-8")
        staging.rename(output)


@lru_cache(maxsize=2)
def assets(directory, model_dir):
    return (
        Encoder(model_dir),
        np.load(directory / "ids.npy", allow_pickle=False),
        np.load(directory / "vectors.npy", mmap_mode="r", allow_pickle=False),
        json.loads((directory / "manifest.json").read_text(encoding="utf-8")),
    )


def neighbors(db_path, question, terms, limit=30):
    root = Path(db_path).resolve().parent
    directory = root / "semantic"
    model_dir = Path(os.environ.get("EU4_EMBED_MODEL_DIR", str(root / "embedding-model")))
    if not (directory / "manifest.json").is_file() or not (model_dir / "model_int8.onnx").is_file():
        return []
    with closing(db_connection(db_path)) as db:
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        marker = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if marker["pages"] != pages:
            raise ValueError("Baza i wyszukiwanie semantyczne pochodzą z różnych wersji. Odbuduj wektory.")
        encoder, row_ids, matrix, _ = assets(directory, model_dir)
        queries = [f"query: {question}"]
        queries.extend(f"query: {term}" for term in terms[:5])
        vectors = encoder.encode(queries)
        scores = np.einsum("ij,kj->ik", matrix, vectors, dtype=np.float32, optimize=False)
        combined = np.maximum(scores[:, 0], scores[:, 1:].max(axis=1) - 0.015) if scores.shape[1] > 1 else scores[:, 0]
        count = min(limit, len(combined))
        if not count:
            return []
        subset = np.argpartition(combined, -count)[-count:]
        top = subset[np.argsort(combined[subset])[::-1]]
        return [(int(row_ids[index]), float(combined[index])) for index in top]


def main():
    parser = argparse.ArgumentParser(description="Dodaj wyszukiwanie po znaczeniu pytania.")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reuse-from", type=Path, help="baza, do której tylko dopisano nowe wpisy")
    args = parser.parse_args()
    build(args.db, args.model_dir, args.output, reuse_from=args.reuse_from)


if __name__ == "__main__":
    main()
