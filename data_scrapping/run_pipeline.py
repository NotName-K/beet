"""
run_pipeline.py
Orquestador único del ciclo completo de ingesta de Beet:

  1. Obtiene el cache-buster `v` fresco automáticamente (sin ir al navegador).
  2. Genera el listado de fixtures + stats agregadas (staging), usando ese `v`.
  3. Descarga el detalle completo (5 fuentes) de cada fixture del staging.

Un solo comando, sin pasos manuales.

Requiere en la MISMA carpeta:
  - obtener_v.py
  - build_comparativas.py
  - build_fixture_details_final.py

Uso básico (equivalente a lo que veníamos corriendo en 3 comandos separados):
    python run_pipeline.py --stats BTTS --limit-detalles 5

Bajar el detalle de TODOS los fixtures del staging (sin límite):
    python run_pipeline.py --stats BTTS

Filtrar por fecha (partidos de hoy, mañana, o los próximos 7 días):
    python run_pipeline.py --stats BTTS --hoy
    python run_pipeline.py --stats BTTS --manana
    python run_pipeline.py --stats BTTS --semana

Rango custom de fechas:
    python run_pipeline.py --stats BTTS --desde 2026-08-01 --hasta 2026-08-05

Ver qué haría sin ejecutar nada todavía (dry-run):
    python run_pipeline.py --stats BTTS --limit-detalles 5 --dry-run
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
    parser.add_argument("--stats", default="BTTS", help="statType(s) para build_comparativas.py (default: BTTS)")
    parser.add_argument("--staging-out", default="comparativas_staging.json", help="archivo de salida del staging")
    parser.add_argument("--detalles-out-dir", default="detalles_fixtures", help="carpeta de salida del detalle por partido")
    parser.add_argument("--limit-detalles", type=int, default=None, help="cuántos fixtures del staging detallar (default: todos)")
    parser.add_argument("--delay", type=float, default=0.5, help="delay entre requests de detalle (segundos)")
    parser.add_argument("--incluir-copas", action="store_true", help="pasa --incluir-copas a build_comparativas.py")
    parser.add_argument("--incluir-premium", action="store_true", help="pasa --incluir-premium a build_comparativas.py")
    grupo_fecha = parser.add_mutually_exclusive_group()
    grupo_fecha.add_argument("--hoy", action="store_true", help="solo partidos de hoy")
    grupo_fecha.add_argument("--manana", action="store_true", help="solo partidos de mañana")
    grupo_fecha.add_argument("--semana", action="store_true", help="partidos de hoy hasta 7 días adelante")
    parser.add_argument("--desde", default=None, help="fecha desde YYYY-MM-DD (alternativa a --hoy/--manana/--semana)")
    parser.add_argument("--hasta", default=None, help="fecha hasta YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="mostrar los comandos sin ejecutarlos")
    args = parser.parse_args()

    script_dir = Path(__file__).parent

    # ---------- Paso 1: build_comparativas.py (obtiene 'v' automáticamente si no se pasa) ----------
    cmd_comparativas = [
        sys.executable, str(script_dir / "build_comparativas.py"),
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
    elif args.semana:
        cmd_comparativas.append("--semana")
    else:
        if args.desde:
            cmd_comparativas += ["--desde", args.desde]
        if args.hasta:
            cmd_comparativas += ["--hasta", args.hasta]
    run_step("1/2 - Listado de fixtures + stats agregadas (staging)", cmd_comparativas, args.dry_run)

    # ---------- Paso 2: build_fixture_details_final.py ----------
    cmd_detalles = [
        sys.executable, str(script_dir / "build_fixture_details_final.py"),
        "--from-staging", args.staging_out,
        "--out-dir", args.detalles_out_dir,
        "--delay", str(args.delay),
    ]
    if args.limit_detalles is not None:
        cmd_detalles += ["--limit", str(args.limit_detalles)]
    run_step("2/2 - Detalle completo por partido (5 fuentes c/u)", cmd_detalles, args.dry_run)

    print(f"\n{'='*70}")
    print("✅ PIPELINE COMPLETO")
    print(f"   Staging: {args.staging_out}")
    print(f"   Detalles: {args.detalles_out_dir}/")
    print('='*70)


if __name__ == "__main__":
    main()
