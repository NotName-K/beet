"""
sqlite_store.py (ex persistencia_sqlite.py)
Capa de persistencia SQLite para la ingesta cruda. Un archivo por tabla
Pydantic de modelos.py (carpeta ingesta/), sin lógica de mercados ni de
dominio acá — esto solo guarda lo que los parsers ya validaron.

Usa SQLAlchemy Core (no ORM) a propósito: los modelos "reales" ya son los
Pydantic de modelos.py — no tiene sentido duplicarlos como clases
ORM también. SQLAlchemy acá es solo capa de tabla + upsert.

Backend: SQLite (decisión de la sesión, ver beet_ingesta_estado_v2.md).
Migrar a Postgres después, si hace falta, es cuestión de cambiar el
connection string — el resto de este módulo no debería tener que tocarse
(create_engine con otra URL, INSERT...ON CONFLICT existe también en
Postgres vía sqlalchemy.dialects.postgresql.insert).
"""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, MetaData, String,
    Table, Text, UniqueConstraint, create_engine, inspect, text,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

metadata = MetaData()

# ---------------------------------------------------------------------------
# 1. raw_odds — sin PK natural en el modelo Pydantic; se usa id autoincrement
#    + unique constraint para que reprocesar el mismo fixture actualice en
#    vez de duplicar filas.
# ---------------------------------------------------------------------------
raw_odds = Table(
    "raw_odds", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("fixture_id", Integer, nullable=False, index=True),
    Column("market_name", String, nullable=False),
    Column("display_rule", String),
    Column("outcome_key", String, nullable=False),
    Column("outcome", String, nullable=False),
    Column("outcome_name", String, nullable=False),
    Column("bookmaker", String, nullable=False),
    Column("decimal_odds", Float, nullable=False),
    Column("external_bet_id", String),
    Column("team_id", Integer),
    Column("ingested_at", DateTime, nullable=False),
    UniqueConstraint("fixture_id", "market_name", "outcome_key", "bookmaker",
                      name="uq_raw_odds_identidad"),
)
# ON CONFLICT en SQLite necesita un índice único real que matchee
# index_elements del upsert — de ahí la UniqueConstraint explícita arriba
# (a diferencia de las demás tablas, acá la identidad no es la PK).

# ---------------------------------------------------------------------------
# 2. raw_match_history — PK natural: match_id (mismo partido puede llegar
#    referenciado desde muchos fixtures distintos, se guarda una sola vez).
# ---------------------------------------------------------------------------
raw_match_history = Table(
    "raw_match_history", metadata,
    Column("match_id", Integer, primary_key=True),
    Column("season_id", Integer, nullable=False),
    Column("date", DateTime, nullable=False),
    Column("status", String, nullable=False),
    Column("is_completed", Boolean, nullable=False),
    Column("slug", String, nullable=False),
    Column("league_id", Integer, nullable=False),
    Column("league_name", String, nullable=False),
    Column("league_slug", String, nullable=False),
    Column("country_name", String, nullable=False),
    Column("home_team_id", Integer, nullable=False),
    Column("home_team_name", String, nullable=False),
    Column("home_team_slug", String, nullable=False),
    Column("away_team_id", Integer, nullable=False),
    Column("away_team_name", String, nullable=False),
    Column("away_team_slug", String, nullable=False),
    Column("referee_id", Integer),
    Column("referee_name", String),
    Column("home_goals_ht", Integer, nullable=False),
    Column("away_goals_ht", Integer, nullable=False),
    Column("home_goals_ft", Integer, nullable=False),
    Column("away_goals_ft", Integer, nullable=False),
    Column("home_corners", Integer, nullable=False),
    Column("away_corners", Integer, nullable=False),
    Column("home_corners_1h", Integer),
    Column("away_corners_1h", Integer),
    Column("home_corners_2h", Integer),
    Column("away_corners_2h", Integer),
    Column("home_yellows", Integer, nullable=False),
    Column("away_yellows", Integer, nullable=False),
    Column("home_reds", Integer, nullable=False),
    Column("away_reds", Integer, nullable=False),
    Column("home_yellow_reds", Integer, nullable=False),
    Column("away_yellow_reds", Integer, nullable=False),
    Column("home_total_shots", Integer, nullable=False),
    Column("away_total_shots", Integer, nullable=False),
    Column("home_shots_on_target", Integer, nullable=False),
    Column("away_shots_on_target", Integer, nullable=False),
    Column("ingested_at", DateTime, nullable=False),
)

