@echo off
REM visor.bat — lanza el visor refactorizado como módulo Python.

setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo No se encontro "python" en el PATH del sistema.
    echo Instala Python o agregalo al PATH y volve a intentar.
    pause
    exit /b 1
)

python -c "import PyQt6.QtWidgets, requests, sqlalchemy, pydantic, playwright" 2>nul
if errorlevel 1 (
    echo Faltan dependencias, instalando desde pyproject.toml...
    python -m pip install -e . --quiet
    if errorlevel 1 (
        echo.
        echo Fallo la instalacion de dependencias. Revisa el error arriba.
        pause
        exit /b 1
    )
)

echo Iniciando BEET ...
python main.py
if errorlevel 1 (
    echo.
    echo El visor termino con error. Revisa la salida arriba.
    pause
)
endlocal