"""
interfaz/datos_fixture.py
Lectura de datos desde staging y bases SQLite.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite_store

TZ_SITIO = timezone(timedelta(hours=-5))
DURACION_ESTIMADA = timedelta(hours=2, minutes=20)


def _cargar_staging(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _estado_partido(kickoff_epoch_ms) -> str:
    if kickoff_epoch_ms is None:
        return "pendiente"
    ahora = datetime.now(timezone.utc)
    kickoff = datetime.fromtimestamp(kickoff_epoch_ms / 1000, tz=timezone.utc)
    if ahora < kickoff:
        return "pendiente"
    if ahora < kickoff + DURACION_ESTIMADA:
        return "en_curso"
    return "finalizado"


def _periodo_partido(epoch_ms) -> str:
    """
    Calcula el periodo del partido en base al tiempo transcurrido desde el kickoff.
    No tiene límite superior: todo lo que pase de 60 min se considera 2H hasta que el 
    estado general del partido pase a 'finalizado'.
    """
    if not epoch_ms:
        return "1H"
        
    import time
    minutos_transcurridos = (time.time() * 1000 - epoch_ms) / 60000
    
    if minutos_transcurridos < 48:
        return "1H"
    elif minutos_transcurridos < 63:  # Damos 15 mins de descanso (48 a 63)
        return "HT"
    else:
        return "2H"  # De 63 en adelante, siempre será 2H.


def _hora_local(kickoff_epoch_ms) -> str:
    if kickoff_epoch_ms is None:
        return "??:??"
    dt = datetime.fromtimestamp(kickoff_epoch_ms / 1000, tz=TZ_SITIO)
    return dt.strftime("%I:%M %p").lstrip("0")


def _fecha_local(kickoff_epoch_ms) -> str:
    if kickoff_epoch_ms is None:
        return "--/--"
    return datetime.fromtimestamp(kickoff_epoch_ms / 1000, tz=TZ_SITIO).strftime("%d/%m")


def _leer_datos_medio_tarjeta(fixture_id: int) -> dict | None:
    """Lee cuotas 1X2 y URLs de logos para la tarjeta resumida."""
    ruta = sqlite_store.DB_DIR / f"{fixture_id}.db"
    if not ruta.exists():
        return None
    engine = sqlite_store.crear_engine(fixture_id)
    with engine.connect() as conn:
        meta = conn.execute(
            sqlite_store.fixture_metadata.select().where(
                sqlite_store.fixture_metadata.c.fixture_id == fixture_id
            )
        ).mappings().first()
        filas_odds = conn.execute(
            sqlite_store.raw_odds.select().where(
                (sqlite_store.raw_odds.c.fixture_id == fixture_id)
                & (sqlite_store.raw_odds.c.market_name == "Result")
            )
        ).mappings().all()
    cuotas = {}
    for fila in filas_odds:
        clave = {
            "RESULT_HOME_WIN": "1", "RESULT_DRAW": "X", "RESULT_AWAY_WIN": "2",
        }.get(fila["outcome"])
        if clave:
            cuotas[clave] = fila["decimal_odds"]
    return {
        "home_team_logo": meta["home_team_logo"] if meta else None,
        "away_team_logo": meta["away_team_logo"] if meta else None,
        "league_logo_url": meta["league_logo_url"] if meta else None,
        "league_name": meta["league_name"] if meta else None,
        "cuotas": cuotas,
    }


def _leer_datos_fixture(fixture_id: int) -> dict[str, list[dict]] | None:
    """Lee todas las tablas de un fixture persistido (solo lectura)."""
    ruta = sqlite_store.DB_DIR / f"{fixture_id}.db"
    if not ruta.exists():
        return None
    engine = sqlite_store.crear_engine(fixture_id)
    with engine.connect() as conn:
        metadata = [dict(r) for r in conn.execute(
            sqlite_store.fixture_metadata.select().where(
                sqlite_store.fixture_metadata.c.fixture_id == fixture_id
            )
        ).mappings().all()]
        odds = [dict(r) for r in conn.execute(
            sqlite_store.raw_odds.select().where(
                sqlite_store.raw_odds.c.fixture_id == fixture_id
            )
        ).mappings().all()]
        refs = [dict(r) for r in conn.execute(
            sqlite_store.fixture_match_history_refs.select().where(
                sqlite_store.fixture_match_history_refs.c.current_fixture_id == fixture_id
            )
        ).mappings().all()]
        match_ids = [r["match_id"] for r in refs]
        historial = []
        if match_ids:
            historial = [dict(r) for r in conn.execute(
                sqlite_store.raw_match_history.select().where(
                    sqlite_store.raw_match_history.c.match_id.in_(match_ids)
                )
            ).mappings().all()]
        errores = [dict(r) for r in conn.execute(
            sqlite_store.validation_errors.select().where(
                sqlite_store.validation_errors.c.fixture_id == fixture_id
            )
        ).mappings().all()]
        records = [dict(r) for r in conn.execute(
            sqlite_store.team_record_summaries.select().where(
                sqlite_store.team_record_summaries.c.fixture_id == fixture_id
            )
        ).mappings().all()]
        standings = [dict(r) for r in conn.execute(
            sqlite_store.team_standings_rows.select().where(
                sqlite_store.team_standings_rows.c.fixture_id == fixture_id
            )
        ).mappings().all()]
    return {
        "fixture_metadata": metadata,
        "raw_odds": odds,
        "raw_match_history": historial,
        "fixture_match_history_refs": refs,
        "validation_errors": errores,
        "team_record_summaries": records,
        "team_standings_rows": standings,
    }


def _info_partido(fixture_id: int, row: dict, datos: dict) -> dict:
    """Consolida la información de cabecera del partido."""
    info = {
        "home_id": None, "away_id": None,
        "home_name": row.get("hometeam", "?"),
        "away_name": row.get("awayteam", "?"),
        "marcador": None,
        "liga": row.get("league_name", "?"),
        "pais": row.get("country", "?"),
        "fecha": _hora_local(row.get("kickoff_epoch_ms")),
        "es_copa": bool(row.get("es_copa")),
        "referee": None,
        "home_logo_url": None, "away_logo_url": None, "flag_url": None,
    }
    meta = next(iter(datos.get("fixture_metadata", [])), None)
    if meta:
        info["home_id"] = meta.get("home_team_id")
        info["away_id"] = meta.get("away_team_id")
        info["home_name"] = meta.get("home_team_name") or info["home_name"]
        info["away_name"] = meta.get("away_team_name") or info["away_name"]
        info["liga"] = meta.get("league_name") or info["liga"]
        info["pais"] = meta.get("country_name") or info["pais"]
        info["referee"] = meta.get("referee_name")
        info["home_logo_url"] = meta.get("home_team_logo")
        info["away_logo_url"] = meta.get("away_team_logo")
        info["flag_url"] = meta.get("country_flag_url")

    propio = next(
        (h for h in datos.get("raw_match_history", []) if h.get("match_id") == fixture_id),
        None,
    )
    if propio:
        info["home_id"] = info["home_id"] or propio.get("home_team_id")
        info["away_id"] = info["away_id"] or propio.get("away_team_id")
        if not meta:
            info["home_name"] = propio.get("home_team_name") or info["home_name"]
            info["away_name"] = propio.get("away_team_name") or info["away_name"]
            info["liga"] = propio.get("league_name") or info["liga"]
            info["pais"] = propio.get("country_name") or info["pais"]
        gh, ga = propio.get("home_goals_ft"), propio.get("away_goals_ft")
        if gh is not None and ga is not None:
            info["marcador"] = (gh, ga)

    if info["home_id"] is None or info["away_id"] is None:
        for r in datos.get("team_record_summaries", []):
            if r.get("context") == "home":
                info["home_id"] = info["home_id"] or r.get("team_id")
            elif r.get("context") == "away":
                info["away_id"] = info["away_id"] or r.get("team_id")
    return info


def _partidos_por_bloque(datos: dict, source_block: str) -> list[dict]:
    match_ids = {
        r["match_id"] for r in datos.get("fixture_match_history_refs", [])
        if r.get("source_block") == source_block
    }
    historial = {h["match_id"]: h for h in datos.get("raw_match_history", [])}
    partidos = [historial[mid] for mid in match_ids if mid in historial]
    partidos.sort(key=lambda h: h.get("date") or "", reverse=True)
    return partidos


def _partidos_h2h(datos: dict) -> list[dict]:
    return _partidos_por_bloque(datos, "headToHead")


def _resultado_relativo(h: dict, home_id) -> str:
    gh, ga = h.get("home_goals_ft"), h.get("away_goals_ft")
    if gh is None or ga is None or gh == ga:
        return "draw"
    ganador_id = h.get("home_team_id") if gh > ga else h.get("away_team_id")
    return "home" if ganador_id == home_id else "away"


def _filtrar_h2h(partidos: list[dict], home_id, filtro: str, liga_actual: str) -> list[dict]:
    if filtro == "torneo":
        return [h for h in partidos if h.get("league_name") == liga_actual]
    if filtro == "local":
        return [h for h in partidos if h.get("home_team_id") == home_id]
    return partidos


def _forma_de(records: list[dict], team_id, contexto: str) -> list[str] | None:
    fila = next(
        (r for r in records if r.get("team_id") == team_id and r.get("context") == contexto),
        None,
    )
    if not fila:
        return None
    valor = fila.get("form")
    if isinstance(valor, str):
        try:
            return json.loads(valor)
        except (json.JSONDecodeError, TypeError):
            return None
    return valor