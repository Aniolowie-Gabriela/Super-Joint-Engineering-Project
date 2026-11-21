@echo off
chcp 65001 >nul
set "PY=%~dp0.eu4\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Najpierw otworz Przygotuj-EU4.
  pause
  exit /b 1
)
"%PY%" -c "import importlib.util as u, sys; sys.exit(not all(map(u.find_spec, ('elevenlabs', 'sounddevice', 'fastapi', 'uvicorn'))))" >nul 2>&1
if errorlevel 1 (
  echo Instaluje pakiety do rozmowy glosowej...
  "%PY%" -m pip install -q -r "%~dp0sources\eu4\mechanics\requirements-voice.txt"
)
"%PY%" "%~dp0sources\eu4\mechanics\demo_web.py" %*
set "EU4_EXIT=%ERRORLEVEL%"
if not "%EU4_EXIT%"=="0" pause
exit /b %EU4_EXIT%
