# Beet

Modelo de predicción y detección de apuestas de valor.

## Visión

Beet predice partidos de fútbol mediante **simulación** (no una fórmula cerrada de probabilidad): a partir de datos históricos y contexto del partido se simula el resultado, y de esa simulación surgen las probabilidades por mercado (1X2, doble oportunidad, DNB, goles, BTTS, corners). Esas probabilidades se comparan luego contra la cuota de la casa de apuestas para detectar *value bets*.

La fuente principal de datos es **Adam Choi** (capturas de pantalla + PDF de odds), pero el modelo está abierto a incorporar más fuentes/variables si eso mejora la precisión de la simulación.

El objetivo no es solo "encontrar cuotas mal calibradas" — es que la predicción en sí sea lo más precisa posible, y que el valor esperado surja de ahí. Cada predicción se puede verificar después contra el resultado real, y esa verificación retroalimenta el propio modelo (backtesting → calibración empírica → mejores predicciones).

Aunque hoy es una herramienta de análisis, la meta de fondo es que llegue a ser lo bastante confiable como para usarse con apuestas reales.

---

## Alcance

### Lo que Beet hace

- **Ingesta automática**: escanea una carpeta, agrupa los 3 archivos por partido (2 imágenes + 1 PDF) y extrae datos estructurados mediante OCR local (Tesseract).
- **Modelado de dominio**: representa partidos, historiales de equipos, cuotas y mercados como objetos Python tipados.
- **Validación de datos**: detecta cuotas corruptas (≤1.00), nombres inconsistentes, secciones faltantes en PDF.
- **Visualización**: dashboard PyQt6 para validar que los parsers extraen correctamente antes de usarlos en el modelo.
- **Backtesting**: (futuro) comparar predicciones vs resultados reales para calibrar el modelo.

### Lo que Beet NO hace (por ahora)

- No coloca apuestas automáticamente ni se conecta a casas de apuestas.
- No es un tipster — comunica probabilidad y valor esperado, no certezas.
- No cubre todos los deportes — foco actual: fútbol.

---

## Estado actual

Arquitectura v2 implementada. El visor de validación de parsers está funcional.

---

## Instalación

```bash
# 1. Clonar el repo
git clone https://github.com/NotName-K/Beet.git
cd Beet

# 2. Crear entorno virtual (recomendado)
python -m venv venv

# Windows:
\venv\Scripts\activate

# 3. Instalar el paquete en modo editable
pip install -e ".[dev]"

# 4. Instalar Tesseract OCR (sistema operativo)
# Windows: descargar de https://github.com/UB-Mannheim/tesseract/wiki
# macOS: brew install tesseract
# Ubuntu: sudo apt-get install tesseract-ocr

# 5. Verificar instalación
python -c "import beet; print(beet.__version__)"
```

---

## Ejecución

| Forma | Comando / Acción |
|-------|-----------------|
| Desarrollo | `python beet-visor.py` |
| Como módulo | `python -m beet.ui` |
| Instalado | `beet-visor` |
| Windows (sin CMD) | Doble clic en `beet-visor.bat` |

---

## Estructura del proyecto

