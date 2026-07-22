"""
Lista de partidos agrupados (uno por LoteIngesta). Al seleccionar uno,
emite la señal `partido_seleccionado(clave, lote)` para que MainWindow
se la pase al controller.
"""
from PyQt6.QtWidgets import QListWidget, QListWidgetItem
from PyQt6.QtCore import pyqtSignal, Qt


class PartidoList(QListWidget):

    partido_seleccionado = pyqtSignal(str, object)  # clave, LoteIngesta

    def __init__(self):
        super().__init__()
        self._lotes: dict = {}
        self.itemClicked.connect(self._on_item_clicked)

    def set_lotes(self, lotes: dict):
        """Reemplaza el contenido de la lista con los lotes recién cargados."""
        self._lotes = lotes
        self.clear()
        for clave in sorted(lotes.keys()):
            item = QListWidgetItem(clave)
            item.setData(Qt.ItemDataRole.UserRole, clave)
            self.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        clave = item.data(Qt.ItemDataRole.UserRole)
        lote = self._lotes.get(clave)
        if lote is not None:
            self.partido_seleccionado.emit(clave, lote)
