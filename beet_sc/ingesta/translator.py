"""
El "pegamento" que faltaba: conecta RawOdds (modelos.py) con
market_registry.py y bookmaker_priority.py. Este es el paso 4 completo del
flujo (sección 10 del diseño), ahora alimentado desde datos reales en vez
de diccionarios armados a mano.

Dos responsabilidades separadas a propósito:
1. parsear_raw_odds_desde_json: JSON crudo del fixture -> list[RawOdds]
   (valida cada outcome; los que fallan van a ValidationErrors, no rompen
   el resto — ver estrategia de validación, sección 3).
2. traducir_fixture: list[RawOdds] -> outcomes traducidos, agrupando por
   (market_name, outcome_key) entre bookmakers y aplicando la prioridad
   de bookmaker_priority.py antes de llamar a market_registry.traducir_outcome.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Union

from bookmaker_priority import elegir_bookmaker
from modelos import RawOdds, ValidationErrors
from market_registry import MARKET_REGISTRY, traducir_outcome
from special_markets import HtFt, Resultado


# ---------------------------------------------------------------------------
# Paso 1: JSON crudo -> list[RawOdds] (+ ValidationErrors por outcome que falle)
# ---------------------------------------------------------------------------

def parsear_raw_odds_desde_json(fixture_json: dict) -> tuple[list[RawOdds], list[ValidationErrors]]:
    """
    Recorre data['odds'] del JSON crudo del fixture y construye una
    RawOdds por outcome. Solo incluye mercados presentes en MARKET_REGISTRY
    (whitelist de ingesta) — un mercado no listado se ignora en silencio
    acá porque la whitelist ya es una decisión de diseño tomada, no un
    error de datos (a diferencia de un outcome que sí está en la
    whitelist pero no valida).
    """
    filas: list[RawOdds] = []
    errores: list[ValidationErrors] = []
    fixture_id = fixture_json["external_id"]

    for bloque in fixture_json["odds"]:
        market_name = bloque["market"]["name"]
        if market_name not in MARKET_REGISTRY:
            continue  # fuera de whitelist — decisión ya tomada, no es error

        for outcome_key, o in bloque["outcomes"].items():
            try:
                filas.append(RawOdds(
                    fixture_id=fixture_id,
                    market_name=market_name,
                    display_rule=bloque["market"].get("displayRule"),
                    outcome_key=outcome_key,
                    outcome=o.get("outcome"),
                    outcome_name=o.get("outcomeName"),
                    bookmaker=o.get("bookmaker"),
                    decimal_odds=o.get("decimalOdds"),
                    external_bet_id=o.get("externalBetId"),
                    team_id=o.get("teamId"),
                ))
            except Exception as e:
                errores.append(ValidationErrors(
                    fixture_id=fixture_id,
                    market_name=market_name,
                    outcome_key=outcome_key,
                    error=str(e),
                    raw_payload=o,
                ))
    return filas, errores


# ---------------------------------------------------------------------------
# Paso 2: list[RawOdds] -> outcomes traducidos, con bookmaker ya elegido
# ---------------------------------------------------------------------------

@dataclass
class OutcomeTraducido:
    market_name: str
    outcome_key: str
    bookmaker_usado: str
    decimal_odds: float
    # Para mercados genéricos: (Resultado | None, línea | None).
    # Para Double Chance: frozenset[Resultado]. Para HT/FT: HtFt.
    traduccion: Union[tuple, frozenset, HtFt]


def traducir_fixture(filas: list[RawOdds]) -> list[OutcomeTraducido]:
    """
    Agrupa las filas por (market_name, outcome_key) — es decir, el MISMO
    outcome lógico reportado por distintos bookmakers — elige el
    bookmaker de mayor prioridad para cada grupo, y traduce ese outcome
    una sola vez usando market_registry.traducir_outcome.

    Nota: se agrupa por outcome_key (la clave del diccionario `outcomes`
    en el JSON fuente, ej. "Aberdeen"), no por `outcome` crudo — para
    Total/Team shots on target el campo `outcome` es igual para todas las
    líneas de un lado (ver sección 8/10), así que agrupar por `outcome`
    colapsaría líneas distintas entre sí.
    """
    grupos: dict[tuple[str, str], list[RawOdds]] = defaultdict(list)
    for fila in filas:
        grupos[(fila.market_name, fila.outcome_key)].append(fila)

    resultado: list[OutcomeTraducido] = []
    for (market_name, outcome_key), candidatos in grupos.items():
        elegido = elegir_bookmaker([c.model_dump() for c in candidatos])
        if elegido is None:
            continue  # no debería pasar (el grupo nunca está vacío), defensivo

        entry = MARKET_REGISTRY[market_name]
        if entry.calculator is None and entry.side_source == "none" and entry.line_source == "none":
            # Caso Handicap Result: se guarda pero no se traduce (ver decisión
            # de sección 6.3) — se omite acá, no es un error.
            continue

        traduccion = traducir_outcome(market_name, elegido["outcome"], elegido["outcome_name"])
        resultado.append(OutcomeTraducido(
            market_name=market_name,
            outcome_key=outcome_key,
            bookmaker_usado=elegido["bookmaker"],
            decimal_odds=elegido["decimal_odds"],
            traduccion=traduccion,
        ))
    return resultado


if __name__ == "__main__":
    import json

    from pathlib import Path
    _fixture_path = Path(__file__).resolve().parent.parent / "fixtures_test" / "fixture_19664045.json"
    with open(_fixture_path) as f:
        fixture_json = json.load(f)

    filas, errores = parsear_raw_odds_desde_json(fixture_json)
    print(f"{len(filas)} filas RawOdds parseadas, {len(errores)} errores de validación")

    traducidos = traducir_fixture(filas)
    print(f"{len(traducidos)} outcomes lógicos traducidos (post-agrupación por bookmaker)\n")

    # Mostrar los casos que ya generaron dudas antes: Result, Total shots on
    # target (línea repetida en outcome crudo), Double Chance, y confirmar
    # que Handicap Result quedó excluido de la traducción.
    interesantes = {"Result", "Total shots on target", "Double Chance", "Handicap Result"}
    for ot in traducidos:
        if ot.market_name in interesantes:
            print(f"{ot.market_name:22s} {ot.outcome_key:12s} bookmaker={ot.bookmaker_usado:18s} "
                  f"odds={ot.decimal_odds:5.2f} -> {ot.traduccion}")

    assert not any(ot.market_name == "Handicap Result" for ot in traducidos), \
        "Handicap Result no debería aparecer traducido"
    print("\nOK: Handicap Result correctamente excluido de la traducción.")
