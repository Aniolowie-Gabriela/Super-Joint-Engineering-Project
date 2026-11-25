"""Read-only search of a prebuilt EU4 semantic index."""

from contextlib import closing
from functools import lru_cache
import json
import os
from pathlib import Path
import sqlite3

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


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


@lru_cache(maxsize=2)
def assets(directory, model_dir):
    return (
        Encoder(model_dir),
        np.load(directory / "ids.npy", allow_pickle=False),
        np.load(directory / "vectors.npy", mmap_mode="r", allow_pickle=False),
        json.loads((directory / "manifest.json").read_text(encoding="utf-8")),
    )


def index_paths(db_path):
    root = Path(db_path).resolve().parent
    directory = root / "semantic"
    model_dir = Path(os.environ.get("EU4_EMBED_MODEL_DIR", str(root / "embedding-model")))
    return directory, model_dir


def complete_index(directory, model_dir):
    files = [
        directory / "manifest.json", directory / "ids.npy", directory / "vectors.npy",
        model_dir / "model_int8.onnx", model_dir / "tokenizer.json",
    ]
    try:
        return all(path.is_file() and path.stat().st_size > 0 for path in files)
    except OSError:
        return False


def neighbors(db_path, question, terms, limit=30, record_ids=None):
    directory, model_dir = index_paths(db_path)
    if not complete_index(directory, model_dir):
        return []
    with closing(db_connection(db_path)) as db:
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        marker = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if marker["pages"] != pages:
            raise ValueError("Baza i wyszukiwanie semantyczne pochodzą z różnych wersji. Odbuduj wektory.")
        encoder, row_ids, matrix, _ = assets(directory, model_dir)
        if record_ids is not None:
            selected = np.flatnonzero(np.isin(row_ids, record_ids))
            row_ids, matrix = row_ids[selected], matrix[selected]
        if not len(row_ids):
            return []
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
