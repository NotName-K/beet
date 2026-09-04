from obtener_v import obtener_v_cacheado
from obtener_fixtures_dia import fetch_stat

data = fetch_stat("BTTS", obtener_v_cacheado())
# un solo fixture + su league_block, para ver todos los campos disponibles
liga = data["dates"][0]["leagues"][0]
print(liga.keys())
print(liga["fixtures"][0].keys())
print(liga["flag"])