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
"""

import re
import sys
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright


def obtener_v_actual(url_fixtures: str = "https://www.adamchoi.co.uk/fixtures", timeout_ms: int = 20000) -> str:
    """Navega a la página de fixtures y captura el `v` real que usa el sitio."""
    v_encontrado = {}

    def on_response(response):
        req_url = response.request.url
        if "getFixturesBySingleStatAsJson.php" in req_url:
            qs = parse_qs(urlparse(req_url).query)
            if "v" in qs:
                v_encontrado["v"] = qs["v"][0]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("response", on_response)
        page.goto(url_fixtures, wait_until="networkidle", timeout=timeout_ms)
        page.wait_for_timeout(2000)
        browser.close()

    if "v" not in v_encontrado:
        raise RuntimeError(
            "No se pudo capturar el parámetro 'v' -- la página puede no haber "
            "disparado la llamada a getFixturesBySingleStatAsJson.php a tiempo. "
            "Probá aumentar timeout_ms o revisar manualmente con network_capture.py."
        )
    return v_encontrado["v"]


if __name__ == "__main__":
    try:
        v = obtener_v_actual()
        print(v)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