# ---------------------------------------------------------------------------
# 3. fixture_match_history_refs — PK compuesta tal como documenta el modelo
# ---------------------------------------------------------------------------
fixture_match_history_refs = Table(
    "fixture_match_history_refs", metadata,
    Column("current_fixture_id", Integer, primary_key=True),
    Column("match_id", Integer, ForeignKey("raw_match_history.match_id"), primary_key=True),
    Column("source_block", String, primary_key=True),
    Column("result", String),
    Column("ht_result", String),
)

# ---------------------------------------------------------------------------
# 4. validation_errors — log append-only, sin upsert (cada corrida puede
#    generar errores nuevos aunque el fixture ya se haya procesado antes)
# ---------------------------------------------------------------------------
validation_errors = Table(
    "validation_errors", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("fixture_id", Integer, nullable=False, index=True),
    Column("market_name", String),
    Column("outcome_key", String),
    Column("error", Text, nullable=False),
    Column("raw_payload", Text, nullable=False),  # JSON serializado
    Column("timestamp", DateTime, nullable=False),
    Column("status", String, nullable=False, default="pending"),
)

# ---------------------------------------------------------------------------
# 5. team_record_summaries — PK compuesta (fixture_id, team_id, context)
# ---------------------------------------------------------------------------
team_record_summaries = Table(
    "team_record_summaries", metadata,
    Column("fixture_id", Integer, primary_key=True),
    Column("team_id", Integer, primary_key=True),
    Column("context", String, primary_key=True),
    Column("position", Integer),
    Column("played", Integer),
    Column("won", Integer),
    Column("draw", Integer),
    Column("lost", Integer),
    Column("goals_for", Integer),
    Column("goals_against", Integer),
    Column("goal_diff", Integer),
    Column("points", Integer),
    Column("points_per_game", Float),
    Column("form", String),  # JSON serializado (list[str])
)

# ---------------------------------------------------------------------------
# 6. team_standings_rows — PK compuesta (fixture_id, perspective, team_id)
# ---------------------------------------------------------------------------
team_standings_rows = Table(
    "team_standings_rows", metadata,
    Column("fixture_id", Integer, primary_key=True),
    Column("perspective", String, primary_key=True),
    Column("team_id", Integer, primary_key=True),
    Column("position", Integer),
    Column("played", Integer),
    Column("points", Integer),
)


# ---------------------------------------------------------------------------
# 7. fixture_metadata — metadata del fixture actual en sí (no de partidos
#    históricos): logos de equipo/liga, país, campeonato, árbitro. A
#    diferencia de raw_match_history (que también guarda league_id/
#    country_name/etc. pero por cada PARTIDO HISTÓRICO referenciado), esta
#    tabla es una fila por fixture_id -- el objeto recent_results.fixture
#    en sí, que hasta ahora se descargaba pero no se persistía en ningún
#    lado. Necesaria para el visor (logos + árbitro + país/campeonato).
# ---------------------------------------------------------------------------
fixture_metadata = Table(
    "fixture_metadata", metadata,
    Column("fixture_id", Integer, primary_key=True),
    Column("season_id", Integer, nullable=False),
    Column("kickoff_date", DateTime, nullable=False),
    Column("status", String, nullable=False),
    Column("league_id", Integer, nullable=False),
    Column("league_name", String, nullable=False),
    Column("league_slug", String, nullable=False),
    Column("league_logo_url", String),
    Column("country_name", String),
    Column("country_slug", String),
    Column("country_flag_url", String),
    Column("home_team_id", Integer, nullable=False),
    Column("home_team_name", String, nullable=False),
    Column("home_team_slug", String, nullable=False),
    Column("home_team_logo", String),
    Column("away_team_id", Integer, nullable=False),
    Column("away_team_name", String, nullable=False),
    Column("away_team_slug", String, nullable=False),
    Column("away_team_logo", String),
    Column("referee_id", Integer),
    Column("referee_name", String),
    Column("referee_slug", String),
    Column("ingested_at", DateTime, nullable=False),
)


