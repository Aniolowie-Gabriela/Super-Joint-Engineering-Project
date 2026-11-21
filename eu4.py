"""Przygotuj lokalnego asystenta EU4 i zadawaj mu pytania."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import venv


ROOT = Path(__file__).resolve().parent
MECHANICS = ROOT / "sources/eu4/mechanics"
DATA = ROOT / ".eu4"
ENV = DATA / ".venv"
PYTHON = ENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
MODEL = "gemma4:e4b"
LOCAL_URL = "http://127.0.0.1:11434"
E5_URL = (
    "https://huggingface.co/Xenova/multilingual-e5-small/resolve/"
    "761b726dd34fb83930e26aab4e9ac3899aa1fa78/"
)
E5_FILES = (
    ("tokenizer.json", "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39"),
    ("onnx/model_int8.onnx", "4d24e2bc01a447951524466ef533e52944bf48509e6552810bcee1a2711cb02c"),
)


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def obtain_embeddings(directory):
    directory.mkdir(parents=True, exist_ok=True)
    cached = os.environ.get("EU4_EMBED_MODEL_DIR")
    for name, checksum in E5_FILES:
        destination = directory / Path(name).name
        if destination.is_file() and digest(destination) == checksum:
            continue
        with tempfile.TemporaryDirectory(dir=directory) as work:
            candidate = Path(work) / destination.name
            if cached:
                shutil.copyfile(Path(cached) / destination.name, candidate)
            else:
                print(f"Pobieram {destination.name} do wyszukiwania źródeł…", flush=True)
                with urlopen(E5_URL + name, timeout=60) as source, candidate.open("wb") as target:
                    shutil.copyfileobj(source, target)
            if digest(candidate) != checksum:
                raise ValueError(f"Plik {destination.name} nie przeszedł kontroli. Sprawdź źródło i uruchom przygotowanie ponownie.")
            candidate.replace(destination)


def prepare_model(url):
    if os.environ.get("EU4_LLM_BACKEND") == "llama.cpp":
        return
    ollama = shutil.which("ollama")
    if ollama is None:
        raise ValueError("Zainstaluj Ollamę z ollama.com i otwórz ją przed przygotowaniem asystenta.")
    try:
        with urlopen(url.rstrip("/") + "/api/version", timeout=4) as response:
            json.load(response)
    except (OSError, ValueError):
        raise ValueError("Otwórz Ollamę, a potem uruchom Przygotuj-EU4 ponownie.") from None
    env = {**os.environ, "OLLAMA_HOST": url}
    have_model = subprocess.run(
        [ollama, "show", MODEL], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if have_model.returncode:
        print("Pobieram Gemmę 4 E4B. To kilka gigabajtów.", flush=True)
        subprocess.run([ollama, "pull", MODEL], env=env, check=True)


def prepare(args):
    game = args.game_dir
    if args.choose_game:
        entered = input("Folder gry (Enter = wspólna wiedza): ").strip().strip('"')
        game = Path(entered) if entered else None
    if game is not None and not (game / "launcher-settings.json").is_file():
        raise ValueError("Wybierz folder instalacji Europa Universalis IV z plikiem launcher-settings.json.")
    if not args.no_model:
        prepare_model(args.url)
    if not PYTHON.is_file():
        print("Przygotowuję Pythona dla asystenta…", flush=True)
        venv.create(ENV, with_pip=True)
    print("Sprawdzam biblioteki asystenta…", flush=True)
    subprocess.run(
        [str(PYTHON), "-m", "pip", "install", "--quiet", "-r", str(MECHANICS / "requirements.txt")], check=True,
    )
    knowledge = DATA / ("game" if game is not None else "shared")
    if not (knowledge / "knowledge.sqlite3").is_file():
        source = ["--game-dir", str(game.resolve())] if game is not None else ["--shared-only"]
        print("Przygotowuję wiedzę o EU4…", flush=True)
        subprocess.run(
            [str(PYTHON), str(MECHANICS / "build_index.py"), *source, "--output", str(knowledge)], check=True,
        )
    if not (knowledge / "semantic/manifest.json").is_file():
        model_dir = knowledge / "embedding-model"
        obtain_embeddings(model_dir)
        print("Przygotowuję wyszukiwanie źródeł…", flush=True)
        subprocess.run(
            [str(PYTHON), str(MECHANICS / "semantic.py"), "--db", str(knowledge / "knowledge.sqlite3"),
             "--model-dir", str(model_dir), "--output", str(knowledge / "semantic")], check=True,
        )
    print("Gotowe. Otwórz Zapytaj-EU4.", flush=True)
    return 0


def chat(args):
    database = args.db or next(
        (DATA / kind / "knowledge.sqlite3" for kind in ("game", "shared")
         if (DATA / kind / "semantic/manifest.json").is_file()),
        None,
    )
    if not PYTHON.is_file() or database is None or not database.is_file():
        raise ValueError("Najpierw otwórz Przygotuj-EU4.")
    question = args.question
    while True:
        if question is None:
            question = input("Pytanie o EU4 (pusty Enter kończy): ").strip()
        if not question.strip():
            return 0
        print("Szukam odpowiedzi…", flush=True)
        result = subprocess.run(
            [str(PYTHON), str(MECHANICS / "ask.py"), "--db", str(database), "--url", args.url, "--", question],
        )
        if args.question is not None or result.returncode:
            return result.returncode
        print()
        question = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="przygotuj asystenta")
    source = setup.add_mutually_exclusive_group()
    source.add_argument("--game-dir", type=Path, help="dołącz pliki własnej instalacji EU4")
    source.add_argument("--choose-game", action="store_true", help="zapytaj o folder gry")
    setup.add_argument("--no-model", action="store_true",
                       help="pomiń Ollamę i Gemmę (np. serwer wyszukiwania dla zewnętrznego agenta)")
    ask = commands.add_parser("ask", help="zadaj pytanie")
    ask.add_argument("question", nargs="?")
    ask.add_argument("--db", type=Path, help="otwórz wskazaną istniejącą bazę")
    for command in (setup, ask):
        command.add_argument("--url", default=LOCAL_URL, help="adres lokalnego modelu")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.exit(1, "Zainstaluj Python 3.12 lub nowszy i spróbuj ponownie.\n")
    sys.path.insert(0, str(MECHANICS))
    from ask import _loopback_address
    try:
        _loopback_address(args.url)
        return prepare(args) if args.command == "setup" else chat(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Przygotowanie lub pytanie nie powiodło się. {error}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        return 0


if __name__ == "__main__":
    sys.exit(main())
