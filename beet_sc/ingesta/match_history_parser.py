from datetime import datetime, timezone
from typing import Optional

from pydantic_core import ValidationError

from modelos import (
    RawMatchHistory, FixtureMatchHistoryRef, SourceBlock, ValidationErrors,
    FixtureMetadata,
)

BLOQUES = {
    "headToHead": SourceBlock.HEAD_TO_HEAD,
    "recentHomeResults": SourceBlock.RECENT_HOME_RESULTS,
    "recentHomeAllResults": SourceBlock.RECENT_HOME_ALL_RESULTS,
    "recentAwayResults": SourceBlock.RECENT_AWAY_RESULTS,
    "recentAwayAllResults": SourceBlock.RECENT_AWAY_ALL_RESULTS,
}


def _epoch_ms_a_datetime(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def parsear_recent_results_desde_json(
    fixture_json: dict,
) -> tuple[list[RawMatchHistory], list[FixtureMatchHistoryRef], list[ValidationErrors]]:
    """
    Recorre fixture_json['recent_results'] (los 5 bloques) y construye:

    - RawMatchHistory: una fila por match_id ÚNICO — el mismo partido
      histórico puede repetirse entre bloques (ej. headToHead y
      recentHomeResults si el rival ya jugó contra el local recientemente),
      por eso se deduplica por match_id (dict, no lista) en vez de insertar
      una vez por bloque.
    - FixtureMatchHistoryRef: una fila por (current_fixture_id, match_id,
      source_block) — acá SÍ se guarda una vez por bloque, porque result/
      ht_result son relativos a qué bloque (y por lo tanto qué equipo de
      referencia) se está mirando.

    Nota leakage (ver diseño, sección de raw_match_history): si el propio
    fixture aparece autorreferenciado en su recent_results, se guarda tal
    cual en ambas tablas — NO se filtra acá a propósito. El filtro
    match_id != current_fixture_id se aplica después, sobre
    fixture_match_history_refs, al momento del backtest.
    """
    current_fixture_id = fixture_json["external_id"]
    recent_results = fixture_json["recent_results"]

    partidos: dict[int, RawMatchHistory] = {}
    refs: list[FixtureMatchHistoryRef] = []
    errores: list[ValidationErrors] = []

    for json_key, source_block in BLOQUES.items():
        for m in recent_results.get(json_key, []):
            match_id = m.get("id")
            liga = m.get("league") or {}
            pais = liga.get("country") or {}
            equipo_local = m.get("homeTeam") or {}
            equipo_visitante = m.get("awayTeam") or {}
            arbitro = m.get("referee") or {}

            if match_id not in partidos:
                try:
                    partidos[match_id] = RawMatchHistory(
                        match_id=match_id,
                        season_id=m.get("seasonId"),
                        date=_epoch_ms_a_datetime(m.get("date")),
                        status=m.get("status"),
                        is_completed=m.get("isCompleted"),
                        slug=m.get("slug"),
                        league_id=liga.get("id"),
                        league_name=liga.get("name"),
                        league_slug=liga.get("slug"),
                        country_name=pais.get("name"),
                        home_team_id=equipo_local.get("id"),
                        home_team_name=equipo_local.get("name"),
                        home_team_slug=equipo_local.get("slug"),
                        away_team_id=equipo_visitante.get("id"),
                        away_team_name=equipo_visitante.get("name"),
                        away_team_slug=equipo_visitante.get("slug"),
                        referee_id=arbitro.get("id"),
                        referee_name=arbitro.get("name"),
                        home_goals_ht=m.get("homeGoalsHt"),
                        away_goals_ht=m.get("awayGoalsHt"),
                        home_goals_ft=m.get("homeGoalsFt"),
                        away_goals_ft=m.get("awayGoalsFt"),
                        home_corners=m.get("homeCorners"),
                        away_corners=m.get("awayCorners"),
                        home_corners_1h=m.get("homeCorners1h"),
                        away_corners_1h=m.get("awayCorners1h"),
                        home_corners_2h=m.get("homeCorners2h"),
                        away_corners_2h=m.get("awayCorners2h"),
                        home_yellows=m.get("homeYellows"),
                        away_yellows=m.get("awayYellows"),
                        home_reds=m.get("homeReds"),
                        away_reds=m.get("awayReds"),
                        home_yellow_reds=m.get("homeYellowReds"),
                        away_yellow_reds=m.get("awayYellowReds"),
                        home_total_shots=m.get("homeTotalShots"),
                        away_total_shots=m.get("awayTotalShots"),
                        home_shots_on_target=m.get("homeShotsOnTarget"),
                        away_shots_on_target=m.get("awayShotsOnTarget"),
                    )
                except Exception as e:
                    errores.append(ValidationErrors(
                        fixture_id=current_fixture_id,
                        market_name=None,
                        outcome_key=f"{json_key}:{match_id}",
                        error=str(e),
                        raw_payload=m,
                    ))
                    continue  # sin RawMatchHistory válido, no generamos el ref

            try:
                refs.append(FixtureMatchHistoryRef(
                    current_fixture_id=current_fixture_id,
                    match_id=match_id,
                    source_block=source_block,
                    result=m.get("result"),
                    ht_result=m.get("htResult"),
                ))
            except Exception as e:
                errores.append(ValidationErrors(
                    fixture_id=current_fixture_id,
                    market_name=None,
                    outcome_key=f"{json_key}:{match_id}:ref",
                    error=str(e),
                    raw_payload=m,
                ))

    return list(partidos.values()), refs, errores

def _elegir_flag_url(country: dict) -> Optional[str]:
    """
    country.code y country.flagUrl están intercambiados entre endpoints
    (confirmado: en standings.league.country vienen en un orden, en
    recent_results.fixture.league.country en el orden inverso). En vez de
    confiar en el nombre del campo, se elige por sufijo de URL: preferimos
    .svg si existe, si no el que haya.
    """
    candidatos = [country.get("code"), country.get("flagUrl")]
    candidatos = [c for c in candidatos if c]
    for c in candidatos:
        if c.endswith(".svg"):
            return c
    return candidatos[0] if candidatos else None


def parsear_fixture_metadata(recent_results_json: Optional[dict]) -> Optional[FixtureMetadata]:
    """
    Extrae la metadata del fixture actual (recent_results.fixture): logos,
    país, campeonato, árbitro. Devuelve None si recent_results falló en la
    descarga o no trae el bloque fixture (falla estructural, no se guarda
    en validation_errors porque no es un outcome individual).
    """
    if not recent_results_json:
        return None

    fixture = recent_results_json.get("fixture")
    if not fixture:
        return None

    league = fixture.get("league") or {}
    country = league.get("country") or {}
    home_team = fixture.get("homeTeam") or {}
    away_team = fixture.get("awayTeam") or {}
    referee = fixture.get("referee") or {}

    try:
        return FixtureMetadata(
            fixture_id=fixture["id"],
            league_id=league["id"],
            league_name=league["name"],
            league_slug=league["slug"],
            league_logo_url=league.get("logoUrl"),
            country_name=country.get("name"),
            country_slug=country.get("slug"),
            country_flag_url=_elegir_flag_url(country),
            kickoff_date=_epoch_ms_a_datetime(fixture["date"]),
            home_team_id=home_team["id"],
            home_team_name=home_team["name"],
            home_team_slug=home_team["slug"],
            home_team_logo=home_team.get("logo"),
            away_team_id=away_team["id"],
            away_team_name=away_team["name"],
            away_team_slug=away_team["slug"],
            away_team_logo=away_team.get("logo"),
            season_id=fixture["seasonId"],
            status=fixture["status"],
            referee_id=referee.get("id"),
            referee_name=referee.get("name"),
            referee_slug=referee.get("slug"),
        )
    except (KeyError, ValidationError) as e:
        print(f"    [fixture-metadata] ERROR parseando: {e}")
        return None
    
if __name__ == "__main__":
    import json

    from pathlib import Path
    _fixture_path = Path(__file__).resolve().parent.parent / "fixtures_test" / "fixture_19664045.json"
    with open(_fixture_path) as f:
        fixture_json = json.load(f)

    partidos, refs, errores = parsear_recent_results_desde_json(fixture_json)
    print(f"{len(partidos)} partidos únicos en RawMatchHistory")
    print(f"{len(refs)} filas en FixtureMatchHistoryRef")
    print(f"{len(errores)} errores de validación")

    # Confirmar el caso de leakage: ¿aparece el propio fixture como match_id?
    current_id = fixture_json["external_id"]
    self_refs = [r for r in refs if r.match_id == current_id]
    print(f"\nLeakage — refs donde match_id == current_fixture_id ({current_id}): {len(self_refs)}")
    for r in self_refs:
        print(f"  source_block={r.source_block.value:24s} result={r.result} ht_result={r.ht_result}")

    # Distribución por source_block
    from collections import Counter
    print("\nRefs por source_block:", dict(Counter(r.source_block.value for r in refs)))

    if errores:
        print("\nErrores de validación:")
        for e in errores:
            print(f"  {e.outcome_key}: {e.error}")