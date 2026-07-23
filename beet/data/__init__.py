"""
Módulo de gestión de datos persistentes.
Aquí se almacenan los resultados de los parsers para análisis posterior,
backtesting y alimentación del modelo de predicción.
"""
from beet.data.gestor import (
    guardar_partido,
    cargar_partido,
    listar_partidos,
    partido_procesado,
    eliminar_partido,
    exportar_a_csv,
    obtener_historial_equipo,
    obtener_todas_las_cuotas,
)

__all__ = [
    "guardar_partido",
    "cargar_partido",
    "listar_partidos",
    "partido_procesado",
    "eliminar_partido",
    "exportar_a_csv",
    "obtener_historial_equipo",
    "obtener_todas_las_cuotas",
]