"""
orquestar_scraping.py
Orquestador de la etapa de SCRAPING de Beet (obtención de datos crudos desde
la fuente). No toca ingesta ni persistencia -- eso lo encadena por separado
pipeline/orquestador.py, llamando primero a este script y después a
orquestar_ingesta.py:

  1. Obtiene el cache-buster `v` fresco automáticamente (sin ir al navegador).
  2. Genera el listado de fixtures + stats agregadas (staging), usando ese `v`.
  3. Descarga el detalle completo (odds/team-records/recent-results) de cada
     fixture del staging.

Un solo comando para toda la etapa de scraping, sin pasos manuales.

Requiere en la MISMA carpeta:
  - obtener_v.py
  - obtener_fixtures_dia.py
  - obtener_fixture_detalle.py

Uso básico (equivalente a lo que veníamos corriendo en 3 comandos separados):
    python orquestar_scraping.py --stats BTTS --limit-detalles 5

Bajar el detalle de TODOS los fixtures del staging (sin límite):
    python orquestar_scraping.py --stats BTTS

Filtrar por fecha (partidos de hoy, mañana, o los próximos 7 días):
    python orquestar_scraping.py --stats BTTS --hoy
    python orquestar_scraping.py --stats BTTS --manana
    python orquestar_scraping.py --stats BTTS --semana

Hoy + mañana en un solo staging (pensado para el visor):
    python orquestar_scraping.py --stats BTTS --hoy-manana

Rango custom de fechas:
    python orquestar_scraping.py --stats BTTS --desde 2026-08-01 --hasta 2026-08-05

Ver qué haría sin ejecutar nada todavía (dry-run):
    python orquestar_scraping.py --stats BTTS --limit-detalles 5 --dry-run
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_step(nombre: str, cmd: list[str], dry_run: bool) -> None:
    print(f"\n{'='*70}")
    print(f"PASO: {nombre}")
    print(f"comando: {' '.join(cmd)}")
    print('='*70)
    if dry_run:
        print("  (dry-run, no se ejecuta)")
        return
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n❌ Falló el paso '{nombre}' (exit code {result.returncode}). Deteniendo el pipeline.")
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stats", default="BTTS", help="statType(s) para obtener_fixtures_dia.py (default: BTTS)")
    parser.add_argument("--staging-out", default="comparativas_staging.json", help="archivo de salida del staging")
    parser.add_argument("--detalles-out-dir", default="detalles_fixtures", help="carpeta de salida del detalle por partido")
    parser.add_argument("--limit-detalles", type=int, default=None, help="cuántos fixtures del staging detallar (default: todos)")
    parser.add_argument("--delay", type=float, default=0.5, help="delay entre requests de detalle (segundos)")
    parser.add_argument("--incluir-copas", action="store_true", help="pasa --incluir-copas a obtener_fixtures_dia.py")
    parser.add_argument("--incluir-premium", action="store_true", help="pasa --incluir-premium a obtener_fixtures_dia.py")
    grupo_fecha = parser.add_mutually_exclusive_group()
    grupo_fecha.add_argument("--hoy", action="store_true", help="solo partidos de hoy")
    grupo_fecha.add_argument("--manana", action="store_true", help="solo partidos de mañana")
    grupo_fecha.add_argument("--hoy-manana", action="store_true", help="partidos de hoy y de mañana (pensado para el visor)")
    grupo_fecha.add_argument("--semana", action="store_true", help="partidos de hoy hasta 7 días adelante")
    parser.add_argument("--desde", default=None, help="fecha desde YYYY-MM-DD (alternativa a --hoy/--manana/--semana)")
    parser.add_argument("--hasta", default=None, help="fecha hasta YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="mostrar los comandos sin ejecutarlos")
    args = parser.parse_args()

    script_dir = Path(__file__).parent

    # ---------- Paso 1: obtener_fixtures_dia.py (obtiene 'v' automáticamente si no se pasa) ----------
    cmd_comparativas = [
        sys.executable, str(script_dir / "obtener_fixtures_dia.py"),
        "--stats", args.stats,
        "--out", args.staging_out,
    ]
    if args.incluir_copas:
        cmd_comparativas.append("--incluir-copas")
    if args.incluir_premium:
        cmd_comparativas.append("--incluir-premium")
    if args.hoy:
        cmd_comparativas.append("--hoy")
    elif args.manana:
        cmd_comparativas.append("--manana")
    elif args.hoy_manana:
        cmd_comparativas.append("--hoy-manana")
    elif args.semana:
        cmd_comparativas.append("--semana")
    else:
        if args.desde:
            cmd_comparativas += ["--desde", args.desde]
        if args.hasta:
            cmd_comparativas += ["--hasta", args.hasta]
    run_step("1/2 - Listado de fixtures + stats agregadas (staging)", cmd_comparativas, args.dry_run)

    # ---------- Paso 2: obtener_fixture_detalle.py ----------
    cmd_detalles = [
        sys.executable, str(script_dir / "obtener_fixture_detalle.py"),
        "--from-staging", args.staging_out,
        "--out-dir", args.detalles_out_dir,
        "--delay", str(args.delay),
    ]
    if args.limit_detalles is not None:
        cmd_detalles += ["--limit", str(args.limit_detalles)]
    run_step("2/2 - Detalle completo por partido (odds, team-records, recent-results)", cmd_detalles, args.dry_run)

    print(f"\n{'='*70}")
    print("✅ PIPELINE COMPLETO")
    print(f"   Staging: {args.staging_out}")
    print(f"   Detalles: {args.detalles_out_dir}/")
    print('='*70)


if __name__ == "__main__":
    main()
