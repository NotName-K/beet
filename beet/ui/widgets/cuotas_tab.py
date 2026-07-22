"""
Tab de cuotas: tabla con mercado, casa, valor y validez, tal como las
entrega ResultadoParseoPDF.

NOTA: no tengo a la vista beet/core/cuota.py ni
beet/ingest/parsers/pdf.py, así que este widget accede a los atributos
de Cuota / ResultadoParseoPDF con getattr() defensivo en vez de
asumir los nombres exactos. Si el modelo real usa otros nombres de
campo, ajustar los getattr() de abajo.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView
)

COLUMNAS = ["Mercado", "Casa", "Valor", "Válida"]


class CuotasTab(QWidget):

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.label_info = QLabel("Sin datos")
        layout.addWidget(self.label_info)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tabla)

    def limpiar(self):
        self.tabla.setRowCount(0)
        self.label_info.setText("Sin datos")

    def mostrar_resultado(self, resultado, tiempo_ms: float):
        """
        resultado: ResultadoParseoPDF (beet.ingest.parsers.pdf)
        Se asume un atributo `cuotas` con una lista de objetos Cuota.
        """
        cuotas = getattr(resultado, "cuotas", [])

        self.tabla.setRowCount(0)
        for cuota in cuotas:
            fila = self.tabla.rowCount()
            self.tabla.insertRow(fila)

            mercado = getattr(cuota, "mercado", "")
            casa = getattr(cuota, "casa", "")
            valor = getattr(cuota, "valor", "")
            # acepta "válida" o "valida" según cómo haya quedado definido
            # el campo en beet/core/cuota.py
            valida = getattr(cuota, "válida", getattr(cuota, "valida", False))

            valores = [mercado, casa, str(valor), "✅" if valida else "—"]
            for col, valor_celda in enumerate(valores):
                self.tabla.setItem(fila, col, QTableWidgetItem(valor_celda))

        info = (
            f"Tipo: ResultadoParseoPDF | "
            f"Registros: {len(cuotas)} | "
            f"Tiempo: {tiempo_ms:.1f} ms"
        )
        errores = getattr(resultado, "errores", None)
        if errores:
            info += f" | Errores: {len(errores)}"
        self.label_info.setText(info)
