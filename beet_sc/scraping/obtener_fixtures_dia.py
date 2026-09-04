"""
obtener_fixtures_dia.py (ex build_comparativas.py)

Descarga fixtures + stats desde los endpoints JSON de Adam Choi y arma un
staging de filas listas para mapear a Comparativa en Beet.

Resuelve los gotchas documentados en el handoff:
  1) Join de stats usa home_league/away_league (liga DOMÉSTICA del equipo),
     nunca "league" (que es la liga del partido, puede ser una copa).
  2) El campo "corners" del fixture es un booleano heredado, se descarta.
  3) subscriptionType == "Premium" -> odds vienen null, se marca premium=True
     y no se trata como error.
  4) percent == null -> se guarda como None ("sin dato"), nunca como 0.
  5) Soporta pedir varios statType en una corrida y los combina por fixture.
  6) Por defecto EXCLUYE partidos de copa (nacional/internacional) y deja solo
     ligas domésticas -- regla verificada contra datos reales: es partido de
     LIGA doméstica si y solo si league == home_league == away_league. Si
     alguno difiere, es copa (los equipos vienen de ligas distintas, o la copa
     tiene su propio código aunque los equipos compartan liga entre sí, como
     la Carabao Cup). Usar --incluir-copas para desactivar el filtro.

Uso:
    pip install requests
    python obtener_fixtures_dia.py --stats BTTS,CORNERS,CARDS --out comparativas_staging.json

    (los nombres de statType válidos hay que confirmarlos contra el sitio;
    por ahora solo se confirmó "BTTS". Si un statType no existe, el request
    igual devuelve 200 pero con teamStats vacío o parcial -- revisa el log.)

    Para el visor (hoy + mañana en una sola lista, agrupada por date_epoch_ms):
    python obtener_fixtures_dia.py --hoy-manana --out comparativas_staging.json
"""

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from obtener_v import obtener_v_cacheado

BASE_URL = "https://www.adamchoi.co.uk/scripts/data/json/scripts/getFixturesBySingleStatAsJson.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.adamchoi.co.uk/fixtures",
    "Accept": "application/json, text/plain, */*",
}


def fetch_stat(stat_type: str, cache_buster: str) -> dict:
    params = {
        "clflc": "abc",
        "nummatches": "All",
        "v": cache_buster,
        "groupBy": "date",
        "statType": stat_type,
        "a": "false",
        "timezoneOffset": 300,
    }
    resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    # el content-type declarado es text/html aunque el body sea JSON (ver handoff)
    return resp.json()


def lookup_stat(team_stats: dict, team: str, league: str, stat_type: str) -> Optional[dict]:
    """
    Busca teamStats[team][league][stat_type]. Devuelve None si falta cualquier
    nivel (equipo nuevo, ascenso/descenso reciente, o statType no disponible
    para ese equipo) en vez de lanzar KeyError -- esto tiene que ser tolerante
    porque va a pasar seguido con equipos de ligas chicas.
    """
    team_entry = team_stats.get(team)
    if not team_entry:
        return None
    league_entry = team_entry.get(league)
    if not league_entry:
        return None
    return league_entry.get(stat_type)


def window_or_none(stat_block: Optional[dict], window: str) -> dict:
    if not stat_block:
        return {"num_matches": None, "percent": None}
    w = stat_block.get(window)
    if not w:
        return {"num_matches": None, "percent": None}
    return {"num_matches": w.get("numMatches"), "percent": w.get("percent")}


