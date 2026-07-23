"""
Parser de PDFs de cuotas con Google Gemini.
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
from dataclasses import dataclass, field
from typing import List

from google import genai
from beet.core.cuota import Cuota

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

MODELO_PDF = "gemini-3.1-flash-lite"

@dataclass
class ResultadoParseoPDF:
    cuotas: List[Cuota] = field(default_factory=list)
    secciones_encontradas: List[str] = field(default_factory=list)
    errores: List[str] = field(default_factory=list)

def _extraer_json(texto: str) -> dict:
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return json.loads(texto)

def _subir_archivo_seguro(client: genai.Client, ruta: str) -> object:
    ext = os.path.splitext(ruta)[1] or ".pdf"
    fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="beet_tmp_")
    os.close(fd)
    try:
        shutil.copy2(ruta, temp_path)
        return client.files.upload(file=temp_path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def parsear_pdf_cuotas(ruta_pdf: str) -> ResultadoParseoPDF:
    resultado = ResultadoParseoPDF()
    client = _get_client()
    
    try:
        logger.info(f"Procesando PDF: {ruta_pdf}")
        archivo = _subir_archivo_seguro(client, ruta_pdf)
        
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
        
        response = client.models.generate_content(
            model=MODELO_PDF,
            config={"system_instruction": system_instruction},
            contents=[archivo, prompt]
        )
        
        data = _extraer_json(response.text)
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