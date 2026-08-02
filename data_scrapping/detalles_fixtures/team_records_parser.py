
import re

from ingestion_models import (
    TeamRecordSummary, TeamRecordContext, TeamStandingsRow,
    construir_team_standings_row, ValidationErrors,
)
from match_history_parser import parsear_recent_results_desde_json

_ORDINAL_RE = re.compile(r"^(\d+)")


def _parsear_position(raw):
    """'2nd' -> 2, '12th' -> 12. None si no matchea (no debería pasar)."""
    if raw is None:
        return None
    m = _ORDINAL_RE.match(str(raw))
    return int(m.group(1)) if m else None


_TYPE_A_CONTEXT = {
    "Home": TeamRecordContext.HOME,
    "Away": TeamRecordContext.AWAY,
    "All": TeamRecordContext.OVERALL,
}

_RECORDS_SIMPLES = {
    "homeTeamHomeRecord": "home",
    "homeTeamOverallRecord": "home",
    "awayTeamAwayRecord": "away",
    "awayTeamOverallRecord": "away",
}


def _resolver_ids(fixture_json: dict):
    """
    Deriva home_team_id y away_team_id reutilizando el parser de
    recent_results ya validado — el propio fixture aparece autorreferenciado
    ahí (leakage confirmado), así que sus datos son la fuente más confiable
    disponible sin adivinar el shape de recent_results['fixture']. Ya no se
    deriva fixture_date acá: dejó de hacer falta cuando se descartó el
    saneo de leakage de TeamStandingsRow (ver ingestion_models.py).
    """
    partidos, _, _ = parsear_recent_results_desde_json(fixture_json)
    fixture_id = fixture_json["external_id"]
    self_match = next((p for p in partidos if p.match_id == fixture_id), None)
    if self_match is None:
        raise ValueError(
            "No se encontró el fixture autorreferenciado en recent_results — "
            "no se puede derivar home/away team id sin él."
        )
    return self_match.home_team_id, self_match.away_team_id


def parsear_team_records_desde_json(fixture_json: dict):
    fixture_id = fixture_json["external_id"]
    tr = fixture_json["team_records"]
    home_team_id, away_team_id = _resolver_ids(fixture_json)

    records: list[TeamRecordSummary] = []
    errores: list[ValidationErrors] = []

    for json_key, lado in _RECORDS_SIMPLES.items():
        bloque = tr.get(json_key)
        if bloque is None:
            continue
        team_id = home_team_id if lado == "home" else away_team_id
        try:
            records.append(TeamRecordSummary(
                fixture_id=fixture_id,
                team_id=team_id,
                context=_TYPE_A_CONTEXT[bloque["type"]],
                position=_parsear_position(bloque.get("position")),
                played=bloque.get("played"),
                won=bloque.get("won"),
                draw=bloque.get("draw"),
                lost=bloque.get("lost"),
                goals_for=bloque.get("goalsFor"),
                goals_against=bloque.get("goalsAg"),
                goal_diff=bloque.get("goalDiff"),
                points=bloque.get("points"),
                points_per_game=bloque.get("pointsPerGame"),
                form=bloque.get("form") or [],
            ))
        except Exception as e:
            errores.append(ValidationErrors(
                fixture_id=fixture_id, market_name=None, outcome_key=json_key,
                error=str(e), raw_payload=bloque,
            ))

    standings: list[TeamStandingsRow] = []
    # NOTA: solo se leen las tablas principales (homeTeamResultsWithStandings /
    # awayTeamResultsWithStandings). Las variantes *Stage se descartan por
    # completo — mismo problema de homeResults/awayResults, con más campos.
    for tabla_key in ("homeTeamResultsWithStandings", "awayTeamResultsWithStandings"):
        for i, fila in enumerate(tr.get(tabla_key, [])):
            data = {
                "perspective": "home" if tabla_key.startswith("home") else "away",
                "team_id": fila.get("team", {}).get("id"),
                "position": _parsear_position(fila.get("position")),
                "played": fila.get("played"),
                "points": fila.get("points"),
            }
            try:
                standings.append(construir_team_standings_row(data))
            except Exception as e:
                errores.append(ValidationErrors(
                    fixture_id=fixture_id, market_name=None,
                    outcome_key=f"{tabla_key}[{i}]", error=str(e), raw_payload=fila,
                ))

    return records, standings, errores


if __name__ == "__main__":
    import json

    with open("fixture_19722821.json") as f:
        fixture_json = json.load(f)

    # Ya no se compara Stage vs tabla principal: se descarta directamente,
    # no se lee en absoluto (ver docstring de TeamStandingsRow).

    records, standings, errores = parsear_team_records_desde_json(fixture_json)

    print(f"\n{len(records)} TeamRecordSummary")
    for r in records:
        print(f"  team_id={r.team_id} context={r.context.value:8s} position={r.position} "
              f"played={r.played} points={r.points} form={r.form}")

    print(f"\n{len(standings)} TeamStandingsRow")
    for s in standings[:4]:
        print(f"  perspective={s.perspective:5s} team_id={s.team_id} "
              f"position={s.position} played={s.played} points={s.points}")

    print(f"\n{len(errores)} errores de validación")
    for e in errores:
        print(f"  {e.outcome_key}: {e.error}")