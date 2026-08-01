"""
obtener_v.py
Extrae automáticamente el valor actual del cache-buster `v` que usa
getFixturesBySingleStatAsJson.php, sin tener que ir al navegador a mano.

Abre la página de fixtures con un navegador real (Playwright), espera a que
la propia página dispare la llamada a getFixturesBySingleStatAsJson.php, y
lee el parámetro `v` directo de esa URL real.

Uso como script (imprime el valor, para usarlo en otro comando):
    python obtener_v.py
    -> 2026631

Uso encadenado con build_comparativas.py (todo en un solo paso, sin copiar nada a mano):
    Windows (cmd):
        for /f %v in ('python obtener_v.py') do python build_comparativas.py --stats BTTS --out comparativas_staging.json --v %v

    Windows (PowerShell):
        $v = python obtener_v.py
        python build_comparativas.py --stats BTTS --out comparativas_staging.json --v $v

Uso como función importable (para integrarlo directo en build_comparativas.py,
así ni siquiera hace falta el paso de dos comandos):
    from obtener_v import obtener_v_actual
    v = obtener_v_actual()

Uso con cache (recomendado para no lanzar un navegador en cada corrida --
'v' cambia con poca frecuencia, no en cada ejecución del pipeline):
    from obtener_v import obtener_v_cacheado
    v = obtener_v_cacheado()                    # usa cache si existe
    v = obtener_v_cacheado(forzar_refresh=True)  # ignora cache, va al navegador
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright

CACHE_PATH = Path(__file__).parent / ".v_cache.json"


def obtener_v_actual(url_fixtures: str = "https://www.adamchoi.co.uk/fixtures", timeout_ms: int = 20000) -> str:
    """Navega a la página de fixtures y captura el `v` real que usa el sitio.

    No usa wait_until="networkidle": el sitio tiene tracking/ads corriendo
    en loop que nunca dejan la red "quieta", así que networkidle expira por
    timeout aunque la página cargó bien y ya disparó la request que nos
    interesa. En vez de eso, esperamos puntualmente esa respuesta.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            with page.expect_response(
                lambda response: "getFixturesBySingleStatAsJson.php" in response.url,
                timeout=timeout_ms,
            ) as response_info:
                page.goto(url_fixtures, wait_until="domcontentloaded", timeout=timeout_ms)
            response = response_info.value
        except Exception as e:
            raise RuntimeError(
                "No se pudo capturar el parámetro 'v' -- la página puede no haber "
                "disparado la llamada a getFixturesBySingleStatAsJson.php a tiempo, "
                "o no cargó (revisar conectividad/bloqueo de red). "
                f"Error original: {e}"
            ) from e
        finally:
            browser.close()

    qs = parse_qs(urlparse(response.url).query)
    if "v" not in qs:
        raise RuntimeError(
            f"Se capturó la respuesta pero sin parámetro 'v' en la URL: {response.url}"
        )
    return qs["v"][0]


def _leer_cache() -> Optional[str]:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        v = data.get("v")
        return str(v) if v else None
    except Exception:
        # cache corrupto/ilegible -- se trata como si no existiera, no debe
        # romper el pipeline
        return None


def _guardar_cache(v: str) -> None:
    try:
        CACHE_PATH.write_text(
            json.dumps({"v": v, "obtenido_en_epoch": time.time()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass  # guardar cache es best-effort, un fallo acá no debe frenar nada


def obtener_v_cacheado(forzar_refresh: bool = False) -> str:
    """Como obtener_v_actual(), pero evita lanzar el navegador si ya hay un
    valor cacheado en disco (.v_cache.json, junto a este script).

    'v' cambia con poca frecuencia (se observó un solo cambio en varios días
    de uso del pipeline), así que lanzar un Chromium headless completo en
    CADA corrida es costo innecesario la mayoría de las veces. Cuando el
    valor cacheado deja de servir (el servidor devuelve 401 al usarlo), el
    caller debe pedir de nuevo con forzar_refresh=True.
    """
    if not forzar_refresh:
        cached = _leer_cache()
        if cached:
            return cached
    v = obtener_v_actual()
    _guardar_cache(v)
    return v


if __name__ == "__main__":
    forzar = "--refresh" in sys.argv
    try:
        v = obtener_v_cacheado(forzar_refresh=forzar)
        print(v)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
