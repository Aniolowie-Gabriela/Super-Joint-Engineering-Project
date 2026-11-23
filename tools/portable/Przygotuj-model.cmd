@echo off
setlocal
chcp 65001 >nul
if not exist "%~dp0python\python.exe" goto broken
"%~dp0python\python.exe" -B -X utf8 "%~dp0app\portable_launcher.py" --prepare-model
set "EU4_EXIT=%ERRORLEVEL%"
pause
exit /b %EU4_EXIT%

:broken
echo Rozpakuj caly ZIP i otworz Przygotuj-model.cmd z wypakowanego folderu.
pause
exit /b 1
