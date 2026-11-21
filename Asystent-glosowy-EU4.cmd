@echo off
chcp 65001 >nul
set "PY=%~dp0.eu4\.venv\Scripts\python.exe"
set "PYW=%~dp0.eu4\.venv\Scripts\pythonw.exe"
if not exist "%PY%" (
  echo Najpierw otworz Przygotuj-EU4.
  pause
  exit /b 1
)
"%PY%" -c "import importlib.util as u, sys; sys.exit(not all(map(u.find_spec, ('elevenlabs', 'sounddevice', 'pynput', 'pystray', 'PIL'))))" >nul 2>&1
if errorlevel 1 (
  echo Instaluje pakiety asystenta glosowego...
  "%PY%" -m pip install -q -r "%~dp0sources\eu4\mechanics\requirements-voice.txt"
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
rem pythonw: bez okna konsoli; ikona pojawi sie w zasobniku systemowym
start "" "%PYW%" "%~dp0sources\eu4\mechanics\voice_app.py" %*
