"""
Parsers para extracción estructurada desde diferentes fuentes.
"""
from .imagen import parsear_imagen_historial, ResultadoParseoImagen
from .pdf import parsear_pdf_cuotas

__all__ = [
    "parsear_imagen_historial",
    "ResultadoParseoImagen",
    "parsear_pdf_cuotas",
]