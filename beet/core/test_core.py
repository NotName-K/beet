"""
Tests de humo para core/. Corren con: python -m pytest tests/ -v
(o simplemente `python tests/test_core.py` si no hay pytest instalado)
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from beet.core import (
    Cuota,
    HistorialEquipo,
    Partido,
    PartidoHistorico,
    sanitizar_para_archivo,
)


def _historial_ok(equipo: str, n: int = 6) -> HistorialEquipo:
    partidos = [
        PartidoHistorico(
            fecha=date(2026, 1, i + 1),
            competicion="Norwegian Eliteserien",
            rival=f"Rival {i}",
            marcador=(2, 1),
            tarjetas_rojas=0,
            hit_mercado_resaltado=bool(i % 2),
        )
        for i in range(n)
    ]
    return HistorialEquipo(equipo=equipo, partidos=partidos)


def test_partido_valido_ok():
    p = Partido(
        liga="Norwegian Eliteserien",
        pais="Norway",
        filtro_liga_aplicado="Eliteserien",
        local="Bodø/Glimt",
        visitante="Lillestrøm",
        historial_local=_historial_ok("Bodø/Glimt"),
        historial_visitante=_historial_ok("Lillestrøm"),
        cuotas=[Cuota(mercado="Over 6.5 Total Corners", valor=1.85, casa_origen="bet365")],
    )
    assert p.clave_archivo == "Bodø/Glimt_vs_Lillestrøm_predictions_Norway_-_Norwegian Eliteserien"
    assert len(p.cuotas_validas) == 1
    assert len(p.cuotas_para_revision) == 0


def test_filtro_liga_all_rechazado():
    try:
        Partido(
            liga="Norwegian Eliteserien",
            pais="Norway",
            filtro_liga_aplicado="All",
            local="A",
            visitante="B",
            historial_local=_historial_ok("A"),
            historial_visitante=_historial_ok("B"),
        )
        raise AssertionError("Debía rechazar filtro_liga_aplicado='All'")
    except ValueError:
        pass


def test_cuota_corrupta_marcada_invalida():
    c = Cuota(mercado="Win", valor=1.00, casa_origen="Unibet")
    assert c.valida is False
    assert c.apta_para_ev is False

    c2 = Cuota(mercado="Win", valor=0.9, casa_origen="Unibet")
    assert c2.valida is False


def test_tarjetas_rojas_rechaza_bool():
    try:
        PartidoHistorico(
            fecha=date(2026, 1, 1),
            competicion="X",
            rival="Y",
            marcador=(1, 0),
            tarjetas_rojas=True,  # trampa: bool es subclase de int
            hit_mercado_resaltado=True,
        )
        raise AssertionError("Debía rechazar tarjetas_rojas booleano")
    except TypeError:
        pass


def test_historial_corto_se_marca_no_bloquea():
    h = HistorialEquipo(equipo="Equipo Ascendido", partidos=[])
    assert h.historial_corto is True
    assert h.cantidad_partidos == 0
    assert h.tasa_hit_mercado() is None


def test_sanitizar_para_archivo_preserva_utf8():
    assert sanitizar_para_archivo("Bodø/Glimt") == "Bodø_Glimt"
    assert sanitizar_para_archivo("Real Madrid") == "Real_Madrid"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests pasaron.")
