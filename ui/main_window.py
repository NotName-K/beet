"""
MainWindow del visor de validación de parsers.

Layout:
┌─────────────────────────────────────────────┐
│ [Abrir carpeta]                             │
├──────────────────┬──────────────────────────┤
│                  │                          │
│  Lista de        │  Tabs:                   │
│  partidos        │  ┌─────────┬─────────┐    │
│                  │  │Historial│ Cuotas  │    │
│                  │  └─────────┴─────────┘    │
│                  │                          │
│                  │  [Info de depuración]    │
│                  │  [Tabla de datos]          │
│                  │                          │
├──────────────────┴──────────────────────────┤
│ Log                                         │
└─────────────────────────────────────────────┘
"""
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTabWidget, QMessageBox,
    QLabel, QSplitter
)
from PyQt6.QtCore import Qt

from beet.controllers import VisorController
from beet.ui.widgets import LogPanel, PartidoList, HistorialTab, CuotasTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Beet — Visor de Validación de Parsers")
        self.setMinimumSize(1200, 700)

        # Controller
        self.controller = VisorController()
        self._conectar_senales()

        self._setup_ui()

    def _conectar_senales(self):
        """Conecta las señales del controller a los slots de la UI."""
        self.controller.lotes_cargados.connect(self._on_lotes_cargados)
        self.controller.historial_listo.connect(self._on_historial_listo)
        self.controller.cuotas_listo.connect(self._on_cuotas_listo)
        self.controller.error_ocurrido.connect(self._on_error)
        self.controller.log_mensaje.connect(self.log_panel.log)

    def _setup_ui(self):
        """Construye la interfaz completa por código."""
        central = QWidget()
        self.setCentralWidget(central)

        layout_principal = QVBoxLayout(central)
        layout_principal.setContentsMargins(8, 8, 8, 8)
        layout_principal.setSpacing(6)

        # ── Barra superior ─────────────────────────────────────────
        barra = QHBoxLayout()
        self.btn_abrir = QPushButton("📁 Abrir carpeta")
        self.btn_abrir.setToolTip("Seleccionar carpeta con capturas")
        self.btn_abrir.clicked.connect(self._on_abrir_carpeta)
        barra.addWidget(self.btn_abrir)

        self.lbl_carpeta = QLabel("Ninguna carpeta cargada")
        self.lbl_carpeta.setStyleSheet("color: #858585; font-style: italic;")
        barra.addWidget(self.lbl_carpeta, stretch=1)

        layout_principal.addLayout(barra)

        # ── Splitter principal (lista | resultados) ────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel izquierdo: lista de partidos
        self.partido_list = PartidoList()
        self.partido_list.partido_seleccionado.connect(self._on_partido_seleccionado)
        splitter.addWidget(self.partido_list)

        # Panel derecho: tabs de resultados
        self.tabs_resultados = QTabWidget()

        # Tab Historial
        self.historial_tab = HistorialTab()
        self.tabs_resultados.addTab(self.historial_tab, "📊 Historial")

        # Tab Cuotas
        self.cuotas_tab = CuotasTab()
        self.tabs_resultados.addTab(self.cuotas_tab, "💰 Cuotas")

        splitter.addWidget(self.tabs_resultados)
        splitter.setSizes([300, 900])  # Proporción 1:3

        layout_principal.addWidget(splitter, stretch=1)

        # ── Panel inferior: Log ───────────────────────────────────────
        self.log_panel = LogPanel()
        layout_principal.addWidget(self.log_panel)

    # ── Slots ──────────────────────────────────────────────────────

    def _on_abrir_carpeta(self):
        """Abre diálogo de selección de carpeta."""
        ruta = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta con capturas",
            str(Path.home()),
        )
        if ruta:
            self.lbl_carpeta.setText(ruta)
            self.log_panel.clear()
            self.historial_tab.clear()
            self.cuotas_tab.clear()
            self.controller.cargar_carpeta(ruta)

    def _on_lotes_cargados(self, lotes: dict):
        """Recibe los lotes agrupados y los muestra en la lista."""
        self.partido_list.set_lotes(lotes)
        self.log_panel.log(f"{len(lotes)} partido(s) listo(s) para procesar.")

    def _on_partido_seleccionado(self, clave: str, lote):
        """Cuando el usuario selecciona un partido, ejecuta los parsers."""
        self.historial_tab.clear()
        self.cuotas_tab.clear()
        self.controller.procesar_partido(clave, lote)

    def _on_historial_listo(self, resultado, tiempo_ms):
        """Muestra el resultado del parser de historial."""
        self.historial_tab.mostrar_resultado(resultado, tiempo_ms)

    def _on_cuotas_listo(self, resultado, tiempo_ms):
        """Muestra el resultado del parser de cuotas."""
        self.cuotas_tab.mostrar_resultado(resultado, tiempo_ms)

    def _on_error(self, mensaje: str):
        """Muestra un error en un diálogo