```
beet/                          ← repo Git
│
├── beet-visor.py              ← Entry point standalone
│   Ejecuta el visor sin necesidad de instalar el paquete.
│   Agrega la raíz del repo al sys.path e importa beet.ui.
│
├── beet-visor.bat             ← Script Windows
│   Doble clic. Ejecuta pythonw (sin ventana de consola).
│   Si falla, reintenta con python + pausa para ver el error.
│
├── pyproject.toml             ← Configuración del proyecto
│   Define nombre, versión, dependencias, scripts de entrada,
│   configuración de pytest, black y ruff.
│
├── .gitignore                 ← Archivos ignorados por Git
│   Excluye: __pycache__, venv/, capturas, *.png, *.pdf, etc.
│
├── README.md                  ← Este archivo
│
└── beet/                      ← Paquete Python principal
    │
    ├── __init__.py            ← Marca el directorio como paquete
    │   Exporta __version__. Sin este archivo Python no reconoce
    │   el directorio como importable.
    │
    ├── core/                  ← 🧠 MODELOS DE DOMINIO
    │   │                      Clases puras de datos. Sin lógica de UI,
    │   │                      sin parsers, sin acceso a archivos.
    │   │
    │   ├── __init__.py
    │   │   Exporta: Partido, Cuota, HistorialEquipo,
    │   │   PartidoHistorico, NOMBRES_CANONICOS, normalizar_nombre
    │   │
    │   ├── partido.py
    │   │   Clase Partido. Representa un partido completo:
    │   │   liga, país, filtro_liga_aplicado, local, visitante,
    │   │   historial_local, historial_visitante, cuotas.
    │   │   Métodos: cuotas_validas(), cuotas_invalidas()
    │   │
    │   ├── cuota.py
    │   │   Clase Cuota (dataclass frozen). Mercado, valor, casa_origen,
    │   │   valida (bool). Validación automática: valor <= 1.00 → valida=False.
    │   │   Las cuotas inválidas van a revisión manual, nunca al cálculo de EV.
    │   │
    │   ├── historial_equipo.py
    │   │   Clases PartidoHistorico (frozen) e HistorialEquipo.
    │   │   PartidoHistorico: fecha, competición, rival, marcador (tuple),
    │   │   tarjetas_rojas, hit_mercado_resaltado (bool).
    │   │   HistorialEquipo: nombre_equipo, es_local, partidos (lista variable).
    │   │   Métodos: tasa_hit_mercado(), goles_promedio()
    │   │
    │   └── normalizacion.py
    │       Tabla NOMBRES_CANONICOS para unificar nombres de equipos
    │       entre fuentes. Ej: "Viking FK" → "Viking", "Bodo Glimt" → "Bodø/Glimt".
    │       Función normalizar_nombre() consulta la tabla o devuelve el nombre limpio.
    │
    ├── ingest/                ← 📥 PIPELINE DE INGESTA
    │   │                      Extrae datos estructurados desde capturas
    │   │                      de pantalla (PNG) y PDFs de odds.
    │   │
    │   ├── __init__.py
    │   │   Exporta: agrupar_lote, parsear_imagen_historial,
    │   │   parsear_pdf_cuotas, LoteIngesta
    │   │
    │   ├── agrupador.py
    │   │   Función agrupar_lote(directorio) → Dict[str, LoteIngesta].
    │   │   Escanea archivos, extrae nombre de partido del filename
    │   │   (patrón: {local}_vs_{visitante}_predictions_{pais}_-_{liga}),
    │   │   agrupa los 3 archivos por partido.
    │   │   Clase LoteIngesta: local, visitante, pais, liga,
    │   │   rutas a img_corners, img_resultado, pdf.
    │   │
    │   └── parsers/
    │       │
    │       ├── __init__.py
    │       │   Exporta: ResultadoParseoImagen, ResultadoParseoPDF
    │       │
    │       ├── imagen.py
    │       │   Parser de imágenes con OCR local (Tesseract).
    │       │   Divide la imagen en 2 paneles (local/visitante).
    │       │   Extrae: stat_type, highlight_market, filtro_liga,
    │       │   nombre de equipos, tabla de historial fila por fila.
    │       │   Detecta hit_mercado_resaltado por color de fondo
    │       │   (verde = hit, rojo = miss).
    │       │   Usa Regiones de Interés (ROI) predefinidas para el layout
    │       │   fijo de Adam Choi.
    │       │   Clase ResultadoParseoImagen: contiene todos los datos extraídos
    │       │   + lista de errores.
    │       │
    │       └── pdf.py
    │           Parser de PDFs de cuotas con pdfplumber.
    │           Limpia ruido conocido ("Resultlt" → "Result").
    │           Itera secciones opcionales (Match Result, Total Match Corners,
    │           Most Corners, BTTS, etc.) — no asume lista fija.
    │           Extrae cuotas por casa de apuestas.
    │           Clase ResultadoParseoPDF: cuotas[], secciones_encontradas[], errores[].
    │
    ├── ui/                    ← 🖥️ INTERFAZ GRÁFICA (PyQt6)
    │   │                      Todo construido por código. Sin Qt Designer.
    │   │                      Muestra datos crudos del parser sin transformar.
    │   │
    │   ├── __init__.py
    │   │   Exporta: MainWindow
    │   │
    │   ├── __main__.py
    │   │   Entry point para "python -m beet.ui".
    │   │   Crea QApplication, instancia MainWindow, ejecuta loop.
    │   │
    │   ├── main_window.py
    │   │   Ventana principal. Layout:
    │   │   - Barra superior: botón "Abrir carpeta", ruta actual
    │   │   - Splitter: lista de partidos (izq) | tabs de resultados (der)
    │   │   - Tabs: Historial (tablas Local/Visitante) | Cuotas (tabla)
    │   │   - Panel inferior: Log de eventos con timestamps
    │   │   Conecta señales del VisorController a slots de la UI.
    │   │
    │   └── widgets/
    │       │
    │       ├── __init__.py
    │       │   Exporta: LogPanel, PartidoList, HistorialTab, CuotasTab
    │       │
    │       ├── log_panel.py
    │       │   Panel de texto inferior. Read-only, scrollable.
    │       │   Métodos: log(mensaje), log_error(mensaje), clear().
    │       │   Colorea errores en rojo, info en gris.
    │       │
    │       ├── partido_list.py
    │       │   Lista de partidos detectados (QListWidget).
    │       │   Emite señal partido_seleccionado(clave, LoteIngesta)
    │       │   cuando el usuario hace click.
    │       │
    │       ├── historial_tab.py
    │       │   Pestaña de historial con 2 sub-tabs (Local / Visitante).
    │       │   Muestra tabla QTableWidget con columnas:
    │       │   Fecha, Competición, Rival, Marcador, Tarjetas Rojas, Hit Mercado.
    │       │   Las filas con hit se pintan de verde, sin hit de rojo.
    │       │   Muestra info de depuración: tipo, cantidad de registros, tiempo.
    │       │
    │       └── cuotas_tab.py
    │           Pestaña de cuotas. Tabla con columnas:
    │           Mercado, Casa, Valor, Válida.
    │           Cuotas inválidas (≤1.00) se pintan de rojo.
    │           Muestra info de depuración: total, inválidas, secciones, tiempo.
    │
    ├── controllers/           ← 🎮 ORQUESTADOR
    │   │                      Conecta UI con ingest. Ejecuta parsers en background.
    │   │
    │   ├── __init__.py
    │   │   Exporta: VisorController
    │   │
    │   └── visor_controller.py
    │       Clase VisorController (QObject).
    │       Usa QThreadPool para ejecutar parsers sin congelar la UI.
    │       Clases internas: WorkerSignals, Worker (QRunnable).
    │       Señales: lotes_cargados, historial_listo, cuotas_listo,
    │       error_ocurrido, log_mensaje.
    │       Métodos: cargar_carpeta(), procesar_partido().
    │       En errores: emite traceback completo para debug.
    │
    ├── services/              ← 🔮 RESERVADO PARA FUTURO
    │   │
    │   └── __init__.py
    │       Vacío por ahora. Aquí irá:
    │       - Motor de simulación de partidos
    │       - Cálculo de probabilidades por mercado
    │       - Detección de value bets (EV)
    │       - Calibración empírica con backtesting
    │
    └── tests/                 ← 🧪 TESTS UNITARIOS
        │
        ├── __init__.py
        │
        └── test_core.py
            Tests de Cuota (validación ≤1.00), PartidoHistorico,
            HistorialEquipo (tasa_hit, goles_promedio), Partido (cuotas válidas/inválidas),
            Normalización (nombres canónicos).
```

---

## Flujo de datos

```
Descargas/
├── Screenshot ... Manta vs LDU Quito ... corners.png
├── Screenshot ... Manta vs LDU Quito ... result.png
└── Manta_vs_LDU Quito ... .pdf
         ↓
[beet/ingest/agrupador.py]
    Escanea → agrupa por nombre → LoteIngesta
         ↓
[beet/ingest/parsers/imagen.py]  ──OCR Tesseract──→  HistorialEquipo (local + visitante)
[beet/ingest/parsers/pdf.py]     ──pdfplumber──→     List[Cuota]
         ↓
[beet/controllers/visor_controller.py]
    QThreadPool → Workers → señales a UI (sin bloquear)
         ↓
[beet/ui/main_window.py]
    Muestra: tablas de historial | tabla de cuotas | log de eventos
```

---

## Decisiones de diseño

### ¿Por qué OCR local (Tesseract) en vez de API de visión?

- **Sin límites de uso**: no hay rate limits ni costos por llamada.
- **Sin dependencia de red**: funciona offline, ideal para batch nocturno.
- **Layout fijo**: las capturas de Adam Choi siempre tienen la misma estructura,
  lo que permite usar ROI predefinidas y regex en vez de ML.
- **Fallback**: si el OCR local falla (imagen borrosa, fuente rara), se puede
  agregar fallback a API en el futuro sin cambiar la arquitectura.

### ¿Por qué PyQt6 y no web?

- **Acceso local a archivos**: escanea carpetas del sistema sin permisos CORS.
- **Sin servidor**: no requiere levantar backend ni navegador.
- **Rendimiento**: QThreadPool permite ejecutar OCR en paralelo sin bloquear UI.
- **Empaquetado**: se puede compilar a .exe con PyInstaller/Nuitka.

### ¿Por qué dataclasses frozen para el core?

- **Inmutabilidad**: los datos de dominio no deberían mutar accidentalmente.
- **Hashables**: se pueden usar como claves de dict o en sets.
- **Claridad**: el código describe exactamente qué campos tiene cada entidad.

---

## Roadmap

| Fase | Estado | Descripción |
|------|--------|-------------|
| 1 | ✅ | Core de modelos (Partido, Cuota, Historial) |
| 2 | ✅ | Ingesta OCR + PDF con validación |
| 3 | ✅ | Visor de validación de parsers (PyQt6) |
| 4 | 🔄 | Motor de simulación (services/) |
| 5 | ⏳ | Calibración empírica + backtesting |
| 6 | ⏳ | Automatización de captura (selenium/playwright) |

---

## Licencia

MIT
