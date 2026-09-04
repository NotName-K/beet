"""
interfaz/visor_datos.py
Visor de datos persistidos (8 tablas) con selector de fixtures.
"""

import re
import sys
import threading
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QListWidget,
    QListWidgetItem, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)
from sqlalchemy import create_engine, select

from .estilos import BG_CARD, BG_ITEM, BORDER, MUTED, SEL_BG, TEXT, _ESTADO_DISPLAY, _font_css
from .componentes import lbl, section_title
import sqlite_store

_RE_FIXTURE_DB = re.compile(r"^(\d+)\.db$")


def _listar_fixtures_con_db() -> list[tuple[int, Path]]:
    if not sqlite_store.DB_DIR.exists():
        return []
    encontrados = []
    for archivo in sqlite_store.DB_DIR.iterdir():
        m = _RE_FIXTURE_DB.match(archivo.name)
        if m:
            encontrados.append((int(m.group(1)), archivo))
    encontrados.sort(key=lambda par: par[1].stat().st_mtime, reverse=True)
    return encontrados


# ── Queries por tabla ── (igual que antes)
def _filas_raw_odds(conn, fixture_id):
    t = sqlite_store.raw_odds
    stmt = t.select().where(t.c.fixture_id == fixture_id).order_by(
        t.c.market_name, t.c.bookmaker
    )
    return [dict(r) for r in conn.execute(stmt).mappings()]

def _filas_raw_match_history(conn, fixture_id):
    hist = sqlite_store.raw_match_history
    refs = sqlite_store.fixture_match_history_refs
    stmt = (
        select(hist, refs.c.source_block, refs.c.result, refs.c.ht_result)
        .select_from(hist.join(refs, hist.c.match_id == refs.c.match_id))
        .where(refs.c.current_fixture_id == fixture_id)
        .order_by(refs.c.source_block, hist.c.date.desc())
    )
    return [dict(r) for r in conn.execute(stmt).mappings()]

def _filas_refs(conn, fixture_id):
    t = sqlite_store.fixture_match_history_refs
    stmt = t.select().where(t.c.current_fixture_id == fixture_id).order_by(
        t.c.source_block
    )
    return [dict(r) for r in conn.execute(stmt).mappings()]

def _filas_team_records(conn, fixture_id):
    t = sqlite_store.team_record_summaries
    stmt = t.select().where(t.c.fixture_id == fixture_id).order_by(t.c.context)
    return [dict(r) for r in conn.execute(stmt).mappings()]

def _filas_standings(conn, fixture_id):
    t = sqlite_store.team_standings_rows
    stmt = t.select().where(t.c.fixture_id == fixture_id).order_by(
        t.c.perspective, t.c.position
    )
    return [dict(r) for r in conn.execute(stmt).mappings()]

def _filas_validation_errors(conn, fixture_id):
    t = sqlite_store.validation_errors
    stmt = t.select().where(t.c.fixture_id == fixture_id).order_by(
        t.c.timestamp.desc()
    )
    return [dict(r) for r in conn.execute(stmt).mappings()]

def _filas_pipeline_status(conn, fixture_id):
    t = sqlite_store.fixture_pipeline_status
    stmt = t.select().where(t.c.fixture_id == fixture_id)
    return [dict(r) for r in conn.execute(stmt).mappings()]

def _filas_fixture_metadata(conn, fixture_id):
    t = sqlite_store.fixture_metadata
    stmt = t.select().where(t.c.fixture_id == fixture_id)
    return [dict(r) for r in conn.execute(stmt).mappings()]

TABLAS = [
    ("fixture_metadata", "Metadata fixture", _filas_fixture_metadata),
    ("raw_odds", "Odds crudas", _filas_raw_odds),
    ("raw_match_history", "Historial partidos", _filas_raw_match_history),
    ("fixture_match_history_refs", "Refs historial↔fixture", _filas_refs),
    ("team_record_summaries", "Team records", _filas_team_records),
    ("team_standings_rows", "Standings", _filas_standings),
    ("validation_errors", "Errores de validación", _filas_validation_errors),
    ("fixture_pipeline_status", "Estado pipeline", _filas_pipeline_status),
]

def _valor_para_celda(valor) -> str:
    return "" if valor is None else str(valor)


class VisorDatos(QWidget):
    lista_actualizada = pyqtSignal(list)
    datos_cargados = pyqtSignal(int, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fixtures: dict[int, Path] = {}
        # ... (el resto del código de VisorDatos, igual que antes,
        # pero usando componentes.lbl y section_title)
        # (copiar todo, solo cambiar los imports de estilos a componentes)