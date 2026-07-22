# Beet — Esquema de datos de ingesta (conclusiones)

Basado en el análisis de 3 partidos reales (K-League 1, Eliteserien x2) con estructura idéntica entre sí.

## 1. Estructura fija de la fuente (Adam Choi)

Por partido, siempre llegan **3 archivos**:
- 2 imágenes: "Total Match Corners" (resaltando "Over 6.5 Total Corners") y "Match Result" (resaltando "Win")
- 1 PDF: pestaña "Odds"

El nombre de archivo trae el identificador `{local}_vs_{visitante}_predictions_{pais}_-_{liga}`, compartido entre las 2 imágenes y el PDF — es la clave natural para el agrupamiento automático del lote.

## 2. Campos por partido (`core.Partido`)

```
Partido
├── liga: str                    # ej. "Norwegian Eliteserien"
├── pais: str                    # ej. "Norway"
├── filtro_liga_aplicado: str    # la pestaña seleccionada al capturar (Eliteserien, no "All")
├── local: str
├── visitante: str
└── historial: HistorialEquipo (uno por cada equipo, ver §3)
```

**Regla de captura obligatoria:** la pestaña de liga (All / Liga / Liga2) debe fijarse explícitamente al automatizar — nunca depender del estado por defecto de la página.

## 3. Historial reciente por equipo (`core.HistorialEquipo`)

Longitud **variable** (5 a 10+ partidos observados) — el modelo no puede asumir N fijo.

Por cada partido histórico, dos vistas (corners y resultado), cada fila trae:

```
PartidoHistorico
├── fecha: date
├── competicion: str              # puede diferir de la liga principal si no se filtró bien
├── rival: str
├── marcador: tuple[int, int]     # (equipo_analizado, rival) — ya viene con la orientación
│                                    correcta según si es local u visitante
├── tarjetas_rojas: int           # 0, 1, 2... NO booleano
└── hit_mercado_resaltado: bool   # color de fila = si el mercado resaltado (Over 6.5 corners /
                                     Win) se cumplió ese partido — dato ya derivado por la fuente
```

**Nota:** por ahora se capturan solo 2 combinaciones de stat type/highlight (corners y resultado). No hay tercera imagen para BTTS u otros mercados — si se quiere ese hit-rate derivado para otro mercado, habría que agregar una tercera captura.

## 4. Cuotas (`core.Cuota`)

```
Cuota
├── mercado: str            # ej. "Over 6.5 Total Corners"
├── valor: float
├── casa_origen: str        # ej. "bet365", "Unibet" — NO asumir una casa única por partido
└── valida: bool            # False si valor <= 1.00 (dato corrupto de la fuente)
```

**Regla de validación obligatoria:** cualquier cuota ≤ 1.00 se marca `valida=False` y nunca entra al cálculo de EV — va a la pantalla de revisión en bloque para que la corrijas o descartes manualmente.

**Secciones del PDF son opcionales**, no todas aparecen siempre (ej. "Most Corners" solo en 1 de los 3 ejemplos). El parser debe iterar secciones presentes, no asumir una lista fija.

## 5. Normalización de nombres

Se confirmó necesidad de manejar:
- Caracteres especiales en nombres de equipo (Bodø, Lillestrøm) — UTF-8 consistente en todo el pipeline, y sanitización al usar como nombre de archivo (ya se hacía en CALIBRE, mantener).
- Variación de nombre del mismo equipo entre fuentes (ej. "Viking FK" en el nombre de archivo vs. "Viking" en el contenido de la página) — se necesitará una tabla de nombres canónicos si en el futuro se cruza con otra fuente de datos.

## 6. Ruido conocido a manejar en el parser de PDF

El texto extraído de PDF puede traer superposición de la barra de navegación sobre los headers de sección (ej. "Resultlt" en vez de "Result"). El parser debe usar posición (bounding box), no solo texto plano, o al menos tener limpieza de ruido conocido.

---

## Confirmaciones finales — schema congelado

1. **Las 2 capturas son siempre fijas**: "Total Match Corners" + highlight "Over 6.5 Total Corners", y "Match Result" + highlight "Win". No varían según el partido — esto simplifica mucho la automatización de captura: la interacción con los dropdowns es la misma secuencia de clics siempre, sin lógica condicional por partido.
2. **Alcance inicial NO incluye** team shots, fouls ni referee stats, aunque Premium esté activo — esas capturas quedan pospuestas para una fase posterior. La ingesta v1 se limita a: 2 imágenes (corners + resultado) + PDF de cuotas.

---

## Resumen — qué está listo para pasar a implementación

- Estructura de archivos y agrupamiento por nombre: **definida**
- Campos de `Partido`, `HistorialEquipo`, `PartidoHistorico`, `Cuota`: **definidos**
- Reglas de validación (cuota ≤1.00, secciones opcionales de PDF): **definidas**
- Alcance de captura (qué imágenes, qué dropdowns, qué NO se captura aún): **definido**
- Automatización de captura (dropdowns fijos, sin lógica condicional): **más simple de lo previsto**, gracias a la confirmación de que la combinación stat type/highlight nunca cambia

Este documento queda como referencia para cuando empecemos a construir `ingest/` y `core/`.