def build_rows(payload_by_stat: dict[str, dict], only_leagues: bool = True, exclude_premium: bool = True) -> list[dict]:
    """
    payload_by_stat: { "BTTS": <json de fetch_stat("BTTS")>, "CORNERS": <...>, ... }

    Se asume que la lista de fixtures (dates/leagues/fixtures) es la MISMA
    entre distintos statType (Adam Choi arma el calendario completo siempre;
    solo cambia qué stat viene resuelta en teamStats). Se usa el primer
    statType como fuente de fixtures y se le van agregando los demás stats.
    """
    stat_names = list(payload_by_stat.keys())
    primary_payload = payload_by_stat[stat_names[0]]

    rows = []

    for date_block in primary_payload.get("dates", []):
        date_epoch_ms = date_block.get("date")

        for league_block in date_block.get("leagues", []):
            league_code = league_block.get("league")
            league_name = league_block.get("leagueName")
            country = league_block.get("country")
            subscription_type = league_block.get("subscriptionType")
            is_premium_league = subscription_type == "Premium"

            for fx in league_block.get("fixtures", []):
                home_team = fx.get("hometeam")
                away_team = fx.get("awayteam")
                home_league = fx.get("home_league")
                away_league = fx.get("away_league")

                # Regla verificada contra datos reales: en partidos de LIGA doméstica,
                # el código de liga del partido coincide con la liga doméstica de
                # AMBOS equipos. En copas (nacionales o internacionales) alguno difiere
                # -- ej. Champions League "UCL1" con equipos de "CZ1" y "F1", o Carabao
                # Cup "ECC1" con equipos de "E3" (la copa tiene su propio código aunque
                # los equipos compartan liga doméstica entre sí).
                es_copa = not (league_code == home_league == away_league)

                if only_leagues and es_copa:
                    continue

                # Confirmado con datos reales: en ligas Premium, 98% de los equipos
                # no traen teamStats (no es solo que falten las odds). Sin stats no
                # sirven para el análisis, así que por defecto se descartan directo
                # en vez de dejarlas pasar como filas vacías -- ver Gotcha #7 del handoff.
                if exclude_premium and is_premium_league:
                    continue

                row = {
                    "fixture_id": fx.get("id"),
                    "external_id": fx.get("externalid"),
                    "date_epoch_ms": date_epoch_ms,
                    "kickoff_epoch_ms": fx.get("datetimestamp"),
                    "league_partido": league_code,       # liga del partido (puede ser copa)
                    "league_name": league_name,
                    "country": country,
                    "es_copa": es_copa,
                    "premium": is_premium_league,
                    "hometeam": home_team,
                    "awayteam": away_team,
                    "home_league_domestica": home_league,  # liga usada para el join de stats
                    "away_league_domestica": away_league,
                    "home_dec_odds": fx.get("home_dec_odds"),
                    "home_bet_url": fx.get("home_bet_url"),
                    "away_dec_odds": fx.get("away_dec_odds"),
                    "away_bet_url": fx.get("away_bet_url"),
                    # nota: se descarta a propósito fx["corners"] -- es un booleano
                    # heredado del template del backend, no la cantidad real de corners.
                    "stats": {},
                }

                for stat_name, payload in payload_by_stat.items():
                    team_stats = payload.get("teamStats", {})

                    home_block = None
                    away_block = None
                    if home_league:
                        home_block = lookup_stat(team_stats, home_team, home_league, stat_name)
                    if away_league:
                        away_block = lookup_stat(team_stats, away_team, away_league, stat_name)

                    row["stats"][stat_name] = {
                        "home_team_home_window": window_or_none(home_block, "Home"),
                        "home_team_all_window": window_or_none(home_block, "All"),
                        "away_team_away_window": window_or_none(away_block, "Away"),
                        "away_team_all_window": window_or_none(away_block, "All"),
                        "home_data_missing": home_block is None,
                        "away_data_missing": away_block is None,
                    }

                rows.append(row)

    return rows


def filter_by_date(rows: list[dict], fecha_desde: Optional[date], fecha_hasta: Optional[date]) -> list[dict]:
    """
    Filtra filas por fecha (usando date_epoch_ms, ya viene alineado a la zona
    horaria pasada en timezoneOffset=300 = UTC-5). Si fecha_desde/fecha_hasta
    son None, no se filtra por ese extremo.
    """
    if fecha_desde is None and fecha_hasta is None:
        return rows

    filtered = []
    for r in rows:
        ms = r.get("date_epoch_ms")
        if ms is None:
            continue
        row_date = datetime.fromtimestamp(ms / 1000).date()
        if fecha_desde is not None and row_date < fecha_desde:
            continue
        if fecha_hasta is not None and row_date > fecha_hasta:
            continue
        filtered.append(r)
    return filtered


