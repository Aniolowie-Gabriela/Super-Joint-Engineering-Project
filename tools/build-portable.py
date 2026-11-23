"""Zbuduj ZIP panelu EU4 z gotową bazą i przenośnym Pythonem Windows x64.

Uruchom skrypt w venv CPythona 3.13 lub nowszego z zainstalowanym
requirements-web.txt. Katalog z danymi musi zawierać knowledge.sqlite3,
semantic/ i embedding-model/.
"""

import argparse
from contextlib import closing
from importlib.metadata import distribution
import json
from pathlib import Path, PurePath
import shutil
import sqlite3
import struct
import subprocess
import sys
import sysconfig
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import numpy as np
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[1]
MECHANICS = ROOT / "sources" / "eu4" / "mechanics"
PORTABLE = ROOT / "tools" / "portable"
APP_NAME = "Asystent-EU4"
APP_FILES = (
    "ask.py", "build_index.py", "chat_history.py", "game_facts.py", "interpret.py", "local_web.py",
    "panel_access.py", "rules.json", "search.py", "semantic.py", "user_sources.py", "web_import.py",
)
DATA_FILES = (
    "knowledge.sqlite3", "coverage.json",
    "embedding-model/model_int8.onnx", "embedding-model/tokenizer.json",
    "semantic/ids.npy", "semantic/manifest.json", "semantic/vectors.npy",
)
UNUSED_STDLIB = {"ensurepip", "idlelib", "site-packages", "test", "tkinter", "turtledemo", "venv"}


def add_file(archive, source, name):
    info = ZipInfo(str(name).replace("\\", "/"))
    info.compress_type = ZIP_DEFLATED
    info.compress_level = 5
    with source.open("rb") as original, archive.open(info, "w") as copied:
        shutil.copyfileobj(original, copied, length=1024 * 1024)


def add_files(archive, files, prefix):
    for source, name in sorted(files, key=lambda pair: pair[1]):
        add_file(archive, source, prefix / name)


def python_runtime(target):
    if sys.platform != "win32" or sysconfig.get_platform() != "win-amd64" or struct.calcsize("P") != 8:
        raise ValueError("Uruchom budowanie w CPythonie Windows x64.")
    if sys.version_info < (3, 13):
        raise ValueError("Użyj CPythona 3.13 lub nowszego.")
    base = Path(sys.base_prefix)
    stdlib = Path(sysconfig.get_path("stdlib"))
    py = f"python{sys.version_info.major}{sys.version_info.minor}"
    target.mkdir()
    for name in ("python.exe", "python3.dll", f"{py}.dll", "LICENSE.txt"):
        shutil.copy2(base / name, target / name)
    for runtime in sorted(base.glob("vcruntime*.dll")):
        shutil.copy2(runtime, target / runtime.name)
    for dll in sorted((base / "DLLs").iterdir()):
        if dll.is_file() and dll.suffix in {".dll", ".pyd"} and dll.name not in {
            "_tkinter.pyd", "libtommath.dll", "tcl90.dll", "tcl9tk90.dll",
        }:
            shutil.copy2(dll, target / dll.name)
    with ZipFile(target / f"{py}.zip", "w") as archive:
        sources = (
            (path, path.relative_to(stdlib)) for path in stdlib.rglob("*.py")
            if path.relative_to(stdlib).parts[0] not in UNUSED_STDLIB
        )
        add_files(archive, sources, PurePath())
    (target / f"{py}._pth").write_text(
        f"{py}.zip\n.\nLib\\site-packages\n..\\app\n", encoding="ascii",
    )


def web_distributions():
    pins = (MECHANICS / "requirements-web.txt").read_text(encoding="utf-8").splitlines()
    pending = [Requirement(pin) for pin in pins if pin.strip() and not pin.lstrip().startswith("#")]
    packages = {}
    while pending:
        requirement = pending.pop()
        if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
            continue
        name = canonicalize_name(requirement.name)
        package = distribution(name)
        if not requirement.specifier.contains(package.version):
            raise ValueError(f"Zainstaluj {requirement} w środowisku używanym do budowania.")
        if name not in packages:
            packages[name] = package
            pending.extend(Requirement(dependency) for dependency in package.requires or ())
    return packages


