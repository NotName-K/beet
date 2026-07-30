"""
Configuración persistente del usuario — hoy solo las API keys de Gemini.

Se guarda en ~/.beet/config.json, es decir, en la carpeta personal del
usuario y NUNCA dentro del repo, para que no vuelva a pasar lo de antes
(keys hardcodeadas y commiteadas por accidente).
"""
from __future__ import annotations

import json
import stat
from pathlib import Path


def directorio_config() -> Path:
    """Carpeta donde vive la configuración, fuera del proyecto."""
    return Path.home() / ".beet"


def ruta_config() -> Path:
    return directorio_config() / "config.json"


def _leer_config() -> dict:
    ruta = ruta_config()
    if not ruta.exists():
        return {}
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def cargar_api_keys() -> list[str]:
    """Devuelve las API keys de Gemini guardadas, o [] si no hay configuración todavía."""
    keys = _leer_config().get("gemini_api_keys", [])
    return [k.strip() for k in keys if k and k.strip()]


def guardar_api_keys(keys: list[str]) -> None:
    """Guarda las API keys de Gemini en ~/.beet/config.json."""
    keys_limpias = [k.strip() for k in keys if k and k.strip()]

    directorio = directorio_config()
    directorio.mkdir(parents=True, exist_ok=True)

    datos = _leer_config()
    datos["gemini_api_keys"] = keys_limpias

    ruta = ruta_config()
    ruta.write_text(json.dumps(datos, indent=2), encoding="utf-8")

    # Restringe el archivo a solo-lectura/escritura del usuario dueño.
    # En Windows esto no aplica de la misma forma (no hay excepción, pero
    # tampoco protección real vía chmod); en Unix sí evita que otros
    # usuarios de la misma máquina lean las keys.
    try:
        ruta.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def hay_api_keys_configuradas() -> bool:
    return len(cargar_api_keys()) > 0
