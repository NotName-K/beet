#!/usr/bin/env python3
import sys
from PyQt6.QtWidgets import QApplication
from interfaz.visor import VisorBeet, _cargar_fuentes_propias, excepthook
from interfaz.estilos import QSS

if __name__ == "__main__":
    sys.excepthook = excepthook
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _cargar_fuentes_propias()
    app.setStyleSheet(QSS)
    win = VisorBeet()
    win.show()
    sys.exit(app.exec())