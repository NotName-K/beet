"""
Beet Ingest — Pipeline de ingesta de datos desde capturas de pantalla y PDFs.
"""
from .agrupador import agrupar_lote, LoteIngesta
from .parsers.imagen import parsear_imagen_historial
from .parsers.pdf import parsear_pdf_cuotas

__all__ = [
    "agrupar_lote",
    "LoteIngesta",
    "parsear_imagen_historial",
    "parsear_pdf_cuotas",
]