def run(stat_types: list[str], out_path: str, only_leagues: bool = True, cache_buster: Optional[str] = None,
        exclude_premium: bool = True, fecha_desde: Optional[date] = None, fecha_hasta: Optional[date] = None):
    v_autogestionado = cache_buster is None
    if v_autogestionado:
        print("No se pasó --v, usando cache local si existe (evita abrir el navegador)...")
        cache_buster = obtener_v_cacheado()
        print(f"  v: {cache_buster}")

    payload_by_stat = {}
    for stat in stat_types:
        print(f"Descargando statType={stat} (v={cache_buster}) ...")
        try:
            payload_by_stat[stat] = fetch_stat(stat, cache_buster)
        except requests.HTTPError as e:
            # Si el 'v' fue auto-obtenido (no lo forzó el usuario con --v) y el
            # servidor devuelve 401, lo más probable es que el cache local ya
            # esté vencido -- refrescamos desde el navegador y reintentamos
            # una sola vez. Si el usuario pasó --v a mano, respetamos su
            # valor y no reintentamos por él.
            status = e.response.status_code if e.response is not None else None
            if v_autogestionado and status == 401:
                print(f"  401 con v cacheado ({cache_buster}) -- refrescando desde el navegador...")
                cache_buster = obtener_v_cacheado(forzar_refresh=True)
                print(f"  v refrescado: {cache_buster}")
                payload_by_stat[stat] = fetch_stat(stat, cache_buster)
            else:
                raise
        n_dates = len(payload_by_stat[stat].get("dates", []))
        n_teams = len(payload_by_stat[stat].get("teamStats", {}))
        print(f"  OK: {n_dates} fechas, {n_teams} equipos en teamStats")

    rows = build_rows(payload_by_stat, only_leagues=only_leagues, exclude_premium=exclude_premium)

    # Orden: por hora de kickoff ascendente. Sin esto, el orden de las filas
    # es el que trae la respuesta cruda del sitio (agrupado por fecha/liga/
    # país, no necesariamente por hora dentro de ese agrupamiento) -- y
    # --limit-detalles en obtener_fixture_detalle.py simplemente toma
    # las primeras N filas del staging tal cual, así que sin este sort podía
    # terminar detallando un partido de dentro de varios días en vez del más
    # próximo. Filas sin kickoff_epoch_ms (no debería pasar, pero por las
    # dudas) quedan al final en vez de reventar el sort.
    rows.sort(key=lambda r: (r.get("kickoff_epoch_ms") is None, r.get("kickoff_epoch_ms") or 0))

    total_antes_filtro_fecha = len(rows)
    rows = filter_by_date(rows, fecha_desde, fecha_hasta)
    if fecha_desde is not None or fecha_hasta is not None:
        desde_str = fecha_desde.isoformat() if fecha_desde else "(sin límite)"
        hasta_str = fecha_hasta.isoformat() if fecha_hasta else "(sin límite)"
        print(f"Filtro de fecha [{desde_str} .. {hasta_str}]: {total_antes_filtro_fecha} -> {len(rows)} filas")

    out = Path(out_path)
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    # resumen rápido de calidad de datos para detectar problemas de join temprano
    total = len(rows)
    missing_home = sum(
        1 for r in rows if any(s["home_data_missing"] for s in r["stats"].values())
    )
    missing_away = sum(
        1 for r in rows if any(s["away_data_missing"] for s in r["stats"].values())
    )
    premium_count = sum(1 for r in rows if r["premium"])

    print(f"\n{total} filas armadas -> {out}  (filtro solo-ligas: {only_leagues}, excluye-premium: {exclude_premium})")
    print(f"  {premium_count} en ligas Premium (sin odds){' -- ya deberían ser 0 si excluye-premium=True' if exclude_premium else ''}")
    print(f"  {missing_home} con datos de local faltantes (equipo/liga sin match en teamStats)")
    print(f"  {missing_away} con datos de visitante faltantes")
    print(
        "\nSi missing_home/missing_away son altos, probablemente sea porque el equipo "
        "es de una liga que Adam Choi no trackea a nivel doméstico (ver Gotcha #7 del "
        "handoff) -- no necesariamente un bug de join."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stats",
        default="BTTS",
        help="Lista de statType separados por coma, ej: BTTS,CORNERS,CARDS "
        "(solo BTTS está confirmado como válido por ahora)",
    )
    parser.add_argument("--out", default="comparativas_staging.json")
    parser.add_argument(
        "--incluir-copas",
        action="store_true",
        help="Por defecto se excluyen partidos de copa (nacional/internacional) y solo "
        "quedan ligas domésticas. Pasa este flag para incluir copas también.",
    )
    parser.add_argument(
        "--incluir-premium",
        action="store_true",
        help="Por defecto se excluyen ligas Premium (98%% no traen teamStats sin "
        "suscripción paga, confirmado con datos reales -- ver Gotcha #7 del handoff). "
        "Pasa este flag para dejarlas pasar igual, marcadas con premium=true.",
    )
    parser.add_argument(
        "--v",
        default=None,
        help="Valor del parámetro 'v' (cache-buster) que espera el servidor. Si no se "
        "pasa, se obtiene automáticamente (sin navegador) con obtener_v.py. Pasalo "
        "manualmente solo si querés forzar un valor específico.",
    )

    grupo_fecha = parser.add_mutually_exclusive_group()
    grupo_fecha.add_argument("--hoy", action="store_true", help="Solo partidos de hoy.")
    grupo_fecha.add_argument("--manana", action="store_true", help="Solo partidos de mañana.")
    grupo_fecha.add_argument(
        "--hoy-manana", action="store_true",
        help="Partidos de hoy y de mañana (rango de 2 días). Pensado para el visor, "
        "que muestra ambos días en una sola lista agrupada por fecha.",
    )
    grupo_fecha.add_argument("--semana", action="store_true", help="Partidos de hoy hasta 7 días adelante.")
    parser.add_argument("--desde", default=None, help="Fecha desde, formato YYYY-MM-DD (inclusive). Combinable con --hasta en vez de los atajos --hoy/--manana/--semana.")
    parser.add_argument("--hasta", default=None, help="Fecha hasta, formato YYYY-MM-DD (inclusive).")

    args = parser.parse_args()

    hoy = date.today()
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    if args.hoy:
        fecha_desde = fecha_hasta = hoy
    elif args.manana:
        fecha_desde = fecha_hasta = hoy + timedelta(days=1)
    elif args.hoy_manana:
        fecha_desde, fecha_hasta = hoy, hoy + timedelta(days=1)
    elif args.semana:
        fecha_desde, fecha_hasta = hoy, hoy + timedelta(days=7)
    else:
        if args.desde:
            fecha_desde = date.fromisoformat(args.desde)
        if args.hasta:
            fecha_hasta = date.fromisoformat(args.hasta)

    run(
        stat_types=[s.strip() for s in args.stats.split(",")],
        out_path=args.out,
        only_leagues=not args.incluir_copas,
        cache_buster=args.v,
        exclude_premium=not args.incluir_premium,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )
