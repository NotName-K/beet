"""
Utilidades compartidas por los parsers de Gemini (imagen.py y pdf.py):
rotación de clientes entre API keys, subida segura de archivos temporales,
extracción de JSON de la respuesta y reintentos ante errores transitorios.

Antes esto estaba duplicado casi al carácter en imagen.py y pdf.py, con
las API keys hardcodeadas en ambos. Ahora las keys se leen de forma
PEREZOSA (recién al pedir el primer cliente, no al importar el módulo)
desde beet.core.config, que a su vez las guarda fuera del repo — así el
diálogo de configuración inicial puede guardarlas antes de que cualquier
parser las necesite, sin importar el orden de imports.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
from typing import Optional

from google import genai

from beet.core.config import cargar_api_keys

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cliente_cycle: Optional["itertools.cycle[genai.Client]"] = None


class SinApiKeysConfiguradas(RuntimeError):
    """No hay ninguna API key de Gemini guardada en ~/.beet/config.json."""


def _inicializar_clientes() -> "itertools.cycle[genai.Client]":
    keys = cargar_api_keys()
    if not keys:
        raise SinApiKeysConfiguradas(
            "No hay API keys de Gemini configuradas. Reinicia Beet y "
            "complétalas en el diálogo inicial, o agrégalas a mano en "
            "~/.beet/config.json."
        )
    clientes = [genai.Client(api_key=k) for k in keys]
    return itertools.cycle(clientes)


def get_client() -> genai.Client:
    """
    Devuelve el siguiente cliente Gemini en la rotación, inicializando la
    rotación en el primer llamado (no al importar el módulo).
    """
    global _cliente_cycle
    with _lock:
        if _cliente_cycle is None:
            _cliente_cycle = _inicializar_clientes()
        return next(_cliente_cycle)


def reiniciar_clientes() -> None:
    """
    Fuerza a releer las API keys en el próximo get_client(). Útil si el
    usuario reconfigura las keys sin reiniciar la app.
    """
    global _cliente_cycle
    with _lock:
        _cliente_cycle = None


def subir_archivo_seguro(client: genai.Client, ruta: str, ext_por_defecto: str) -> object:
    ext = os.path.splitext(ruta)[1] or ext_por_defecto
    fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="beet_tmp_")
    os.close(fd)
    try:
        shutil.copy2(ruta, temp_path)
        return client.files.upload(file=temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def extraer_json(texto: str) -> dict:
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    texto_limpio = texto.replace('```json', '').replace('```', '').strip()
    return json.loads(texto_limpio)


def _es_error_transitorio(exc: Exception) -> bool:
    """Detecta errores de rate limit / cuota / sobrecarga que ameritan reintento."""
    msg = str(exc).lower()
    return any(s in msg for s in ("429", "resource_exhausted", "rate limit", "quota", "unavailable", "503"))


def generar_con_reintentos(client, system_instruction, archivo, prompt, modelo, intentos=3):
    """
    Con pocas API keys rotando y varios workers concurrentes durante el
    auto-escaneo, es fácil pegar en un rate limit puntual. Reintenta con
    backoff antes de rendirse, en vez de guardar el fallo como
    'procesado' sin datos y nunca reintentarlo.
    """
    ultimo_error = None
    for intento in range(1, intentos + 1):
        try:
            return client.models.generate_content(
                model=modelo,
                config={"system_instruction": system_instruction},
                contents=[archivo, prompt]
            )
        except Exception as e:
            ultimo_error = e
            if intento < intentos and _es_error_transitorio(e):
                espera = 2 ** intento  # 2s, 4s, ...
                logger.warning(f"Error transitorio ({e}), reintentando en {espera}s (intento {intento}/{intentos})")
                time.sleep(espera)
                continue
            raise
    raise ultimo_error
