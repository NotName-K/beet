"""
Parser de PDFs de cuotas con Google Gemini.
Usa la API oficial google-genai con system_instruction y workaround de ruta temporal.
Las API keys se leen desde beet.core.config (~/.beet/config.json), nunca
hardcodeadas aquí — ver beet/ingest/parsers/_gemini_common.py.
"""
import logging
from dataclasses import dataclass, field
from typing import List

from beet.core.cuota import Cuota
from beet.ingest.parsers._gemini_common import (
    get_client,
    subir_archivo_seguro,
    extraer_json,
    generar_con_reintentos,
    SinApiKeysConfiguradas,
)

logger = logging.getLogger(__name__)

MODELO_PDF = "gemini-3.1-flash-lite"


@dataclass
class ResultadoParseoPDF:
    cuotas: List[Cuota] = field(default_factory=list)
    secciones_encontradas: List[str] = field(default_factory=list)
    errores: List[str] = field(default_factory=list)


def parsear_pdf_cuotas(ruta_pdf: str) -> ResultadoParseoPDF:
    resultado = ResultadoParseoPDF()

    try:
        client = get_client()
    except SinApiKeysConfiguradas as e:
        resultado.errores.append(str(e))
        return resultado

    try:
        logger.info(f"Procesando PDF: {ruta_pdf}")
        archivo = subir_archivo_seguro(client, ruta_pdf, ".pdf")

        system_instruction = (
            "Extrae todas las cuotas de apuestas de este PDF de Adam Choi/bet365. "
            "Devuelve SOLO un JSON válido, sin markdown, sin texto adicional."
        )

        prompt = """
Estructura JSON requerida:
{
  "secciones": ["Result", "BTTS", "Match Goals O/U", "Total Corners"],
  "cuotas": [
    {"mercado": "1X2 - Local", "valor": 1.85, "casa": "bet365"},
    {"mercado": "BTTS - Si", "valor": 1.72, "casa": "bet365"}
  ]
}
"""

        # Antes esto llamaba a generate_content() directo, sin reintentos:
        # una falla transitoria (rate limit/cuota) se guardaba como
        # "procesado" sin datos y nunca se reintentaba — mismo problema
        # que ya se había resuelto para imagen.py pero no para PDFs.
        response = generar_con_reintentos(
            client, system_instruction, archivo, prompt, MODELO_PDF
        )

        data = extraer_json(response.text)
        resultado.secciones_encontradas = data.get("secciones", [])

        for c in data.get("cuotas", []):
            try:
                resultado.cuotas.append(Cuota(
                    mercado=str(c["mercado"]),
                    valor=float(c["valor"]),
                    casa_origen=str(c.get("casa", "bet365"))
                ))
            except Exception as e:
                resultado.errores.append(f"Error mapeando cuota {c}: {e}")

    except Exception as e:
        logger.exception(f"Error crítico procesando PDF {ruta_pdf}")
        resultado.errores.append(f"Error procesando PDF {ruta_pdf}: {str(e)}")

    return resultado
