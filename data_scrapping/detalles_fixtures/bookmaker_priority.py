"""
Selección de bookmaker por prioridad para el traductor raw_odds -> Comparativa/Pronostico.

Orden aplicado: BET365 > SPORTMONKSBET365 > UNIBET.

Cualquier bookmaker nuevo que aparezca en raw_odds y no esté en esta lista
cae al final del orden (después de UNIBET) en vez de romper la selección —
se loggea como aviso para revisión, siguiendo el mismo criterio de whitelist
estricta usado en el resto del pipeline: lo desconocido no se ignora en
silencio, pero tampoco bloquea el flujo.
"""

import logging
from typing import Iterable

logger = logging.getLogger(__name__)

BOOKMAKER_PRIORITY: list[str] = ["BET365", "SPORTMONKSBET365", "UNIBET"]


def _priority_key(bookmaker: str) -> int:
    """Índice de prioridad; bookmakers desconocidos van al final."""
    try:
        return BOOKMAKER_PRIORITY.index(bookmaker)
    except ValueError:
        logger.warning(
            "Bookmaker desconocido '%s' no está en BOOKMAKER_PRIORITY — "
            "se trata con prioridad más baja que todas las conocidas.",
            bookmaker,
        )
        return len(BOOKMAKER_PRIORITY)


def elegir_bookmaker(outcomes_por_bookmaker: Iterable[dict]) -> dict | None:
    """
    Dado un conjunto de registros raw_odds para el MISMO outcome lógico
    (mismo fixture, mismo market_name, mismo outcome_key) mecanizados por
    distintos bookmakers, devuelve el registro del bookmaker de mayor
    prioridad disponible.

    Cada elemento de `outcomes_por_bookmaker` es un dict con al menos la
    clave "bookmaker" (ej. el row de raw_odds ya cargado).

    Devuelve None si la lista de entrada está vacía (ese outcome no tiene
    cuota de ningún bookmaker para este fixture/mercado).
    """
    candidatos = list(outcomes_por_bookmaker)
    if not candidatos:
        return None
    return min(candidatos, key=lambda row: _priority_key(row["bookmaker"]))


if __name__ == "__main__":
    # Smoke test con datos de forma similar a los de fixture_19722821.json:
    # Double Chance trae UNIBET y SPORTMONKSBET365 para el mismo outcome lógico.
    ejemplo = [
        {"bookmaker": "UNIBET", "decimal_odds": 1.30, "outcome": "HOME_WIN_OR_AWAY_WIN"},
        {"bookmaker": "SPORTMONKSBET365", "decimal_odds": 1.28, "outcome": "HOME_WIN_OR_AWAY_WIN"},
    ]
    print(elegir_bookmaker(ejemplo))
    # Esperado: gana SPORTMONKSBET365 sobre UNIBET (no hay BET365 en este caso)

    ejemplo_con_bet365 = ejemplo + [
        {"bookmaker": "BET365", "decimal_odds": 1.29, "outcome": "HOME_WIN_OR_AWAY_WIN"}
    ]
    print(elegir_bookmaker(ejemplo_con_bet365))
    # Esperado: gana BET365 sobre las otras dos

    print(elegir_bookmaker([]))
    # Esperado: None

    print(elegir_bookmaker([{"bookmaker": "PINNACLE", "decimal_odds": 1.31, "outcome": "X"}]))
    # Esperado: PINNACLE (única opción), con warning loggeado por desconocido
