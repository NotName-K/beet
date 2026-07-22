"""
Agrupador de archivos por partido.

Cada partido llega con 3 archivos que comparten el patrón:
  {local}_vs_{visitante}_predictions_{pais}_-_{liga}.{ext}
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import os


@dataclass
class LoteIngesta:
    """
    Representa un lote de archivos para un mismo partido.
    """
    local: str
    visitante: str
    pais: str
    liga: str
    
    # Rutas a los archivos
    imagen_corners: Optional[Path] = None      # Total Match Corners
    imagen_resultado: Optional[Path] = None      # Match Result
    pdf_odds: Optional[Path] = None              # Odds
    
    def esta_completo(self) -> bool:
        """True si tenemos los 3 archivos esperados."""
        return all([
            self.imagen_corners is not None,
            self.imagen_resultado is not None,
            self.pdf_odds is not None,
        ])
    
    def archivos_faltantes(self) -> List[str]:
        """Lista de tipos de archivo que faltan."""
        faltan = []
        if self.imagen_corners is None:
            faltan.append("imagen_corners")
        if self.imagen_resultado is None:
            faltan.append("imagen_resultado")
        if self.pdf_odds is None:
            faltan.append("pdf_odds")
        return faltan


# Patrón del nombre de archivo:
# {local}_vs_{visitante}_predictions_{pais}_-_{liga}.{ext}
# Ej: "Bucheon 1995 vs Anyang predictions South Korea - K League 1.png"
PATRON_NOMBRE = re.compile(
    r'^(?P<local>.+?)_vs_(?P<visitante>.+?)_predictions_(?P<pais>.+?)_-_(?P<liga>.+?)\.(?P<ext>png|jpg|jpeg|pdf)$',
    re.IGNORECASE
)


def _extraer_clave(ruta: Path) -> Optional[Tuple[str, str, str, str]]:
    """Extrae (local, visitante, pais, liga) del nombre de archivo."""
    match = PATRON_NOMBRE.match(ruta.name)
    if not match:
        return None
    return (
        match.group('local'),
        match.group('visitante'),
        match.group('pais'),
        match.group('liga'),
    )


def _tipo_archivo(ruta: Path) -> Optional[str]:
    """Determina qué tipo de archivo es según contenido/nombre."""
    nombre_lower = ruta.name.lower()
    ext = ruta.suffix.lower()
    
    if ext == '.pdf':
        return 'pdf_odds'
    
    # Para imágenes, inferimos por orden de llegada o contenido
    # En la práctica, el usuario las nombra o las herramientas de captura
    # las generan en orden. Usamos heurística:
    if 'corner' in nombre_lower or 'corners' in nombre_lower:
        return 'imagen_corners'
    if 'result' in nombre_lower:
        return 'imagen_resultado'
    
    # Fallback: si no se puede inferir, retornar None
    # El orquestador debe manejar esto (ej. preguntar al usuario)
    return None


def agrupar_lote(directorio: str) -> Dict[str, LoteIngesta]:
    """
    Escanea un directorio y agrupa archivos por partido.
    
    Args:
        directorio: Ruta al directorio con las capturas.
    
    Returns:
        Dict[clave_str, LoteIngesta] — un lote por partido.
    
    Raises:
        ValueError: Si hay archivos que no coinciden con el patrón esperado.
    """
    lotes: Dict[str, LoteIngesta] = {}
    ruta_dir = Path(directorio)
    
    for archivo in sorted(ruta_dir.iterdir()):
        if not archivo.is_file():
            continue
        
        clave_tupla = _extraer_clave(archivo)
        if clave_tupla is None:
            # Archivo que no coincide con el patrón — lo reportamos
            continue  # o loggear warning
        
        local, visitante, pais, liga = clave_tupla
        clave_str = f"{local}_vs_{visitante}_{pais}_{liga}"
        
        if clave_str not in lotes:
            lotes[clave_str] = LoteIngesta(
                local=local,
                visitante=visitante,
                pais=pais,
                liga=liga,
            )
        
        tipo = _tipo_archivo(archivo)
        lote = lotes[clave_str]
        
        if tipo == 'imagen_corners':
            lote.imagen_corners = archivo
        elif tipo == 'imagen_resultado':
            lote.imagen_resultado = archivo
        elif tipo == 'pdf_odds':
            lote.pdf_odds = archivo
        else:
            # No se pudo inferir el tipo — reportar
            pass
    
    return lotes