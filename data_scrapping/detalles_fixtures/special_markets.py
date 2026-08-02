"""
Mapeos fijos para los dos mercados "especiales" del MarketRegistry que no
encajan en el modelo genérico side_source/line_source:

- Double Chance: cada outcome combina DOS resultados posibles (no un lado
  simple, no una línea).
- Half Time/Full Time: cada outcome combina resultado al descanso +
  resultado final (hasta 9 combinaciones posibles).

Estas tablas se declaran en la entrada correspondiente del MarketRegistry
(calculator=... y una referencia a este mapeo) en vez de usar el parser
genérico de side/line. Ver sección 6.3 del diseño de ingesta.
"""

from enum import Enum
from typing import NamedTuple


class Resultado(str, Enum):
    """Resultado de un partido (o de una mitad) desde la perspectiva local/visitante."""
    LOCAL = "LOCAL"
    EMPATE = "EMPATE"
    VISITANTE = "VISITANTE"


# ---------------------------------------------------------------------------
# Double Chance — 3 combinaciones fijas, verificadas en fixture_19722821
# ---------------------------------------------------------------------------

# Cada entrada mapea el `outcome` crudo a los dos resultados que cubre.
# No hay "línea" ni "lado simple": el outcome ya es la unidad completa.
DOUBLE_CHANCE_MAP: dict[str, frozenset[Resultado]] = {
    "HOME_WIN_OR_DRAW": frozenset({Resultado.LOCAL, Resultado.EMPATE}),
    "AWAY_WIN_OR_DRAW": frozenset({Resultado.VISITANTE, Resultado.EMPATE}),
    "HOME_WIN_OR_AWAY_WIN": frozenset({Resultado.LOCAL, Resultado.VISITANTE}),
}


def traducir_double_chance(outcome: str) -> frozenset[Resultado]:
    """
    Traduce un `outcome` crudo de Double Chance a los dos Resultado que cubre.

    Lanza KeyError si el outcome no es uno de los 3 valores conocidos —
    igual que con la whitelist de mercados/campos: un valor nuevo no
    documentado debe fallar ruidosamente, no ignorarse en silencio.
    """
    return DOUBLE_CHANCE_MAP[outcome]


# ---------------------------------------------------------------------------
# Half Time/Full Time — hasta 9 combinaciones (3 HT x 3 FT)
# ---------------------------------------------------------------------------

class HtFt(NamedTuple):
    ht: Resultado
    ft: Resultado


# Generadas por el patrón HT_FT_<mitad>_<final> confirmado en el `outcome`.
# 4 de las 9 están verificadas contra datos reales (fixture_19722821):
# HOME_HOME, DRAW_HOME, AWAY_AWAY, DRAW_AWAY. Las otras 5 se derivan del
# mismo patrón de nombres pero aún no se han visto en un fixture real —
# quedan documentadas como tal por si el naming real difiere.
HT_FT_MAP: dict[str, HtFt] = {
    "HT_FT_HOME_HOME": HtFt(Resultado.LOCAL, Resultado.LOCAL),            # verificado
    "HT_FT_HOME_DRAW": HtFt(Resultado.LOCAL, Resultado.EMPATE),           # sin verificar
    "HT_FT_HOME_AWAY": HtFt(Resultado.LOCAL, Resultado.VISITANTE),        # sin verificar
    "HT_FT_DRAW_HOME": HtFt(Resultado.EMPATE, Resultado.LOCAL),           # verificado
    "HT_FT_DRAW_DRAW": HtFt(Resultado.EMPATE, Resultado.EMPATE),          # sin verificar
    "HT_FT_DRAW_AWAY": HtFt(Resultado.EMPATE, Resultado.VISITANTE),       # verificado
    "HT_FT_AWAY_HOME": HtFt(Resultado.VISITANTE, Resultado.LOCAL),        # sin verificar
    "HT_FT_AWAY_DRAW": HtFt(Resultado.VISITANTE, Resultado.EMPATE),       # sin verificar
    "HT_FT_AWAY_AWAY": HtFt(Resultado.VISITANTE, Resultado.VISITANTE),    # verificado
}


def traducir_ht_ft(outcome: str) -> HtFt:
    """
    Traduce un `outcome` crudo de Half Time/Full Time al resultado de
    descanso + resultado final.

    Lanza KeyError si el outcome no es uno de los 9 valores conocidos.
    """
    return HT_FT_MAP[outcome]


if __name__ == "__main__":
    # Smoke test contra los outcomes reales vistos en fixture_19722821.json
    casos_double_chance = ["HOME_WIN_OR_DRAW", "AWAY_WIN_OR_DRAW", "HOME_WIN_OR_AWAY_WIN"]
    for c in casos_double_chance:
        print(c, "->", traducir_double_chance(c))

    casos_ht_ft = ["HT_FT_HOME_HOME", "HT_FT_DRAW_HOME", "HT_FT_AWAY_AWAY", "HT_FT_DRAW_AWAY"]
    for c in casos_ht_ft:
        print(c, "->", traducir_ht_ft(c))
