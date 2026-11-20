@echo off
chcp 65001 >nul
if not exist "%~dp0.eu4\.venv\Scripts\python.exe" (
  echo Najpierw otworz Przygotuj-EU4.
  pause
  exit /b 1
)
"%~dp0.eu4\.venv\Scripts\python.exe" "%~dp0eu4.py" ask %*
set "EU4_EXIT=%ERRORLEVEL%"
if not "%EU4_EXIT%"=="0" pause
exit /b %EU4_EXIT%
