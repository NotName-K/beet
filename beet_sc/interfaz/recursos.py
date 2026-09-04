"""
interfaz/recursos.py
Gestión de imágenes (banderas, logos, escudos) e íconos SVG.
"""

import hashlib
import sys
import threading
import unicodedata
from pathlib import Path
from urllib.parse import urlparse
import requests
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QBrush, QPen, QColor, QFont, QTransform
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QLabel
from .estilos import ACCENT2  

_RAIZ = Path(__file__).resolve().parent.parent

# ── Banderas de países ─────────────────────────────────────────────────────
FLAGS_BASE_URL = "https://flagcdn.com/w80/{codigo}.png"

_PAIS_A_ISO2 = {
    "argentina": "ar", "australia": "au", "austria": "at", "belarus": "by",
    "belgica": "be", "belgium": "be", "bolivia": "bo", "brasil": "br",
    "brazil": "br", "bulgaria": "bg", "canada": "ca", "chile": "cl",
    "china": "cn", "colombia": "co", "croacia": "hr", "croatia": "hr",
    "chipre": "cy", "cyprus": "cy", "czech republic": "cz", "republica checa": "cz",
    "czechia": "cz", "dinamarca": "dk", "denmark": "dk", "ecuador": "ec", 
    "egipto": "eg", "egypt": "eg", "emiratos arabes unidos": "ae", 
    "united arab emirates": "ae", "uae": "ae", "eslovaquia": "sk", "slovakia": "sk",
    "eslovenia": "si", "slovenia": "si", "espana": "es", "spain": "es", 
    "estados unidos": "us", "usa": "us", "finlandia": "fi", "finland": "fi", 
    "francia": "fr", "france": "fr", "gales": "gb", "wales": "gb", 
    "grecia": "gr", "greece": "gr", "alemania": "de", "germany": "de",
    "holanda": "nl", "netherlands": "nl", "hungria": "hu", "hungary": "hu", 
    "india": "in", "inglaterra": "gb-eng", "england": "gb-eng", "irlanda": "ie", 
    "ireland": "ie", "northern ireland": "gb", "islandia": "is", "iceland": "is", 
    "israel": "il", "italia": "it", "italy": "it", "japon": "jp", "japan": "jp", 
    "mexico": "mx", "montenegro": "me", "noruega": "no", "norway": "no", 
    "nueva zelanda": "nz", "new zealand": "nz", "paises bajos": "nl", 
    "paraguay": "py", "peru": "pe", "polonia": "pl", "poland": "pl", 
    "portugal": "pt", "republica de corea": "kr", "corea del sur": "kr", 
    "south korea": "kr", "korea republic": "kr", "korea": "kr",
    "rumania": "ro", "romania": "ro", "rusia": "ru", "russia": "ru", 
    "arabia saudita": "sa", "arabia saudi": "sa", "saudi arabia": "sa",
    "serbia": "rs", "escocia": "gb", "scotland": "gb-sct", "sudafrica": "za", 
    "south africa": "za", "suecia": "se", "sweden": "se", "suiza": "ch", 
    "switzerland": "ch", "turquia": "tr", "turkey": "tr", "ucrania": "ua", 
    "ukraine": "ua", "uruguay": "uy", "venezuela": "ve",
}
_FLAG_CACHE: dict[str, bytes | None] = {}
_FLAG_LOCK = threading.Lock()


def _sin_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _codigo_pais(row: dict) -> str | None:
    for key in (
        "country_code", "countryCode", "country_iso", "country_iso2",
        "iso2", "iso_code", "codigo_pais",
    ):
        value = row.get(key)
        if value:
            value = str(value).strip().lower()
            if len(value) == 2 and value.isalpha():
                return value
    pais = _sin_acentos(str(row.get("country", "")).strip().lower())
    return _PAIS_A_ISO2.get(pais)


