"""
interfaz/tarjeta_fixture.py
Tarjeta de fixture (rediseño curvo) con escudos, cuotas y apertura por clic.
"""

import threading
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QWidget,
    QSizePolicy, QGraphicsDropShadowEffect
)
from .estilos import (
    BG_ITEM, BORDER, MUTED, TEXT, BG_CARD_DOCK, ACENTO_ESTADO_PARTIDO
)
from .componentes import lbl
from .recursos import (
    escudo_label, _descargar_imagen
)
from .datos_fixture import (
    _leer_datos_medio_tarjeta, _hora_local, _periodo_partido
)
from .ventana_fixture import VentanaDatosFixture


# ── Tamaños del diseño ───────────────────────────────────────────────────
RADIO_TARJETA = 28
TAM_ESCUDO_EQUIPO = 64
TAM_LOGO_LIGA = 40
ANCHO_COLUMNA_CENTRO = 96


class TarjetaFixture(QFrame):
    procesar_clicked = pyqtSignal(int)
    medio_cargado = pyqtSignal(dict)

    def __init__(self, row: dict, estado: dict | None, estado_partido: str = "pendiente", parent=None):
        super().__init__(parent)
        self.external_id = row["external_id"]
        self._row = row
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setToolTip(f"external_id: {self.external_id}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setMinimumWidth(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Sombra
        sombra = QGraphicsDropShadowEffect(self)
        sombra.setBlurRadius(24)
        sombra.setXOffset(0)
        sombra.setYOffset(6)
        sombra.setColor(QColor(0, 0, 0, 140))
        self.setGraphicsEffect(sombra)

        self.setStyleSheet(
            f"QFrame#card {{ background:{BG_CARD_DOCK}; "
            f"border:1px solid rgba(255,255,255,30); border-radius:{RADIO_TARJETA}px; }}"
        )

        lay_ext = QHBoxLayout(self)
        lay_ext.setContentsMargins(0, 0, 0, 0)
        lay_ext.setSpacing(0)

        cuerpo = QVBoxLayout()
        # Margen superior amplio (20px) para simetría tras quitar la fila de cabecera
        cuerpo.setContentsMargins(18, 16, 18, 12)
        cuerpo.setSpacing(6)
        lay_ext.addLayout(cuerpo, stretch=1)

        # ── Fila central: escudo eq1 — [logo liga / hora] — escudo eq2 ────
        color_nombre = MUTED if estado_partido == "finalizado" else TEXT
        nombre_home = str(row.get("hometeam", "?"))
        nombre_away = str(row.get("awayteam", "?"))
        nombre_liga = str(row.get("league_name", "?"))
        nombre_liga_tooltip = f"{nombre_liga} (Copa)" if row.get("es_copa") else nombre_liga

        fila_equipos = QHBoxLayout()
        fila_equipos.setSpacing(8)

        # Columna Local
        col_home = QVBoxLayout()
        col_home.setSpacing(8)
        col_home.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.escudo_home = escudo_label(nombre_home, None, TAM_ESCUDO_EQUIPO)
        col_home.addWidget(self.escudo_home, alignment=Qt.AlignmentFlag.AlignHCenter)
        lbl_home = lbl(nombre_home, 11, bold=True, color=color_nombre)
        lbl_home.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_home.setWordWrap(True)
        lbl_home.setFixedHeight(32)
        col_home.addWidget(lbl_home)
        fila_equipos.addLayout(col_home, stretch=1)

        # Columna Centro (Logo + Hora/Estado)
        col_centro = QVBoxLayout()
        col_centro.setContentsMargins(0, 0, 0, 0)
        col_centro.setSpacing(6)
        col_centro.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.escudo_liga = escudo_label(nombre_liga, None, TAM_LOGO_LIGA)
        self.escudo_liga.setToolTip(nombre_liga_tooltip)
        col_centro.addWidget(self.escudo_liga, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Lógica de la píldora central
        if estado_partido == "en_curso":
            texto_centro = _periodo_partido(row.get("kickoff_epoch_ms")) or "1T"
            bg_pildora = ACENTO_ESTADO_PARTIDO.get(estado_partido, "#E53935")
            color_texto_centro = "#FFFFFF"
        else:
            texto_centro = _hora_local(row.get("kickoff_epoch_ms"))
            bg_pildora = BG_ITEM
            color_texto_centro = TEXT

        pildora_hora = QFrame()
        pildora_hora.setObjectName("pildora_hora")
        pildora_hora.setStyleSheet(
            f"QFrame#pildora_hora {{ background:{bg_pildora}; border-radius:12px; }}"
        )
        lay_hora = QVBoxLayout(pildora_hora)
        lay_hora.setContentsMargins(12, 4, 12, 4)
        
        lbl_hora_centro = lbl(texto_centro, 11, bold=True, color=color_texto_centro, mono=True)
        lbl_hora_centro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay_hora.addWidget(lbl_hora_centro)
        col_centro.addWidget(pildora_hora, alignment=Qt.AlignmentFlag.AlignHCenter)

        centro_wrap = QWidget()
        centro_wrap.setLayout(col_centro)
        centro_wrap.setFixedWidth(ANCHO_COLUMNA_CENTRO)
        centro_wrap.setStyleSheet("background:transparent;")
        fila_equipos.addWidget(centro_wrap, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Columna Visitante
        col_away = QVBoxLayout()
        col_away.setSpacing(8)
        col_away.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.escudo_away = escudo_label(nombre_away, None, TAM_ESCUDO_EQUIPO)
        col_away.addWidget(self.escudo_away, alignment=Qt.AlignmentFlag.AlignHCenter)
        lbl_away = lbl(nombre_away, 11, bold=True, color=color_nombre)
        lbl_away.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_away.setWordWrap(True)
        lbl_away.setFixedHeight(32)
        col_away.addWidget(lbl_away)
        fila_equipos.addLayout(col_away, stretch=1)

        cuerpo.addLayout(fila_equipos)

        # ── Fila inferior: solo cuotas centradas limpiamente ──
        self._lbl_cuota: dict[str, QLabel] = {}

        def _columna_cuota(clave: str, ancho_fijo: int | None = None) -> QWidget:
            et_valor = lbl("–", 11, bold=True, color=TEXT, mono=True)
            et_valor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            wrap = QWidget()
            lay_w = QVBoxLayout(wrap)
            lay_w.setContentsMargins(0, 0, 0, 0)
            lay_w.addWidget(et_valor)
            wrap.setStyleSheet("background:transparent;")
            if ancho_fijo:
                wrap.setFixedWidth(ancho_fijo)
            self._lbl_cuota[clave] = et_valor
            return wrap

        def _divisor_vertical() -> QFrame:
            div = QFrame()
            div.setFixedWidth(1)
            div.setFixedHeight(14)
            div.setStyleSheet(f"background:{BORDER};")
            return div

        self.marco_cuotas = QFrame()
        self.marco_cuotas.setObjectName("marco_cuotas")
        self.marco_cuotas.setFixedHeight(28)
        self.marco_cuotas.setFixedWidth(180) 
        self.marco_cuotas.setStyleSheet(
            f"QFrame#marco_cuotas {{ background:{BG_ITEM}; border:1px solid {BORDER}; "
            f"border-radius:14px; }}"
        )
        lay_cuotas = QHBoxLayout(self.marco_cuotas)
        lay_cuotas.setContentsMargins(6, 0, 6, 0)
        lay_cuotas.setSpacing(0)
        lay_cuotas.addWidget(_columna_cuota("1"), stretch=1)
        lay_cuotas.addWidget(_divisor_vertical())
        lay_cuotas.addWidget(_columna_cuota("X", ANCHO_COLUMNA_CENTRO - 30))
        lay_cuotas.addWidget(_divisor_vertical())
        lay_cuotas.addWidget(_columna_cuota("2"), stretch=1)
        self.marco_cuotas.setVisible(False)

        fila_inf = QHBoxLayout()
        fila_inf.setContentsMargins(0, 0, 0, 0)
        fila_inf.setSpacing(0)
        fila_inf.addStretch(1)
        fila_inf.addWidget(self.marco_cuotas)
        fila_inf.addStretch(1)

        cuerpo.addLayout(fila_inf)

        self.medio_cargado.connect(self._on_medio_cargado)
        threading.Thread(
            target=self._cargar_medio_en_hilo, daemon=True
        ).start()

        self._status = estado["status"] if estado else None

    def mousePressEvent(self, event):
        """Abre la ventana de detalles al hacer clic izquierdo sobre la tarjeta."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._abrir_datos()
        super().mousePressEvent(event)

    def _abrir_datos(self):
        ventana = VentanaDatosFixture(self.external_id, self._row, parent=None)
        ventana.exec()

    def _cargar_medio_en_hilo(self):
        datos = _leer_datos_medio_tarjeta(self.external_id)
        if not datos:
            return
        home_logo = _descargar_imagen(datos["home_team_logo"]) if datos["home_team_logo"] else None
        away_logo = _descargar_imagen(datos["away_team_logo"]) if datos["away_team_logo"] else None
        league_logo = _descargar_imagen(datos["league_logo_url"]) if datos.get("league_logo_url") else None
        self.medio_cargado.emit({
            "home_logo": home_logo,
            "away_logo": away_logo,
            "league_logo": league_logo,
            "league_name": datos.get("league_name"),
            "cuotas": datos["cuotas"],
        })

    def _on_medio_cargado(self, medio: dict):
        for logo, destino, tam in (
            (medio.get("home_logo"), self.escudo_home, TAM_ESCUDO_EQUIPO),
            (medio.get("away_logo"), self.escudo_away, TAM_ESCUDO_EQUIPO),
            (medio.get("league_logo"), self.escudo_liga, TAM_LOGO_LIGA),
        ):
            if not logo:
                continue
            pix = QPixmap()
            if pix.loadFromData(logo):
                destino.setPixmap(pix.scaled(
                    tam, tam,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))

        cuotas = medio.get("cuotas") or {}
        if not cuotas:
            return
        for clave in ("1", "X", "2"):
            valor = cuotas.get(clave)
            if valor is None:
                continue
            self._lbl_cuota[clave].setText(f"{valor:.2f}")
        self.marco_cuotas.setVisible(True)

    def set_resultado(self, resultado: dict):
        self._status = resultado.get("status")