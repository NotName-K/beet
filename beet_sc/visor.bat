@echo off
REM visor.bat — lanza el visor refactorizado como módulo Python.
REM Se ejecuta desde la raíz del proyecto Beet, independientemente de
REM cuál sea el directorio de trabajo desde el que se haga doble-click.

setlocal
cd /d "%~dp0"

REM Comprobamos que Python esté disponible.
where python >nul 2>nul
if errorlevel 1 (
    echo No se encontro "python" en el PATH del sistema.
    echo Instala Python o agregalo al PATH y volve a intentar.
    pause
    exit /b 1
)

echo Iniciando BEET Visor...
python -m interfaz.visor
if errorlevel 1 (
    echo.
    echo El visor termino con error. Revisa la salida arriba.
    pause
)
endlocal
