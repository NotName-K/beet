# interfaz/__init__.py
"""
interfaz - Paquete de la interfaz gráfica BEET.

Contiene el visor principal (VisorBeet) y las vistas de fixtures y datos.
"""

from .visor import VisorBeet
from .visor_datos import VisorDatos
from .visor_fixtures import VisorFixtures, VentanaLog
from .ventana_fixture import VentanaDatosFixture
from .tarjeta_fixture import TarjetaFixture
from .estilos import QSS
from .componentes import lbl, section_title

__all__ = [
    "VisorBeet",
    "VisorDatos",
    "VisorFixtures",
    "VentanaLog",
    "VentanaDatosFixture",
    "TarjetaFixture",
    "QSS",
    "lbl",
    "section_title",
]