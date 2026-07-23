"""
Parser de imágenes de historial con OCR local (Tesseract).

Estrategia:
1. Dividir la imagen en dos paneles (local / visitante)
2. Extraer metadatos (stat type, highlight market, pestaña de liga)
3. Extraer la tabla de historial fila por fila
4. Detectar color de fondo de cada fila para determinar hit_mercado_resaltado
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import List, Tuple, Optional
import logging

import cv2
import numpy as np
from PIL import Image
import pytesseract

from beet.core.historial_equipo import PartidoHistorico, HistorialEquipo
from beet.core.normalizacion import normalizar_nombre

logger = logging.getLogger(__name__)


# ── Configuración de zonas de interés (ROI) ──────────────────────────────
# Basado en análisis de muestras reales (1774x585)
# Estas coordenadas son relativas al PANEL (mitad de la imagen)
# Se ajustan automáticamente si la imagen tiene otro tamaño.

ROI_CONFIG = {
    'header': {
        'y_start_rel': 0.02,
        'y_end_rel': 0.10,
    },
    'stat_type': {
        'y_start_rel': 0.10,
        'y_end_rel': 0.18,
    },
    'highlight_market': {
        'y_start_rel': 0.18,
        'y_end_rel': 0.26,
    },
    'liga_tabs': {
        'y_start_rel': 0.26,
        'y_end_rel': 0.35,
    },
    'tabla_header': {
        'y_start_rel': 0.35,
        'y_end_rel': 0.42,
    },
    'tabla_filas': {
        'y_start_rel': 0.42,
        'y_end_rel': 0.98,
    },
}


@dataclass
class ResultadoParseoImagen:
    """
    Resultado del parseo de una imagen de historial.
    """
    stat_type: str = ""           # "Total Match Corners" o "Match Result"
    highlight_market: str = ""    # "Over 6.5 Total Corners" o "Win"
    filtro_liga: str = ""         # "K-League 1", "All", etc.
    equipo_local_nombre: str = ""
    equipo_visitante_nombre: str = ""
    historial_local: Optional[HistorialEquipo] = None
    historial_visitante: Optional[HistorialEquipo] = None
    errores: List[str] = field(default_factory=list)
    usó_fallback_api: bool = False


# ── Funciones de utilidad OCR ────────────────────────────────────────────

def _ocr_zona(img_np: np.ndarray, y_start: int, y_end: int, 
              x_start: int = 0, x_end: Optional[int] = None) -> str:
    """Extrae texto de una zona rectangular de la imagen."""
    if x_end is None:
        x_end = img_np.shape[1]
    zona = img_np[y_start:y_end, x_start:x_end]
    if zona.size == 0:
        return ""
    pil_img = Image.fromarray(zona)
    texto = pytesseract.image_to_string(pil_img, config='--psm 6')
    return texto.strip()


def _detectar_pestaña_activa(img_np: np.ndarray, y_start: int, y_end: int) -> str:
    """
    Detecta qué pestaña de liga está activa (resaltada).
    Busca el texto sobre fondo más oscuro (la pestaña activa).
    """
    zona = img_np[y_start:y_end, :]
    if zona.size == 0:
        return "All"  # fallback
    
    # Convertir a escala de grises
    if len(zona.shape) == 3:
        gray = cv2.cvtColor(zona, cv2.COLOR_RGB2GRAY)
    else:
        gray = zona
    
    # Threshold para separar texto de fondo
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    
    # OCR de toda la zona
    texto = pytesseract.image_to_string(
        Image.fromarray(zona), 
        config='--psm 6'
    )
    
    # Heurística: la pestaña activa suele tener fondo más oscuro
    # Buscamos las palabras conocidas
    for liga in ["K-League 1", "K League 2", "Eliteserien", "All"]:
        if liga in texto:
            return liga
    
    # Fallback: buscar cualquier texto que parezca liga
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]
    if lineas:
        # La pestaña activa suele ser la primera o la que tiene más contraste
        return lineas[0]
    
    return "All"


def _extraer_filas_tabla(img_np: np.ndarray, y_start: int, y_end: int,
                         equipo_analizado: str, es_local_panel: bool) -> List[PartidoHistorico]:
    """
    Extrae filas de la tabla de historial.
    
    Args:
        img_np: Imagen del panel (local o visitante)
        y_start, y_end: Zona de la tabla
        equipo_analizado: Nombre del equipo cuyo historial estamos extrayendo
        es_local_panel: True si este panel es el equipo local en el partido actual
    
    Returns:
        Lista de PartidoHistorico
    """
    zona_tabla = img_np[y_start:y_end, :]
    if zona_tabla.size == 0:
        return []
    
    # OCR de toda la zona de tabla
    texto = pytesseract.image_to_string(
        Image.fromarray(zona_tabla),
        config='--psm 6'  # Assume a single uniform block of text
    )
    
    partidos = []
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]
    
    # Patrones de extracción
    # Formato típico: "Jul 19 2026 K-League 1 Bucheon 1995 1-3 Seoul"
    # O para visitante: "Jul 12 2026 K-League 1 Incheon United 5-3 Anyang"
    
    patron_fila = re.compile(
        r'(?P<fecha>[A-Za-z]{3}\s+\d{1,2}\s+\d{4})\s+'
        r'(?P<competicion>[A-Za-z\-]+\s*\d?)\s+'
        r'(?P<resto>.+)'
    )
    
    patron_marcador = re.compile(r'(\d+)\s*[-–]\s*(\d+)')
    
    for linea in lineas:
        # Ignorar header de tabla
        if any(h in linea.lower() for h in ['corners score', 'full time score', 'date', 'competition']):
            continue
        
        match = patron_fila.match(linea)
        if not match:
            continue
        
        fecha_str = match.group('fecha')
        competicion = match.group('competicion').strip()
        resto = match.group('resto')
        
        # Parsear fecha
        try:
            fecha = datetime.strptime(fecha_str, '%b %d %Y').date()
        except ValueError:
            try:
                fecha = datetime.strptime(fecha_str, '%b %d %Y').date()
            except ValueError:
                continue  # No pudimos parsear la fecha
        
        # Extraer marcador del resto
        marcador_match = patron_marcador.search(resto)
        if not marcador_match:
            continue
        
        goles_a = int(marcador_match.group(1))
        goles_b = int(marcador_match.group(2))
        
        # Determinar rival y orientación del marcador
        # En panel local: "Bucheon 1995 1-3 Seoul" → equipo=local, rival=Seoul, marcador=(1,3)
        # En panel visitante: "Incheon United 5-3 Anyang" → equipo=visitante, rival=Incheon, marcador=(3,5)
        
        texto_antes_marcador = resto[:marcador_match.start()].strip()
        texto_despues_marcador = resto[marcador_match.end():].strip()
        
        # Detectar tarjetas rojas (cuadrado rojo en la imagen)
        # Heurística: si hay un carácter extraño o un hueco antes del nombre del equipo
        tarjetas_rojas = 0
        if '🔴' in linea or '[red]' in linea.lower():
            tarjetas_rojas = 1  # Simplificación, en la práctica se detecta por color
        
        # Determinar rival
        if es_local_panel:
            # El equipo analizado aparece antes del marcador
            rival = texto_despues_marcador.strip()
            marcador = (goles_a, goles_b)
        else:
            # El equipo analizado aparece después del marcador
            rival = texto_antes_marcador.strip()
            # Limpiar nombre del rival (puede tener artefactos OCR)
            rival = rival.replace('i', '').replace('|', '').strip()
            marcador = (goles_b, goles_a)  # Invertimos para perspectiva del equipo
        
        # Detectar hit_mercado_resaltado por color de fondo
        # Esto requiere análisis de color — por ahora, placeholder
        # En la imagen real, las filas con hit tienen fondo verde claro
        hit = False  # Se detecta en paso posterior de análisis de color
        
        partidos.append(PartidoHistorico(
            fecha=fecha,
            competicion=competicion,
            rival=normalizar_nombre(rival),
            marcador=marcador,
            tarjetas_rojas=tarjetas_rojas,
            hit_mercado_resaltado=hit,
        ))
    
    return partidos


def _detectar_hits_por_color(img_np: np.ndarray, y_start: int, y_end: int,
                              partidos: List[PartidoHistorico]) -> List[PartidoHistorico]:
    """
    Analiza el color de fondo de cada fila para detectar hits.
    Las filas con fondo verde claro indican que el mercado resaltado se cumplió.
    """
    zona = img_np[y_start:y_end, :]
    if zona.size == 0 or len(partidos) == 0:
        return partidos
    
    # Altura aproximada de cada fila
    altura_total = y_end - y_start
    altura_fila = altura_total // max(len(partidos), 1)
    
    partidos_con_hit = []
    for i, partido in enumerate(partidos):
        # Tomar muestra del color de fondo en el centro de la fila
        y_muestra = y_start + (i * altura_fila) + (altura_fila // 2)
        if y_muestra >= img_np.shape[0]:
            break
        
        # Muestra en el centro horizontal
        x_muestra = img_np.shape[1] // 2
        
        color = img_np[y_muestra, x_muestra]
        
        # Detectar verde: canal G significativamente mayor que R y B
        if len(color) >= 3:
            r, g, b = int(color[0]), int(color[1]), int(color[2])
            # Verde claro típico: G > R+20 y G > B+20
            es_verde = g > r + 15 and g > b + 15
            # También detectar rojo (miss): R > G+20
            es_rojo = r > g + 15 and r > b + 15
            
            hit = es_verde and not es_rojo
        else:
            hit = False
        
        # Crear nuevo PartidoHistorico con hit actualizado
        partidos_con_hit.append(PartidoHistorico(
            fecha=partido.fecha,
            competicion=partido.competicion,
            rival=partido.rival,
            marcador=partido.marcador,
            tarjetas_rojas=partido.tarjetas_rojas,
            hit_mercado_resaltado=hit,
        ))
    
    return partidos_con_hit


def _extraer_nombre_equipo_header(img_np: np.ndarray, y_start: int, y_end: int) -> str:
    """Extrae el nombre del equipo del header del panel."""
    texto = _ocr_zona(img_np, y_start, y_end)
    # Formato típico: "Bucheon 1995 recent home results"
    # o "Anyang recent away results"
    
    match = re.search(r'(.+?)\s+recent\s+(home|away)\s+results', texto, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Fallback: primera línea no vacía
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]
    if lineas:
        return lineas[0]
    
    return "Desconocido"


def _extraer_stat_type(img_np: np.ndarray, y_start: int, y_end: int) -> str:
    """Extrae el valor del dropdown 'Show stat type'."""
    texto = _ocr_zona(img_np, y_start, y_end)
    match = re.search(r'Show\s+stat\s+type:\s*(.+)', texto, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('v').strip()
    return ""


def _extraer_highlight_market(img_np: np.ndarray, y_start: int, y_end: int) -> str:
    """Extrae el valor del dropdown 'Highlight market'."""
    texto = _ocr_zona(img_np, y_start, y_end)
    match = re.search(r'Highlight\s+market:\s*(.+)', texto, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('v').strip()
    return ""


# ── Función pública principal ────────────────────────────────────────────

def parsear_imagen_historial(ruta_imagen: str) -> ResultadoParseoImagen:
    """
    Parsea una imagen de captura de Adam Choi y extrae los historiales.
    
    Args:
        ruta_imagen: Ruta al archivo PNG/JPG.
    
    Returns:
        ResultadoParseoImagen con los datos extraídos.
    """
    resultado = ResultadoParseoImagen()
    
    try:
        img = Image.open(ruta_imagen)
        img_np = np.array(img)
        
        # Convertir a RGB si es necesario
        if img_np.shape[2] == 4:  # RGBA
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
        
        h_total, w_total = img_np.shape[:2]
        mid = w_total // 2
        
        # ── Panel Izquierdo (Local) ─────────────────────────────────────
        panel_local = img_np[:, :mid]
        h_panel, w_panel = panel_local.shape[:2]
        
        # Calcular zonas absolutas
        def zona(rel_start, rel_end):
            return int(h_panel * rel_start), int(h_panel * rel_end)
        
        # Extraer metadatos del panel local
        y1, y2 = zona(0.02, 0.10)
        resultado.equipo_local_nombre = _extraer_nombre_equipo_header(panel_local, y1, y2)
        
        y1, y2 = zona(0.10, 0.18)
        resultado.stat_type = _extraer_stat_type(panel_local, y1, y2)
        
        y1, y2 = zona(0.18, 0.26)
        resultado.highlight_market = _extraer_highlight_market(panel_local, y1, y2)
        
        y1, y2 = zona(0.26, 0.35)
        resultado.filtro_liga = _detectar_pestaña_activa(panel_local, y1, y2)
        
        # Extraer tabla de historial local
        y_tabla_start, y_tabla_end = zona(0.35, 0.98)
        partidos_local = _extraer_filas_tabla(
            panel_local, y_tabla_start, y_tabla_end,
            resultado.equipo_local_nombre, es_local_panel=True
        )
        partidos_local = _detectar_hits_por_color(
            panel_local, y_tabla_start, y_tabla_end, partidos_local
        )
        
        resultado.historial_local = HistorialEquipo(
            equipo=normalizar_nombre(resultado.equipo_local_nombre),
            partidos=partidos_local,
        )
        
        # ── Panel Derecho (Visitante) ────────────────────────────────────
        panel_visitante = img_np[:, mid:]
        
        y1, y2 = zona(0.02, 0.10)
        resultado.equipo_visitante_nombre = _extraer_nombre_equipo_header(panel_visitante, y1, y2)
        
        y_tabla_start, y_tabla_end = zona(0.35, 0.98)
        partidos_visitante = _extraer_filas_tabla(
            panel_visitante, y_tabla_start, y_tabla_end,
            resultado.equipo_visitante_nombre, es_local_panel=False
        )
        partidos_visitante = _detectar_hits_por_color(
            panel_visitante, y_tabla_start, y_tabla_end, partidos_visitante
        )
        
        resultado.historial_visitante = HistorialEquipo(
            equipo=normalizar_nombre(resultado.equipo_visitante_nombre),
            partidos=partidos_visitante,
        )
        
    except Exception as e:
        resultado.errores.append(f"Error parseando {ruta_imagen}: {str(e)}")
        logger.exception("Error en parseo de imagen")
    
    return resultado