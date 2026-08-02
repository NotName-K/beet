"""
Los 5 modelos Pydantic de la capa de ingesta cruda (paso 3 del flujo, ver
sección 10 del diseño). Cada uno define CÓMO se guarda una pieza del
fixture, antes de que market_registry.py la traduzca a algo calculable.

No hay lógica de traducción de mercados acá — eso vive en market_registry.py
y special_markets.py. Estos modelos son solo la forma de la tabla + su
validación de forma (tipos, rangos, y en el caso de TeamStandingsRow, el
filtro de leakage).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# 1. RawOdds — una fila por outcome válido de un bookmaker
# ---------------------------------------------------------------------------

class RawOdds(BaseModel):
    """
    Una fila por outcome de un mercado, tal como llega de un bookmaker.
    Ver sección 4 del diseño.
    """
    fixture_id: int
    market_name: str
    display_rule: Optional[str] = None
    outcome_key: str
    outcome: str
    outcome_name: str
    bookmaker: str
    decimal_odds: float = Field(gt=1.0)  # una cuota decimal válida siempre es > 1.0
    # Optional porque SPORTMONKSBET365 nunca lo reporta — comportamiento
    # normal de esa casa, no dato corrupto (ver sección 4).
    external_bet_id: Optional[str] = None
    # Se guarda tal cual pero NO es confiable para identificar local/
    # visitante — no usar en ningún cálculo aguas abajo (ver sección 4).
    team_id: Optional[int] = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# 2. RawMatchHistory — un partido histórico, una sola fila (PK match_id)
# ---------------------------------------------------------------------------

# ingestion_models.py — reemplazar la clase RawMatchHistory completa

class RawMatchHistory(BaseModel):
    """
    Un partido histórico, guardado una sola vez (PK match_id) sin importar
    en cuántos fixtures actuales aparezca como referencia. NO incluye
    result/ht_result — esos son relativos al fixture que consulta, no
    propiedad del partido en sí (ver FixtureMatchHistoryRef). Ver sección 4.

    Campos separados por local/visitante (corners, cards, shots) porque
    los mercados "Team X" de la whitelist (Team Corners, Team Cards, Team
    shots on target) necesitan comparar cada lado por separado contra el
    histórico — un total combinado no alcanza para calibrarlos.
    """
    match_id: int
    season_id: int
    date: datetime
    status: str
    is_completed: bool
    slug: str

    league_id: int
    league_name: str
    league_slug: str
    country_name: str

    home_team_id: int
    home_team_name: str
    home_team_slug: str
    away_team_id: int
    away_team_name: str
    away_team_slug: str

    referee_id: Optional[int] = None
    referee_name: Optional[str] = None

    # Siempre presentes (verificado en 3 fixtures, sección 4 del diseño)
    home_goals_ht: int
    away_goals_ht: int
    home_goals_ft: int
    away_goals_ft: int

    # Corners totales, siempre presentes
    home_corners: int
    away_corners: int

    # Por mitad — disponibilidad depende de la liga de origen, homogénea
    # dentro de un mismo fixture (ver sección 2.2)
    home_corners_1h: Optional[int] = None
    away_corners_1h: Optional[int] = None
    home_corners_2h: Optional[int] = None
    away_corners_2h: Optional[int] = None

    # Cards completas, se guardan las tres por lado
    home_yellows: int
    away_yellows: int
    home_reds: int
    away_reds: int
    home_yellow_reds: int
    away_yellow_reds: int

    # Sin mercado de odds asociado hoy; valor de calibración futura
    home_total_shots: int
    away_total_shots: int

    # Alimenta Total/Team shots on target
    home_shots_on_target: int
    away_shots_on_target: int

    ingested_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# 3. FixtureMatchHistoryRef — la relación fixture actual <-> partido histórico
# ---------------------------------------------------------------------------

class SourceBlock(str, Enum):
    """Los 5 bloques de origen dentro de recent_results (sección 2)."""
    HEAD_TO_HEAD = "headToHead"
    RECENT_HOME_RESULTS = "recentHomeResults"
    RECENT_HOME_ALL_RESULTS = "recentHomeAllResults"
    RECENT_AWAY_RESULTS = "recentAwayResults"
    RECENT_AWAY_ALL_RESULTS = "recentAwayAllResults"


class FixtureMatchHistoryRef(BaseModel):
    """
    PK compuesta (current_fixture_id, match_id, source_block). result/
    ht_result viven acá y no en RawMatchHistory porque son relativos al
    equipo de referencia del fixture actual, no propiedad del partido
    histórico (confirmado con 0 discrepancias en 80 registros — ver
    sección 2). Ausentes en headToHead por diseño de la fuente.
    """
    current_fixture_id: int
    match_id: int
    source_block: SourceBlock
    result: Optional[Literal["W", "D", "L"]] = None
    ht_result: Optional[Literal["W", "D", "L"]] = None

    @model_validator(mode="after")
    def head_to_head_sin_resultado(self) -> "FixtureMatchHistoryRef":
        """headHead nunca trae result/ht_result — si aparecen, es un cambio
        de la fuente que merece revisión manual, no fallar silenciosamente."""
        if self.source_block == SourceBlock.HEAD_TO_HEAD and (self.result or self.ht_result):
            raise ValueError(
                "headToHead no debería traer result/ht_result — "
                "la fuente pudo haber cambiado, revisar antes de aceptar este dato"
            )
        return self


# ---------------------------------------------------------------------------
# 4. ValidationErrors — cola de fallos de validación
# ---------------------------------------------------------------------------

class ValidationErrorStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"


class ValidationErrors(BaseModel):
    """
    Un outcome/registro que no pasó la validación. raw_payload se guarda
    completo (no solo el mensaje) para poder reprocesar sin volver a pedir
    el fixture a la fuente. status permite que un script separado
    reprocese los "pending" contra el validador actual sin mezclar
    fallos de bugs ya corregidos con errores de datos reales (sección 3).
    """
    fixture_id: int
    market_name: Optional[str] = None
    outcome_key: Optional[str] = None
    error: str
    raw_payload: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: ValidationErrorStatus = ValidationErrorStatus.PENDING


# ---------------------------------------------------------------------------
# 5. TeamRecords — dos formas bajo la misma sección (ver sección 7)
# ---------------------------------------------------------------------------

class TeamRecordContext(str, Enum):
    HOME = "home"
    AWAY = "away"
    OVERALL = "overall"


class TeamRecordSummary(BaseModel):
    """
    Los 4 records simples (home/awayTeam[Home/Away/Overall]Record) —
    un objeto chico y plano por equipo x contexto. Ver sección 7.
    """
    fixture_id: int
    team_id: int
    context: TeamRecordContext
    position: Optional[int] = None
    played: Optional[int] = None
    won: Optional[int] = None
    draw: Optional[int] = None
    lost: Optional[int] = None
    goals_for: Optional[int] = None
    goals_against: Optional[int] = None
    goal_diff: Optional[int] = None
    points: Optional[int] = None
    points_per_game: Optional[float] = None
    form: list[str] = Field(default_factory=list)


class TeamStandingsRow(BaseModel):
    """
    Una fila de la tabla de posiciones completa (home/awayTeamResultsWith-
    Standings). Ver sección 7.

    NO incluye home_results/away_results: se confirmó (fixture_19664045,
    Emelec vs Aucas — Liga Pro Ecuador) que esos campos no son el historial
    propio del equipo de la fila, sino el último enfrentamiento de ese
    equipo contra el equipo ANCLA del fixture (home_results = partido
    donde el ancla jugó de local, away_results = donde jugó de visita),
    con el campo result calculado desde la perspectiva del ANCLA, no de
    la fila. Confirmado sistemático: 31/31 entradas verificables contra
    recent_results (venue + result) vienen invertidas desde la
    perspectiva del equipo de la fila. Redundante además con
    recent_results.headToHead. Se descarta también toda la variante
    Stage (mismo problema, mismos partidos, más campos). Por eso ya no
    hace falta fixture_date ni saneo de leakage acá — ese problema
    desapareció junto con el campo que lo causaba.
    """
    perspective: Literal["home", "away"]
    team_id: int
    position: Optional[int] = None
    played: Optional[int] = None
    points: Optional[int] = None


def construir_team_standings_row(data: dict) -> TeamStandingsRow:
    """
    Punto de entrada recomendado para construir TeamStandingsRow, en vez de
    TeamStandingsRow(**data) directo — se mantiene como función (en vez de
    llamar al constructor directo desde el parser) por si en el futuro
    hace falta lógica de saneo adicional acá, igual que en el resto del
    módulo.
    """
    return TeamStandingsRow.model_validate(data)


if __name__ == "__main__":
    # Smoke test 1: RawOdds con external_bet_id ausente (caso SPORTMONKSBET365)
    o = RawOdds(
        fixture_id=19722821, market_name="Result", outcome_key="RESULT_HOME_WIN",
        outcome="RESULT_HOME_WIN", outcome_name="Aberdeen", bookmaker="SPORTMONKSBET365",
        decimal_odds=1.85,
    )
    print("RawOdds ok:", o.external_bet_id is None)

    
    # Smoke test 2: RawMatchHistory con campos completos (liga con Corners1h/2h)
    m = RawMatchHistory(
        match_id=123, season_id=2025, date=datetime(2026, 7, 1),
        status="FT", is_completed=True, slug="team-a-vs-team-b",
        league_id=501, league_name="Premiership", league_slug="premiership",
        country_name="Scotland",
        home_team_id=1, home_team_name="Team A", home_team_slug="team-a",
        away_team_id=2, away_team_name="Team B", away_team_slug="team-b",
        home_goals_ht=1, away_goals_ht=0, home_goals_ft=2, away_goals_ft=1,
        home_corners=5, away_corners=3,
        home_yellows=2, away_yellows=1, home_reds=0, away_reds=0,
        home_yellow_reds=0, away_yellow_reds=0,
        home_total_shots=10, away_total_shots=8,
        home_shots_on_target=4, away_shots_on_target=3,
    )
    print("RawMatchHistory ok:", m.home_corners_1h is None)

    # Smoke test 3: FixtureMatchHistoryRef rechaza result en headToHead
    try:
        FixtureMatchHistoryRef(
            current_fixture_id=1, match_id=2, source_block=SourceBlock.HEAD_TO_HEAD, result="W"
        )
        print("FALLO: debería haber rechazado result en headToHead")
    except ValueError:
        print("FixtureMatchHistoryRef ok: rechazó result en headToHead")

    # Smoke test 4: ValidationErrors default status
    ve = ValidationErrors(fixture_id=1, error="cuota negativa", raw_payload={"x": 1})
    print("ValidationErrors ok:", ve.status == ValidationErrorStatus.PENDING)

    # Smoke test 5: TeamStandingsRow ya no persiste home_results/away_results
    # (descartados por el hallazgo de fixture_19664045, ver docstring de la clase)
    row_data = {"perspective": "away", "team_id": 99, "position": 5, "played": 20, "points": 30}
    row = construir_team_standings_row(row_data)
    print("TeamStandingsRow ok:", row.position == 5 and not hasattr(row, "away_results"))