# ---------------------------------------------------------------------------
# 8. fixture_pipeline_status — tracking del avance de cada fixture en el
#    pipeline completo (scraping -> ingesta -> persistencia), separado de
#    los datos en sí. Ver beet_unificacion_flujo.md.
#
#    Quién la escribe: a propósito NO se escribe automáticamente desde
#    guardar_resultado() ni desde orquestar_ingesta.py -- eso acoplaría los
#    3 scripts existentes (scraping/ingesta/persistencia) a la idea de
#    tracking. La escribe pipeline/orquestador.py (el orquestador de más
#    alto nivel, todavía no construido), llamando a las funciones
#    marcar_*/obtener_estado_pipeline de más abajo en cada paso.
# ---------------------------------------------------------------------------

ESTADOS_PIPELINE = (
    "pendiente", "scraped", "ingested", "persisted",
    "failed_scraping", "failed_ingesta", "failed_persistencia",
)

fixture_pipeline_status = Table(
    "fixture_pipeline_status", metadata,
    Column("fixture_id", Integer, primary_key=True),
    Column("scraped_at", DateTime),
    Column("ingested_at", DateTime),
    Column("persisted_at", DateTime),
    Column("status", String, nullable=False, default="pendiente"),
    # evita COUNT(*) contra validation_errors en cada carga del visor
    Column("validation_error_count", Integer, nullable=False, default=0),
    # motivo si status empieza con failed_ (excepción de infra, no error de
    # validación por outcome -- eso vive en validation_errors)
    Column("error_detail", Text),
    # Nullable a propósito: se completan recién en marcar_ingested (una vez
    # que hay RawOdds traducidos de donde sacarlos -- ver
    # pipeline/orquestador.py, mercado "Double Chance"/"HOME_WIN_OR_AWAY_WIN").
    # No existen para fixtures marcados solo failed_scraping, ni para los
    # trackeados antes de este campo (bases viejas, columna queda NULL).
    # Es display únicamente -- no reemplaza home_team_id/away_team_id, que
    # viven en team_records_parser.py y son la identidad real del equipo.
    Column("home_team_name", String),
    Column("away_team_name", String),
)


# Carpeta fija donde viven las bases -- separada del código para no mezclar
# datos con el repo. Se resuelve por la ubicación de ESTE archivo (mismo
# patrón que usa interfaz/visor.py con _RAIZ), NO por el cwd desde el que
# se invoque -- correr el pipeline desde otra carpeta (o que visor.bat
# haga `cd` a la raíz del proyecto) no debe crear una carpeta duplicada.
# Este módulo vive en beet_sc/persistencia/sqlite_store.py, así que
# .parent.parent da la raíz del proyecto (beet_sc/), y DB_DIR queda en
# beet_sc/db/ -- carpeta hermana de interfaz/, persistencia/, scraping/.
_RAIZ = Path(__file__).resolve().parent.parent
DB_DIR = _RAIZ / "db"


def _migrar_columnas_pipeline_status(engine: Engine) -> None:
    """
    ALTER TABLE aditivo para fixture_pipeline_status. create_all() (usado
    en crear_engine) solo crea TABLAS que faltan -- nunca agrega COLUMNAS
    nuevas a una tabla que ya existe en un .db viejo. Confirmado con un
    caso real: una .db persistida antes de agregar home_team_name/
    away_team_name pasaba a leerse como "nunca trackeado" en el visor
    (SELECT explota por columna inexistente, la excepción se traga
    silenciosamente en el caller). Se llama antes de leer O escribir esta
    tabla -- ver crear_engine (escritura) y obtener_estado_pipeline /
    listar_estados_pipeline* (lectura, que abren el engine directo sin
    pasar por crear_engine -- ver comentario en
    listar_estados_pipeline_multi sobre por qué no llaman a crear_engine).

    Idempotente y barato (una PRAGMA + 0 ALTER si ya está al día). Solo
    cubre fixture_pipeline_status por ahora -- es la única tabla a la que
    se le agregaron columnas después de haber .db en producción; si el
    día de mañana pasa lo mismo con otra tabla, generalizar esto a
    recibir la Table en vez de tenerla hardcodeada.
    """
    inspector = inspect(engine)
    if "fixture_pipeline_status" not in inspector.get_table_names():
        return  # no existe todavía -- create_all() la crea completa, nada que migrar
    existentes = {c["name"] for c in inspector.get_columns("fixture_pipeline_status")}
    faltantes = [c for c in fixture_pipeline_status.columns if c.name not in existentes]
    if not faltantes:
        return
    with engine.begin() as conn:
        for columna in faltantes:
            tipo_sql = columna.type.compile(dialect=engine.dialect)
            conn.execute(text(
                f'ALTER TABLE fixture_pipeline_status ADD COLUMN "{columna.name}" {tipo_sql}'
            ))


