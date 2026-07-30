from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTabWidget, QMessageBox,
    QLabel, QSplitter
)
from PyQt6.QtCore import Qt
from beet.controllers.visor_controller import VisorController
from beet.ui.widgets.log_panel import LogPanel
from beet.ui.widgets.partido_list import PartidoList
from beet.ui.widgets.historial_tab import HistorialTab
from beet.ui.widgets.cuotas_tab import CuotasTab

def _carpeta_downloads() -> Path:
    return Path.home() / "Downloads"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Beet — Visor")
        self.resize(1200, 800)
        self._ultimo_lote_por_clave = {}
        self._carpeta_actual = _carpeta_downloads()
        # Partido actualmente mostrado en los tabs. El auto-escaneo procesa
        # TODOS los partidos de la carpeta en background; sin este filtro,
        # el resultado de cualquier otro partido que termine de procesarse
        # pisaba lo que el usuario tenía abierto en pantalla.
        self._clave_seleccionada: Optional[str] = None
        self.controller = VisorController()
        self._setup_ui()
        self._conectar_senales()
        
        if self._carpeta_actual.is_dir():
            self.label_ruta.setText(str(self._carpeta_actual))
            self.controller.cargar_carpeta(str(self._carpeta_actual))

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout_principal = QVBoxLayout(central)

        barra_superior = QHBoxLayout()
        self.btn_abrir_carpeta = QPushButton("📁 Abrir carpeta")
        self.label_ruta = QLabel("(ninguna carpeta seleccionada)")
        barra_superior.addWidget(self.btn_abrir_carpeta)
        barra_superior.addWidget(self.label_ruta, stretch=1)
        layout_principal.addLayout(barra_superior)

        splitter_central = QSplitter(Qt.Orientation.Horizontal)
        self.partido_list = PartidoList()
        splitter_central.addWidget(self.partido_list)
        
        self.tabs = QTabWidget()
        self.historial_tab = HistorialTab()
        self.cuotas_tab = CuotasTab()
        self.tabs.addTab(self.historial_tab, "Historial")
        self.tabs.addTab(self.cuotas_tab, "Cuotas")
        
        splitter_central.addWidget(self.tabs)
        splitter_central.setStretchFactor(0, 1)
        splitter_central.setStretchFactor(1, 3)
        layout_principal.addWidget(splitter_central, stretch=1)

        self.log_panel = LogPanel()
        layout_principal.addWidget(self.log_panel)

    def _conectar_senales(self):
        self.btn_abrir_carpeta.clicked.connect(self._on_abrir_carpeta)
        self.partido_list.partido_seleccionado.connect(self._on_partido_seleccionado)
        
        self.controller.lotes_cargados.connect(self._on_lotes_cargados)
        self.controller.historial_goles_listo.connect(self._on_goles_listo)
        self.controller.historial_corners_listo.connect(self._on_corners_listo)
        self.controller.cuotas_listo.connect(self._on_cuotas_listo)
        self.controller.error_ocurrido.connect(self._on_error)
        self.controller.log_mensaje.connect(self.log_panel.log)

    def _on_abrir_carpeta(self):
        ruta = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta con partidos", str(self._carpeta_actual)
        )
        if not ruta:
            return
        self._carpeta_actual = Path(ruta)
        self.label_ruta.setText(ruta)
        self.controller.cargar_carpeta(ruta)

    def _on_partido_seleccionado(self, clave: str, lote):
        self._clave_seleccionada = clave
        self.historial_tab.limpiar()
        self.cuotas_tab.limpiar()
        self.controller.procesar_partido(clave, lote)

    def _on_lotes_cargados(self, lotes: dict):
        self._ultimo_lote_por_clave = lotes
        self.partido_list.set_lotes(lotes)

    def _on_goles_listo(self, clave: str, resultado, tiempo_ms: float):
        if clave != self._clave_seleccionada:
            return
        self.historial_tab.mostrar_resultado(resultado, tiempo_ms, tipo="goles")

    def _on_corners_listo(self, clave: str, resultado, tiempo_ms: float):
        if clave != self._clave_seleccionada:
            return
        self.historial_tab.mostrar_resultado(resultado, tiempo_ms, tipo="corners")

    def _on_cuotas_listo(self, clave: str, resultado, tiempo_ms: float):
        if clave != self._clave_seleccionada:
            return
        self.cuotas_tab.mostrar_resultado(resultado, tiempo_ms)

    def _on_error(self, mensaje: str):
        self.log_panel.log_error(mensaje)
        QMessageBox.critical(self, "Error", mensaje)