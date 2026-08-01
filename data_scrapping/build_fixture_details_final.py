"""
build_fixture_details.py
Descarga el detalle completo de un partido desde Adam Choi / api.choistats.com.
"""

import argparse
import json
import time
from pathlib import Path
from typing import Optional

import requests
import urllib3

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== HEADERS PARA api.choistats.com (odds, chances, team-records) ==========
HEADERS_CHOISTATS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.5",
    "Authorization-Client": "ADAMCHOI.CO.UK",
    "Connection": "keep-alive",
    "Origin": "https://www.adamchoi.co.uk",
    "X-AdamChoi-Api-Token": "45834886-68b3-11eb-99f4-9e36325824ad",
    "Sec-GPC": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# ========== HEADERS PARA www.adamchoi.co.uk directo (comparison-stats) ==========
# Copiados EXACTOS de un cURL real del navegador para este endpoint puntual.
# OJO: a diferencia de choistats.com, acá el navegador NO manda Origin ni
# X-AdamChoi-Api-Token — mandarlos de más es lo que probablemente gatillaba el 403.
HEADERS_ADAMCHOI_DIRECT = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Authorization-Client": "ADAMCHOI.CO.UK",
    "Sec-GPC": "1",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "TE": "trailers",
}

# Cookie exacta (sin sb-bhjrlmnnseavaoapqlkr-auth-token, no hace falta)
COOKIE_STRING = (
    "_ga_8MTGZ91RT2=GS2.1.s1785477942$o14$g1$t1785477947$j55$l0$h0; "
    "_ga=GA1.3.1259201419.1776566076; "
    "_pubcid=2a2c7a2b-2c92-480b-a03b-82ed5b42e5ea; "
    "__gads=ID=35983ed40def41c8:T=1781124240:RT=1783468468:S=ALNI_MZML0Kpe8VjYCYh0dLVTbtVl-dpMQ; "
    "__gpi=UID=000013c9223e929e:T=1781124240:RT=1783468468:S=ALNI_MaY2GYc2tRv_5bJhy89yxJwqWQzWw; "
    "__eoi=ID=41fcc126e3dd794c:T=1781124240:RT=1783468468:S=AA-AfjaQji5AZYPzIAzDuetZSzLk; "
    "FCCDCF=%5Bnull%2Cnull%2Cnull%2Cnull%2Cnull%2Cnull%2C%5B%5B32%2C%22%5B%5C%22818402f3-3a7c-4212-bf35-f8338caf2794%5C%22%2C%5B1781463845%2C667000000%5D%5D%22%5D%5D%5D; "
    "_gid=GA1.3.1203602925.1785477946"
)

# ========== HEADERS PARA recent-results (levemente distintos: cross-site, Referer genérico) ==========
HEADERS_RECENT_RESULTS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.adamchoi.co.uk/",
    "X-AdamChoi-Api-Token": "45834886-68b3-11eb-99f4-9e36325824ad",
    "Origin": "https://www.adamchoi.co.uk",
    "Sec-GPC": "1",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

def get_session(external_id: int, headers: dict) -> requests.Session:
    session = requests.Session()
    session.headers.update(headers)
    if "Referer" not in headers:
        session.headers["Referer"] = f"https://www.adamchoi.co.uk/fixture/{external_id}/austria-bundesliga-lask-linz-vs-grazer-ak"
    session.headers["Cookie"] = COOKIE_STRING
    session.verify = False
    return session

def get_json_cffi(url: str, params: dict, external_id: int, label: str, headers: dict) -> Optional[dict]:
    """Igual que get_json pero usando curl_cffi para imitar el fingerprint TLS de Firefox real."""
    req_headers = dict(headers)
    req_headers["Referer"] = f"https://www.adamchoi.co.uk/fixture/{external_id}/austria-bundesliga-lask-linz-vs-grazer-ak"
    req_headers["Cookie"] = COOKIE_STRING
    try:
        r = cffi_requests.get(url, params=params, headers=req_headers, impersonate="firefox135", timeout=20)
        print(f"    [{label} via curl_cffi] status={r.status_code}")
        if r.status_code != 200:
            print(f"    [{label} via curl_cffi] body preview: {r.text[:300]!r}")
            return None
        data = r.text
        if not data or not (data.lstrip().startswith('{') or data.lstrip().startswith('[')):
            print(f"    [{label} via curl_cffi] warning: respuesta no parece JSON")
            return None
        return json.loads(data)
    except Exception as e:
        print(f"    [{label} via curl_cffi] ERROR: {e}")
        return None

