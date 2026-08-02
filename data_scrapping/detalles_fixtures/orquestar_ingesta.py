"""
Orquestador de la capa de ingesta cruda: encadena los 3 parsers ya
validados (odds -> raw_odds, recent_results -> raw_match_history,
team_records -> TeamRecordSummary/TeamStandingsRow) sobre un mismo
fixture y devuelve todo consolidado.

Nombre a propósito distinto de `run_pipeline.py`, que ya existe en el
repo y es el pipeline de OBTENCIÓN del JSON crudo desde el sitio web
(obtener_v -> build_comparativas -> build_fixture_details_final). Este
script arranca donde ese termina: toma un fixture_json ya descargado
y produce las filas RAW listas para persistir.

Persistencia: TODAVÍA NO DEFINIDA (SQLite/Postgres/archivos). Por ahora
`procesar_fixture` devuelve todo en memoria, consolidado en un solo
dict, listo para que quien decida el backend lo conecte sin tener que
tocar los 3 parsers de nuevo.
"""

from dataclasses import dataclass, field

from translator import parsear_raw_odds_desde_json, traducir_fixture
from match_history_parser import parsear_recent_results_desde_json
from team_records_parser import parsear_team_records_desde_json


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

    return resultado


def persistir(resultado: ResultadoIngesta) -> None:
    """
    STUB — backend de persistencia todavía no definido (SQLite/Postgres/
    archivos, pendiente de decisión). Por ahora solo confirma que el
    resultado está listo para guardarse; conectar acá cuando se elija
    el backend.
    """
    raise NotImplementedError(
        "Backend de persistencia pendiente de decidir (SQLite/Postgres/"
        "archivos) — procesar_fixture() ya deja todo listo en memoria."
    )


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Orquesta los 3 parsers de ingesta cruda sobre un fixture ya descargado.")
    ap.add_argument("fixture_path", help="Ruta al JSON del fixture (ej. fixture_19664045.json)")
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
    print(f"  total errores de validación: {r.total_errores}")
