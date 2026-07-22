"""
Modelo principal de un partido de ingesta. Agrupa el historial de ambos
equipos (siempre 2, uno por cada uno) y las cuotas extraídas del PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from beet.core.cuota import Cuota
from beet.core.historial_equipo import HistorialEquipo


@dataclass
class Partido:
    liga: str  # ej. "Norwegian Eliteserien"
    pais: str  # ej. "Norway"
    filtro_liga_aplicado: str  # pestaña seleccionada al capturar (nunca "All" por defecto)
    local: str
    visitante: str
    historial_local: HistorialEquipo
    historial_visitante: HistorialEquipo
    cuotas: list[Cuota] = field(default_factory=list)

    def __post_init__(self) -> None:
        for campo, valor in (
            ("liga", self.liga),
            ("pais", self.pais),
            ("filtro_liga_aplicado", self.filtro_liga_aplicado),
            ("local", self.local),
            ("visitante", self.visitante),
        ):
            if not valor or not valor.strip():
                raise ValueError(f"Partido.{campo} no puede estar vacío")

        if self.filtro_liga_aplicado.strip().lower() == "all":
            raise ValueError(
                "filtro_liga_aplicado no puede ser 'All': la pestaña de liga debe "
                "fijarse explícitamente al capturar, nunca depender del default de la página."
            )

        if self.local == self.visitante:
            raise ValueError("local y visitante no pueden ser el mismo equipo")

        if self.historial_local.equipo != self.local:
            raise ValueError(
                f"historial_local.equipo ({self.historial_local.equipo!r}) "
                f"no coincide con local ({self.local!r})"
            )
        if self.historial_visitante.equipo != self.visitante:
            raise ValueError(
                f"historial_visitante.equipo ({self.historial_visitante.equipo!r}) "
                f"no coincide con visitante ({self.visitante!r})"
            )

    @property
    def clave_archivo(self) -> str:
        """
        Reconstruye la clave natural de agrupamiento del lote:
        `{local}_vs_{visitante}_predictions_{pais}_-_{liga}`
        Útil para verificar que el Partido armado corresponde al archivo original.
        """
        return f"{self.local}_vs_{self.visitante}_predictions_{self.pais}_-_{self.liga}"

    @property
    def cuotas_validas(self) -> list[Cuota]:
        """Cuotas aptas para entrar al cálculo de EV (valor > 1.00)."""
        return [c for c in self.cuotas if c.valida]

    @property
    def cuotas_para_revision(self) -> list[Cuota]:
        """Cuotas marcadas inválidas (<=1.00) — van a pantalla de revisión manual."""
        return [c for c in self.cuotas if not c.valida]
