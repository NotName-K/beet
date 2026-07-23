"""
Parser de imágenes de historial con Google Gemini.
Usa la API oficial google-genai con system_instruction y workaround de ruta temporal.
"""
import json
import re
import threading
import itertools
import logging
import tempfile
import shutil
import os
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional

from google import genai
from beet.core.historial_equipo import PartidoHistorico, HistorialEquipo
from beet.core.normalizacion import normalizar_nombre

logger = logging.getLogger(__name__)

API_KEYS = [
    "AIzaSyBbhovMtMabhcM5g_qsVFPqHvaT-hghezs",
    "AIzaSyAtciMewnK2Btk5EJ-4DyQhtDR3qhj05oU"
]
_clientes = [genai.Client(api_key=k) for k in API_KEYS]
_cliente_cycle = itertools.cycle(_clientes)
_lock = threading.Lock()

def _get_client() -> genai.Client:
    with _lock:
        return next(_cliente_cycle)

MODELO_IMAGEN = "gemini-3.1-flash-lite"

@dataclass
class ResultadoParseoImagen:
    stat_type: str = ""
    highlight_market: str = ""
    filtro_liga: str = ""
    equipo_local_nombre: str = ""
    equipo_visitante_nombre: str = ""
    historial_local: Optional[HistorialEquipo] = None
    historial_visitante: Optional[HistorialEquipo] = None
    errores: List[str] = field(default_factory=list)

def _parsear_fecha(date_str: str) -> Optional[datetime.date]:
    for fmt in ["%Y-%m-%d", "%b %d %Y", "%d %b %Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def _extraer_json(texto: str) -> dict:
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    texto_limpio = texto.replace('```json', '').replace('```', '').strip()
    return json.loads(texto_limpio)

def _subir_archivo_seguro(client: genai.Client, ruta: str) -> object:
    ext = os.path.splitext(ruta)[1] or ".png"
    fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="beet_tmp_")
    os.close(fd)
    try:
        shutil.copy2(ruta, temp_path)
        return client.files.upload(file=temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def _es_error_transitorio(exc: Exception) -> bool:
    """Detecta errores de rate limit / cuota / sobrecarga que ameritan reintento."""
    msg = str(exc).lower()
    return any(s in msg for s in ("429", "resource_exhausted", "rate limit", "quota", "unavailable", "503"))

def _generar_con_reintentos(client, system_instruction, archivo, prompt, intentos=3):
    """
    Con solo 2 API keys rotando y varios workers concurrentes durante el
    auto-escaneo, es fácil pegar en un rate limit puntual. Antes eso se
    atrapaba como error genérico, se guardaba como 'procesado' y nunca se
    reintentaba. Ahora reintentamos con backoff antes de rendirnos.
    """
    ultimo_error = None
    for intento in range(1, intentos + 1):
        try:
            return client.models.generate_content(
                model=MODELO_IMAGEN,
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

def parsear_imagen_historial(ruta_imagen: str) -> ResultadoParseoImagen:
    resultado = ResultadoParseoImagen()
    client = _get_client()
    
    try:
        logger.info(f"Procesando imagen: {ruta_imagen}")
        archivo = _subir_archivo_seguro(client, ruta_imagen)
        
        system_instruction = (
            "Eres un experto en extraer datos de capturas de apuestas de Adam Choi. "
            "Analiza la imagen y extrae la información en formato JSON puro. "
            "hit_mercado_resaltado es TRUE si el fondo de la fila es VERDE, FALSE si es ROJO. "
            "Devuelve SOLO el JSON, sin texto adicional, sin markdown, sin explicaciones."
        )

        prompt = """
Estructura JSON requerida:
{
  "stat_type": "string",
  "highlight_market": "string",
  "filtro_liga": "string",
  "equipo_local_nombre": "string",
  "equipo_visitante_nombre": "string",
  "historial_local": [
    {"fecha": "YYYY-MM-DD", "competicion": "string", "rival": "string", "goles_equipo_analizado": int, "goles_rival": int, "tarjetas_rojas": int, "hit_mercado_resaltado": bool}
  ],
  "historial_visitante": [
    {"fecha": "YYYY-MM-DD", "competicion": "string", "rival": "string", "goles_equipo_analizado": int, "goles_rival": int, "tarjetas_rojas": int, "hit_mercado_resaltado": bool}
  ]
}
"""
        
        response = _generar_con_reintentos(
            client, system_instruction, archivo, prompt
        )
        
        data = _extraer_json(response.text)

        resultado.stat_type = data.get("stat_type", "")
        resultado.highlight_market = data.get("highlight_market", "")
        resultado.filtro_liga = data.get("filtro_liga", "")
        resultado.equipo_local_nombre = data.get("equipo_local_nombre", "")
        resultado.equipo_visitante_nombre = data.get("equipo_visitante_nombre", "")

        partidos_local = []
        for p in data.get("historial_local", []):
            fecha = _parsear_fecha(p.get("fecha", ""))
            if not fecha: continue
            partidos_local.append(PartidoHistorico(
                fecha=fecha, competicion=p.get("competicion", ""),
                rival=normalizar_nombre(p.get("rival", "")),
                marcador=(int(p["goles_equipo_analizado"]), int(p["goles_rival"])),
                tarjetas_rojas=int(p.get("tarjetas_rojas", 0)),
                hit_mercado_resaltado=bool(p.get("hit_mercado_resaltado", False))
            ))
        if partidos_local:
            resultado.historial_local = HistorialEquipo(
                equipo=normalizar_nombre(resultado.equipo_local_nombre),
                partidos=partidos_local
            )

        partidos_vis = []
        for p in data.get("historial_visitante", []):
            fecha = _parsear_fecha(p.get("fecha", ""))
            if not fecha: continue
            partidos_vis.append(PartidoHistorico(
                fecha=fecha, competicion=p.get("competicion", ""),
                rival=normalizar_nombre(p.get("rival", "")),
                marcador=(int(p["goles_equipo_analizado"]), int(p["goles_rival"])),
                tarjetas_rojas=int(p.get("tarjetas_rojas", 0)),
                hit_mercado_resaltado=bool(p.get("hit_mercado_resaltado", False))
            ))
        if partidos_vis:
            resultado.historial_visitante = HistorialEquipo(
                equipo=normalizar_nombre(resultado.equipo_visitante_nombre),
                partidos=partidos_vis
            )

    except Exception as e:
        logger.exception(f"Error crítico parseando {ruta_imagen}")
        resultado.errores.append(f"Error parseando {ruta_imagen}: {str(e)}")
        
    return resultado