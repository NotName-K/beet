"""
Historial reciente de un equipo, tal como llega de las 2 capturas fijas
(corners y resultado). Longitud variable: 5 a 10+ partidos, nunca N fijo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class PartidoHistorico:
    fecha: date
    competicion: str  # puede diferir de la liga principal si no se filtró bien
    rival: str
    marcador: tuple[int, int]  # (equipo_analizado, rival) — orientación ya correcta
    tarjetas_rojas: int  # 0, 1, 2... NUNCA booleano
    hit_mercado_resaltado: bool  # si el mercado resaltado se cumplió ese partido

    def __post_init__(self) -> None:
        # bool es subclase de int en Python — hay que rechazarlo explícitamente
        # o "True" pasaría silenciosamente como tarjetas_rojas=1.
        if isinstance(self.tarjetas_rojas, bool) or not isinstance(self.tarjetas_rojas, int):
            raise TypeError(
                f"tarjetas_rojas debe ser int, no bool ni {type(self.tarjetas_rojas).__name__}"
            )
        if self.tarjetas_rojas < 0:
            raise ValueError("tarjetas_rojas no puede ser negativo")

        if len(self.marcador) != 2 or not all(isinstance(g, int) for g in self.marcador):
            raise ValueError("marcador debe ser una tupla de 2 enteros (equipo_analizado, rival)")
        if any(g < 0 for g in self.marcador):
            raise ValueError("marcador no puede tener goles negativos")

        if not self.rival or not self.rival.strip():
            raise ValueError("rival no puede estar vacío")


@dataclass
class HistorialEquipo:
    equipo: str
    partidos: list[PartidoHistorico] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.equipo or not self.equipo.strip():
            raise ValueError("equipo no puede estar vacío")
        if len(self.partidos) < 5:
            # No es un error duro (podría venir de un equipo recién ascendido con
            # poco historial), pero conviene poder detectarlo aguas arriba.
            self._historial_corto = True
        else:
            self._historial_corto = False

    @property
    def historial_corto(self) -> bool:
        """True si hay menos de 5 partidos — señal para revisión, no bloqueo."""
        return self._historial_corto

    @property
    def cantidad_partidos(self) -> int:
        return len(self.partidos)

    def tasa_hit_mercado(self) -> float | None:
        """Proporción de partidos donde se cumplió el mercado resaltado."""
        if not self.partidos:
            return None
        aciertos = sum(1 for p in self.partidos if p.hit_mercado_resaltado)
        return aciertos / len(self.partidos)
