"""
Agrupador de archivos por partido.

Cada partido llega con 3 archivos:
  - 1 PDF de cuotas ("odds")
  - 2 capturas de pantalla (PNG): una de "Match Result" y otra de
    "Total Match Corners". Ninguna de las dos incluye esas palabras en
    el nombre — se distinguen por el momento de captura, que la
    herramienta de recorte de Windows antepone como
    "Screenshot {fecha} at {hora} ...". Por convención confirmada del
    usuario, la captura más antigua es siempre "Match Result" y la más
    reciente es siempre "Total Match Corners".

Nombres reales observados (no siguen un único patrón consistente):
  "Náutico vs Londrina predictions _ Brazil - Serie B.pdf"
  "Screenshot 2026-07-22 at 16-11-44 Náutico vs Londrina predictions Brazil - Serie B.png"
  "Screenshot 2026-07-22 at 16-11-50 Náutico vs Londrina predictions Brazil - Serie B.png"

Notar que el PDF trae un " _ " suelto antes del país que los PNG no
traen — probablemente un artefacto de cómo se guardó ese archivo en
particular. El regex de abajo tolera ambos casos.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional


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


@dataclass
class _InfoArchivo:
    """Resultado interno de parsear el nombre de un archivo."""
    local: str
    visitante: str
    pais: str
    liga: str
    momento_captura: Optional[datetime] = None  # solo presente en screenshots


# Patrón real del nombre de archivo. Tolera:
#   - un prefijo opcional "Screenshot {fecha} at {hora} " (lo agrega la
#     herramienta de recorte de Windows en las capturas, no en los PDF)
#   - espacios como separador ("Local vs Visitante predictions Pais - Liga")
#     en vez de guiones bajos
#   - un "_" suelto y opcional antes del país (aparece en algunos PDF)
PATRON_NOMBRE = re.compile(
    r'^(?:Screenshot\s+(?P<fecha_captura>\d{4}-\d{2}-\d{2})\s+at\s+'
    r'(?P<hora_captura>\d{2}-\d{2}-\d{2})\s+)?'
    r'(?P<local>.+?)\s+vs\s+(?P<visitante>.+?)\s+predictions\s*_?\s*'
    r'(?P<pais>.+?)\s+-\s+(?P<liga>.+?)'
    r'\.(?P<ext>png|jpg|jpeg|pdf)$',
    re.IGNORECASE
)


def _extraer_info(ruta: Path) -> Optional[_InfoArchivo]:
    """Extrae local/visitante/pais/liga (y el timestamp de captura, si es
    una screenshot) del nombre de archivo."""
    match = PATRON_NOMBRE.match(ruta.name)
    if not match:
        return None

    momento_captura = None
    fecha_captura = match.group('fecha_captura')
    hora_captura = match.group('hora_captura')
    if fecha_captura and hora_captura:
        try:
            momento_captura = datetime.strptime(
                f"{fecha_captura} {hora_captura}", "%Y-%m-%d %H-%M-%S"
            )
        except ValueError:
            momento_captura = None

    return _InfoArchivo(
        local=match.group('local'),
        visitante=match.group('visitante'),
        pais=match.group('pais'),
        liga=match.group('liga'),
        momento_captura=momento_captura,
    )


def agrupar_lote(directorio: str) -> Dict[str, LoteIngesta]:
    """
    Escanea un directorio y agrupa archivos por partido.

    Args:
        directorio: Ruta al directorio con las capturas.

    Returns:
        Dict[clave_str, LoteIngesta] — un lote por partido.
    """
    lotes: Dict[str, LoteIngesta] = {}

    # Imágenes pendientes de clasificar como corners/resultado, agrupadas
    # por partido — se deciden al final, comparando timestamps entre sí,
    # no se puede saber mirando un solo archivo de forma aislada.
    imagenes_por_clave: Dict[str, List[Tuple[Path, Optional[datetime]]]] = {}

    ruta_dir = Path(directorio)

    for archivo in sorted(ruta_dir.iterdir()):
        if not archivo.is_file():
            continue

        info = _extraer_info(archivo)
        if info is None:
            # Archivo que no coincide con el patrón esperado — se ignora.
            continue

        clave_str = f"{info.local}_vs_{info.visitante}_{info.pais}_{info.liga}"

        if clave_str not in lotes:
            lotes[clave_str] = LoteIngesta(
                local=info.local,
                visitante=info.visitante,
                pais=info.pais,
                liga=info.liga,
            )

        if archivo.suffix.lower() == '.pdf':
            lotes[clave_str].pdf_odds = archivo
        else:
            imagenes_por_clave.setdefault(clave_str, []).append(
                (archivo, info.momento_captura)
            )

    # Asignar imagen_resultado / imagen_corners según el orden de captura:
    # la más antigua es "Match Result", la más reciente es
    # "Total Match Corners" (orden fijo confirmado por el usuario).
    for clave_str, imagenes in imagenes_por_clave.items():
        lote = lotes[clave_str]

        con_timestamp = sorted(
            (img for img in imagenes if img[1] is not None),
            key=lambda par: par[1],
        )
        sin_timestamp = [img for img in imagenes if img[1] is None]

        if len(con_timestamp) >= 2:
            lote.imagen_resultado = con_timestamp[0][0]
            lote.imagen_corners = con_timestamp[1][0]
        elif len(con_timestamp) == 1 and not sin_timestamp:
            # Una sola imagen con timestamp y ninguna otra: no hay forma
            # confiable de saber si es resultado o corners. Se asigna a
            # imagen_corners porque es la única que el pipeline actual
            # (VisorController → parsear_imagen_historial) procesa hoy.
            lote.imagen_corners = con_timestamp[0][0]
        elif sin_timestamp:
            # Imágenes renombradas a mano, sin el prefijo "Screenshot ...":
            # tampoco hay señal para diferenciarlas. Se toma la primera en
            # orden alfabético por el mismo motivo de arriba.
            lote.imagen_corners = sorted(sin_timestamp, key=lambda p: p[0].name)[0][0]

    return lotes
