"""
diagnostico_v.py
Verifica ÚNICAMENTE el cacheo de 'v' -- no genera staging, no detalla
fixtures, no toca nada del pipeline real. Poné este archivo junto a
obtener_v.py (misma carpeta) para que el import funcione.

Uso:
    python diagnostico_v.py            # prueba cache normal + refresh forzado
    python diagnostico_v.py --limpiar  # borra el cache antes de probar
"""

import sys
import time

from obtener_v import obtener_v_cacheado, CACHE_PATH


def main():
    if "--limpiar" in sys.argv:
        CACHE_PATH.unlink(missing_ok=True)
        print(f"Cache borrado: {CACHE_PATH}\n")

    print(f"Archivo de cache: {CACHE_PATH}")
    print(f"¿Existe ya?: {CACHE_PATH.exists()}\n")

    print("== 1) Llamada normal (usa el cache si hay uno) ==")
    t0 = time.time()
    v = obtener_v_cacheado()
    dt = time.time() - t0
    print(f"v = {v}  (tardó {dt:.2f}s)")
    print("-> vino del cache (no abrió navegador)" if dt < 1 else "-> abrió el navegador para obtenerlo")
    print()

    print("== 2) Misma llamada otra vez (ahora SIEMPRE debería venir del cache) ==")
    t0 = time.time()
    v2 = obtener_v_cacheado()
    dt2 = time.time() - t0
    print(f"v = {v2}  (tardó {dt2:.2f}s)")
    assert v2 == v, "el valor cambió entre dos lecturas de cache seguidas, algo está mal"
    print("OK: mismo valor, sin abrir navegador" if dt2 < 1 else "ADVERTENCIA: tardó como si hubiera abierto navegador")
    print()

    print("== 3) forzar_refresh=True (esta SIEMPRE debe abrir el navegador) ==")
    t0 = time.time()
    v3 = obtener_v_cacheado(forzar_refresh=True)
    dt3 = time.time() - t0
    print(f"v = {v3}  (tardó {dt3:.2f}s)")


if __name__ == "__main__":
    main()
