"""
ver_partidos.py
Muestra en consola los partidos de comparativas_staging.json, agrupados por
día y por liga/país. No hace requests -- solo lee el JSON que ya generaste
con build_comparativas.py / run_pipeline.py.

Uso:
    python ver_partidos.py
    python ver_partidos.py --archivo comparativas_staging.json
    python ver_partidos.py --pais Colombia
    python ver_partidos.py --liga "Serie B"
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# mismo huso que usa build_comparativas.py (UTC-5, coincide con el sitio y con Colombia)
TZ_SITIO = timezone(timedelta(hours=-5))

DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_es(d) -> str:
    dia_semana = DIAS_ES[d.weekday()]
    mes = MESES_ES[d.month - 1]
    return f"{dia_semana} {d.day} de {mes}, {d.year}"


def cargar(archivo: str) -> list[dict]:
    path = Path(archivo)
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {archivo}. Generalo primero con:\n"
            f"  python build_comparativas.py --stats BTTS --out {archivo}\n"
            f"  o: python run_pipeline.py --stats BTTS"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archivo", default="comparativas_staging.json")
    parser.add_argument("--pais", default=None, help="filtrar por país (coincidencia parcial, sin importar mayúsculas)")
    parser.add_argument("--liga", default=None, help="filtrar por liga (coincidencia parcial, sin importar mayúsculas)")
    args = parser.parse_args()

    rows = cargar(args.archivo)

    if args.pais:
        rows = [r for r in rows if r.get("country") and args.pais.lower() in r["country"].lower()]
    if args.liga:
        rows = [r for r in rows if r.get("league_name") and args.liga.lower() in r["league_name"].lower()]

    if not rows:
        print("No hay partidos que coincidan con los filtros.")
        return

    # Agrupar por día (usando kickoff_epoch_ms si está, si no date_epoch_ms)
    por_dia = defaultdict(list)
    for r in rows:
        ms = r.get("kickoff_epoch_ms") or r.get("date_epoch_ms")
        if ms is None:
            continue
        dia = datetime.fromtimestamp(ms / 1000, tz=TZ_SITIO).date()
        por_dia[dia].append(r)

    for dia in sorted(por_dia.keys()):
        partidos_dia = por_dia[dia]
        print(f"\n{'='*70}")
        print(f"📅 {fecha_es(dia)}  ({len(partidos_dia)} partidos)")
        print('='*70)

        # Agrupar dentro del día por país -> liga
        por_pais_liga = defaultdict(list)
        for r in partidos_dia:
            key = (r.get("country") or "?", r.get("league_name") or "?")
            por_pais_liga[key].append(r)

        for (pais, liga) in sorted(por_pais_liga.keys()):
            partidos = por_pais_liga[(pais, liga)]
            print(f"\n  🌍 {pais} — {liga}")
            for r in sorted(partidos, key=lambda x: x.get("kickoff_epoch_ms") or 0):
                ms = r.get("kickoff_epoch_ms")
                hora = datetime.fromtimestamp(ms / 1000, tz=TZ_SITIO).strftime("%H:%M") if ms else "??:??"
                copa = " [COPA]" if r.get("es_copa") else ""
                print(f"     {hora}  {r['hometeam']} vs {r['awayteam']}{copa}")

    print(f"\n{'='*70}")
    print(f"Total: {len(rows)} partidos en {len(por_dia)} día(s)")


if __name__ == "__main__":
    main()
