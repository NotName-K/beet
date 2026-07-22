"""
Parser de PDF de cuotas usando pdfplumber.

Estrategia:
1. Extraer texto de cada página
2. Limpiar ruido conocido (superposición de navegación)
3. Identificar secciones de mercados
4. Extraer cuotas por casa de apuestas
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
import logging

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from beet.core.cuota import Cuota

logger = logging.getLogger(__name__)


# Ruido conocido a limpiar
RUIDO_CONOCIDO = [
    (r'Resultlt', 'Result'),  # Barra de navegación superpuesta
    (r'Odddsl', 'Odds'),
    (r'Over\s+(\d+\.?\d*)\s+Total\s+Corners', r'Over \1 Total Corners'),
]


@dataclass
class ResultadoParseoPDF:
    """
    Resultado del parseo de un PDF de cuotas.
    """
    cuotas: List[Cuota] = field(default_factory=list)
    secciones_encontradas: List[str] = field(default_factory=list)
    errores: List[str] = field(default_factory=list)


def _limpiar_texto(texto: str) -> str:
    """Limpia ruido conocido del texto extraído del PDF."""
    for patron, reemplazo in RUIDO_CONOCIDO:
        texto = re.sub(patron, reemplazo, texto, flags=re.IGNORECASE)
    return texto


def _extraer_seccion(texto: str, titulo_seccion: str) -> Optional[str]:
    """
    Extrae el bloque de texto correspondiente a una sección del PDF.
    Las secciones están separadas por headers en mayúsculas o negrita.
    """
    # Patrón: título de sección seguido de contenido hasta la siguiente sección
    patron = re.compile(
        rf'{re.escape(titulo_seccion)}\\s*\\n(.*?)(?=\\n[A-Z][A-Z\\s]{{3,}}\\n|\\Z)',
        re.DOTALL | re.IGNORECASE
    )
    match = patron.search(texto)
    if match:
        return match.group(1).strip()
    return None


def _parsear_tabla_cuotas(bloque_texto: str, mercado: str) -> List[Cuota]:
    """
    Parsea un bloque de texto con formato tabla de cuotas.
    
    Formato típico:
    bet365    1.85
    Unibet    1.90
    """
    cuotas = []
    
    # Patrones comunes de líneas de cuota
    # Casa: valor  o  Casa valor  o  Casa    valor
    patron_linea = re.compile(
        r'^\\s*(?P<casa>[A-Za-z0-9\\s\\.]+?)\\s+(?P<valor>\\d+\\.\\d+)\\s*$'
    )
    
    for linea in bloque_texto.split('\n'):
        linea = linea.strip()
        if not linea:
            continue
        
        match = patron_linea.match(linea)
        if match:
            casa = match.group('casa').strip()
            try:
                valor = float(match.group('valor'))
                cuotas.append(Cuota(
                    mercado=mercado,
                    valor=valor,
                    casa_origen=casa,
                ))
            except ValueError:
                continue
    
    return cuotas


# Secciones conocidas que pueden aparecer en el PDF
SECCIONES_CONOCIDAS = [
    "Match Result",
    "Total Match Corners",
    "Most Corners",
    "Both Teams To Score",
    "Over/Under 2.5 Goals",
]


def parsear_pdf_cuotas(ruta_pdf: str) -> ResultadoParseoPDF:
    """
    Parsea un PDF de cuotas de Adam Choi.
    
    Args:
        ruta_pdf: Ruta al archivo PDF.
    
    Returns:
        ResultadoParseoPDF con las cuotas extraídas.
    """
    resultado = ResultadoParseoPDF()
    
    if pdfplumber is None:
        resultado.errores.append("pdfplumber no está instalado. Instalar con: pip install pdfplumber")
        return resultado
    
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            texto_completo = ""
            for page in pdf.pages:
                texto = page.extract_text()
                if texto:
                    texto_completo += texto + "\n"
        
        texto_limpio = _limpiar_texto(texto_completo)
        
        # Intentar extraer cada sección conocida
        for seccion in SECCIONES_CONOCIDAS:
            bloque = _extraer_seccion(texto_limpio, seccion)
            if bloque:
                resultado.secciones_encontradas.append(seccion)
                cuotas_seccion = _parsear_tabla_cuotas(bloque, seccion)
                resultado.cuotas.extend(cuotas_seccion)
        
        # Si no encontramos secciones estructuradas, intentar parseo genérico
        if not resultado.cuotas:
            # Buscar cualquier patrón de cuota en el texto
            patron_generico = re.compile(
                r'(?P<casa>[A-Za-z][A-Za-z0-9\\s\\.]{2,20})\\s+(?P<valor>\\d+\\.\\d{2})'
            )
            for match in patron_generico.finditer(texto_limpio):
                casa = match.group('casa').strip()
                valor = float(match.group('valor'))
                # Intentar inferir el mercado del contexto
                mercado = "Unknown"
                resultado.cuotas.append(Cuota(
                    mercado=mercado,
                    valor=valor,
                    casa_origen=casa,
                ))
        
    except Exception as e:
        resultado.errores.append(f"Error parseando PDF {ruta_pdf}: {str(e)}")
        logger.exception("Error en parseo de PDF")
    
    return resultado