def _descargar_bandera(codigo: str) -> bytes | None:
    # 1. Nivel memoria RAM
    with _FLAG_LOCK:
        if codigo in _FLAG_CACHE:
            return _FLAG_CACHE[codigo]

    # 2. Nivel disco local
    ruta_disco = CACHE_DIR_FLAGS / f"{codigo}.png"
    if ruta_disco.exists():
        try:
            data = ruta_disco.read_bytes()
            with _FLAG_LOCK:
                _FLAG_CACHE[codigo] = data
            return data
        except OSError as e:
            print(f"[banderas] no se pudo leer cache {ruta_disco}: {e}", file=sys.stderr)

    # 3. Descarga desde la web si no está en disco
    url = FLAGS_BASE_URL.format(codigo=codigo)
    try:
        response = requests.get(
            url,
            timeout=5,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            },
        )
        response.raise_for_status()
        data = response.content
    except Exception as e:
        print(f"[banderas] error descargando {codigo!r} desde {url}: {e}", file=sys.stderr)
        data = None

    # 4. Guardar en disco para futuros inicios
    if data is not None:
        try:
            CACHE_DIR_FLAGS.mkdir(parents=True, exist_ok=True)
            ruta_disco.write_bytes(data)
        except OSError as e:
            print(f"[banderas] no se pudo cachear en disco {ruta_disco}: {e}", file=sys.stderr)

    with _FLAG_LOCK:
        _FLAG_CACHE[codigo] = data
    return data

# ── Logos de equipos (cache en disco + memoria) ─────────────────────────
# ── Directorios de caché en disco ──
CACHE_DIR_FLAGS = _RAIZ / "cache" / "banderas"
CACHE_DIR_LOGOS = _RAIZ / "cache" / "logos"
_IMG_CACHE: dict[str, bytes | None] = {}
_IMG_LOCK = threading.Lock()


def _ruta_cache_logo(url: str) -> Path:
    extension = Path(urlparse(url).path).suffix or ".img"
    clave = hashlib.md5(url.encode("utf-8")).hexdigest()
    return CACHE_DIR_LOGOS / f"{clave}{extension}"


def _descargar_imagen(url: str) -> bytes | None:
    with _IMG_LOCK:
        if url in _IMG_CACHE:
            return _IMG_CACHE[url]

    ruta_disco = _ruta_cache_logo(url)
    if ruta_disco.exists():
        try:
            data = ruta_disco.read_bytes()
            with _IMG_LOCK:
                _IMG_CACHE[url] = data
            return data
        except OSError as e:
            print(f"[imagenes] no se pudo leer cache {ruta_disco}: {e}", file=sys.stderr)

    try:
        response = requests.get(
            url,
            timeout=5,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            },
        )
        response.raise_for_status()
        data = response.content
    except Exception as e:
        print(f"[imagenes] error descargando {url!r}: {e}", file=sys.stderr)
        data = None

    if data is not None:
        try:
            CACHE_DIR_LOGOS.mkdir(parents=True, exist_ok=True)
            ruta_disco.write_bytes(data)
        except OSError as e:
            print(f"[imagenes] no se pudo cachear en disco {ruta_disco}: {e}", file=sys.stderr)

    with _IMG_LOCK:
        _IMG_CACHE[url] = data
    return data


# ── Escudos de equipo (placeholder o logo real) ──────────────────────────
_PALETA_ESCUDOS = [
    "#3d6ef5", "#e84545", "#00d17a", "#f5a623", "#8e5cf7",
    "#f5497f", "#17a2b8", "#c7913a", "#5c9df7", "#e05fa0",
]


def _color_para_equipo(clave: str) -> str:
    h = hashlib.md5(str(clave).encode("utf-8")).hexdigest()
    return _PALETA_ESCUDOS[int(h, 16) % len(_PALETA_ESCUDOS)]


def _iniciales_equipo(nombre: str) -> str:
    palabras = [p for p in str(nombre).split() if p]
    if not palabras:
        return "?"
    if len(palabras) == 1:
        return palabras[0][:2].upper()
    return (palabras[0][0] + palabras[-1][0]).upper()


