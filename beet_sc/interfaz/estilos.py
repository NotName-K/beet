"""
interfaz/estilos.py
Paleta "SofaScore", QSS y constantes compartidas.
"""

# ── Paleta SofaScore ───────────────────────────────────────────────────────────
BG = "#1a1c24"
BG_PANEL = "#22242f"
BG_CARD = "#1e2030"
BG_ITEM = "#14151e"
ACCENT = "#3d6ef5"
ACCENT2 = "#6b8ff8"
TEXT = "#ffffff"
MUTED = "#9097a5"
GREEN = "#00d17a"
RED = "#e84545"
ORANGE = "#f5a623"
BORDER = "#2a2d3e"
SEL_BG = "#1e2d5a"
BG_CARD_DOCK = "#252838"

# ── Tipografía ──────────────────────────────────────────────────────────────
FONT_UI_STACK = ["Manrope", "Segoe UI", "Inter", "Helvetica Neue", "Arial"]
FONT_MONO_STACK = ["Consolas", "JetBrains Mono", "Courier New", "monospace"]
FONT_UI = FONT_UI_STACK[0]
FONT_MONO = FONT_MONO_STACK[0]

def _font_css(mono: bool) -> str:
    stack = FONT_MONO_STACK if mono else FONT_UI_STACK
    return ", ".join(f'"{f}"' if " " in f else f for f in stack)

# ── QSS global (combinado de visor.py y estilos.py) ──────────────────────
QSS = f"""
* {{
    font-family: {_font_css(mono=False)};
}}
QMainWindow, QWidget#root {{
    background: {BG};
}}
QWidget {{
    background: {BG};
    color: {TEXT};
}}
QFrame#header_bar {{
    background: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
}}
QFrame#card {{
    background: {BG_CARD_DOCK};
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 22px;
}}
QPushButton#btn_action {{
    background: {ACCENT};
    color: {TEXT};
    font-weight: bold;
    font-size: 12px;
    border: none;
    border-radius: 8px;
    padding: 11px;
}}
QPushButton#btn_action:hover {{
    background: {ACCENT2};
}}
QPushButton#btn_action:disabled {{
    background: {BORDER};
    color: {MUTED};
}}
QPushButton#btn_secondary {{
    background: {BG_CARD};
    color: {ACCENT};
    font-size: 11px;
    border: 1px solid {ACCENT};
    border-radius: 8px;
    padding: 8px;
}}
QPushButton#btn_secondary:hover {{
    background: {SEL_BG};
}}
QPushButton#btn_secondary:checked {{
    background: {SEL_BG};
    color: {TEXT};
    border: 1px solid {ACCENT2};
    font-weight: bold;
}}
QPushButton#btn_accion {{
    background: {BG_ITEM};
    color: {ACCENT2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px 10px;
}}
QPushButton#btn_accion:hover {{
    border: 1px solid {ACCENT2};
    background: {SEL_BG};
}}
QPushButton#btn_accion:disabled {{
    color: {MUTED};
    border: 1px solid {BORDER};
}}
QPushButton#btn_accion[estado="persistido"] {{
    background: transparent;
    color: {ORANGE};
    border: 1px solid transparent;
    padding: 6px 10px;
}}
QPushButton#btn_accion[estado="persistido"]:hover {{
    background: {BG_ITEM};
    border: 1px solid {ORANGE};
}}
QTextEdit {{
    background: {BG_ITEM};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    font-size: 11px;
    padding: 6px;
}}
QScrollBar:vertical {{
    background: {BG};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 30px;
}}
QLabel#section_title {{
    color: {MUTED};
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 1px;
}}
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {BORDER};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    font-weight: bold;
    font-size: 11px;
    padding: 10px 18px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 2px solid {GREEN};
}}
QTabBar::tab:hover {{
    color: {TEXT};
}}
QFrame#stat_card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#pill {{
    border-radius: 14px;
}}
QPushButton#btn_filtro {{
    background: {BG_ITEM};
    color: {MUTED};
    font-size: 10px;
    font-weight: bold;
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 6px 14px;
}}
QPushButton#btn_filtro:checked {{
    background: {SEL_BG};
    color: {TEXT};
    border: 1px solid {ACCENT};
}}
QPushButton#btn_filtro:hover {{
    color: {TEXT};
}}
"""

# ── Estado de fixture_pipeline_status ──────────────────────────────────────
_ESTADO_DISPLAY = {
    None: ("○ pendiente (no procesado)", MUTED),
    "pendiente": ("○ pendiente", MUTED),
    "scraped": ("… scrapeado, falta ingesta", ORANGE),
    "ingested": ("… ingerido, falta persistir", ORANGE),
    "persisted": ("✅", GREEN),
    "failed_scraping": ("❌ falló scraping", RED),
    "failed_ingesta": ("❌ falló ingesta", RED),
    "failed_persistencia": ("❌ falló persistencia", RED),
}

# ── Acento de estado del partido (en_curso/pendiente/finalizado) ──────────
ACENTO_ESTADO_PARTIDO = {
    "en_curso": RED,
    "pendiente": ACCENT2,
    "finalizado": GREEN,
}