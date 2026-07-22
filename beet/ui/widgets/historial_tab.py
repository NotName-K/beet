"""
Tab de historial: dos sub-tabs (Local / Visitante), cada una con una tabla
de PartidoHistorico. Muestra el dato crudo del ResultadoParseoImagen tal
como lo entrega el parser — sin recalcular ni transformar nada.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QLabel, QHeaderView
)

COLUMNAS = ["Fecha", "Competición", "Rival", "Marcador", "Tarjetas rojas", "Hit"]


class HistorialTab(QWidget):

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.label_info = QLabel("Sin datos")
        layout.addWidget(self.label_info)

        self.sub_tabs = QTabWidget()
        self.tabla_local = self._crear_tabla()
        self.tabla_visitante = self._crear_tabla()
        self.sub_tabs.addTab(self.tabla_local, "Local")
        self.sub_tabs.addTab(self.tabla_visitante, "Visitante")
        layout.addWidget(self.sub_tabs)

    def _crear_tabla(self) -> QTableWidget:
        tabla = QTableWidget()
        tabla.setColumnCount(len(COLUMNAS))
        tabla.setHorizontalHeaderLabels(COLUMNAS)
        tabla.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return tabla

    def limpiar(self):
        self.tabla_local.setRowCount(0)
        self.tabla_visitante.setRowCount(0)
        self.label_info.setText("Sin datos")

    def mostrar_resultado(self, resultado, tiempo_ms: float):
        """
        resultado: ResultadoParseoImagen (beet.ingest.parsers.imagen)
        """
        self._llenar_tabla(self.tabla_local, resultado.historial_local)
        self._llenar_tabla(self.tabla_visitante, resultado.historial_visitante)

        n_local = len(resultado.historial_local.partidos) if resultado.historial_local else 0
        n_visitante = len(resultado.historial_visitante.partidos) if resultado.historial_visitante else 0
        total = n_local + n_visitante

        info = (
            f"Tipo: ResultadoParseoImagen | "
            f"Registros: {total} (local: {n_local}, visitante: {n_visitante}) | "
            f"Tiempo: {tiempo_ms:.1f} ms"
        )
        if resultado.errores:
            info += f" | Errores: {len(resultado.errores)}"
        self.label_info.setText(info)

    def _llenar_tabla(self, tabla: QTableWidget, historial):
        tabla.setRowCount(0)
        if historial is None:
            return
        for partido in historial.partidos:
            fila = tabla.rowCount()
            tabla.insertRow(fila)
            marcador_str = f"{partido.marcador[0]}-{partido.marcador[1]}"
            valores = [
                str(partido.fecha),
                partido.competicion,
                partido.rival,
                marcador_str,
                str(partido.tarjetas_rojas),
                "✅" if partido.hit_mercado_resaltado else "—",
            ]
            for col, valor in enumerate(valores):
                tabla.setItem(fila, col, QTableWidgetItem(valor))
