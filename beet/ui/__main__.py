#!/usr/bin/env python3
"""
Uso: python -m beet.ui
"""
import sys
from PyQt6.QtWidgets import QApplication, QDialog
from beet.ui import MainWindow
from beet.ui.widgets.api_keys_dialog import ApiKeysDialog
from beet.core.config import hay_api_keys_configuradas


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Si todavía no hay API keys guardadas (~/.beet/config.json), se piden
    # ANTES de crear la ventana principal: el auto-escaneo arranca en el
    # constructor de MainWindow y necesita las keys ya disponibles.
    if not hay_api_keys_configuradas():
        dialogo = ApiKeysDialog()
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            # El usuario cerró el diálogo sin guardar ninguna key: no tiene
            # sentido seguir, los parsers no podrían funcionar.
            sys.exit(0)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
