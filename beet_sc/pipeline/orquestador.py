"""
pipeline/orquestador.py
Orquestador de ALTO NIVEL de Beet: conecta las 3 etapas ya construidas por
separado -- scraping/ (obtener_v, obtener_fixture_detalle), ingesta/
(orquestar_ingesta) y persistencia/ (sqlite_store) -- para UN fixture o
para todos los fixtures "pendientes" de un día, y es el ÚNICO lugar que
escribe fixture_pipeline_status (ver decisión en beet_unificacion_flujo.md:
no acoplar los 3 scripts existentes a la idea de tracking).

No reemplaza a orquestar_scraping.py: ese sigue siendo el que genera
comparativas_staging.json (listado del día) vía obtener_fixtures_dia.py.
Este orquestador consume ese staging para "procesar_dia", y para un
fixture puntual llama directo a obtener_fixture_detalle.fetch_fixture_detail
(no hace falta pasar por el staging para reprocesar UN fixture ya conocido).

Distinción "no disponible aún" vs "error real" de scraping: TODAVÍA
ABIERTA en el diseño (ver beet_unificacion_flujo.md, sección Abierto).
Acá se usa un heurístico de primera pasada -- odds ausente en la respuesta
=> failed_scraping -- documentado como tentativo, no como decisión cerrada.
"""

import argparse
import json
import sys
from pathlib import Path

