import sys
from pathlib import Path

from PyQt6.QtCore import QByteArray
from PyQt6.QtWidgets import QApplication
from PyQt6.QtSvgWidgets import QSvgWidget

BASE = Path(__file__).resolve().parent.parent
FLAG = BASE / "cache" / "flags" / "jp.svg"

print("FLAG:", FLAG)
print("EXISTE:", FLAG.exists())
print("TAMAÑO:", FLAG.stat().st_size if FLAG.exists() else 0)

app = QApplication(sys.argv)

widget = QSvgWidget()

data = FLAG.read_bytes()

print("BYTES:", len(data))

widget.load(QByteArray(data))

print("VALID:", widget.renderer().isValid())
print("DEFAULT SIZE:", widget.renderer().defaultSize().width(),
      widget.renderer().defaultSize().height())

widget.setFixedSize(200, 140)
widget.show()

sys.exit(app.exec())