def get_json(url: str, params: dict, external_id: int, label: str, headers: dict = HEADERS_CHOISTATS) -> Optional[dict]:
    session = get_session(external_id, headers)
    try:
        r = session.get(url, params=params, timeout=20)
        if r.status_code != 200:
            print(f"    [{label}] status={r.status_code}")
            return None

        r.encoding = 'utf-8'
        data = r.text

        if not data or not (data.lstrip().startswith('{') or data.lstrip().startswith('[')):
            print(f"    [{label}] warning: respuesta no parece JSON")
            return None

        return json.loads(data)
    except json.JSONDecodeError as e:
        print(f"    [{label}] JSON decode error: {e}")
        if 'r' in locals():
            print(f"    [{label}] preview: {r.text[:200]}")
        return None
    except Exception as e:
        print(f"    [{label}] ERROR: {e}")
        return None

def fetch_fixture_detail(external_id: int, token: str) -> dict:
    print(f"  Descargando detalle de fixture {external_id} ...")

    odds = get_json(
        f"https://api.choistats.com/api/widget/match/{external_id}/odds",
        {"clflc": "abc", "lang": "en", "token": token},
        external_id, "odds",
    )
    chances = get_json(
        f"https://api.choistats.com/api/widget/chances/fixture/{external_id}",
        {"clflc": "abc", "bookmakerId": "", "token": token},
        external_id, "chances",
    )
    team_records = get_json(
        f"https://api.choistats.com/api/widget/match/{external_id}/team-records",
        {"clflc": "abc", "token": token},
        external_id, "team-records",
    )
    recent_results = get_json(
        f"https://api.choistats.com/api/widget/match/{external_id}/recent-results",
        {"clflc": "abc", "lang": "en", "token": token},
        external_id, "recent-results",
        headers=HEADERS_RECENT_RESULTS,
    )
    if HAS_CURL_CFFI:
        comparison_stats = get_json_cffi(
            "https://www.adamchoi.co.uk/scripts/data/json/scripts/pages/comparison/getComparisonStatsAsJson.php",
            {"clflc": "abc", "fixtureid": external_id, "numrecentmatches": 10},
            external_id, "comparison-stats",
            headers=HEADERS_ADAMCHOI_DIRECT,
        )
        if comparison_stats is None:
            print("    [comparison-stats] curl_cffi tampoco funcionó, reintentando con requests normal...")
            comparison_stats = get_json(
                "https://www.adamchoi.co.uk/scripts/data/json/scripts/pages/comparison/getComparisonStatsAsJson.php",
                {"clflc": "abc", "fixtureid": external_id, "numrecentmatches": 10},
                external_id, "comparison-stats",
                headers=HEADERS_ADAMCHOI_DIRECT,
            )
    else:
        print("    [comparison-stats] curl_cffi no instalado (pip install curl_cffi), usando requests normal")
        comparison_stats = get_json(
            "https://www.adamchoi.co.uk/scripts/data/json/scripts/pages/comparison/getComparisonStatsAsJson.php",
            {"clflc": "abc", "fixtureid": external_id, "numrecentmatches": 10},
            external_id, "comparison-stats",
            headers=HEADERS_ADAMCHOI_DIRECT,
        )
    if comparison_stats is None:
        print("    [comparison-stats] nota: sigue bloqueado, se guarda como null y se sigue")

    return {
        "external_id": external_id,
        "odds": odds,
        "chances": chances,
        "team_records": team_records,
        "recent_results": recent_results,
        "comparison_stats": comparison_stats,
    }

def run(external_ids: list[int], out_dir: str, token: str, delay_s: float):
    out_path = Path(out_dir)
    out_path.mkdir(exist_ok=True)

    ok, failed = 0, []
    for i, eid in enumerate(external_ids, 1):
        print(f"[{i}/{len(external_ids)}]")
        detail = fetch_fixture_detail(eid, token)

        missing = [k for k in ("odds", "chances") if detail.get(k) is None]
        if missing:
            failed.append((eid, missing))

        fname = out_path / f"fixture_{eid}.json"
        fname.write_text(json.dumps(detail, indent=2, ensure_ascii=False), encoding="utf-8")
        ok += 1

        if i < len(external_ids):
            time.sleep(delay_s)

    print(f"\n{ok} detalles guardados en {out_path}/")
    if failed:
        print(f"{len(failed)} con algún endpoint faltante:")
        for eid, missing in failed:
            print(f"  fixture {eid}: faltó {missing}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-id", type=int, help="un solo fixture externalid")
    parser.add_argument(
        "--from-staging",
        help="ruta a comparativas_staging.json (salida de build_comparativas.py)",
    )
    parser.add_argument("--limit", type=int, default=None, help="límite de fixtures a procesar")
    parser.add_argument("--out-dir", default="detalles_fixtures")
    parser.add_argument("--token", default="45834886-68b3-11eb-99f4-9e36325824ad")
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    if args.external_id:
        ids = [args.external_id]
    elif args.from_staging:
        rows = json.loads(Path(args.from_staging).read_text(encoding="utf-8"))
        ids = [row["external_id"] for row in rows if row.get("external_id")]
        if args.limit:
            ids = ids[: args.limit]
    else:
        parser.error("hay que pasar --external-id o --from-staging")

    run(ids, args.out_dir, args.token, args.delay)