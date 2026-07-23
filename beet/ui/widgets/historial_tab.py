"""
Tab de historial: dos tabs principales (Goles / Corners),
cada uno con sub-tabs (Local / Visitante).
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QLabel, QHeaderView
)
from PyQt6.QtCore import Qt

COLUMNAS = ["Fecha", "Competición", "Rival", "Marcador", "Tarjetas rojas", "Hit"]

class HistorialTab(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.label_info = QLabel("Sin datos")
        layout.addWidget(self.label_info)
        # Antes goles y corners compartían self.label_info: el segundo
        # resultado que llegaba pisaba el texto del primero (incluyendo
        # cualquier aviso de "Errores: N"). Ahora se guardan por separado
        # y se muestran juntos.
        self._info_goles = "Goles: sin datos"
        self._info_corners = "Corners: sin datos"
        
        self.tabs_principales = QTabWidget()
        
        # Tab de GOLES
        self.tab_goles = QWidget()
        layout_goles = QVBoxLayout(self.tab_goles)
        self.sub_tabs_goles = QTabWidget()
        self.tabla_goles_local = self._crear_tabla()
        self.tabla_goles_visitante = self._crear_tabla()
        self.sub_tabs_goles.addTab(self.tabla_goles_local, "Local")
        self.sub_tabs_goles.addTab(self.tabla_goles_visitante, "Visitante")
        layout_goles.addWidget(self.sub_tabs_goles)
        
        # Tab de CORNERS
        self.tab_corners = QWidget()
        layout_corners = QVBoxLayout(self.tab_corners)
        self.sub_tabs_corners = QTabWidget()
        self.tabla_corners_local = self._crear_tabla()
        self.tabla_corners_visitante = self._crear_tabla()
        self.sub_tabs_corners.addTab(self.tabla_corners_local, "Local")
        self.sub_tabs_corners.addTab(self.tabla_corners_visitante, "Visitante")
        layout_corners.addWidget(self.sub_tabs_corners)
        
        self.tabs_principales.addTab(self.tab_goles, "📊 Goles (Match Result)")
        self.tabs_principales.addTab(self.tab_corners, "🚩 Corners (Total Match Corners)")
        
        layout.addWidget(self.tabs_principales)

    def _crear_tabla(self) -> QTableWidget:
        tabla = QTableWidget()
        tabla.setColumnCount(len(COLUMNAS))
        tabla.setHorizontalHeaderLabels(COLUMNAS)
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return tabla

    def limpiar(self):
        for tabla in [
            self.tabla_goles_local, self.tabla_goles_visitante,
            self.tabla_corners_local, self.tabla_corners_visitante
        ]:
            tabla.setRowCount(0)
        self._info_goles = "Goles: sin datos"
        self._info_corners = "Corners: sin datos"
        self.label_info.setText("Sin datos")

    def mostrar_resultado(self, resultado, tiempo_ms: float, tipo: str = "corners"):
        if tipo == "goles":
            self._llenar_tabla(self.tabla_goles_local, resultado.historial_local)
            self._llenar_tabla(self.tabla_goles_visitante, resultado.historial_visitante)
            
            n_local = len(resultado.historial_local.partidos) if resultado.historial_local else 0
            n_visitante = len(resultado.historial_visitante.partidos) if resultado.historial_visitante else 0
            
            info = f"GOLES | Registros: {n_local + n_visitante} (local: {n_local}, visitante: {n_visitante}) | Tiempo: {tiempo_ms:.1f} ms"
            if resultado.errores:
                info += f" | ⚠️ Errores: {len(resultado.errores)}"
            self._info_goles = info
            self.label_info.setText(f"{self._info_goles}   ||   {self._info_corners}")
            
        elif tipo == "corners":
            self._llenar_tabla(self.tabla_corners_local, resultado.historial_local)
            self._llenar_tabla(self.tabla_corners_visitante, resultado.historial_visitante)
            
            n_local = len(resultado.historial_local.partidos) if resultado.historial_local else 0
            n_visitante = len(resultado.historial_visitante.partidos) if resultado.historial_visitante else 0
            
            info = f"CORNERS | Registros: {n_local + n_visitante} (local: {n_local}, visitante: {n_visitante}) | Tiempo: {tiempo_ms:.1f} ms"
            if resultado.errores:
                info += f" | ⚠️ Errores: {len(resultado.errores)}"
            self._info_corners = info
            self.label_info.setText(f"{self._info_goles}   ||   {self._info_corners}")

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
                "✅" if partido.hit_mercado_resaltado else "❌",
            ]
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                tabla.setItem(fila, col, item)
                
                if partido.hit_mercado_resaltado:
                    item.setBackground(Qt.GlobalColor.green)
                else:
                    item.setBackground(Qt.GlobalColor.red)