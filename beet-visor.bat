@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: Activar venv si existe
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python beet-visor.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Codigo %errorlevel%
    pause
)
