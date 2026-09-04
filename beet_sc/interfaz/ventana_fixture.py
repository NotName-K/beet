"""
interfaz/ventana_fixture.py
Diálogo de detalle de un fixture persistido: cabecera + pestañas.
"""

import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTabWidget, QGridLayout,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QButtonGroup, QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from .estilos import BG, BG_PANEL, BG_ITEM, BG_CARD, BORDER, MUTED, TEXT, ACCENT, ACCENT2, GREEN, RED
from .componentes import lbl, section_title, hline, vline, pill, badge_resultado, _fila_racha, _chip_meta
from .recursos import escudo_label, _descargar_imagen
from .datos_fixture import (
    _leer_datos_fixture, _info_partido, _partidos_por_bloque, _partidos_h2h,
    _resultado_relativo, _filtrar_h2h, _forma_de, _hora_local
)
import sqlite_store


# ── Funciones auxiliares para la cabecera y pestañas ────────────────────

def _header_partido(info: dict) -> QWidget:
    marco = QFrame()
    marco.setStyleSheet(f"background:{BG_PANEL}; border-bottom:1px solid {BORDER};")
    lay = QVBoxLayout(marco)
    lay.setContentsMargins(20, 16, 20, 18)
    lay.setSpacing(8)

    fila_liga = QHBoxLayout()
    fila_liga.setSpacing(8)
    fila_liga.addStretch()
    if info.get("flag_url"):
        bandera = QLabel()
        bandera.setFixedSize(18, 13)
        bandera.setStyleSheet("background:transparent;")
        data = _descargar_imagen(info["flag_url"])
        if data:
            pix = QPixmap()
            if pix.loadFromData(data):
                bandera.setPixmap(pix.scaled(
                    18, 13, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
        fila_liga.addWidget(bandera, alignment=Qt.AlignmentFlag.AlignVCenter)
    fila_liga.addWidget(lbl(f"{info['pais']} — {info['liga']}", 10, bold=True, color=TEXT))
    if info["es_copa"]:
        copa_pill = QFrame()
        copa_pill.setStyleSheet(f"background:{ACCENT}; border-radius:8px;")
        lay_copa = QHBoxLayout(copa_pill)
        lay_copa.setContentsMargins(8, 2, 8, 2)
        lay_copa.addWidget(lbl("COPA", 8, bold=True, color=TEXT))
        fila_liga.addWidget(copa_pill, alignment=Qt.AlignmentFlag.AlignVCenter)
    fila_liga.addStretch()
    lay.addLayout(fila_liga)

    fila_meta = QHBoxLayout()
    fila_meta.setSpacing(10)
    fila_meta.addStretch()
    fila_meta.addWidget(_chip_meta(info["fecha"], mono=True))
    if info.get("referee"):
        div = vline()
        div.setFixedHeight(11)
        fila_meta.addWidget(div)
        fila_meta.addWidget(_chip_meta(f"Árbitro: {info['referee']}"))
    fila_meta.addStretch()
    lay.addLayout(fila_meta)

    enfrentamiento = QHBoxLayout()
    enfrentamiento.setSpacing(18)
    enfrentamiento.addStretch()

    lado_home = QVBoxLayout()
    lado_home.setSpacing(4)
    lado_home.addWidget(escudo_label(info["home_name"], info["home_id"], 52, info.get("home_logo_url")), alignment=Qt.AlignmentFlag.AlignCenter)
    nom_home = lbl(info["home_name"], 11, bold=True)
    nom_home.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lado_home.addWidget(nom_home)
    enfrentamiento.addLayout(lado_home)

    enfrentamiento.addSpacing(10)
    if info["marcador"]:
        gh, ga = info["marcador"]
        marcador_txt = f"{gh}   -   {ga}"
        color_marcador = TEXT
    else:
        marcador_txt = "vs"
        color_marcador = MUTED
    marcador_lbl = lbl(marcador_txt, 24, bold=True, color=color_marcador, mono=True)
    marcador_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    marcador_lbl.setMinimumWidth(90)
    enfrentamiento.addWidget(marcador_lbl)
    enfrentamiento.addSpacing(10)

    lado_away = QVBoxLayout()
    lado_away.setSpacing(4)
    lado_away.addWidget(escudo_label(info["away_name"], info["away_id"], 52, info.get("away_logo_url")), alignment=Qt.AlignmentFlag.AlignCenter)
    nom_away = lbl(info["away_name"], 11, bold=True)
    nom_away.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lado_away.addWidget(nom_away)
    enfrentamiento.addLayout(lado_away)

    enfrentamiento.addStretch()
    lay.addLayout(enfrentamiento)
    return marco


def _fila_stats(records: list[dict], team_id, contexto: str) -> dict | None:
    return next(
        (r for r in records if r.get("team_id") == team_id and r.get("context") == contexto),
        None,
    )


def _tarjeta_equipo_stats(
    nombre: str, team_id, fila: dict | None, logo_url: str | None = None,
    racha: list[str] | None = None, etiqueta_racha: str = "Últimos 5",
) -> QFrame:
    card = QFrame()
    card.setObjectName("stat_card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)

    cab = QHBoxLayout()
    cab.addWidget(escudo_label(nombre, team_id, 36, logo_url))
    col_nom = QVBoxLayout()
    col_nom.setSpacing(1)
    col_nom.addWidget(lbl(nombre, 11, bold=True))
    pos = fila.get("position") if fila else None
    col_nom.addWidget(lbl(f"Posición {pos}" if pos is not None else "Posición —", 9, color=MUTED))
    cab.addLayout(col_nom)
    cab.addStretch()
    lay.addLayout(cab)
    lay.addWidget(hline())

    if fila is None:
        lay.addWidget(lbl("Sin estadísticas para este contexto.", 9, color=MUTED))
        lay.addStretch()
        return card

    pts = fila.get("points")
    lay_pts = QHBoxLayout()
    lay_pts.addStretch()
    lay_pts.addWidget(lbl(str(pts) if pts is not None else "—", 26, bold=True, color=GREEN, mono=True))
    lbl_pts_sufijo = lbl("PTS", 9, bold=True, color=MUTED)
    lbl_pts_sufijo.setContentsMargins(4, 10, 0, 0)
    lay_pts.addWidget(lbl_pts_sufijo)
    lay_pts.addStretch()
    lay.addLayout(lay_pts)

    grid = QGridLayout()
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(4)
    campos = (
        ("J", fila.get("played"), TEXT),
        ("G", fila.get("won"), GREEN),
        ("E", fila.get("draw"), MUTED),
        ("P", fila.get("lost"), RED),
    )
    for col, (etiqueta, valor, color) in enumerate(campos):
        v = lbl(str(valor) if valor is not None else "—", 13, bold=True, color=color, mono=True)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        e = lbl(etiqueta, 8, color=MUTED)
        e.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(v, 0, col)
        grid.addWidget(e, 1, col)
    lay.addLayout(grid)

    dif = fila.get("goal_diff")
    if dif is not None:
        color_dif = GREEN if dif > 0 else (RED if dif < 0 else MUTED)
        texto_dif = f"{'+' if dif > 0 else ''}{dif}"
        gf, ga = fila.get("goals_for"), fila.get("goals_against")
        dif_lbl = lbl(f"Goles {gf}-{ga}  ({texto_dif})", 9, bold=True, color=color_dif, mono=True)
        dif_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(dif_lbl)

    lay.addWidget(hline())
    lay.addLayout(_fila_racha(etiqueta_racha, racha))
    lay.addStretch()
    return card


def _tab_clasificacion(datos: dict, info: dict) -> QWidget:
    records = datos.get("team_record_summaries", [])
    cont = QWidget()
    lay = QVBoxLayout(cont)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(14)

    lay.addWidget(lbl(
        "Comparativa de los dos equipos del fixture — la tabla completa de "
        "la liga no está disponible (el pipeline solo persiste posición/"
        "PJ/Pts del resto de los clubes, sin nombre ni G/E/P/goles).",
        8, color=MUTED,
    ))

    fila_toggle = QHBoxLayout()
    fila_toggle.setSpacing(8)
    btn_rol = QPushButton("COMO LOCAL / VISITANTE")
    btn_gen = QPushButton("GENERAL")
    grupo = QButtonGroup(cont)
    grupo.setExclusive(True)
    for b in (btn_rol, btn_gen):
        b.setObjectName("btn_filtro")
        b.setCheckable(True)
        grupo.addButton(b)
        fila_toggle.addWidget(b)
    btn_rol.setChecked(True)
    fila_toggle.addStretch()
    lay.addLayout(fila_toggle)

    area_cards = QHBoxLayout()
    area_cards.setSpacing(14)
    lay.addLayout(area_cards)
    lay.addStretch()

    def refrescar():
        while area_cards.count():
            item = area_cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        ctx_home, ctx_away = ("home", "away") if btn_rol.isChecked() else ("overall", "overall")
        etq_racha_home = "Últimos 5 (local)" if btn_rol.isChecked() else "Últimos 5 (general)"
        etq_racha_away = "Últimos 5 (visitante)" if btn_rol.isChecked() else "Últimos 5 (general)"
        area_cards.addWidget(_tarjeta_equipo_stats(
            info["home_name"], info["home_id"], _fila_stats(records, info["home_id"], ctx_home),
            info.get("home_logo_url"),
            racha=_forma_de(records, info["home_id"], ctx_home), etiqueta_racha=etq_racha_home,
        ))
        area_cards.addWidget(_tarjeta_equipo_stats(
            info["away_name"], info["away_id"], _fila_stats(records, info["away_id"], ctx_away),
            info.get("away_logo_url"),
            racha=_forma_de(records, info["away_id"], ctx_away), etiqueta_racha=etq_racha_away,
        ))

    btn_rol.toggled.connect(lambda checked: refrescar() if checked else None)
    btn_gen.toggled.connect(lambda checked: refrescar() if checked else None)
    refrescar()
    return cont


def _fila_partido_h2h(h: dict) -> QFrame:
    fila = QFrame()
    fila.setStyleSheet(f"background:{BG_ITEM}; border-radius:8px;")
    lay = QHBoxLayout(fila)
    lay.setContentsMargins(12, 8, 12, 8)
    lay.setSpacing(10)

    fecha_str = str(h.get("date") or "")[:10]
    lbl_fecha = lbl(fecha_str, 9, color=MUTED)
    lbl_fecha.setFixedWidth(80)
    lay.addWidget(lbl_fecha)

    lay.addWidget(escudo_label(h.get("home_team_name", "?"), h.get("home_team_id"), 22))
    lay.addWidget(lbl(h.get("home_team_name", "?"), 9))
    lay.addStretch()

    gh, ga = h.get("home_goals_ft"), h.get("away_goals_ft")
    marcador = f"{gh} - {ga}" if gh is not None and ga is not None else "—"
    lbl_marc = lbl(marcador, 11, bold=True)
    lbl_marc.setFixedWidth(50)
    lbl_marc.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(lbl_marc)

    lay.addStretch()
    lay.addWidget(lbl(h.get("away_team_name", "?"), 9))
    lay.addWidget(escudo_label(h.get("away_team_name", "?"), h.get("away_team_id"), 22))

    lay.addWidget(vline())
    lay.addWidget(lbl(f"⚽ {h.get('league_name', '?')}", 8, color=MUTED))
    return fila


def _tab_h2h(datos: dict, info: dict) -> QWidget:
    partidos = _partidos_h2h(datos)
    cont = QWidget()
    lay = QVBoxLayout(cont)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(14)

    if not partidos:
        lay.addWidget(lbl("Sin historial cara a cara para este fixture.", 10, color=MUTED))
        lay.addStretch()
        return cont

    fila_pills = QHBoxLayout()
    fila_pills.setSpacing(10)
    fila_pills.addStretch()
    lay.addLayout(fila_pills)

    fila_filtros = QHBoxLayout()
    fila_filtros.setSpacing(8)
    botones = {}
    grupo = QButtonGroup(cont)
    grupo.setExclusive(True)
    for clave, etiqueta in (
        ("todos", "TODOS"), ("local", "COMO LOCAL"), ("torneo", "ESTE TORNEO"),
    ):
        b = QPushButton(etiqueta)
        b.setObjectName("btn_filtro")
        b.setCheckable(True)
        grupo.addButton(b)
        fila_filtros.addWidget(b)
        botones[clave] = b
    botones["todos"].setChecked(True)
    fila_filtros.addStretch()
    lay.addLayout(fila_filtros)

    scroll_lista = QScrollArea()
    scroll_lista.setWidgetResizable(True)
    scroll_lista.setStyleSheet("background:transparent; border:none;")
    contenedor_lista = QWidget()
    lay_lista = QVBoxLayout(contenedor_lista)
    lay_lista.setContentsMargins(0, 0, 0, 0)
    lay_lista.setSpacing(6)
    lay_lista.addStretch()
    scroll_lista.setWidget(contenedor_lista)
    lay.addWidget(scroll_lista, stretch=1)

    def refrescar():
        while fila_pills.count() > 1:
            item = fila_pills.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        filtro = next(c for c, b in botones.items() if b.isChecked())
        filtrados = _filtrar_h2h(partidos, info["home_id"], filtro, info["liga"])

        resultados = [_resultado_relativo(h, info["home_id"]) for h in filtrados]
        gana_local = resultados.count("home")
        empates = resultados.count("draw")
        gana_visitante = resultados.count("away")

        fila_pills.insertWidget(0, pill(f"{info['home_name']}  {gana_local}", RED, TEXT))
        fila_pills.insertWidget(1, pill(f"Empates  {empates}", MUTED, "#14151e"))
        fila_pills.insertWidget(2, pill(f"{info['away_name']}  {gana_visitante}", "#ffffff", "#14151e"))

        while lay_lista.count() > 1:
            item = lay_lista.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not filtrados:
            lay_lista.insertWidget(0, lbl("Sin partidos para este filtro.", 9, color=MUTED))
        else:
            for i, h in enumerate(filtrados):
                lay_lista.insertWidget(i, _fila_partido_h2h(h))

    for b in botones.values():
        b.toggled.connect(lambda checked: refrescar() if checked else None)
    refrescar()
    return cont


def _columna_partidos_equipo(
    nombre: str, team_id, logo_url: str | None, partidos: list[dict],
) -> QWidget:
    contenedor = QWidget()
    col = QVBoxLayout(contenedor)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(8)

    cab = QHBoxLayout()
    cab.addWidget(escudo_label(nombre, team_id, 26, logo_url))
    cab.addWidget(lbl(nombre, 10, bold=True))
    cab.addStretch()
    col.addLayout(cab)
    col.addWidget(hline())

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("background:transparent; border:none;")
    interior = QWidget()
    lay_int = QVBoxLayout(interior)
    lay_int.setContentsMargins(0, 0, 0, 0)
    lay_int.setSpacing(6)
    if not partidos:
        lay_int.addWidget(lbl("Sin partidos para este filtro.", 9, color=MUTED))
    else:
        for h in partidos:
            lay_int.addWidget(_fila_partido_h2h(h))
    lay_int.addStretch()
    scroll.setWidget(interior)
    col.addWidget(scroll, stretch=1)
    return contenedor


def _tab_partidos_recientes(datos: dict, info: dict) -> QWidget:
    cont = QWidget()
    lay = QVBoxLayout(cont)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(14)

    fila_toggle = QHBoxLayout()
    fila_toggle.setSpacing(8)
    btn_rol = QPushButton("LOCAL / VISITA")
    btn_gen = QPushButton("GENERAL")
    grupo = QButtonGroup(cont)
    grupo.setExclusive(True)
    for b in (btn_rol, btn_gen):
        b.setObjectName("btn_filtro")
        b.setCheckable(True)
        grupo.addButton(b)
        fila_toggle.addWidget(b)
    btn_rol.setChecked(True)
    fila_toggle.addStretch()
    lay.addLayout(fila_toggle)

    area_cols = QHBoxLayout()
    area_cols.setSpacing(14)
    lay.addLayout(area_cols, stretch=1)

    def refrescar():
        while area_cols.count():
            item = area_cols.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if btn_rol.isChecked():
            bloque_home, bloque_away = "recentHomeResults", "recentAwayResults"
        else:
            bloque_home, bloque_away = "recentHomeAllResults", "recentAwayAllResults"
        area_cols.addWidget(_columna_partidos_equipo(
            info["home_name"], info["home_id"], info.get("home_logo_url"),
            _partidos_por_bloque(datos, bloque_home),
        ))
        area_cols.addWidget(_columna_partidos_equipo(
            info["away_name"], info["away_id"], info.get("away_logo_url"),
            _partidos_por_bloque(datos, bloque_away),
        ))

    btn_rol.toggled.connect(lambda checked: refrescar() if checked else None)
    btn_gen.toggled.connect(lambda checked: refrescar() if checked else None)
    refrescar()
    return cont


def _tab_cuotas(datos: dict) -> QWidget:
    cuotas = datos.get("raw_odds", [])
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("background:transparent; border:none;")

    cont = QWidget()
    lay = QVBoxLayout(cont)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(12)

    if not cuotas:
        lay.addWidget(lbl("Sin cuotas persistidas para este fixture.", 10, color=MUTED))
        lay.addStretch()
        scroll.setWidget(cont)
        return scroll

    por_mercado: dict[str, list[dict]] = {}
    for c in cuotas:
        por_mercado.setdefault(c.get("market_name", "?"), []).append(c)

    for mercado, filas in por_mercado.items():
        card = QFrame()
        card.setObjectName("stat_card")
        lay_card = QVBoxLayout(card)
        lay_card.setContentsMargins(14, 10, 14, 10)
        lay_card.setSpacing(6)
        lay_card.addWidget(lbl(mercado, 10, bold=True, color=ACCENT2))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(4)
        for i, f in enumerate(filas):
            grid.addWidget(lbl(f.get("outcome_name", "?"), 9), i, 0)
            grid.addWidget(lbl(f.get("bookmaker", "?"), 8, color=MUTED), i, 1)
            grid.addWidget(lbl(f"{f.get('decimal_odds', '?')}", 9, bold=True, color=GREEN, mono=True), i, 2)
        lay_card.addLayout(grid)
        lay.addWidget(card)

    lay.addStretch()
    scroll.setWidget(cont)
    return scroll


# ── Clase VentanaDatosFixture ─────────────────────────────────────────────

class VentanaDatosFixture(QDialog):
    _ETIQUETAS_TABLA = {
        "fixture_metadata": "Metadata",
        "raw_odds": "Cuotas",
        "raw_match_history": "Historial",
        "fixture_match_history_refs": "Refs. historial",
        "validation_errors": "Errores de validación",
        "team_record_summaries": "Records de equipo",
        "team_standings_rows": "Tabla de posiciones",
    }

    def __init__(self, fixture_id: int, row: dict, parent=None):
        super().__init__(parent)
        titulo_partido = f"{row.get('hometeam', '?')} vs {row.get('awayteam', '?')}"
        self.setWindowTitle(f"⚽  {titulo_partido}  ({fixture_id})")
        self.resize(980, 660)
        self.setStyleSheet(f"background:{BG}; color:{TEXT};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        datos = _leer_datos_fixture(fixture_id)
        if datos is None:
            cont = QWidget()
            lay_msg = QVBoxLayout(cont)
            lay_msg.setContentsMargins(20, 20, 20, 20)
            lay_msg.addWidget(lbl(
                f"No se encontró {fixture_id}.db en {sqlite_store.DB_DIR} — "
                "este fixture no tiene datos persistidos todavía.",
                11, color=MUTED,
            ))
            layout.addWidget(cont)
            return

        info = _info_partido(fixture_id, row, datos)
        layout.addWidget(_header_partido(info))

        tabs = QTabWidget()
        tabs.addTab(_tab_clasificacion(datos, info), "CLASIFICACIÓN")
        tabs.addTab(_tab_partidos_recientes(datos, info), "PARTIDOS RECIENTES")
        tabs.addTab(_tab_h2h(datos, info), "CARA A CARA")
        tabs.addTab(_tab_cuotas(datos), "CUOTAS")
        tabs.addTab(self._tab_datos_crudos(datos), "DATOS CRUDOS")
        layout.addWidget(tabs, stretch=1)

    def _tab_datos_crudos(self, datos: dict) -> QWidget:
        sub = QTabWidget()
        sub.setStyleSheet(
            f"QTabBar::tab {{ background:{BG_ITEM}; color:{TEXT}; padding:6px 14px; "
            f"border-bottom: none; }}"
            f" QTabBar::tab:selected {{ background:{ACCENT}; color:{TEXT}; }}"
            f" QTabWidget::pane {{ border: 1px solid {BG_ITEM}; }}"
        )
        for clave, filas in datos.items():
            etiqueta = self._ETIQUETAS_TABLA.get(clave, clave)
            sub.addTab(self._tabla_widget(filas), f"{etiqueta} ({len(filas)})")
        return sub

    @staticmethod
    def _tabla_widget(filas: list[dict]) -> QWidget:
        if not filas:
            contenedor = QWidget()
            QVBoxLayout(contenedor).addWidget(
                lbl("Sin filas para este fixture.", 10, color=MUTED)
            )
            return contenedor

        columnas = list(filas[0].keys())
        tabla = QTableWidget(len(filas), len(columnas))
        tabla.setHorizontalHeaderLabels(columnas)
        tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        tabla.setStyleSheet(
            f"QTableWidget {{ background:{BG_ITEM}; color:{TEXT}; gridline-color:#333; }}"
            f" QHeaderView::section {{ background:{BG}; color:{MUTED}; padding:4px; }}"
        )

        for fila_idx, fila in enumerate(filas):
            for col_idx, columna in enumerate(columnas):
                valor = fila.get(columna)
                if columna == "form" and isinstance(valor, str):
                    try:
                        valor = ", ".join(json.loads(valor))
                    except (json.JSONDecodeError, TypeError):
                        pass
                texto = "" if valor is None else str(valor)
                tabla.setItem(fila_idx, col_idx, QTableWidgetItem(texto))
        return tabla