@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: Activar venv si existe
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: Ejecutar el visor
python beet-visor.py

:: Si hay error, pausar para ver el mensaje en consola
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Codigo de salida: %errorlevel%
    echo Revisa que las dependencias esten instaladas (pip install -e .)
    pause
)