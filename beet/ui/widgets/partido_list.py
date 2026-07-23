"""
Lista de partidos detectados en la carpeta.
Muestra indicador visual (✓) si el partido ya tiene datos persistentes.
"""
from PyQt6.QtWidgets import QListWidget, QListWidgetItem
from PyQt6.QtCore import pyqtSignal, Qt
from beet.ingest import LoteIngesta
from beet.data import partido_procesado

class PartidoList(QListWidget):
    partido_seleccionado = pyqtSignal(str, object)

    def __init__(self):
        super().__init__()
        self._lotes: dict[str, LoteIngesta] = {}
        self.itemClicked.connect(self._on_item_clicked)

    def set_lotes(self, lotes: dict[str, LoteIngesta]):
        self.clear()
        self._lotes = lotes
        
        for clave, lote in lotes.items():
            # Verificar si ya tiene datos persistentes
            tiene_datos = partido_procesado(clave)
            
            # Crear item con indicador visual
            if tiene_datos:
                texto = f"✓ {clave}"
            else:
                texto = clave
            
            item = QListWidgetItem(texto)
            
            # Marcar visualmente los que ya tienen datos
            if tiene_datos:
                item.setForeground(Qt.GlobalColor.darkGreen)
            
            self.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        texto = item.text()
        # Quitar el indicador "✓ " si existe
        if texto.startswith("✓ "):
            texto = texto[2:]
        
        if texto in self._lotes:
            self.partido_seleccionado.emit(texto, self._lotes[texto])