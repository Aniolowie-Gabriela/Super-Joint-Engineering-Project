@echo off
setlocal
chcp 65001 >nul
if not exist "%~dp0python\python.exe" goto broken
"%~dp0python\python.exe" -B -X utf8 "%~dp0app\portable_launcher.py" %*
set "EU4_EXIT=%ERRORLEVEL%"
if not "%EU4_EXIT%"=="0" pause
exit /b %EU4_EXIT%

:broken
echo Rozpakuj caly ZIP i otworz Uruchom-EU4.cmd z wypakowanego folderu.
pause
exit /b 1
