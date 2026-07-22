"""
Modelo de cuota (odds) extraída del PDF de un partido.

Regla de negocio (definida en esquema-datos-ingesta.md):
    Cualquier cuota <= 1.00 es un dato corrupto de la fuente. Se marca
    `valida=False` y NUNCA debe entrar al cálculo de EV. En vez de
    descartarse silenciosamente, debe quedar visible para revisión manual.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Cuota:
    mercado: str
    valor: float
    casa_origen: str  # ej. "bet365", "Unibet" — puede haber varias casas por partido
    valida: bool = field(init=False)

    def __post_init__(self) -> None:
        if not self.mercado or not self.mercado.strip():
            raise ValueError("Cuota.mercado no puede estar vacío")
        if not self.casa_origen or not self.casa_origen.strip():
            raise ValueError("Cuota.casa_origen no puede estar vacío")

        # `valida` no se recibe del exterior: se deriva siempre del valor,
        # para que no sea posible instanciar una Cuota con valor corrupto
        # marcada como válida por error del llamador.
        object.__setattr__(self, "valida", self.valor > 1.00)

    @property
    def apta_para_ev(self) -> bool:
        """Alias explícito para dejar clara la intención en el motor de EV."""
        return self.valida
