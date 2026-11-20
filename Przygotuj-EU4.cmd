@echo off
chcp 65001 >nul
where py.exe >nul 2>&1
if errorlevel 1 (
  python "%~dp0eu4.py" setup --choose-game %*
) else (
  py -3 "%~dp0eu4.py" setup --choose-game %*
)
set "EU4_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %EU4_EXIT%
