"""
Diálogo que se muestra al arrancar si todavía no hay API keys de Gemini
guardadas. Las guarda en ~/.beet/config.json, fuera del repo — ver
beet/core/config.py.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox
)

from beet.core.config import cargar_api_keys, guardar_api_keys, ruta_config


class ApiKeysDialog(QDialog):
    """
    Pide 1 o 2 API keys de Gemini (se usan en rotación si hay 2) y las
    guarda al aceptar. No se puede cerrar sin guardar al menos una key
    válida, porque los parsers no pueden funcionar sin ninguna.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar API keys de Gemini")
        self.setMinimumWidth(480)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Beet necesita al menos una API key de Google Gemini para parsear "
            "imágenes y PDFs.\n\n"
            f"Se guardan en:\n{ruta_config()}\n"
            "(fuera del repo — nunca se sube a git)\n\n"
            "La segunda key es opcional; si la agregas, se rota entre ambas "
            "para repartir la cuota."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        keys_existentes = cargar_api_keys()

        self.input_key1 = QLineEdit()
        self.input_key1.setPlaceholderText("API key 1 (obligatoria)")
        if len(keys_existentes) > 0:
            self.input_key1.setText(keys_existentes[0])
        layout.addWidget(self.input_key1)

        self.input_key2 = QLineEdit()
        self.input_key2.setPlaceholderText("API key 2 (opcional)")
        if len(keys_existentes) > 1:
            self.input_key2.setText(keys_existentes[1])
        layout.addWidget(self.input_key2)

        botones = QHBoxLayout()
        botones.addStretch(1)
        self.btn_guardar = QPushButton("Guardar y continuar")
        self.btn_guardar.clicked.connect(self._on_guardar)
        botones.addWidget(self.btn_guardar)
        layout.addLayout(botones)

    def _on_guardar(self) -> None:
        key1 = self.input_key1.text().strip()
        key2 = self.input_key2.text().strip()

        if not key1:
            QMessageBox.warning(
                self, "Falta la API key",
                "Necesitas ingresar al menos una API key para continuar."
            )
            return

        keys = [key1] + ([key2] if key2 else [])
        guardar_api_keys(keys)
        self.accept()
