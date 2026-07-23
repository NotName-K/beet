"""
Gestor de datos persistentes para partidos procesados.
Cada partido se guarda como un JSON estructurado en data/partidos/{clave}.json
"""
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import asdict

from beet.ingest.parsers.imagen import ResultadoParseoImagen
from beet.ingest.parsers.pdf import ResultadoParseoPDF
from beet.core.historial_equipo import HistorialEquipo, PartidoHistorico
from beet.core.cuota import Cuota

logger = logging.getLogger(__name__)

# Directorio de datos persistentes
DATA_DIR = Path(__file__).parent.parent / "data"
PARTIDOS_DIR = DATA_DIR / "partidos"

def _ensure_dirs():
    """Crea los directorios si no existen."""
    PARTIDOS_DIR.mkdir(parents=True, exist_ok=True)

def _clave_a_ruta(clave: str) -> Path:
    """Convierte una clave de partido en ruta de archivo JSON."""
    # Sanitizar la clave para que sea un nombre de archivo válido
    clave_limpia = clave.replace("/", "_").replace("\\", "_").replace(":", "_")
    return PARTIDOS_DIR / f"{clave_limpia}.json"

def _serializar_fecha(obj):
    """Helper para serializar objetos date/datetime en JSON."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Tipo no serializable: {type(obj)}")

def guardar_partido(
    clave: str,
    resultado_goles: Optional[ResultadoParseoImagen] = None,
    resultado_corners: Optional[ResultadoParseoImagen] = None,
    resultado_cuotas: Optional[ResultadoParseoPDF] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Guarda o actualiza los datos de un partido.
    
    Args:
        clave: Identificador único del partido (ej: "Ceara_vs_CRB_Brazil_Serie_B")
        resultado_goles: Datos extraídos de imagen_resultado (Match Result)
        resultado_corners: Datos extraídos de imagen_corners (Total Match Corners)
        resultado_cuotas: Datos extraídos del PDF de odds
        metadata: Información adicional (fecha procesamiento, versión parser, etc.)
    """
    _ensure_dirs()
    ruta = _clave_a_ruta(clave)
    
    # Cargar datos existentes si hay
    datos = {}
    if ruta.exists():
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)
        except Exception as e:
            logger.warning(f"No se pudo cargar datos existentes para {clave}: {e}")
    
    # Actualizar metadatos
    if metadata is None:
        metadata = {}
    metadata["ultima_actualizacion"] = datetime.now().isoformat()
    metadata["clave"] = clave
    datos["metadata"] = metadata
    
    # Actualizar con nuevos resultados
    if resultado_goles is not None:
        datos["goles"] = _serializar_resultado_imagen(resultado_goles)
        datos["goles_timestamp"] = datetime.now().isoformat()
    
    if resultado_corners is not None:
        datos["corners"] = _serializar_resultado_imagen(resultado_corners)
        datos["corners_timestamp"] = datetime.now().isoformat()
    
    if resultado_cuotas is not None:
        datos["cuotas"] = _serializar_resultado_pdf(resultado_cuotas)
        datos["cuotas_timestamp"] = datetime.now().isoformat()
    
    # Guardar
    try:
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2, default=_serializar_fecha)
        logger.info(f"Datos guardados para {clave}")
    except Exception as e:
        logger.error(f"Error guardando datos para {clave}: {e}")

def cargar_partido(clave: str) -> Optional[Dict[str, Any]]:
    """
    Carga los datos de un partido.
    
    Returns:
        Dict con claves 'metadata', 'goles', 'corners', 'cuotas' o None si no existe.
    """
    ruta = _clave_a_ruta(clave)
    if not ruta.exists():
        return None
    
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        # Deserializar objetos
        resultado = {"metadata": datos.get("metadata", {})}
        
        if "goles" in datos:
            resultado["goles"] = _deserializar_resultado_imagen(datos["goles"])
        
        if "corners" in datos:
            resultado["corners"] = _deserializar_resultado_imagen(datos["corners"])
        
        if "cuotas" in datos:
            resultado["cuotas"] = _deserializar_resultado_pdf(datos["cuotas"])
        
        return resultado
    except Exception as e:
        logger.error(f"Error cargando datos para {clave}: {e}")
        return None

def listar_partidos() -> List[str]:
    """Lista todas las claves de partidos procesados."""
    _ensure_dirs()
    return [p.stem for p in PARTIDOS_DIR.glob("*.json")]

