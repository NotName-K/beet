
import copy
import json
from translator import parsear_raw_odds_desde_json

with open("fixture_19722821.json") as f:
    fixture_json = json.load(f)

# Caso A: decimal_odds inválida (falla el Field(gt=1.0) de RawOdds)
json_a = copy.deepcopy(fixture_json)
primer_bloque = json_a["odds"][0]
primera_key = next(iter(primer_bloque["outcomes"]))
primer_bloque["outcomes"][primera_key]["decimalOdds"] = 0.5  # inválida

filas_a, errores_a = parsear_raw_odds_desde_json(json_a)
print(f"Caso A (odds=0.5): {len(errores_a)} errores")
if errores_a:
    e = errores_a[0]
    print(f"  market={e.market_name} outcome_key={e.outcome_key}")
    print(f"  error={e.error}")
    print(f"  raw_payload guardado completo: {e.raw_payload}")
    print(f"  status={e.status}")

# Caso B: campo requerido ausente (falta 'outcome')
json_b = copy.deepcopy(fixture_json)
segundo_bloque = json_b["odds"][1]
segunda_key = next(iter(segundo_bloque["outcomes"]))
del segundo_bloque["outcomes"][segunda_key]["outcome"]

filas_b, errores_b = parsear_raw_odds_desde_json(json_b)
print(f"\nCaso B (falta 'outcome'): {len(errores_b)} errores")
if errores_b:
    print(f"  error={errores_b[0].error}")

# Confirmar que el resto del fixture se parseó normal a pesar del error
print(f"\nCaso A: {len(filas_a)} filas OK de todos modos (vs 99 normal)")
print(f"Caso B: {len(filas_b)} filas OK de todos modos (vs 99 normal)")