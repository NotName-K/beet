#!/usr/bin/env python3
"""
Entry point ejecutable. No modificar el paquete beet.
"""
import sys
import os

# Agregar repo al path para imports absolutos
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from PyQt6.QtWidgets import QApplication
from beet.ui import MainWindow  # import absoluto estándar

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()