def copy_packages(target):
    packages = web_distributions()
    site = target / "Lib" / "site-packages"
    for package in packages.values():
        for name in package.files or ():
            if ".." in name.parts or "__pycache__" in name.parts or name.suffix == ".pyc":
                continue
            source = package.locate_file(name)
            if source.is_file():
                destination = site / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    versions = "".join(f"{name}=={packages[name].version}\n" for name in sorted(packages))
    (target / "packages.txt").write_text(versions, encoding="utf-8")


def copy_app(target, data):
    app = target / "app"
    app.mkdir()
    for name in APP_FILES:
        shutil.copy2(MECHANICS / name, app / name)
    shutil.copytree(MECHANICS / "web_ui", app / "web_ui")
    shutil.copy2(PORTABLE / "portable_launcher.py", app)
    for name in ("Uruchom-EU4.cmd", "Przygotuj-model.cmd", "Przygotuj-wyszukiwanie.cmd", "Zacznij-tutaj.txt"):
        shutil.copy2(PORTABLE / name, target)
    shutil.copy2(PORTABLE / "E5-LICENSE.txt", target / "E5-LICENSE.txt")
    for name in DATA_FILES:
        destination = target / "data" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(data / name, destination)


def verify_bundle(folder):
    data = folder / "data"
    semantic = data / "semantic"
    coverage = json.loads((data / "coverage.json").read_text(encoding="utf-8"))
    marker = json.loads((semantic / "manifest.json").read_text(encoding="utf-8"))
    with closing(sqlite3.connect((data / "knowledge.sqlite3").as_uri() + "?mode=ro", uri=True)) as db:
        check = db.execute("PRAGMA quick_check").fetchone()[0]
        count = db.execute("SELECT count(*) FROM record").fetchone()[0]
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        index_ids = {row[0] for row in db.execute("SELECT id FROM record")}
    if check != "ok" or count != coverage["chunks"] or count != marker["records"] or pages != marker["pages"]:
        raise ValueError("Baza, opis zawartości i manifest wektorów muszą pochodzić z tego samego indeksu.")
    ids = np.load(semantic / "ids.npy", allow_pickle=False)
    vectors = np.load(semantic / "vectors.npy", allow_pickle=False)
    if ids.shape != (marker["vectors"],) or vectors.shape != (len(ids), 384):
        raise ValueError("Liczba lub rozmiar wektorów nie zgadza się z manifestem E5.")
    vector_ids = set(ids.tolist())
    if len(vector_ids) != len(ids) or not vector_ids.issubset(index_ids):
        raise ValueError("Indeks E5 zawiera powtórzone lub nieistniejące identyfikatory kart.")
    python = folder / "python" / "python.exe"
    subprocess.run(
        [str(python), "-B", "-X", "utf8", "-c", "import fastapi, numpy, onnxruntime, tokenizers, uvicorn"],
        cwd=folder, check=True,
    )
    subprocess.run(
        [str(python), "-B", "-X", "utf8", str(folder / "app" / "local_web.py"), "--help"],
        cwd=folder, check=True,
    )
    subprocess.run(
        [str(python), "-B", "-X", "utf8", "-c",
         "from semantic import neighbors; found = neighbors('data/knowledge.sqlite3', 'morale armii', (), 3);"
         " assert len(found) == 3"],
        cwd=folder, check=True,
    )


def build(data, output, work_dir):
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="eu4-", dir=work_dir) as scratch:
        folder = Path(scratch) / APP_NAME
        folder.mkdir()
        python_runtime(folder / "python")
        copy_packages(folder / "python")
        copy_app(folder, data)
        verify_bundle(folder)
        with tempfile.NamedTemporaryFile(prefix=".eu4-", suffix=".zip", dir=output.parent, delete=False) as staging:
            pending = Path(staging.name)
        try:
            with ZipFile(pending, "w") as archive:
                files = ((path, path.relative_to(folder)) for path in folder.rglob("*") if path.is_file())
                add_files(archive, files, PurePath(APP_NAME))
            pending.replace(output)
        finally:
            pending.unlink(missing_ok=True)
    print(f"{output} ({output.stat().st_size / 1024**2:.1f} MiB)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path, help="folder gotowej bazy i plików E5")
    parser.add_argument("--output", required=True, type=Path, help="docelowy plik ZIP")
    parser.add_argument("--work-dir", type=Path, default=ROOT.parent, help="krótka ścieżka folderu roboczego")
    args = parser.parse_args()
    try:
        build(args.data.resolve(), args.output.resolve(), args.work_dir.resolve())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