_SCRAPING_DIR = str(Path(__file__).resolve().parent.parent / "scraping")
_INGESTA_DIR = str(Path(__file__).resolve().parent.parent / "ingesta")
_PERSISTENCIA_DIR = str(Path(__file__).resolve().parent.parent / "persistencia")
for _p in (_SCRAPING_DIR, _INGESTA_DIR, _PERSISTENCIA_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import obtener_v
from obtener_fixture_detalle import fetch_fixture_detail
import orquestar_ingesta
import sqlite_store


def _extraer_nombres_equipos(raw_odds: list) -> tuple[str | None, str | None]:
    """
    Saca (home_team_name, away_team_name) del outcome "Home or Away" del
    mercado Double Chance -- es el único lugar donde el nombre del equipo
    aparece como texto libre y en orden fijo (local primero, separado por
    " or "), confirmado contra datos reales (ver 19717275.db). Se busca
    por `outcome == "HOME_WIN_OR_AWAY_WIN"` (el código) y no por
    market_name en texto, porque es más estable ante variaciones de
    nombre del mercado entre bookmakers.

    Solo para display en el visor (ver fixture_pipeline_status) -- si el
    mercado no vino en este fixture (bookmaker no lo ofrece, liga sin ese
    mercado, etc.) devuelve (None, None) sin romper nada aguas abajo.
    """
    for o in raw_odds:
        if o.market_name == "Double Chance" and o.outcome == "HOME_WIN_OR_AWAY_WIN":
            partes = o.outcome_name.split(" or ")
            if len(partes) == 2:
                return partes[0].strip(), partes[1].strip()
    return None, None


def procesar_fixture(external_id: int, token: str | None = None) -> dict:
    """
    Corre el pipeline completo para UN fixture: scraping -> ingesta ->
    persistencia, actualizando fixture_pipeline_status en cada paso.

    Reprocesa sin importar el estado actual del fixture (cubre el caso
    "Procesar fixture individual" del visor) -- como la persistencia ya es
    upsert en 5 de las 6 tablas de datos, reprocesar no duplica.

    Ya no recibe db_path: cada fixture tiene su propio archivo
    (beet_sc/db/<external_id>.db, ver sqlite_store.crear_engine), así que
    el destino se resuelve solo a partir de external_id.

    Devuelve un dict con al menos {"fixture_id", "status"} y, según dónde
    haya terminado, "error" o "total_errores".
    """
    engine = sqlite_store.crear_engine(external_id)

    # ---------- 1. Scraping ----------
    try:
        token = token or obtener_v.obtener_v_cacheado()
        fixture_json = fetch_fixture_detail(external_id, token)
    except Exception as e:
        sqlite_store.marcar_failed(engine, external_id, etapa="scraping", error_detail=str(e))
        return {"fixture_id": external_id, "status": "failed_scraping", "error": str(e)}

    if fixture_json.get("odds") is None:
        # Heurístico tentativo (ver docstring del módulo): no distingue
        # todavía "no disponible aún en la fuente" de "error real" -- de
        # momento las trata igual, marcando failed_scraping.
        detalle = "odds ausente en la respuesta (fixture no disponible en la fuente, o error de descarga -- ver nota de heurístico tentativo)"
        sqlite_store.marcar_failed(engine, external_id, etapa="scraping", error_detail=detalle)
        return {"fixture_id": external_id, "status": "failed_scraping", "error": detalle}

    sqlite_store.marcar_scraped(engine, external_id)

    # ---------- 2. Ingesta ----------
    try:
        resultado = orquestar_ingesta.procesar_fixture(fixture_json)
    except Exception as e:
        sqlite_store.marcar_failed(engine, external_id, etapa="ingesta", error_detail=str(e))
        return {"fixture_id": external_id, "status": "failed_ingesta", "error": str(e)}

    home_team_name, away_team_name = _extraer_nombres_equipos(resultado.raw_odds)
    sqlite_store.marcar_ingested(
        engine, external_id,
        home_team_name=home_team_name, away_team_name=away_team_name,
    )

    # ---------- 3. Persistencia ----------
    try:
        orquestar_ingesta.persistir(resultado)
    except Exception as e:
        sqlite_store.marcar_failed(engine, external_id, etapa="persistencia", error_detail=str(e))
        return {"fixture_id": external_id, "status": "failed_persistencia", "error": str(e)}

    sqlite_store.marcar_persisted(engine, external_id, validation_error_count=resultado.total_errores)

    return {
        "fixture_id": external_id,
        "status": "persisted",
        "total_errores": resultado.total_errores,
    }


def procesar_dia(
    staging_path: str = "comparativas_staging.json",
    reprocesar_todo: bool = False,
) -> list[dict]:
    """
    Corre procesar_fixture() para cada fixture listado en `staging_path`
    (salida de obtener_fixtures_dia.py) que todavía NO esté "persisted"
    (cubre pendiente / nunca trackeado / cualquier failed_* -- se
    considera candidato a reintento, no solo "pendiente" en sentido
    estricto). No reprocesa los ya persisted salvo reprocesar_todo=True
    (cubre "forzar re-proceso masivo", ver Abierto en el diseño).

    Nota: desde que obtener_fixtures_dia.py soporta --hoy-manana, el
    staging puede traer fixtures que todavía no arrancaron. Se procesan
    igual -- la fuente ya tiene odds/stats con antelación (confirmado:
    varían poco entre hoy y el kickoff), y como la persistencia es
    upsert, el disparo automático post-partido (ver beet_unificacion_flujo.md,
    "Detección de partido terminado") va a refrescarlos igual con los
    valores finales. Procesarlos ya de antemano solo adelanta trabajo,
    no genera datos falsos ni duplicados.

    Ya no recibe db_path: cada fixture vive en su propio archivo, así que
    la consulta de estados actuales usa listar_estados_pipeline_multi
    (abre solo los archivos que ya existen, sin crear vacíos de más).

    Un `v` fresco se obtiene UNA sola vez acá (no por fixture) -- 'v'
    cambia con poca frecuencia (ver obtener_v.py), así que no vale la
    pena cachear/refrescar por cada fixture del día.
    """
    rows = json.loads(Path(staging_path).read_text(encoding="utf-8"))
    external_ids = [row["external_id"] for row in rows if row.get("external_id")]

    if not reprocesar_todo:
        estados = {
            fid: e["status"]
            for fid, e in sqlite_store.listar_estados_pipeline_multi(external_ids).items()
        }
        external_ids = [eid for eid in external_ids if estados.get(eid) != "persisted"]

    token = obtener_v.obtener_v_cacheado()

    resultados = []
    for i, eid in enumerate(external_ids, 1):
        print(f"[{i}/{len(external_ids)}] procesando fixture {eid} ...")
        r = procesar_fixture(eid, token=token)
        print(f"  -> {r['status']}")
        resultados.append(r)

    ok = sum(1 for r in resultados if r["status"] == "persisted")
    print(f"\n{ok}/{len(resultados)} fixtures persistidos correctamente.")
    return resultados


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Orquestador de alto nivel: scraping -> ingesta -> persistencia + fixture_pipeline_status."
    )
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--fixture", type=int, help="procesa un solo fixture (external_id)")
    grupo.add_argument("--dia", action="store_true", help="procesa todos los fixtures pendientes del staging")
    ap.add_argument("--staging", default="comparativas_staging.json", help="ruta al staging (solo con --dia)")
    ap.add_argument("--reprocesar-todo", action="store_true", help="con --dia, reprocesa también los ya persisted")
    args = ap.parse_args()

    if args.fixture:
        r = procesar_fixture(args.fixture)
        print(json.dumps(r, indent=2, ensure_ascii=False))
        if r["status"] != "persisted":
            sys.exit(1)
    else:
        procesar_dia(staging_path=args.staging, reprocesar_todo=args.reprocesar_todo)
