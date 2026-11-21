#!/usr/bin/env bash
# Demo w przeglądarce: rozmowa z agentem ElevenLabs, źródła EU4 szukane lokalnie.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/.eu4/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Najpierw uruchom: python3 eu4.py setup --no-model" >&2
  exit 1
fi
if ! "$PY" -c "import importlib.util as u, sys; sys.exit(not all(map(u.find_spec, ('elevenlabs', 'sounddevice', 'fastapi', 'uvicorn'))))" >/dev/null 2>&1; then
  echo "Instaluję pakiety do rozmowy głosowej…"
  "$PY" -m pip install -q -r "$ROOT/sources/eu4/mechanics/requirements-voice.txt"
fi
exec "$PY" "$ROOT/sources/eu4/mechanics/demo_web.py" "$@"
