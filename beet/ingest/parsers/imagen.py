"""
Parser de imágenes de historial con Google Gemini.
Usa la API oficial google-genai con system_instruction y workaround de ruta temporal.
Las API keys se leen desde beet.core.config (~/.beet/config.json), nunca
hardcodeadas aquí — ver beet/ingest/parsers/_gemini_common.py.
"""
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional

from beet.core.historial_equipo import PartidoHistorico, HistorialEquipo
from beet.core.normalizacion import normalizar_nombre
from beet.ingest.parsers._gemini_common import (
    get_client,
    subir_archivo_seguro,
    extraer_json,
    generar_con_reintentos,
    SinApiKeysConfiguradas,
)

logger = logging.getLogger(__name__)

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


def parsear_imagen_historial(ruta_imagen: str) -> ResultadoParseoImagen:
    resultado = ResultadoParseoImagen()

    try:
        client = get_client()
    except SinApiKeysConfiguradas as e:
        resultado.errores.append(str(e))
        return resultado

    try:
        logger.info(f"Procesando imagen: {ruta_imagen}")
        archivo = subir_archivo_seguro(client, ruta_imagen, ".png")

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

        response = generar_con_reintentos(
            client, system_instruction, archivo, prompt, MODELO_IMAGEN
        )

        data = extraer_json(response.text)

        resultado.stat_type = data.get("stat_type", "")
        resultado.highlight_market = data.get("highlight_market", "")
        resultado.filtro_liga = data.get("filtro_liga", "")
        resultado.equipo_local_nombre = data.get("equipo_local_nombre", "")
        resultado.equipo_visitante_nombre = data.get("equipo_visitante_nombre", "")

        partidos_local = []
        for p in data.get("historial_local", []):
            fecha = _parsear_fecha(p.get("fecha", ""))
            if not fecha:
                continue
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
            if not fecha:
                continue
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
