from pathlib import Path
import hashlib
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
DB_DIR = ROOT / "db"
CACHE = ROOT / "cache" / "logos"

print("=" * 90)
print("DIAGNÓSTICO DEFINITIVO DE ESCUDOS")
print("=" * 90)

print("ROOT :", ROOT)
print("DB   :", DB_DIR)
print("CACHE:", CACHE)

# ---------------------------------------------------------------------
# 1. CACHE
# ---------------------------------------------------------------------

print("\n" + "=" * 90)
print("1. ARCHIVOS DEL CACHE")
print("=" * 90)

archivos_cache = sorted(
    p for p in CACHE.iterdir()
    if p.is_file()
)

for p in archivos_cache:
    print(p.name)

print("\nTOTAL CACHE:", len(archivos_cache))


# ---------------------------------------------------------------------
# 2. TODAS LAS DB
# ---------------------------------------------------------------------

print("\n" + "=" * 90)
print("2. METADATA DE LAS DB")
print("=" * 90)

dbs = sorted(DB_DIR.glob("*.db"))

print("DB encontradas:", len(dbs))

for db in dbs:

    print("\n" + "-" * 90)
    print("DB:", db.name)
    print("-" * 90)

    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row

        tablas = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

        print("fixture_metadata existe:",
              "fixture_metadata" in tablas)

        if "fixture_metadata" not in tablas:
            conn.close()
            continue

        columnas = [
            r["name"]
            for r in conn.execute(
                "PRAGMA table_info(fixture_metadata)"
            )
        ]

        print("Columnas:", columnas)

        rows = conn.execute(
            "SELECT * FROM fixture_metadata"
        ).fetchall()

        print("Filas:", len(rows))

        for row in rows:

            print("\nFIXTURE:", row["fixture_id"])
            print("HOME:", row["home_team_name"])
            print("AWAY:", row["away_team_name"])

            home_url = row["home_team_logo"]
            away_url = row["away_team_logo"]

            print("\n HOME LOGO")
            print(" URL :", repr(home_url))

            if home_url:

                md5 = hashlib.md5(
                    home_url.encode("utf-8")
                ).hexdigest()

                print(" MD5 :", md5)

                candidatos = [
                    CACHE / md5,
                    CACHE / f"{md5}.png",
                    CACHE / f"{md5}.svg",
                    CACHE / f"{md5}.webp",
                    CACHE / f"{md5}.jpg",
                    CACHE / f"{md5}.jpeg",
                    CACHE / f"{md5}.img",
                ]

                for candidato in candidatos:
                    if candidato.exists():
                        print(" ENCONTRADO:", candidato.name)

                encontrados = [
                    p for p in CACHE.glob(md5 + ".*")
                ]

                if encontrados:
                    print(
                        " GLOB:",
                        [p.name for p in encontrados]
                    )

                if not encontrados and not (CACHE / md5).exists():
                    print(" !!! NO ENCONTRADO EN CACHE !!!")

            else:
                print(" !!! HOME URL ES NONE/VACÍA !!!")


            print("\n AWAY LOGO")
            print(" URL :", repr(away_url))

            if away_url:

                md5 = hashlib.md5(
                    away_url.encode("utf-8")
                ).hexdigest()

                print(" MD5 :", md5)

                candidatos = [
                    CACHE / md5,
                    CACHE / f"{md5}.png",
                    CACHE / f"{md5}.svg",
                    CACHE / f"{md5}.webp",
                    CACHE / f"{md5}.jpg",
                    CACHE / f"{md5}.jpeg",
                    CACHE / f"{md5}.img",
                ]

                for candidato in candidatos:
                    if candidato.exists():
                        print(" ENCONTRADO:", candidato.name)

                encontrados = [
                    p for p in CACHE.glob(md5 + ".*")
                ]

                if encontrados:
                    print(
                        " GLOB:",
                        [p.name for p in encontrados]
                    )

                if not encontrados and not (CACHE / md5).exists():
                    print(" !!! NO ENCONTRADO EN CACHE !!!")

            else:
                print(" !!! AWAY URL ES NONE/VACÍA !!!")

        conn.close()

    except Exception as e:

        print("ERROR:", repr(e))


# ---------------------------------------------------------------------
# 3. PRUEBA REAL DE QT
# ---------------------------------------------------------------------

print("\n" + "=" * 90)
print("3. PRUEBA DE CARGA CON QPIXMAP")
print("=" * 90)

try:

    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()

    if app is None:
        app = QApplication(sys.argv)

    correctos = 0
    fallos = 0

    for archivo in archivos_cache:

        pix = QPixmap()

        ok = pix.load(str(archivo))

        print(
            f"{archivo.name:45} "
            f"QPixmap.load={ok} "
            f"null={pix.isNull()} "
            f"size={pix.width()}x{pix.height()}"
        )

        if ok and not pix.isNull():
            correctos += 1
        else:
            fallos += 1

    print("\nQT CORRECTOS:", correctos)
    print("QT FALLIDOS :", fallos)

except Exception as e:

    print("NO SE PUDO PROBAR QT:")
    print(repr(e))


print("\n" + "=" * 90)
print("FIN DEL DIAGNÓSTICO")
print("=" * 90)