"""
MarketRegistry: mapea cada market_name de la whitelist de ingesta (19
mercados, sección 1.1 del diseño) a la estrategia declarativa para extraer
lado y línea de sus outcomes (sección 6 del diseño), más el parser genérico
compartido que ambas estrategias usan.

Los dos mercados "especiales" (Double Chance, Half Time/Full Time) no usan
este parser genérico — usan las tablas de mapeo fijo en special_markets.py.
Handicap Result no usa parser en absoluto (calculator=None, side_source/
line_source="none") porque se decidió inferir su cuota desde el mercado
Result (1X2) en el futuro MercadoCalculator, en vez de parsear sus outcomes.
"""

import re
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel

from special_markets import Resultado, traducir_double_chance, traducir_ht_ft


# ---------------------------------------------------------------------------
# Modelo de entrada del registry
# ---------------------------------------------------------------------------

SideSource = Literal["outcome_suffix", "outcome_prefix", "outcome_infix", "none", "special"]
LineSource = Literal["outcome", "outcome_name", "none"]


class MarketRegistryEntry(BaseModel):
    market_name: str
    side_source: SideSource
    line_source: LineSource
    # calculator=None: mercado guardado (whitelist de ingesta) pero sin
    # MercadoCalculator implementado todavía — el motor lo ignora hasta
    # que se implemente. No es un error, es el estado esperado para varios
    # mercados en esta etapa (ver sección 6, nota de MarketRegistry vs
    # whitelist de ingesta).
    calculator: Optional[str] = None  # placeholder: nombre del futuro MercadoCalculator


# ---------------------------------------------------------------------------
# Parser genérico de lado — compartido por todas las entradas con
# side_source != "none"/"special"
# ---------------------------------------------------------------------------

def extraer_lado(outcome: str, side_source: SideSource) -> Optional[Resultado]:
    """
    Extrae el lado (local/visitante/empate) de un `outcome` crudo.

    side_source documenta DÓNDE se espera el token (prefijo/sufijo/infijo)
    por razones de legibilidad del registry, pero el parser en sí es
    posicionalmente agnóstico: separa el `outcome` por `_` y busca el
    primer token que sea exactamente HOME/AWAY/DRAW. Esto es suficiente
    porque el vocabulario de outcomes ya es consistente (ver sección 6.1) y
    evita mantener un regex distinto por posición.

    Nota: no se puede usar `\\b` de regex para esto — `_` cuenta como
    carácter de palabra, así que `RESULT_HOME_WIN` se ve como un solo
    "word" y `\\bHOME\\b` nunca hace match ahí. Separar por `_` evita el problema.

    Devuelve None si side_source es "none" (mercado tipo total, sin lado)
    o si no se encuentra ningún token (indica un outcome inesperado que
    debe fallar más arriba, no aquí).
    """
    if side_source == "none":
        return None
    if side_source == "special":
        raise ValueError("Los mercados 'special' no usan extraer_lado — usar special_markets.py")

    tokens = outcome.split("_")
    for token in tokens:
        if token in ("HOME", "AWAY", "DRAW"):
            return {"HOME": Resultado.LOCAL, "AWAY": Resultado.VISITANTE, "DRAW": Resultado.EMPATE}[token]
    return None  # outcome inesperado — el llamador decide si es error


# ---------------------------------------------------------------------------
# Parser genérico de línea — compartido por todas las entradas con
# line_source != "none"
# ---------------------------------------------------------------------------

# Ej: TOTAL_CORNERS_OVER_7_5 -> 7.5 ; HOME_WIN_MINUS_1 -> -1.0
_LINE_FROM_OUTCOME_RE = re.compile(r"(OVER|UNDER|MINUS|PLUS)_(\d+)(?:_(\d+))?$")

# Ej: "Over 7.5" -> 7.5 ; "Aberdeen (-1)" no aplica (Handicap no usa este source)
_LINE_FROM_NAME_RE = re.compile(r"(Over|Under)\s+([\d.]+)", re.IGNORECASE)


def extraer_linea(outcome: str, outcome_name: str, line_source: LineSource) -> Optional[float]:
    """
    Extrae la línea numérica (ej. 7.5, -1.0) de un outcome, desde el campo
    declarado por line_source.

    "outcome": parsea el patrón OVER_N_M / UNDER_N_M / MINUS_N / PLUS_N al
    final del `outcome` (ej. `TOTAL_CORNERS_OVER_7_5`). Válido para 17 de
    los 19 mercados whitelist (sección 6.1).

    "outcome_name": parsea "Over N.N" / "Under N.N" desde `outcomeName` en
    vez de `outcome`. Excepción confirmada para Total/Team shots on target
    (sección 6.1): ahí el `outcome` es fijo sin línea (ej.
    `MATCH_SHOTS_ON_TARGET_OVER`), la línea solo existe en `outcomeName`.

    "none": el mercado no tiene línea (ej. Result, BTTS).
    """
    if line_source == "none":
        return None

    if line_source == "outcome":
        match = _LINE_FROM_OUTCOME_RE.search(outcome)
        if match is None:
            return None
        sign, entero, decimal = match.groups()
        valor = float(f"{entero}.{decimal}") if decimal else float(entero)
        return -valor if sign == "MINUS" else valor

    if line_source == "outcome_name":
        match = _LINE_FROM_NAME_RE.search(outcome_name)
        if match is None:
            return None
        return float(match.group(2))

    raise ValueError(f"line_source desconocido: {line_source}")


