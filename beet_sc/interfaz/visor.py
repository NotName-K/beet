#!/usr/bin/env python3
"""
interfaz/visor.py
Punto de entrada de la aplicación BEET. Ventana principal con la vista de fixtures.
"""

import sys, subprocess

def _instalar_si_falta():
    import importlib
    faltantes = []
    for paquete, modulo in (("PyQt6", "PyQt6"), ("requests", "requests")):
        try:
            importlib.import_module(modulo)
        except ImportError:
            faltantes.append(paquete)
    if faltantes:
        print(f"Instalando dependencias: {', '.join(faltantes)} …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", *faltantes])
        print("✅ Instalación completa. Iniciando visor…\n")

_instalar_si_falta()

from pathlib import Path
_RAIZ = Path(__file__).resolve().parent.parent
for _carpeta in ("pipeline", "persistencia", "scraping"):
    _p = str(_RAIZ / _carpeta)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase
from .estilos import QSS, TEXT
from .componentes import lbl
from .visor_fixtures import VisorFixtures

_RUTA_FUENTES = Path(__file__).resolve().parent / "assets" / "fonts"


def _cargar_fuentes_propias():
    """Registra las fuentes embebidas del proyecto (ej. Manrope) en QFontDatabase."""
    ruta_manrope = _RUTA_FUENTES / "Manrope[wght].ttf"
    if not ruta_manrope.exists():
        print(f"[fuentes] no se encontró {ruta_manrope}, se usará el fallback del sistema")
        return
    id_fuente = QFontDatabase.addApplicationFont(str(ruta_manrope))
    if id_fuente == -1:
        print("[fuentes] no se pudo cargar Manrope, se usará el fallback del sistema")
        return
    familias = QFontDatabase.applicationFontFamilies(id_fuente)
    print(f"[fuentes] Manrope cargada como: {familias}")


class VisorBeet(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚽  BEET — Pipeline de Ingesta")
        self.setMinimumSize(1050, 640)
        self.setStyleSheet(QSS)

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)

        root_lay = QVBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        root_lay.addWidget(self._build_header())
        root_lay.addWidget(VisorFixtures(), stretch=1)

    def _build_header(self):
        bar = QFrame()
        bar.setObjectName("header_bar")
        bar.setFixedHeight(56)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(0)

        marca = lbl("⚽ BEET", 15, bold=True, color=TEXT)
        lay.addWidget(marca)
        lay.addStretch()
        return bar

def excepthook(exc_type, exc_value, exc_tb):
    import traceback
    print("Excepción no capturada:")
    traceback.print_exception(exc_type, exc_value, exc_tb)

if __name__ == "__main__":
    sys.excepthook = excepthook
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _cargar_fuentes_propias()
    app.setStyleSheet(QSS)
    win = VisorBeet()
    win.show()
    sys.exit(app.exec())