"""
Panel inferior de log: texto con scroll, timestamp por línea y color
según severidad (verde = info, rojo = error).
"""
import html
from datetime import datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit


class LogPanel(QWidget):
    """
    No contiene lógica de negocio: solo recibe strings y los muestra.
    `log()` se conecta directo a la señal `log_mensaje` del controller.
    `log_error()` la llama MainWindow además de mostrar el QMessageBox.
    """

    COLOR_INFO = "#6bcB6b"
    COLOR_ERROR = "#ff6b6b"
    COLOR_TIMESTAMP = "#888888"

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumHeight(160)
        self.text_edit.setStyleSheet(
            "background-color: #1e1e1e; font-family: Consolas, monospace;"
        )
        layout.addWidget(self.text_edit)

    def log(self, mensaje: str):
        """Línea informativa (verde)."""
        self._agregar_linea(mensaje, self.COLOR_INFO)

    def log_error(self, mensaje: str):
        """Línea de error (rojo)."""
        self._agregar_linea(mensaje, self.COLOR_ERROR)

    def _agregar_linea(self, mensaje: str, color: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        mensaje_escapado = html.escape(mensaje).replace("\n", "<br>")
        linea_html = (
            f'<span style="color:{self.COLOR_TIMESTAMP}">[{timestamp}]</span> '
            f'<span style="color:{color}">{mensaje_escapado}</span>'
        )
        self.text_edit.append(linea_html)
        barra = self.text_edit.verticalScrollBar()
        barra.setValue(barra.maximum())
