"""
interfaz/componentes.py
Widgets y helpers de UI compartidos entre todas las vistas.
"""

from PyQt6.QtWidgets import QLabel, QFrame, QHBoxLayout, QVBoxLayout
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from .estilos import (
    TEXT, MUTED, GREEN, RED, BORDER, BG_ITEM, BG_CARD, ACCENT, ACCENT2,
    FONT_UI_STACK, FONT_MONO_STACK, _font_css,
)


def lbl(text, size=11, bold=False, color=TEXT, mono=False):
    """Etiqueta con fuente UI (por defecto) o mono (para datos numéricos)."""
    w = QLabel(text)
    stack = FONT_MONO_STACK if mono else FONT_UI_STACK
    f = QFont(stack[0], size)
    f.setBold(bold)
    f.setFamilies(stack)
    w.setFont(f)
    w.setStyleSheet(
        f"color:{color}; background:transparent; font-family:{_font_css(mono)};"
    )
    return w


def section_title(text):
    """Título de sección (en mayúsculas, tamaño pequeño, color MUTED)."""
    w = QLabel(text.upper())
    w.setObjectName("section_title")
    f = QFont(FONT_UI_STACK[0], 8)
    f.setBold(True)
    f.setFamilies(FONT_UI_STACK)
    w.setFont(f)
    w.setStyleSheet(
        f"color:{MUTED}; background:transparent; letter-spacing:1px; "
        f"font-family:{_font_css(mono=False)};"
    )
    return w


def hline():
    """Separador horizontal delgado."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background:{BORDER}; border:none;")
    return sep


def vline():
    """Separador vertical delgado."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFixedWidth(1)
    sep.setStyleSheet(f"background:{BORDER}; border:none;")
    return sep


def pill(texto: str, bg: str, color_texto: str = TEXT) -> QFrame:
    """Etiqueta tipo píldora con fondo y texto personalizados."""
    marco = QFrame()
    marco.setObjectName("pill")
    marco.setStyleSheet(f"QFrame#pill {{ background:{bg}; border-radius:14px; }}")
    lay_p = QHBoxLayout(marco)
    lay_p.setContentsMargins(16, 8, 16, 8)
    etiqueta = lbl(texto, 11, bold=True, color=color_texto)
    lay_p.addWidget(etiqueta)
    return marco


_RESULTADO_DISPLAY = {
    "W": (GREEN, "V"),
    "D": (MUTED, "E"),
    "L": (RED, "D"),
}


def badge_resultado(resultado: str | None, subrayado: bool = False, tamano: int = 24) -> QFrame:
    """Bloque redondeado para un resultado (V/E/D) con color y posible subrayado."""
    color, texto = _RESULTADO_DISPLAY.get(resultado, (BORDER, "?"))
    cont = QFrame()
    cont.setStyleSheet("background:transparent;")
    lay_c = QVBoxLayout(cont)
    lay_c.setContentsMargins(0, 0, 0, 0)
    lay_c.setSpacing(3)

    caja = QFrame()
    caja.setFixedSize(tamano, tamano)
    caja.setStyleSheet(
        f"background:{color}; border-radius:{tamano // 4}px;"
    )
    lay_caja = QVBoxLayout(caja)
    lay_caja.setContentsMargins(0, 0, 0, 0)
    etiqueta = lbl(texto, 9, bold=True, color=TEXT, mono=True)
    etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay_caja.addWidget(etiqueta)
    lay_c.addWidget(caja)

    raya = QFrame()
    raya.setFixedHeight(2)
    raya.setStyleSheet(f"background:{GREEN if subrayado else 'transparent'}; border:none;")
    lay_c.addWidget(raya)
    return cont


def _chip_meta(texto: str, mono: bool = False, color: str = MUTED) -> QLabel:
    """Ítem de metadatos (fecha, árbitro, etc.) con estilo consistente."""
    return lbl(texto, 9, color=color, mono=mono)


def _fila_racha(etiqueta: str, resultados: list[str] | None) -> QHBoxLayout:
    """Fila con badges para una racha de resultados (W/D/L)."""
    cont = QHBoxLayout()
    cont.setSpacing(6)
    lbl_etq = lbl(etiqueta, 9, color=MUTED)
    lbl_etq.setFixedWidth(150)
    cont.addWidget(lbl_etq)
    if not resultados:
        cont.addWidget(lbl("Sin datos", 9, color=MUTED))
        cont.addStretch()
        return cont
    for i, r in enumerate(resultados):
        cont.addWidget(badge_resultado(r, subrayado=(i == len(resultados) - 1)))
    cont.addStretch()
    return cont