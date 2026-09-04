"""
Orquestador de la capa de ingesta cruda: encadena los 3 parsers ya
validados (odds -> raw_odds, recent_results -> raw_match_history,
team_records -> TeamRecordSummary/TeamStandingsRow) sobre un mismo
fixture y devuelve todo consolidado.

Nombre a propósito distinto de `orquestar_scraping.py` (carpeta
scraping/), que es el pipeline de OBTENCIÓN del JSON crudo desde el sitio
web (obtener_v -> obtener_fixtures_dia -> obtener_fixture_detalle). Este
script arranca donde ese termina: toma un fixture_json ya descargado
y produce las filas RAW listas para persistir.

Persistencia: SQLite, vía persistencia/sqlite_store.py (decisión ya
cerrada, ver beet_ingesta_estado_v2.md) -- `persistir()` conecta ahí
de verdad, no es un stub.
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field

from translator import parsear_raw_odds_desde_json, traducir_fixture
from match_history_parser import (
    parsear_recent_results_desde_json,
    parsear_fixture_metadata,
)
from team_records_parser import parsear_team_records_desde_json

# persistencia/ es carpeta hermana de ingesta/ en la estructura acordada
# (ex persistencia_sqlite.py -> persistencia/sqlite_store.py). Pendiente:
# ese archivo todavía no se pasó a esta sesión, así que este import
# fallará hasta que exista en esa ruta.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "persistencia"))
import sqlite_store as persistencia_sqlite


@dataclass
class ResultadoIngesta:
    fixture_id: int

    raw_odds: list = field(default_factory=list)
    outcomes_traducidos: list = field(default_factory=list)
    errores_odds: list = field(default_factory=list)

    raw_match_history: list = field(default_factory=list)
    fixture_match_history_refs: list = field(default_factory=list)
    errores_match_history: list = field(default_factory=list)

    team_record_summaries: list = field(default_factory=list)
    team_standings_rows: list = field(default_factory=list)
    errores_team_records: list = field(default_factory=list)

    fixture_metadata: object = None  # FixtureMetadata | None

    @property
    def total_errores(self) -> int:
        return (
            len(self.errores_odds)
            + len(self.errores_match_history)
            + len(self.errores_team_records)
        )


def procesar_fixture(fixture_json: dict) -> ResultadoIngesta:
    """
    Corre los 3 parsers sobre el mismo fixture_json ya descargado.
    No detiene la ingesta si una de las 3 piezas falla parcialmente —
    cada parser ya aísla sus propios errores por outcome/fila (ver
    ValidationErrors), así que un problema en team_records no debe
    impedir que odds/match_history queden guardados.
    """
    fixture_id = fixture_json["external_id"]
    resultado = ResultadoIngesta(fixture_id=fixture_id)

    raw_odds, errores_odds = parsear_raw_odds_desde_json(fixture_json)
    resultado.raw_odds = raw_odds
    resultado.errores_odds = errores_odds
    resultado.outcomes_traducidos = traducir_fixture(raw_odds)

    partidos, refs, errores_mh = parsear_recent_results_desde_json(fixture_json)
    resultado.raw_match_history = partidos
    resultado.fixture_match_history_refs = refs
    resultado.errores_match_history = errores_mh

    records, standings, errores_tr = parsear_team_records_desde_json(fixture_json)
    resultado.team_record_summaries = records
    resultado.team_standings_rows = standings
    resultado.errores_team_records = errores_tr

    resultado.fixture_metadata = parsear_fixture_metadata(fixture_json.get("recent_results"))

    return resultado


def persistir(resultado: ResultadoIngesta) -> None:
    """
    Persiste el resultado en SQLite (ver persistencia/sqlite_store.py — decisión
    de backend documentada en beet_ingesta_estado_v2.md). Un archivo .db por
    fixture (ver crear_engine), nombrado con resultado.fixture_id -- no hace
    falta pasar ruta, cada partido sabe dónde le toca vivir. Upsert en las 5
    tablas identificables por clave natural; validation_errors es
    append-only a propósito (cada corrida puede sumar errores nuevos aunque
    el fixture ya se haya procesado antes).
    """
    engine = persistencia_sqlite.crear_engine(resultado.fixture_id)
    persistencia_sqlite.guardar_resultado(engine, resultado)


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Orquesta los 3 parsers de ingesta cruda sobre un fixture ya descargado.")
    ap.add_argument("fixture_path", help="Ruta al JSON del fixture (ej. fixture_19664045.json)")
    ap.add_argument("--db", action="store_true",
                     help="Si se pasa, persiste en SQLite tras procesar "
                          "(un archivo beet_sc/db/<fixture_id>.db por partido)")
    args = ap.parse_args()

    with open(args.fixture_path, encoding="utf-8") as f:
        fixture_json = json.load(f)

    r = procesar_fixture(fixture_json)

    print(f"Fixture {r.fixture_id}")
    print(f"  raw_odds: {len(r.raw_odds)} filas, {len(r.outcomes_traducidos)} outcomes traducidos, "
          f"{len(r.errores_odds)} errores")
    print(f"  raw_match_history: {len(r.raw_match_history)} partidos únicos, "
          f"{len(r.fixture_match_history_refs)} refs, {len(r.errores_match_history)} errores")
    print(f"  team_records: {len(r.team_record_summaries)} summaries, "
          f"{len(r.team_standings_rows)} standings rows, {len(r.errores_team_records)} errores")
    print(f"  fixture_metadata: {'OK' if r.fixture_metadata else 'FALTANTE'}")
    print(f"  total errores de validación: {r.total_errores}")

    if args.db:
        persistir(r)
        print(f"  guardado en beet_sc/db/{r.fixture_id}.db")
