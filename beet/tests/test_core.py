"""
Tests unitarios para el core de Beet.
"""
import pytest
from datetime import date

from beet.core.cuota import Cuota
from beet.core.historial_equipo import PartidoHistorico, HistorialEquipo
from beet.core.partido import Partido
from beet.core.normalizacion import normalizar_nombre, NOMBRES_CANONICOS


class TestCuota:
    def test_cuota_valida(self):
        c = Cuota(mercado="Over 2.5", valor=1.85, casa_origen="bet365")
        assert c.valida is True
        assert c.valor == 1.85
    
    def test_cuota_invalida_por_valor_bajo(self):
        c = Cuota(mercado="Over 2.5", valor=0.95, casa_origen="bet365")
        assert c.valida is False
    
    def test_cuota_invalida_exactamente_1_00(self):
        c = Cuota(mercado="Over 2.5", valor=1.00, casa_origen="bet365")
        assert c.valida is False


class TestPartidoHistorico:
    def test_creacion_basica(self):
        p = PartidoHistorico(
            fecha=date(2026, 7, 19),
            competicion="K-League 1",
            rival="Seoul",
            marcador=(1, 3),
            hit_mercado_resaltado=True,
        )
        assert p.marcador == (1, 3)
        assert p.hit_mercado_resaltado is True


class TestHistorialEquipo:
    def test_tasa_hit_mercado(self):
        partidos = [
            PartidoHistorico(date(2026, 7, 1), "Liga", "A", (2, 1), hit_mercado_resaltado=True),
            PartidoHistorico(date(2026, 7, 2), "Liga", "B", (1, 1), hit_mercado_resaltado=False),
            PartidoHistorico(date(2026, 7, 3), "Liga", "C", (3, 0), hit_mercado_resaltado=True),
        ]
        hist = HistorialEquipo("Test FC", es_local=True, partidos=partidos)
        assert hist.tasa_hit_mercado() == pytest.approx(2/3)
    
    def test_tasa_hit_sin_partidos(self):
        hist = HistorialEquipo("Test FC", es_local=True, partidos=[])
        assert hist.tasa_hit_mercado() == 0.0
    
    def test_goles_promedio(self):
        partidos = [
            PartidoHistorico(date(2026, 7, 1), "Liga", "A", (2, 1)),
            PartidoHistorico(date(2026, 7, 2), "Liga", "B", (0, 3)),
        ]
        hist = HistorialEquipo("Test FC", es_local=True, partidos=partidos)
        gf, gc = hist.goles_promedio()
        assert gf == 1.0
        assert gc == 2.0


class TestPartido:
    def test_cuotas_validas_e_invalidas(self):
        p = Partido(
            liga="K-League 1",
            pais="South Korea",
            filtro_liga_aplicado="K-League 1",
            local="Bucheon 1995",
            visitante="Anyang",
        )
        p.cuotas = [
            Cuota("Over 6.5 Corners", 1.85, "bet365"),
            Cuota("Over 6.5 Corners", 0.95, "Unibet"),  # inválida
            Cuota("Match Result", 2.10, "bet365"),
        ]
        assert len(p.cuotas_validas()) == 2
        assert len(p.cuotas_invalidas()) == 1


class TestNormalizacion:
    def test_normalizar_nombre_existente(self):
        assert normalizar_nombre("Viking FK") == "Viking"
    
    def test_normalizar_nombre_desconocido(self):
        assert normalizar_nombre("Nuevo Equipo") == "Nuevo Equipo"
    
    def test_normalizar_con_espacios(self):
        assert normalizar_nombre("  Viking FK  ") == "Viking"