# ---------------------------------------------------------------------------
# El registry: 19 mercados de la whitelist de ingesta (sección 1.1 / 6.3)
# ---------------------------------------------------------------------------

MARKET_REGISTRY: dict[str, MarketRegistryEntry] = {
    "Result": MarketRegistryEntry(
        market_name="Result", side_source="outcome_suffix", line_source="none"),
    "BTTS": MarketRegistryEntry(
        market_name="BTTS", side_source="none", line_source="none"),
    "Match Goals Overs/Unders": MarketRegistryEntry(
        market_name="Match Goals Overs/Unders", side_source="none", line_source="outcome"),
    "Team Goals Overs/Unders": MarketRegistryEntry(
        market_name="Team Goals Overs/Unders", side_source="outcome_prefix", line_source="outcome"),
    "Double Chance": MarketRegistryEntry(
        market_name="Double Chance", side_source="special", line_source="none"),
    "Total Corners": MarketRegistryEntry(
        market_name="Total Corners", side_source="none", line_source="outcome"),
    "Team Corners": MarketRegistryEntry(
        market_name="Team Corners", side_source="outcome_prefix", line_source="outcome"),
    "Handicap Result": MarketRegistryEntry(
        market_name="Handicap Result", side_source="none", line_source="none",
        calculator=None),  # decisión: se infiere desde Result (1X2), no se parsea
    "First Half Result": MarketRegistryEntry(
        market_name="First Half Result", side_source="outcome_suffix", line_source="none"),
    "Second Half Result": MarketRegistryEntry(
        market_name="Second Half Result", side_source="outcome_suffix", line_source="none"),
    "First Half Total Goals": MarketRegistryEntry(
        market_name="First Half Total Goals", side_source="none", line_source="outcome"),
    "Second Half Total Goals": MarketRegistryEntry(
        market_name="Second Half Total Goals", side_source="none", line_source="outcome"),
    "First Half Team Goals": MarketRegistryEntry(
        market_name="First Half Team Goals", side_source="outcome_infix", line_source="outcome"),
    "Second Half Team Goals": MarketRegistryEntry(
        market_name="Second Half Team Goals", side_source="outcome_infix", line_source="outcome"),
    "Half Time/Full Time": MarketRegistryEntry(
        market_name="Half Time/Full Time", side_source="special", line_source="none"),
    "Total Cards": MarketRegistryEntry(
        market_name="Total Cards", side_source="none", line_source="outcome"),
    "Team Cards": MarketRegistryEntry(
        market_name="Team Cards", side_source="outcome_prefix", line_source="outcome"),
    "Total shots on target": MarketRegistryEntry(
        market_name="Total shots on target", side_source="none", line_source="outcome_name"),
    "Team shots on target": MarketRegistryEntry(
        market_name="Team shots on target", side_source="outcome_infix", line_source="outcome_name"),
}

assert len(MARKET_REGISTRY) == 19, "El registry debe tener exactamente los 19 mercados whitelist"


# ---------------------------------------------------------------------------
# Punto de entrada del traductor: combina side + line + casos especiales
# ---------------------------------------------------------------------------

def traducir_outcome(market_name: str, outcome: str, outcome_name: str):
    """
    Traduce un outcome crudo de raw_odds a su representación de dominio,
    usando la entrada correspondiente del MarketRegistry.

    Devuelve:
    - Para mercados "special" (Double Chance, HT/FT): lo que devuelva su
      traductor propio (frozenset[Resultado] o HtFt).
    - Para mercados genéricos: una tupla (lado: Resultado | None, línea: float | None).

    Lanza KeyError si market_name no está en el registry (mercado no
    soportado por el traductor todavía, aunque esté en raw_odds).
    """
    entry = MARKET_REGISTRY[market_name]

    if entry.side_source == "special":
        if market_name == "Double Chance":
            return traducir_double_chance(outcome)
        if market_name == "Half Time/Full Time":
            return traducir_ht_ft(outcome)
        raise ValueError(f"Mercado 'special' sin traductor propio: {market_name}")

    lado = extraer_lado(outcome, entry.side_source)
    linea = extraer_linea(outcome, outcome_name, entry.line_source)
    return (lado, linea)


if __name__ == "__main__":
    # Smoke test contra outcomes reales de fixture_19722821.json
    casos = [
        ("Result", "RESULT_HOME_WIN", "Aberdeen"),
        ("Team Goals Overs/Unders", "HOME_TEAM_GOALS_OVER_0_5", "Aberdeen Over 0.5"),
        ("Total Corners", "TOTAL_CORNERS_OVER_7_5", "Over 7.5"),
        ("Handicap Result", "HOME_WIN_MINUS_1", "Aberdeen (-1)"),
        ("Total shots on target", "MATCH_SHOTS_ON_TARGET_OVER", "Over 7.5"),
        ("Team shots on target", "TEAM_SHOTS_ON_TARGET_HOME_OVER", "Aberdeen Over 3.5"),
        ("Double Chance", "HOME_WIN_OR_DRAW", "Aberdeen or Draw"),
        ("Half Time/Full Time", "HT_FT_DRAW_AWAY", "HT/FT - Draw/Hearts"),
    ]
    for market, outcome, outcome_name in casos:
        print(f"{market:28s} {outcome:35s} -> {traducir_outcome(market, outcome, outcome_name)}")
