@echo off
cd /d "%~dp0"

py --version >nul 2>&1 || (
    echo [X] Python 3.12+ not found
    echo.
    echo Please install Python:
    echo   1. Open https://www.python.org/downloads/
    echo   2. Download Python 3.12 or newer
    echo   3. Run installer, check "Add Python to PATH"
    echo   4. Re-run this script
    echo.
    start https://www.python.org/downloads/
    pause & exit /b 1
)

where uv >nul 2>&1 || (
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
)

uv run python boot.py
pause
