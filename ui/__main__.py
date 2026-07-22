"""
Entry point para ejecutar el visor.

Uso:
    python -m beet.ui
"""
import sys
from PyQt6.QtWidgets import QApplication

from beet.ui import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Estilo consistente cross-platform

    # Paleta oscura opcional
    # app.setStyleSheet("""
    #     QMainWindow { background-color: #1e1e1e; }
    #     QWidget { background-color: #1e1e1e; color: #d4d4d4; }
    # """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()