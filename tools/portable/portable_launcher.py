"""Uruchom rozpakowany panel EU4 albo przygotuj lokalną Gemmę."""

import ctypes
from http.client import HTTPConnection, HTTPException
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
MODEL = "gemma4:e4b"
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
INSTALL_PAGE = "https://ollama.com/download/windows"


def ollama_executable():
    executable = shutil.which("ollama.exe")
    if executable:
        return Path(executable)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        default = Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe"
        if default.is_file():
            return default
    return None


def ollama_running():
    connection = HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=0.4)
    try:
        connection.request("GET", "/api/version")
        with connection.getresponse() as response:
            return response.status == 200
    except (OSError, HTTPException):
        return False
    finally:
        connection.close()


def ollama_environment():
    return {**os.environ, "OLLAMA_HOST": OLLAMA_URL, "OLLAMA_NO_CLOUD": "1"}


def start_ollama(executable):
    subprocess.Popen(
        [str(executable), "serve"],
        cwd=executable.parent,
        env=ollama_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def prepare_model():
    executable = ollama_executable()
    if executable is None:
        print("Aby uruchomić Gemmę, zainstaluj Ollamę.")
        print(f"Otwieram oficjalną stronę pobierania {INSTALL_PAGE}")
        webbrowser.open(INSTALL_PAGE)
        print("Pobierz i uruchom instalator Ollamy.")
        input("Po zakończeniu instalacji naciśnij Enter. ")
        executable = ollama_executable()
        if executable is None:
            raise RuntimeError("Po zainstalowaniu Ollamy otwórz ponownie Przygotuj-model.cmd.")
    if not ollama_running():
        print("Uruchamiam Ollamę…", flush=True)
        start_ollama(executable)
        deadline = time.monotonic() + 15
        while not ollama_running():
            if time.monotonic() >= deadline:
                raise RuntimeError("Otwórz Ollamę z menu Start i ponów Przygotuj-model.cmd.")
            time.sleep(0.4)
    env = ollama_environment()
    available = subprocess.run(
        [str(executable), "show", MODEL],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if available.returncode:
        print("Pobieram Gemmę 4 E4B. Model zajmuje kilka GB.", flush=True)
        downloaded = subprocess.run([str(executable), "pull", MODEL], env=env)
        if downloaded.returncode:
            raise RuntimeError("Sprawdź połączenie i wersję Ollamy, potem ponów Przygotuj-model.cmd.")
    print("Model jest pobrany. Wróć do panelu, aby uruchomić i sprawdzić Gemmę.")
    return 0


def run_panel(arguments):
    backend = os.environ.get("EU4_LLM_BACKEND", "ollama")
    model_url = os.environ.get("EU4_MODEL_URL", OLLAMA_URL).rstrip("/")
    if backend == "ollama" and model_url == OLLAMA_URL:
        try:
            executable = ollama_executable()
            if executable and not ollama_running():
                start_ollama(executable)
        except OSError:
            print("Uruchom Ollamę przez Przygotuj-model.cmd, aby korzystać z Gemmy.")
    configured_db = os.environ.get("EU4_RAG_DB")
    database = Path(configured_db).expanduser().resolve() if configured_db else ROOT / "data" / "knowledge.sqlite3"
    try:
        ctypes.WinDLL("msvcp140.dll")
        ctypes.WinDLL("msvcp140_1.dll")
    except OSError:
        print("Podstawowe wyszukiwanie jest dostępne. Aby wyszukiwać według znaczenia,")
        print("otwórz Przygotuj-wyszukiwanie.cmd i zainstaluj pakiet Microsoft.")
    command = [
        sys.executable, "-B", "-X", "utf8", str(ROOT / "app" / "local_web.py"),
        "--db", str(database), *arguments,
    ]
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    try:
        sys.exit(prepare_model() if sys.argv[1:] == ["--prepare-model"] else run_panel(sys.argv[1:]))
    except (OSError, RuntimeError) as error:
        sys.exit(str(error))
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)
