#!/usr/bin/env python3
"""
Uso: python -m beet.ui
"""
import sys
from PyQt6.QtWidgets import QApplication
from beet.ui import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
