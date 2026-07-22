"""
Normalización de nombres de equipo.

Cubre los dos problemas confirmados en el análisis:
1. Caracteres especiales (Bodø, Lillestrøm) — mantener UTF-8 consistente en
   todo el pipeline; sanitizar solo al usar el nombre como nombre de archivo
   (igual que ya se hacía en CALIBRE).
2. Variación de nombre del mismo equipo entre fuentes (ej. "Viking FK" en el
   nombre de archivo vs. "Viking" en el contenido de la página) — tabla de
   nombres canónicos, para cuando se cruce con otra fuente de datos.
"""

from __future__ import annotations

import re
import unicodedata


def sanitizar_para_archivo(nombre: str) -> str:
    """
    Devuelve una versión segura de `nombre` para usar en un nombre de archivo,
    preservando UTF-8 (Bodø, Lillestrøm, etc.) y solo reemplazando los
    caracteres que rompen el sistema de archivos (espacios, barras, etc.).
    """
    nombre = nombre.strip()
    nombre = re.sub(r"[\\/:*?\"<>|]", "_", nombre)
    nombre = re.sub(r"\s+", "_", nombre)
    return nombre


def normalizar_para_comparar(nombre: str) -> str:
    """
    Versión sin acentos/diacríticos en minúsculas, SOLO para comparar o
    hacer lookup — nunca usar esta versión para mostrar o guardar, ya que
    pierde información (Bodø -> Bod).
    """
    sin_acentos = unicodedata.normalize("NFKD", nombre)
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    return sin_acentos.strip().lower()


# Tabla de nombres canónicos: placeholder vacío por ahora.
# Se define en el documento que "se necesitará una tabla de nombres canónicos
# si en el futuro se cruza con otra fuente de datos" — no es urgente para v1
# (una sola fuente, Adam Choi), pero se deja el punto de extensión listo.
#
# Ejemplo de uso futuro:
#   NOMBRES_CANONICOS["Viking FK"] = "Viking"
NOMBRES_CANONICOS: dict[str, str] = {}


def nombre_canonico(nombre: str) -> str:
    """Devuelve el nombre canónico si existe una entrada mapeada; si no, el original."""
    return NOMBRES_CANONICOS.get(nombre, nombre)


def normalizar_nombre(nombre: str) -> str:
    """
    Normaliza un nombre de equipo extraído por OCR para uso en el pipeline
    (comparación, almacenamiento en PartidoHistorico/HistorialEquipo, etc.).

    Mantiene UTF-8 (Bodø, Lillestrøm) — NO usar `normalizar_para_comparar`
    aquí, que elimina diacríticos y perdería información. Solo colapsa
    espacios repetidos (artefacto común de OCR) y aplica el mapeo de
    nombres canónicos cuando existe una entrada para ese nombre.
    """
    nombre = re.sub(r"\s+", " ", nombre.strip())
    return nombre_canonico(nombre)