def partido_procesado(clave: str) -> bool:
    """Verifica si un partido ya tiene datos guardados."""
    return _clave_a_ruta(clave).exists()

def eliminar_partido(clave: str) -> bool:
    """Elimina los datos de un partido."""
    ruta = _clave_a_ruta(clave)
    if ruta.exists():
        ruta.unlink()
        logger.info(f"Datos eliminados para {clave}")
        return True
    return False

def exportar_a_csv(clave: str, ruta_salida: Optional[Path] = None) -> Optional[Path]:
    """
    Exporta los datos de un partido a CSV para análisis en Excel/pandas.
    
    Returns:
        Ruta del archivo CSV creado o None si falló.
    """
    import csv
    
    datos = cargar_partido(clave)
    if not datos:
        return None
    
    if ruta_salida is None:
        ruta_salida = DATA_DIR / f"{clave}_export.csv"
    
    try:
        with open(ruta_salida, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow(["Tipo", "Equipo", "Fecha", "Competicion", "Rival", 
                           "Marcador", "Tarjetas Rojas", "Hit Mercado"])
            
            # Goles - Local
            if "goles" in datos and datos["goles"].get("historial_local"):
                for p in datos["goles"]["historial_local"]["partidos"]:
                    writer.writerow([
                        "Goles", datos["goles"]["historial_local"]["equipo"],
                        p["fecha"], p["competicion"], p["rival"],
                        f"{p['marcador'][0]}-{p['marcador'][1]}",
                        p["tarjetas_rojas"], p["hit_mercado_resaltado"]
                    ])
            
            # Goles - Visitante
            if "goles" in datos and datos["goles"].get("historial_visitante"):
                for p in datos["goles"]["historial_visitante"]["partidos"]:
                    writer.writerow([
                        "Goles", datos["goles"]["historial_visitante"]["equipo"],
                        p["fecha"], p["competicion"], p["rival"],
                        f"{p['marcador'][0]}-{p['marcador'][1]}",
                        p["tarjetas_rojas"], p["hit_mercado_resaltado"]
                    ])
            
            # Corners - Local
            if "corners" in datos and datos["corners"].get("historial_local"):
                for p in datos["corners"]["historial_local"]["partidos"]:
                    writer.writerow([
                        "Corners", datos["corners"]["historial_local"]["equipo"],
                        p["fecha"], p["competicion"], p["rival"],
                        f"{p['marcador'][0]}-{p['marcador'][1]}",
                        p["tarjetas_rojas"], p["hit_mercado_resaltado"]
                    ])
            
            # Corners - Visitante
            if "corners" in datos and datos["corners"].get("historial_visitante"):
                for p in datos["corners"]["historial_visitante"]["partidos"]:
                    writer.writerow([
                        "Corners", datos["corners"]["historial_visitante"]["equipo"],
                        p["fecha"], p["competicion"], p["rival"],
                        f"{p['marcador'][0]}-{p['marcador'][1]}",
                        p["tarjetas_rojas"], p["hit_mercado_resaltado"]
                    ])
            
            # Cuotas
            if "cuotas" in datos:
                writer.writerow([])  # Línea en blanco
                writer.writerow(["Cuota", "Mercado", "Valor", "Casa", "Válida"])
                for c in datos["cuotas"].get("cuotas", []):
                    writer.writerow([
                        "Cuota", c["mercado"], c["valor"], 
                        c["casa_origen"], c["valida"]
                    ])
        
        logger.info(f"Exportado a {ruta_salida}")
        return ruta_salida
    except Exception as e:
        logger.error(f"Error exportando {clave}: {e}")
        return None

def obtener_historial_equipo(equipo: str, tipo: str = "goles") -> List[Dict[str, Any]]:
    """
    Obtiene todo el historial de un equipo desde todos los partidos procesados.
    
    Args:
        equipo: Nombre del equipo (normalizado)
        tipo: "goles" o "corners"
    
    Returns:
        Lista de partidos del equipo.
    """
    historial = []
    
    for archivo in PARTIDOS_DIR.glob("*.json"):
        try:
            with open(archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            
            if tipo in datos:
                # Buscar en local
                if datos[tipo].get("historial_local"):
                    if datos[tipo]["historial_local"]["equipo"].lower() == equipo.lower():
                        historial.extend(datos[tipo]["historial_local"]["partidos"])
                
                # Buscar en visitante
                if datos[tipo].get("historial_visitante"):
                    if datos[tipo]["historial_visitante"]["equipo"].lower() == equipo.lower():
                        historial.extend(datos[tipo]["historial_visitante"]["partidos"])
        except Exception as e:
            logger.warning(f"Error leyendo {archivo}: {e}")
    
    return historial

def obtener_todas_las_cuotas() -> List[Dict[str, Any]]:
    """Obtiene todas las cuotas de todos los partidos procesados."""
    todas_cuotas = []
    
    for archivo in PARTIDOS_DIR.glob("*.json"):
        try:
            with open(archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            
            if "cuotas" in datos:
                for cuota in datos["cuotas"].get("cuotas", []):
                    cuota["partido"] = archivo.stem
                    todas_cuotas.append(cuota)
        except Exception as e:
            logger.warning(f"Error leyendo {archivo}: {e}")
    
    return todas_cuotas

# ── Funciones auxiliares de serialización ──────────────────────────────

def _serializar_resultado_imagen(resultado: ResultadoParseoImagen) -> dict:
    return {
        "stat_type": resultado.stat_type,
        "highlight_market": resultado.highlight_market,
        "filtro_liga": resultado.filtro_liga,
        "equipo_local_nombre": resultado.equipo_local_nombre,
        "equipo_visitante_nombre": resultado.equipo_visitante_nombre,
        "historial_local": _serializar_historial(resultado.historial_local),
        "historial_visitante": _serializar_historial(resultado.historial_visitante),
        "errores": resultado.errores,
    }

def _serializar_historial(historial: Optional[HistorialEquipo]) -> Optional[dict]:
    if historial is None:
        return None
    return {
        "equipo": historial.equipo,
        "partidos": [
            {
                "fecha": partido.fecha.isoformat(),
                "competicion": partido.competicion,
                "rival": partido.rival,
                "marcador": list(partido.marcador),
                "tarjetas_rojas": partido.tarjetas_rojas,
                "hit_mercado_resaltado": partido.hit_mercado_resaltado,
            }
            for partido in historial.partidos
        ]
    }

def _serializar_resultado_pdf(resultado: ResultadoParseoPDF) -> dict:
    return {
        "cuotas": [
            {
                "mercado": cuota.mercado,
                "valor": cuota.valor,
                "casa_origen": cuota.casa_origen,
                "valida": cuota.valida,
            }
            for cuota in resultado.cuotas
        ],
        "secciones_encontradas": resultado.secciones_encontradas,
        "errores": resultado.errores,
    }

def _deserializar_resultado_imagen(datos: dict) -> ResultadoParseoImagen:
    resultado = ResultadoParseoImagen(
        stat_type=datos.get("stat_type", ""),
        highlight_market=datos.get("highlight_market", ""),
        filtro_liga=datos.get("filtro_liga", ""),
        equipo_local_nombre=datos.get("equipo_local_nombre", ""),
        equipo_visitante_nombre=datos.get("equipo_visitante_nombre", ""),
        errores=datos.get("errores", []),
    )
    
    if "historial_local" in datos and datos["historial_local"]:
        resultado.historial_local = _deserializar_historial(datos["historial_local"])
    
    if "historial_visitante" in datos and datos["historial_visitante"]:
        resultado.historial_visitante = _deserializar_historial(datos["historial_visitante"])
    
    return resultado

def _deserializar_historial(datos: dict) -> HistorialEquipo:
    partidos = []
    for p in datos.get("partidos", []):
        partidos.append(PartidoHistorico(
            fecha=date.fromisoformat(p["fecha"]),
            competicion=p["competicion"],
            rival=p["rival"],
            marcador=tuple(p["marcador"]),
            tarjetas_rojas=p["tarjetas_rojas"],
            hit_mercado_resaltado=p["hit_mercado_resaltado"],
        ))
    
    return HistorialEquipo(
        equipo=datos["equipo"],
        partidos=partidos,
    )

def _deserializar_resultado_pdf(datos: dict) -> ResultadoParseoPDF:
    cuotas = []
    for c in datos.get("cuotas", []):
        cuotas.append(Cuota(
            mercado=c["mercado"],
            valor=c["valor"],
            casa_origen=c["casa_origen"],
        ))
    
    return ResultadoParseoPDF(
        cuotas=cuotas,
        secciones_encontradas=datos.get("secciones_encontradas", []),
        errores=datos.get("errores", []),
    )