def crear_escudo(
    nombre: str, clave_color: str | None = None, tamano: int = 40,
    logo_url: str | None = None,
) -> QPixmap:
    """Genera un QPixmap con el escudo del equipo (logo real o placeholder)."""
    if logo_url:
        data = _descargar_imagen(logo_url)
        if data:
            pix_real = QPixmap()
            if pix_real.loadFromData(data):
                return pix_real.scaled(
                    tamano, tamano,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

    color = QColor(_color_para_equipo(clave_color if clave_color is not None else nombre))
    pix = QPixmap(tamano, tamano)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, tamano, tamano)

    painter.setPen(QPen(QColor("#ffffff")))
    f = QFont("Consolas", int(tamano * 0.34))
    f.setBold(True)
    painter.setFont(f)
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, _iniciales_equipo(nombre))
    painter.end()
    return pix


def escudo_label(
    nombre: str, clave_color: str | None = None, tamano: int = 40,
    logo_url: str | None = None,
) -> QLabel:
    lbl_escudo = QLabel()
    lbl_escudo.setFixedSize(tamano, tamano)
    lbl_escudo.setPixmap(crear_escudo(nombre, clave_color, tamano, logo_url))
    lbl_escudo.setToolTip(str(nombre))
    lbl_escudo.setStyleSheet("background:transparent;")
    return lbl_escudo


# ── Íconos SVG (copa y flecha) ───────────────────────────────────────────
_ICONOS_DIR = Path(__file__).resolve().parent / "assets"
_ICONO_COPA = _ICONOS_DIR / "icon_copa.svg"
_ICONO_FLECHA = _ICONOS_DIR / "icon_flecha.svg"
_ICONO_CACHE: dict[tuple, QPixmap] = {}


def _pixmap_svg(ruta: Path, alto: int, color: str) -> QPixmap:
    clave = (str(ruta), alto, color)
    pixmap_cacheado = _ICONO_CACHE.get(clave)
    if pixmap_cacheado is not None:
        return pixmap_cacheado

    renderer = QSvgRenderer(str(ruta))
    view_box = renderer.viewBoxF()
    ancho = alto if not view_box.height() else round(alto * view_box.width() / view_box.height())

    pixmap = QPixmap(max(ancho, 1), alto)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()

    _ICONO_CACHE[clave] = pixmap
    return pixmap


def _icono_flecha_header(colapsado: bool, alto: int, color: str) -> QPixmap:
    """
    Flecha para headers colapsables (HOY/MAÑANA, EN JUEGO, etc.), reusando
    el mismo asset `icon_flecha.svg` (apunta a la derecha por defecto).
    Colapsado -> apunta hacia abajo (90°). Expandido -> apunta hacia
    arriba (-90°).
    """
    grados = 90 if colapsado else -90
    clave = (str(_ICONO_FLECHA), alto, color, grados)
    pixmap_cacheado = _ICONO_CACHE.get(clave)
    if pixmap_cacheado is not None:
        return pixmap_cacheado

    base = _pixmap_svg(_ICONO_FLECHA, alto, color)
    rotado = base.transformed(
        QTransform().rotate(grados), Qt.TransformationMode.SmoothTransformation
    )
    _ICONO_CACHE[clave] = rotado
    return rotado


def _icono_boton_accion(persisted: bool) -> QPixmap:
    color = ACCENT2  # ACCENT2 viene de estilos, importarlo
    flecha = _pixmap_svg(_ICONO_FLECHA, 14, color)
    copa = _pixmap_svg(_ICONO_COPA, 20, color)
    gap = 5
    ancho_total = copa.width() + gap + flecha.width()
    alto = max(copa.height(), flecha.height())

    combinado = QPixmap(ancho_total, alto)
    combinado.fill(Qt.GlobalColor.transparent)
    painter = QPainter(combinado)
    if persisted:
        painter.drawPixmap(0, (alto - copa.height()) // 2, copa)
    painter.drawPixmap(ancho_total - flecha.width(), (alto - flecha.height()) // 2, flecha)
    painter.end()
    return combinado