def crear_engine(fixture_id: int | str) -> Engine:
    """
    Crea (o abre) el engine de UN partido puntual y garantiza que las 7
    tablas existan en su archivo (idempotente).

    Un archivo .db por fixture, nombrado con su id (ej. 19735503.db),
    dentro de DB_DIR (creada si no existe) -- así cada partido queda
    aislado y es fácil ubicar/borrar/inspeccionar uno sin tocar los demás.
    Se pasa `fixture_id=":memory:"` para el smoke test, sin tocar disco.

    Importante: create_all() es aditivo -- solo crea las tablas que faltan,
    nunca borra ni pisa datos existentes. Reprocesar el mismo fixture hace
    upsert fila por fila (ver _upsert) sobre su propio archivo, así que
    correr el pipeline de nuevo sobre un fixture nunca sobreescribe el
    archivo completo, solo actualiza sus filas.
    """
    if fixture_id == ":memory:":
        db_path = ":memory:"
    else:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        db_path = DB_DIR / f"{fixture_id}.db"
    engine = create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)
    _migrar_columnas_pipeline_status(engine)
    return engine


def _upsert_pipeline_status(engine: Engine, fixture_id: int, **campos) -> None:
    """
    Upsert de una fila de fixture_pipeline_status. A diferencia de
    `_upsert` (usado por las 6 tablas de datos, donde cada fila siempre
    trae el set completo de columnas), acá cada llamada solo trae un
    subconjunto (ej. marcar_scraped solo trae scraped_at+status) -- por
    eso el UPDATE solo toca esas columnas explícitas, nunca las demás.
    Usar `_upsert` tal cual acá pisaría con NULL las columnas ya
    guardadas por una llamada anterior (ej. marcar_ingested borrando el
    scraped_at que había puesto marcar_scraped) -- confirmado con el
    smoke test antes de este fix.
    """
    fila = {"fixture_id": fixture_id, **campos}
    stmt = sqlite_insert(fixture_pipeline_status).values(fila)
    columnas_actualizables = {nombre: stmt.excluded[nombre] for nombre in campos}
    stmt = stmt.on_conflict_do_update(
        index_elements=["fixture_id"], set_=columnas_actualizables
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def marcar_scraped(engine: Engine, fixture_id: int, when: datetime | None = None) -> None:
    _upsert_pipeline_status(
        engine, fixture_id,
        scraped_at=when or datetime.utcnow(), status="scraped",
    )


def marcar_ingested(
    engine: Engine, fixture_id: int, when: datetime | None = None,
    home_team_name: str | None = None, away_team_name: str | None = None,
) -> None:
    """
    home_team_name/away_team_name son opcionales y solo para display en el
    visor (ver docstring de las columnas en fixture_pipeline_status) -- si
    no se pasan (o no se pudieron extraer, ver orquestador.py), quedan
    NULL y no rompe nada; el resto del pipeline no las usa para lógica.
    """
    campos = {"ingested_at": when or datetime.utcnow(), "status": "ingested"}
    if home_team_name is not None:
        campos["home_team_name"] = home_team_name
    if away_team_name is not None:
        campos["away_team_name"] = away_team_name
    _upsert_pipeline_status(engine, fixture_id, **campos)


def marcar_persisted(
    engine: Engine, fixture_id: int,
    validation_error_count: int = 0, when: datetime | None = None,
) -> None:
    _upsert_pipeline_status(
        engine, fixture_id,
        persisted_at=when or datetime.utcnow(), status="persisted",
        validation_error_count=validation_error_count,
    )


def marcar_failed(
    engine: Engine, fixture_id: int,
    etapa: str, error_detail: str,
) -> None:
    """
    etapa: "scraping" | "ingesta" | "persistencia" -- se traduce a
    status="failed_<etapa>". Cualquier otro valor rompe ruidosamente en vez
    de guardar un status inválido en silencio.
    """
    status = f"failed_{etapa}"
    if status not in ESTADOS_PIPELINE:
        raise ValueError(f"etapa desconocida: {etapa!r} (status resultante {status!r} no es válido)")
    _upsert_pipeline_status(engine, fixture_id, status=status, error_detail=error_detail)


def obtener_estado_pipeline(engine: Engine, fixture_id: int) -> dict | None:
    """Devuelve la fila de fixture_pipeline_status para un fixture, o None si nunca se trackeó."""
    _migrar_columnas_pipeline_status(engine)
    with engine.connect() as conn:
        row = conn.execute(
            fixture_pipeline_status.select().where(fixture_pipeline_status.c.fixture_id == fixture_id)
        ).mappings().first()
    return dict(row) if row else None


def listar_estados_pipeline(engine: Engine, fixture_ids: list[int] | None = None) -> list[dict]:
    """
    Devuelve todas las filas de fixture_pipeline_status, o solo las de
    `fixture_ids` si se pasa (ej. para el listado de fixtures del día que
    muestra el visor).
    """
    _migrar_columnas_pipeline_status(engine)
    with engine.connect() as conn:
        stmt = fixture_pipeline_status.select()
        if fixture_ids is not None:
            stmt = stmt.where(fixture_pipeline_status.c.fixture_id.in_(fixture_ids))
        rows = conn.execute(stmt).mappings().all()
    return [dict(r) for r in rows]


def listar_estados_pipeline_multi(fixture_ids: list[int]) -> dict[int, dict]:
    """
    Versión multi-archivo de `obtener_estado_pipeline`, para el visor: como
    ahora cada fixture vive en su propio .db (ver crear_engine), no hay un
    único engine que tenga el estado de todos. Recorre solo los fixture_ids
    pedidos y abre el archivo de cada uno EN DB_DIR SI YA EXISTE -- a
    propósito no llama a crear_engine (que crearía el archivo con las 7
    tablas vacías solo para consultar un fixture que nunca se procesó).
    Fixtures sin archivo todavía no aparecen en el dict devuelto (mismo
    significado que el None que devuelve obtener_estado_pipeline para un
    fixture nunca trackeado).
    """
    resultados: dict[int, dict] = {}
    for fixture_id in fixture_ids:
        ruta = DB_DIR / f"{fixture_id}.db"
        if not ruta.exists():
            continue
        engine = create_engine(f"sqlite:///{ruta}")
        estado = obtener_estado_pipeline(engine, fixture_id)
        if estado is not None:
            resultados[fixture_id] = estado
    return resultados


def _upsert(conn, tabla: Table, filas: list[dict], index_elements: list[str]):
    if not filas:
        return
    stmt = sqlite_insert(tabla).values(filas)
    columnas_actualizables = {
        c.name: stmt.excluded[c.name]
        for c in tabla.columns
        if c.name not in index_elements
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=index_elements, set_=columnas_actualizables
    )
    conn.execute(stmt)


def guardar_resultado(engine: Engine, resultado) -> None:
    """
    Persiste un ResultadoIngesta (ver orquestar_ingesta.py) en las 7 tablas
    de datos. Upsert en todo salvo validation_errors (append-only, ver
    docstring de la tabla) — reprocesar el mismo fixture actualiza en vez
    de duplicar. NO toca fixture_pipeline_status (ver docstring de esa
    tabla) — eso lo hace pipeline/orquestador.py después de llamar acá.
    """
    with engine.begin() as conn:
        _upsert(
            conn, raw_odds,
            [{
                "fixture_id": o.fixture_id, "market_name": o.market_name,
                "display_rule": o.display_rule, "outcome_key": o.outcome_key,
                "outcome": o.outcome, "outcome_name": o.outcome_name,
                "bookmaker": o.bookmaker, "decimal_odds": o.decimal_odds,
                "external_bet_id": o.external_bet_id, "team_id": o.team_id,
                "ingested_at": o.ingested_at,
            } for o in resultado.raw_odds],
            index_elements=["fixture_id", "market_name", "outcome_key", "bookmaker"],
        )

        _upsert(
            conn, raw_match_history,
            [{
                "match_id": m.match_id, "season_id": m.season_id, "date": m.date,
                "status": m.status, "is_completed": m.is_completed, "slug": m.slug,
                "league_id": m.league_id, "league_name": m.league_name,
                "league_slug": m.league_slug, "country_name": m.country_name,
                "home_team_id": m.home_team_id, "home_team_name": m.home_team_name,
                "home_team_slug": m.home_team_slug, "away_team_id": m.away_team_id,
                "away_team_name": m.away_team_name, "away_team_slug": m.away_team_slug,
                "referee_id": m.referee_id, "referee_name": m.referee_name,
                "home_goals_ht": m.home_goals_ht, "away_goals_ht": m.away_goals_ht,
                "home_goals_ft": m.home_goals_ft, "away_goals_ft": m.away_goals_ft,
                "home_corners": m.home_corners, "away_corners": m.away_corners,
                "home_corners_1h": m.home_corners_1h, "away_corners_1h": m.away_corners_1h,
                "home_corners_2h": m.home_corners_2h, "away_corners_2h": m.away_corners_2h,
                "home_yellows": m.home_yellows, "away_yellows": m.away_yellows,
                "home_reds": m.home_reds, "away_reds": m.away_reds,
                "home_yellow_reds": m.home_yellow_reds, "away_yellow_reds": m.away_yellow_reds,
                "home_total_shots": m.home_total_shots, "away_total_shots": m.away_total_shots,
                "home_shots_on_target": m.home_shots_on_target,
                "away_shots_on_target": m.away_shots_on_target,
                "ingested_at": m.ingested_at,
            } for m in resultado.raw_match_history],
            index_elements=["match_id"],
        )

        _upsert(
            conn, fixture_match_history_refs,
            [{
                "current_fixture_id": r.current_fixture_id, "match_id": r.match_id,
                "source_block": r.source_block.value, "result": r.result,
                "ht_result": r.ht_result,
            } for r in resultado.fixture_match_history_refs],
            index_elements=["current_fixture_id", "match_id", "source_block"],
        )

        errores = (
            resultado.errores_odds + resultado.errores_match_history
            + resultado.errores_team_records
        )
        if errores:
            conn.execute(validation_errors.insert(), [{
                "fixture_id": e.fixture_id, "market_name": e.market_name,
                "outcome_key": e.outcome_key, "error": e.error,
                "raw_payload": json.dumps(e.raw_payload, default=str),
                "timestamp": e.timestamp, "status": e.status.value,
            } for e in errores])

        _upsert(
            conn, team_record_summaries,
            [{
                "fixture_id": r.fixture_id, "team_id": r.team_id,
                "context": r.context.value, "position": r.position,
                "played": r.played, "won": r.won, "draw": r.draw, "lost": r.lost,
                "goals_for": r.goals_for, "goals_against": r.goals_against,
                "goal_diff": r.goal_diff, "points": r.points,
                "points_per_game": r.points_per_game,
                "form": json.dumps(r.form),
            } for r in resultado.team_record_summaries],
            index_elements=["fixture_id", "team_id", "context"],
        )

        _upsert(
            conn, team_standings_rows,
            [{
                "fixture_id": s.fixture_id, "perspective": s.perspective,
                "team_id": s.team_id, "position": s.position,
                "played": s.played, "points": s.points,
            } for s in resultado.team_standings_rows],
            index_elements=["fixture_id", "perspective", "team_id"],
        )

        fm = resultado.fixture_metadata
        _upsert(
            conn, fixture_metadata,
            [{
                "fixture_id": fm.fixture_id, "season_id": fm.season_id,
                "kickoff_date": fm.kickoff_date, "status": fm.status,
                "league_id": fm.league_id, "league_name": fm.league_name,
                "league_slug": fm.league_slug, "league_logo_url": fm.league_logo_url,
                "country_name": fm.country_name, "country_slug": fm.country_slug,
                "country_flag_url": fm.country_flag_url,
                "home_team_id": fm.home_team_id, "home_team_name": fm.home_team_name,
                "home_team_slug": fm.home_team_slug, "home_team_logo": fm.home_team_logo,
                "away_team_id": fm.away_team_id, "away_team_name": fm.away_team_name,
                "away_team_slug": fm.away_team_slug, "away_team_logo": fm.away_team_logo,
                "referee_id": fm.referee_id, "referee_name": fm.referee_name,
                "referee_slug": fm.referee_slug, "ingested_at": fm.ingested_at,
            }] if fm else [],
            index_elements=["fixture_id"],
        )

def obtener_historico_db(limite_dias: int = 7) -> list[dict]:
    """
    Escanea los archivos .db individuales recientes y extrae la metadata 
    de los partidos finalizados para el visor.
    """
    import time
    from datetime import datetime, timezone
    from sqlalchemy import create_engine, inspect, text
    
    resultados = []
    if not DB_DIR.exists():
        return []
        
    epoch_limite = (time.time() - (limite_dias * 86400)) * 1000
    
    for db_path in DB_DIR.glob("*.db"):
        try:
            engine = create_engine(f"sqlite:///{db_path}")
            # Forma segura y compatible (SQLAlchemy 2.0+) de verificar tablas
            if not inspect(engine).has_table("fixture_metadata"):
                continue
                
            with engine.connect() as conn:
                row = conn.execute(text(
                    "SELECT fixture_id, home_team_name, away_team_name, league_name, country_name, kickoff_date, status "
                    "FROM fixture_metadata"
                )).mappings().first()
                
                if not row:
                    continue
                    
                # 1. Extraer y normalizar fecha
                kickoff = row["kickoff_date"]
                if isinstance(kickoff, str):
                    try:
                        kickoff = datetime.fromisoformat(kickoff)
                    except ValueError:
                        # Fallback por si guardó sin la 'T' de ISO
                        kickoff = datetime.strptime(kickoff, "%Y-%m-%d %H:%M:%S.%f")
                
                if kickoff.tzinfo is None:
                    kickoff = kickoff.replace(tzinfo=timezone.utc)
                    
                epoch_ms = int(kickoff.timestamp() * 1000)
                
                # 2. Criterio de "Finalizado": Por status literal o si ya pasaron 4 horas del inicio
                ya_paso_tiempo = (time.time() * 1000) - epoch_ms > (2.5 * 3600 * 1000)
                es_status_final = str(row["status"]).lower() in ("finished", "ended", "finalizado", "ft")
                
                # Filtrar solo por ventana de días (ej. últimos 7 días) y que esté terminado
                if (epoch_ms > epoch_limite) and (ya_paso_tiempo or es_status_final):
                    resultados.append({
                        "external_id": row["fixture_id"],
                        "hometeam": row["home_team_name"],
                        "awayteam": row["away_team_name"],
                        "league_name": row["league_name"],
                        "country": row["country_name"],
                        "kickoff_epoch_ms": epoch_ms,
                        "es_copa": False
                    })
        except Exception as e:
            # Ahora si algo falla, lo escupe en consola para que sepamos por qué
            print(f"⚠️ Error leyendo histórico en {db_path.name}: {e}") 
            
    # Ordenar del más reciente al más antiguo
    resultados.sort(key=lambda x: x["kickoff_epoch_ms"], reverse=True)
    return resultados

if __name__ == "__main__":
    # Smoke test: crea un engine en memoria, confirma que las 8 tablas
    # existen, y ejercita el ciclo de vida completo de fixture_pipeline_status.
    engine = crear_engine(":memory:")
    print("Tablas creadas:", sorted(metadata.tables.keys()))

    fid = 999999
    print("Estado inicial:", obtener_estado_pipeline(engine, fid))

    marcar_scraped(engine, fid)
    marcar_ingested(engine, fid)
    marcar_persisted(engine, fid, validation_error_count=2)
    estado = obtener_estado_pipeline(engine, fid)
    print("Estado tras scraped->ingested->persisted:", estado)
    assert estado["status"] == "persisted"
    assert estado["validation_error_count"] == 2
    assert estado["scraped_at"] is not None and estado["persisted_at"] is not None

    marcar_failed(engine, fid, etapa="ingesta", error_detail="timeout de prueba")
    estado = obtener_estado_pipeline(engine, fid)
    print("Estado tras marcar_failed:", estado)
    assert estado["status"] == "failed_ingesta"
    assert estado["error_detail"] == "timeout de prueba"
    # persisted_at/scraped_at no se pisan al fallar un paso posterior --
    # upsert solo toca las columnas que se le pasan explícitamente
    assert estado["persisted_at"] is not None

    try:
        marcar_failed(engine, fid, etapa="algo_inventado", error_detail="x")
        print("FALLO: debería haber rechazado una etapa desconocida")
    except ValueError:
        print("OK: etapa desconocida rechazada")

    print("listar_estados_pipeline:", listar_estados_pipeline(engine, fixture_ids=[fid, 123]))
