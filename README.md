# Beet

Modelo de predicción y detección de apuestas de valor.

## Visión

Beet predice partidos de fútbol mediante simulación (no una fórmula cerrada de probabilidad): a partir de datos históricos y contexto del partido se simula el resultado, y de esa simulación surgen las probabilidades por mercado (1X2, doble oportunidad, DNB, goles, BTTS, corners). Esas probabilidades se comparan luego contra la cuota de la casa de apuestas para detectar value bets.

La fuente principal de datos es Adam Choi (capturas de pantalla + PDF de odds), procesadas con **Google Gemini** (visión + PDF nativo). El modelo está abierto a incorporar más fuentes/variables si eso mejora la precisión de la simulación.

El objetivo no es solo "encontrar cuotas mal calibradas" — es que la predicción en sí sea lo más precisa posible, y que el valor esperado surja de ahí. Cada predicción se puede verificar después contra el resultado real, y esa verificación retroalimenta el propio modelo (backtesting → calibración empírica → mejores predicciones).

Aunque hoy es una herramienta de análisis, la meta de fondo es que llegue a ser lo bastante confiable como para usarse con apuestas reales.

## Alcance

### Lo que Beet hace

- **Ingesta automática con IA**: escanea una carpeta, agrupa los 3 archivos por partido (2 imágenes + 1 PDF) y extrae datos estructurados mediante **Google Gemini** (visión para imágenes, PDF nativo para cuotas).
- **Pool de API Keys configurable**: usa 1 o 2 claves de Gemini (a elección del usuario, pedidas por diálogo en el primer arranque) en rotación para repartir la cuota y evitar rate limits. Se guardan en `~/.beet/config.json`, fuera del repo.
- **Datos persistentes**: guarda los resultados en `beet/data/partidos/*.json` para no gastar tokens en partidos ya procesados y alimentar el backtesting futuro.
- **Doble extracción**: procesa tanto los goles (Match Result) como los corners (Total Match Corners) de cada partido.
- **Modelado de dominio**: representa partidos, historiales de equipos, cuotas y mercados como objetos Python tipados.
- **Validación de datos**: detecta cuotas corruptas (≤1.00), nombres inconsistentes, secciones faltantes en PDF.
- **Visualización**: dashboard PyQt6 para validar que los parsers extraen correctamente antes de usarlos en el modelo.
- **Backtesting**: (futuro) comparar predicciones vs resultados reales para calibrar el modelo.

### Lo que Beet NO hace (por ahora)

- No coloca apuestas automáticamente ni se conecta a casas de apuestas.
- No es un tipster — comunica probabilidad y valor esperado, no certezas.
- No cubre todos los deportes — foco actual: fútbol.

## Estado actual 30/07/26

Arquitectura v3 implementada. El visor de validación de parsers está funcional con Gemini.
**Paralelamente, el pipeline de ingesta 100% HTTP desde Adam Choi está validado en scripts standalone** (ver sección "Investigación paralela" más abajo) — genera JSON completos por partido con 5 endpoints, incluyendo tarjetas rojas, pero aún no está integrado en el paquete `beet/`.

### Cambios recientes (v3.0)

- **Migración de OCR local a Google Gemini**: se eliminó Tesseract, OpenCV y pdfplumber. Ahora se usa `gemini-3.1-flash-lite` para visión y PDFs.
- **Pool de 2 API Keys**: procesamiento en paralelo con round-robin para evitar rate limits.
- **Doble imagen procesada**: se extraen tanto los goles (Match Result) como los corners (Total Match Corners) de cada partido.
- **Datos persistentes**: módulo `beet/data/` guarda resultados en `beet/data/partidos/*.json` para reutilización y backtesting.
- **Indicador visual**: los partidos ya procesados se muestran con "✓" verde en la lista.
- **Fix de Unicode**: workaround para rutas con tildes/ñ en Windows (Ceará, Goiás, São Paulo).
- **Escaneo automático**: al cargar una carpeta, se procesan todos los partidos en background automáticamente.

### Cambios recientes (v3.1)

- **API Keys ya no están hardcodeadas**: se migraron a `~/.beet/config.json`, fuera del repo. Al arrancar la app por primera vez (o si el archivo de config no existe), un diálogo (`beet/ui/widgets/api_keys_dialog.py`) pide 1 o 2 keys de Gemini y las guarda. Las keys se leen de forma perezosa (recién al pedir el primer cliente, no al importar el módulo), para que el diálogo pueda guardarlas antes de que cualquier parser las necesite.
- **Módulo compartido `_gemini_common.py`**: se deduplicó la lógica repetida entre `imagen.py` y `pdf.py` (rotación de clientes, subida de archivos temporales, extracción de JSON, reintentos con backoff).
- **Reintentos en el parser de PDF**: `pdf.py` no tenía la lógica de reintentos ante rate limit/cuota que sí tenía `imagen.py` — ahora ambos la comparten.
- **Fix de crash fatal en `visor_controller.py`**: los workers se identificaban con `id(worker)`, pero al ser `QRunnable` con auto-eliminación, Python podía reutilizar esa misma dirección de memoria para el siguiente worker creado, causando colisiones y un `KeyError` que escapaba de un slot de Qt y crasheaba la app a nivel de sistema operativo. Ahora se usa un contador incremental único (`itertools.count()`).
- **Fix de resultados cruzados en la UI**: el auto-escaneo procesa todos los partidos en background; antes, el resultado de cualquier partido que terminara de procesarse pisaba lo que el usuario tenía abierto en pantalla, sin importar cuál estuviera seleccionado. Las señales del controller ahora llevan la clave del partido, y la ventana principal descarta los resultados que no correspondan al partido seleccionado.
- **Fix de columna "Casa" vacía en la tab de Cuotas**: leía un atributo `casa` que no existe en el modelo `Cuota` (el campo real es `casa_origen`).

## Instalación

```bash
# 1. Clonar el repo
git clone https://github.com/NotName-K/Beet.git
cd Beet

# 2. Crear entorno virtual (recomendado)
python -m venv venv
# Windows:
venv\Scripts\activate

# 3. Instalar el paquete en modo editable
pip install -e ".[dev]"

# 4. Instalar Google Gemini SDK
pip install google-genai
```

**API Keys de Gemini**: no van en el código. La primera vez que corras la app (`python beet-visor.py` o `python -m beet.ui`), si no existe `~/.beet/config.json` se abre un diálogo pidiendo 1 o 2 keys de Gemini (la segunda es opcional, se usa en rotación para repartir cuota). Quedan guardadas ahí, fuera del repo, y no hace falta volver a ingresarlas en corridas futuras. Si preferís configurarlas a mano, podés crear el archivo vos mismo:

```json
{
  "gemini_api_keys": ["tu-key-1", "tu-key-2"]
}
```

## Ejecución

| Forma | Comando / Acción |
| --- | --- |
| Desarrollo | `python beet-visor.py` |
| Como módulo | `python -m beet.ui` |
| Instalado | `beet-visor` |
| Windows (sin CMD) | Doble clic en `beet-visor.bat` |

## Estructura del proyecto

> ⚠️ **Nota sobre rutas**: los datos persistentes NO están en una carpeta `data/` a nivel de repo — viven en `beet/data/` (dentro del paquete Python). Es decir, la ruta completa es `beet/beet/data/partidos/` si estás parado en el directorio padre del repo clonado.

```
Beet/                          ← repo Git (raíz del clone)
 │
 ├── beet-visor.py              ← Entry point standalone
 │   Ejecuta el visor sin necesidad de instalar el paquete.
 │   Agrega la raíz del repo al sys.path e importa beet.ui.
 │   Si no hay API Keys guardadas (~/.beet/config.json), muestra
 │   ApiKeysDialog antes de crear la ventana principal.
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
 │   Excluye: __pycache__, venv/, beet/data/partidos/, *.csv
 │
 ├── README.md                  ← Este archivo
 │
 └── beet/                      ← Paquete Python principal (⚠️ data/ vive aquí adentro, no en la raíz)
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
     │   │   HistorialEquipo: equipo (str), partidos (lista variable).
     │   │   Métodos: tasa_hit_mercado(), historial_corto (property).
     │   │
     │   ├── normalizacion.py
     │   │   Tabla NOMBRES_CANONICOS para unificar nombres de equipos
     │   │   entre fuentes. Ej: "Viking FK" → "Viking", "Bodo Glimt" → "Bodø/Glimt".
     │   │   Función normalizar_nombre() consulta la tabla o devuelve el nombre limpio.
     │   │
     │   └── config.py
     │       Configuración persistente del usuario (hoy: API Keys de Gemini).
     │       Guarda/lee ~/.beet/config.json — FUERA del repo, nunca se commitea.
     │       Funciones: cargar_api_keys(), guardar_api_keys(), hay_api_keys_configuradas().
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
     │   │   Tolerancia: guiones bajos opcionales, espacios, prefijos de screenshot.
     │   │
     │   └── parsers/
     │       │
     │       ├── __init__.py
     │       │   Exporta: ResultadoParseoImagen, ResultadoParseoPDF
     │       │
     │       ├── _gemini_common.py
     │       │   Lógica compartida entre imagen.py y pdf.py: rotación de
     │       │   clientes Gemini (round-robin), subida de archivos temporales,
     │       │   extracción de JSON de la respuesta y reintentos con backoff
     │       │   ante errores transitorios (rate limit/cuota).
     │       │   Lee las API Keys de beet.core.config de forma PEREZOSA
     │       │   (recién al pedir el primer cliente, no al importar el módulo).
     │       │
     │       ├── imagen.py
     │       │   Parser de imágenes con Google Gemini Vision.
     │       │   Usa gemini-3.1-flash-lite para extraer datos de capturas.
     │       │   Extrae: stat_type, highlight_market, filtro_liga,
     │       │   nombre de equipos, tabla de historial fila por fila.
     │       │   Detecta hit_mercado_resaltado por color de fondo
     │       │   (verde = hit, rojo = miss).
     │       │   Workaround de Unicode: copia archivo a ruta temporal ASCII.
     │       │   Clase ResultadoParseoImagen: contiene todos los datos extraídos
     │       │   + lista de errores.
     │       │
     │       └── pdf.py
     │           Parser de PDFs de cuotas con Google Gemini PDF nativo.
     │           Usa gemini-3.1-flash-lite para leer PDFs directamente.
     │           Extrae cuotas con casa_origen="bet365" (fuente Adam Choi).
     │           Workaround de Unicode: copia archivo a ruta temporal ASCII.
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
     │   │   Si no hay API Keys guardadas (~/.beet/config.json), muestra
     │   │   ApiKeysDialog ANTES de crear MainWindow (el auto-escaneo
     │   │   arranca en su constructor y ya las necesita disponibles).
     │   │   Crea QApplication, instancia MainWindow, ejecuta loop.
     │   │
     │   ├── main_window.py
     │   │   Ventana principal. Layout:
     │   │   - Barra superior: botón "Abrir carpeta", ruta actual
     │   │   - Splitter: lista de partidos (izq) | tabs de resultados (der)
     │   │   - Tabs: Historial (Goles/Corners) | Cuotas (tabla)
     │   │   - Panel inferior: Log de eventos con timestamps
     │   │   Conecta señales del VisorController a slots de la UI.
     │   │   Carga automáticamente ~/Downloads al abrir.
     │   │
     │   └── widgets/
     │       │
     │       ├── __init__.py
     │       │   Exporta: LogPanel, PartidoList, HistorialTab, CuotasTab
     │       │
     │       ├── api_keys_dialog.py
     │       │   Diálogo inicial (ApiKeysDialog) que pide 1 o 2 API Keys
     │       │   de Gemini si ~/.beet/config.json todavía no existe.
     │       │   Las guarda vía beet.core.config.guardar_api_keys().
     │       │
     │       ├── log_panel.py
     │       │   Panel de texto inferior. Read-only, scrollable.
     │       │   Métodos: log(mensaje), log_error(mensaje), clear().
     │       │   Colorea errores en rojo, info en gris.
     │       │
     │       ├── partido_list.py
     │       │   Lista de partidos detectados (QListWidget).
     │       │   Muestra "✓" verde para partidos ya procesados.
     │       │   Emite señal partido_seleccionado(clave, LoteIngesta)
     │       │   cuando el usuario hace click.
     │       │
     │       ├── historial_tab.py
     │       │   Pestaña de historial con tabs principales (Goles / Corners),
     │       │   cada uno con sub-tabs (Local / Visitante).
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
     ├── controllers/           ← 🎛️ ORQUESTADOR
     │   │                      Conecta UI con ingest. Ejecuta parsers en background.
     │   │
     │   ├── __init__.py
     │   │   Exporta: VisorController
     │   │
     │   └── visor_controller.py
     │       Clase VisorController (QObject).
     │       Usa QThreadPool para ejecutar parsers sin congelar la UI.
     │       Clases internas: WorkerSignals, Worker (QRunnable).
     │       Señales: lotes_cargados, historial_goles_listo, historial_corners_listo,
     │       cuotas_listo, error_ocurrido, log_mensaje. Las 3 de resultado
     │       llevan la clave del partido, para que la UI descarte resultados
     │       de partidos que no son el seleccionado (auto-escaneo en background).
     │       Cada worker se identifica con un contador incremental propio
     │       (nunca id(worker) — un QRunnable con autoDelete puede reutilizar
     │       esa dirección de memoria para el siguiente worker creado).
     │       Métodos: cargar_carpeta(), procesar_partido().
     │       Auto-escaneo: procesa todos los partidos al cargar carpeta.
     │       Verifica datos persistentes antes de llamar a Gemini.
     │       En errores: emite traceback completo para debug.
     │
     ├── data/                  ← 📊 DATOS PERSISTENTES (ruta completa: beet/data/)
     │   │                      Almacena resultados de parsers para análisis posterior.
     │   │
     │   ├── partidos/               ← JSON por partido procesado
     │   ├── __init__.py
     │   │   Exporta: guardar_partido, cargar_partido, listar_partidos,
     │   │   partido_procesado, eliminar_partido, exportar_a_csv,
     │   │   obtener_historial_equipo, obtener_todas_las_cuotas
     │   │
     │   ├── gestor.py
     │   │   Funciones de gestión de datos persistentes.
     │   │   Guarda/carga partidos en beet/data/partidos/{clave}.json.
     │   │   Exporta a CSV para análisis en Excel/pandas.
     │   │   Obtiene historial completo de equipos.
     │   │
     │   └── README.md
     │       Documentación del formato JSON y uso en análisis.
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
             HistorialEquipo (tasa_hit, historial_corto), Partido (cuotas válidas/inválidas),
             Normalización (nombres canónicos).

## Flujo de datos

```mermaid
flowchart TD
    A["📂 Descargas/<br/>3 archivos por partido<br/>(2 imágenes + 1 PDF)"] --> B["🔍 beet/ingest/agrupador.py<br/>Escanea y extrae nombre del partido<br/>desde el filename, agrupa los 3 archivos"]
    B --> C(["LoteIngesta"])
    C --> D["🎛️ beet/controllers/visor_controller.py<br/>Genera clave única del partido"]
    D --> E{"¿Existe en<br/>beet/data/partidos/clave.json?"}
    E -- Sí --> F["💾 Carga desde disco<br/>(sin gastar tokens)"]
    E -- No --> G["🚀 Lanza 3 workers en QThreadPool"]

    G --> W1["Worker 1<br/>imagen.py → Gemini Vision<br/>HistorialEquipo (goles)"]
    G --> W2["Worker 2<br/>imagen.py → Gemini Vision<br/>HistorialEquipo (corners)"]
    G --> W3["Worker 3<br/>pdf.py → Gemini PDF<br/>List[Cuota]"]

    W1 --> H["🗄️ beet/data/gestor.py<br/>Guarda resultados consolidados"]
    W2 --> H
    W3 --> H
    F --> I["📡 Emite señales a UI<br/>(sin bloquear el hilo principal)"]
    H --> I
    I --> J["🖥️ beet/ui/main_window.py<br/>Tabs Goles/Corners · Tabla de cuotas · Log de eventos"]

    style A fill:#2d3748,stroke:#4299e1,color:#fff
    style J fill:#2d3748,stroke:#48bb78,color:#fff
    style E fill:#553c9a,stroke:#9f7aea,color:#fff
    style G fill:#744210,stroke:#ed8936,color:#fff
```

> El indicador **"✓" verde** en la lista de partidos (`beet/ui/widgets/partido_list.py`) marca los partidos que ya tienen JSON persistido y no necesitan volver a llamar a Gemini.

## Decisiones de diseño

### ¿Por qué Google Gemini en vez de OCR local?

- **Precisión superior**: Gemini entiende el layout, los colores (verde=hit, rojo=miss) y las tablas anidadas sin necesidad de preprocesamiento de imágenes ni ROI frágiles.
- **PDF nativo**: lee PDFs directamente, sin depender de pdfplumber que falla con tablas complejas.
- **Costo mínimo**: la capa gratuita de Gemini 3.1 Flash Lite es muy generosa.
- **Trade-off**: requiere conexión a internet y tiene rate limits (mitigado con pool de 2 API Keys).

### ¿Por qué API Keys configurables en vez de hardcodeadas?

- **Nunca deben quedar en git**: hubo un incidente real donde dos keys quedaron commiteadas en `imagen.py`/`pdf.py` y el repo se hizo público con ellas expuestas — se revocaron a tiempo y se limpió el historial con `git filter-repo`, pero el diseño tenía que dejar de depender de eso.
- **Se guardan en `~/.beet/config.json`**, fuera del repo — imposible que un `git push` las vuelva a exponer.
- **Diálogo en el primer arranque**: si el archivo de config no existe, `ApiKeysDialog` las pide antes de crear la ventana principal.
- **Lectura perezosa**: `_gemini_common.py` recién inicializa los clientes de Gemini al pedir el primero, no al importar el módulo — así el orden de imports no importa, el diálogo siempre alcanza a guardarlas antes de que se necesiten.
- **Rotación (round-robin)**: si hay 2 keys, cada una tiene su propio límite de requests por minuto — los workers las toman alternadamente vía `itertools.cycle` + `threading.Lock()` para concurrencia segura. Con 1 sola key también funciona, solo que sin ese margen extra de cuota.

### ¿Por qué datos persistentes en JSON?

- **No gastar tokens**: si ya procesaste un partido, no lo reprocesas.
- **Backtesting futuro**: los datos históricos alimentarán el motor de simulación.
- **Exportable a CSV**: función `exportar_a_csv()` para análisis en Excel/pandas.
- **Legible**: JSON indentado, fácil de inspeccionar y debuggear.

### ¿Por qué PyQt6 y no web?

- Acceso local a archivos sin permisos CORS.
- Sin servidor: no requiere levantar backend ni navegador.
- Rendimiento: QThreadPool permite ejecutar parsers en paralelo sin bloquear UI.
- Empaquetado: se puede compilar a .exe con PyInstaller/Nuitka.

### ¿Por qué dataclasses frozen para el core?

- Inmutabilidad: los datos de dominio no deberían mutar accidentalmente.
- Hashables: se pueden usar como claves de dict o en sets.
- Claridad: el código describe exactamente qué campos tiene cada entidad.

### ¿Por qué workaround de Unicode para rutas?

- El SDK `google-genai` falla con rutas que contienen tildes/ñ (Ceará, São Paulo).
- Solución: copiar archivo a ruta temporal ASCII antes de subirlo a Gemini.
- Limpieza automática: el archivo temporal se borra inmediatamente después.

## Investigación paralela: pipeline de ingesta 100% HTTP desde Adam Choi

> ⚠️ **Estado: validado en scripts standalone, NO integrado aún en `beet/`**.  
> Los scripts corren por fuera del paquete principal y sus resultados (JSON crudos) están listos para ser mapeados al modelo `Comparativa` cuando se defina su forma final (Pydantic vs dataclasses).

Paralelamente al visor de validación con Gemini, se investigó y validó un **pipeline completamente automatizado vía HTTP** que consume los endpoints reales de Adam Choi (`adamchoi.co.uk` + backend `api.choistats.com`), eliminando la necesidad de capturas de pantalla, PDFs e interpretación por visión de IA para la ingesta de datos.

### Scripts standalone (vigentes)

> Estos scripts viven **por fuera del paquete `beet/`** (en la raíz del repo o en una carpeta de investigación). Son el resultado de las sesiones de handoff v1–v4.

| Script | Función | Estado |
|---|---|---|
| `obtener_v.py` | Obtiene automáticamente el cache-buster `v` fresco abriendo la página de fixtures con Playwright headless y capturando la request real del sitio. | ✅ Validado: extrae `v` sin intervención manual |
| `build_comparativas.py` | Descarga listado de fixtures + stats agregadas por equipo (join correcto por liga doméstica). Filtra copas y ligas Premium. Usa `obtener_v.py` internamente si no se pasa `--v`. | ✅ Validado: 173 filas limpias de 413 fixtures |
| `build_fixture_details_final.py` | Descarga detalle completo por partido (5 endpoints) y guarda un JSON por `external_id`. Maneja compresión, TLS fingerprinting (`curl_cffi`) y headers específicos por endpoint. | ✅ Validado en lote (5+ fixtures, todos los endpoints completos) |
| `run_pipeline.py` | **Orquestador único**: ejecuta `build_comparativas.py` + `build_fixture_details_final.py` en secuencia con un solo comando. Equivalente a correr los 3 pasos anteriores manualmente. | ✅ Validado: pipeline completo end-to-end |

**Uso típico (un solo comando):**
```bash
pip install requests curl_cffi playwright
python run_pipeline.py --stats BTTS --limit-detalles 5
```

Esto genera:
- `comparativas_staging.json` — listado filtrado de fixtures con stats agregadas
- `detalles_fixtures/fixture_<external_id>.json` — un JSON por partido con las 5 fuentes

### Cinco endpoints confirmados y funcionando

Cada fixture procesado genera un JSON con estas 6 claves top-level:
`external_id, odds, chances, team_records, recent_results, comparison_stats`.

#### 1. `odds` — lista de mercados (23–44 por fixture)

```json
[
  {
    "market": { "name": "Result", "displayRule": "THREE_WAY" },
    "outcomes": {
      "Celtic": { "outcome": "RESULT_HOME_WIN", "bookmaker": "UNIBET",
                  "decimalOdds": 1.19, "fractionalOdds": "2/11",
                  "bookmakerBetUrl": "...", "teamId": 53, ... }
    }
  }
]
```

Cada outcome trae su propio campo `bookmaker` (ej. "BET365", "UNIBET") —
esto es exactamente el `casa_origen` que se necesitaba. Cobertura real
observada: Result, BTTS, Match/Team Goals O/U, Double Chance, Total/Team
Corners, 1st/2nd Half Goals y Corners, Result & BTTS combinados, BTTS &
Overs, Win To Nil, Clean Sheet, HT/FT, Cards, Booking Points, Handicap
Result, **y mercados de jugador** (goleador, tarjeta, tiros, tiros a
puerta, asistencia). El número de mercados varía por fixture — no asumir
que siempre están todos.

#### 2. `chances` — probabilidades pre-calculadas por choistats (candidato a `estrella`)

```json
{
  "statType": "1+ First Half Goals",
  "chance": 91,
  "fixtureOdds": { "outcomeName": "Total 1H Goals - Over 0.5",
                    "bookmaker": "BET365", "decimalOdds": 1.2, ... },
  "homeStats": [ { "stat": "<strong>1+ goal...</strong> in 5/5 league matches",
                    "isStreak": false } ],
  "awayStats": [ ... ]
}
```

Cada entrada trae la probabilidad ya calculada por el proveedor (`chance`)
**ligada a la cuota real de esa apuesta específica**
(`fixtureOdds.decimalOdds`). Candidato natural para
`hit_mercado_resaltado`/`estrella` — permite comparar probabilidad justa vs
cuota implícita sin calibrar nada propio. ⚠️ En algunos fixtures `chances`
viene vacío o con muy pocas entradas (0–7 vistos) — no se investigó todavía
si es esperado (partido sin suficiente histórico) o señal de un problema.

#### 3. `team_records` — posición y récord en tabla, separado Home/Away/Overall

```json
{
  "homeTeamHomeRecord": { "type": "Home", "position": "3rd", "played": 0,
                            "won": 0, "draw": 0, "lost": 0, "goalsFor": 0,
                            "goalsAg": 0, "points": 0, "pointsPerGame": 0.0,
                            "form": [] },
  "homeTeamOverallRecord": {...}, "awayTeamAwayRecord": {...},
  "awayTeamOverallRecord": {...},
  "homeTeamResultsWithStandings": [...], "awayTeamResultsWithStandings": [...],
  "homeTeamId": ..., "awayTeamId": ..., "fixtureWithoutStats": ...
}
```

Si `played: 0` y todo en cero, no es un bug — es literalmente la primera
fecha de esa liga en la temporada. El pipeline debe distinguir "sin datos
por inicio de temporada" de "sin datos por error".

#### 4. `recent_results` — historial partido a partido, Home/Away separados + H2H

```json
{
  "fixture": {...},
  "recentHomeResults": [ {...42-50 partidos...} ],
  "recentHomeAllResults": [...],
  "recentAwayResults": [...],
  "recentAwayAllResults": [...],
  "headToHead": [ {...historial directo, visto desde 2021...} ],
  "quickStats": [ { "groupName": "Result", "quickStats": [ {...rachas con
                     % y cuota asociada...} ] } ],
  "homeTeamId": ..., "awayTeamId": ...
}
```

Cada partido trae: `homeGoals`, `awayGoals`, `homeGoalsHt`, `awayGoalsHt`,
`homeCorners`, `awayCorners`, `homeCards`, `awayCards`, `homeBookingPoints`,
`awayBookingPoints`, `timestamp`, `date`, `where` (H/A), `vs` (equipo de
referencia). Este endpoint resolvió el pendiente de `tarjetas_rojas`:
separa **roja directa** (`homeReds`/`awayReds`) de **roja por doble
amarilla** (`homeYellowReds`/`awayYellowReds`). También trae `homeFouls`,
`homeTotalShots`, `homeOffsides`, `referee`, entre otros campos no
explorados en profundidad todavía.

`quickStats` trae rachas tipo "Unbeaten en 9/10 partidos" con desglose
Home/Away/Overall, `last10*Perc`, y también ligadas a `fixtureOdds` —
mismo patrón que `chances`, otro candidato a insumo de `estrella`.

#### 5. `comparison_stats` — el más denso, indicadores + tabla + rachas

```json
{
  "stats": [
    { "stattype": "Over 25 Booking Points", "statid": "BookingPointsOver25",
      "homeO": 82, "awayO": 74,      // % overall
      "homeH": 74, "awayA": 74,      // % home (local) / away (visitante)
      "homePO": "31/38", "awayPO": "28/38",   // muestra overall
      "homeP": "14/19", "awayP": "14/19",     // muestra home/away
      "Booking Points": true, "All": true, "BTTS": false, ... }
  ],
  "leaguetable": [...], "leaguetableresults": [...],
  "recentmatches": [...], "homestreaks": [...], "awaystreaks": [...],
  "headtohead": [...],
  "hometeam": "...", "awayteam": "...", "hometeamid": ..., "awayteamid": ...,
  "homeleaguename": "...", "awayleaguename": "...",
  "fixtureleaguename": "...", "fixtureleagueslug": "...",
  "subscriptionType": null | "Premium", "refereeid": ...
}
```

`stats[]` trae ~110–118 indicadores por fixture, cada uno con % y muestra
Home/Away/Overall ya calculados — reemplaza en gran parte lo que
`build_comparativas.py` armaba a mano cruzando `teamStats` del listado
general. `leaguetable` puede venir vacío si la temporada no arrancó.

### Descubrimientos técnicos clave

- **CORS/Origin**: los endpoints de `api.choistats.com` devuelven 401 si falta el header `Origin: https://www.adamchoi.co.uk`. El `token` de la URL es público/fijo; el control está en el WAF de Cloudflare, no en autenticación de sesión.
- **Compresión**: `Accept-Encoding` debe ser solo `gzip, deflate`. Si se incluye `br` o `zstd` y no están instaladas las librerías de descompresión, el body llega como bytes binarios ilegibles aunque el status sea 200.
- **TLS fingerprinting**: el endpoint `getComparisonStatsAsJson.php` bloqueaba con 403 aunque los headers fueran idénticos a los del navegador. La causa real era el fingerprint TLS de `requests` vs un navegador real. Se resolvió usando `curl_cffi` con `impersonate="firefox135"`.
- **Redes con inspección SSL corporativa (Fortinet, etc.)**: pueden generar errores de certificado y bloqueos que se confunden con rechazos del sitio. Si aparecen 403/errores de certificado sin explicación clara, verificar primero la red.
- **Cache-buster**: el parámetro `v` en `getFixturesBySingleStatAsJson.php` se valida en el servidor; si vence, se recaptura desde el navegador (parece incremental, subió de `2026630` a `2026631`). `obtener_v.py` lo resuelve automáticamente sin intervención manual.
- **Join de stats**: la clave correcta para cruzar `teamStats` con un fixture es `home_league` / `away_league` (liga doméstica del equipo), **no** `league` (que puede ser una copa internacional). Usar `league` rompe el lookup silenciosamente en partidos de copa.
- **Ligas Premium**: el 98% de las ligas Premium no traen `teamStats` ni odds; el pipeline las descarta por defecto. El 5% residual de datos faltantes en ligas gratis es por ascensos/descensos de temporada (mismatch de código de liga).

### Puntos frágiles a vigilar

> Revisados y priorizados en sesión posterior a v4. Solo uno queda como riesgo
> activo real; el resto está descartado o ya mitigado.

1. **`COOKIE_STRING` hardcodeada — sin impacto real, confirmado.** Son todas
   cookies de analytics/publicidad de terceros (`_ga`, `__gads`, `__gpi`,
   `_pubcid`, `FCCDCF`), ninguna es cookie de sesión propia del sitio. El 403
   que se resolvió con `curl_cffi` era por fingerprint TLS, no por esta cookie.
   No tocar salvo que empiece a fallar (señal clara: 401/403 después de que
   venía andando).

2. **Referer con slug de texto fijo — riesgo bajo, revisado en detalle.** La
   URL tiene forma `/fixture/<ID>/<slug-de-texto>`. Se confirmó que
   `{external_id}` **sí se reemplaza correctamente por partido** — verificado
   contra `comparativas_staging.json`. Lo único fijo es el slug de texto final
   (nombres de equipos), que en la inmensa mayoría de sitios es cosmético/SEO
   y no se valida server-side. Se decidió explícitamente **no tocarlo**.

3. **`curl_cffi` / fingerprint TLS — único punto con riesgo activo real.** No
   depende de nada que el equipo controle — depende de que Adam Choi no
   endurezca su WAF. No hay forma de arreglarlo preventivamente más allá del
   fallback ya existente a `requests` normal (que probablemente reciba 403
   igual si `curl_cffi` deja de servir). Único mantenimiento sugerido: al
   actualizar la librería, confirmar que `impersonate="firefox135"` siga
   siendo un fingerprint soportado (estos nombres van rotando de versión en
   versión).

4. **El `v` que vence — resuelto, no requiere intervención.** Ya lo resuelve
   `obtener_v.py` automáticamente (Playwright headless) en cada corrida de
   `build_comparativas.py`. El default hardcodeado puede seguir desactualizado
   sin problema porque no se usa salvo que se fuerce un valor puntual con `--v`.

5. **Fortinet / inspección SSL corporativa — condición de entorno, no de
   código.** No arreglable desde el script. Ya documentado como primer
   diagnóstico si aparece un bloqueo sin explicación clara (headers idénticos
   al navegador, cookie fresca, y aun así falla).

6. **`Accept-Encoding` sin `br`/`zstd` — resuelto y estable.** Decisión de
   configuración, no algo que "venza" con el tiempo. Sin riesgo de seguimiento.

### Salida actual

- **JSON de staging** (`comparativas_staging.json`): listado de fixtures filtrados con stats agregadas.
- **JSON de detalle por partido** (`detalles_fixtures/fixture_<external_id>.json`): objeto con 5 claves (`odds`, `chances`, `team_records`, `recent_results`, `comparison_stats`) listo para ser transformado al modelo de dominio de Beet.
- **Datos ya extraídos en disco**: todos los partidos solicitados fueron procesados exitosamente mediante `run_pipeline.py`; los JSON crudos están disponibles para análisis y para alimentar el futuro motor de simulación. **Aún no se ha implementado el consumo de estos JSON dentro del paquete `beet/` ni se han mapeado al modelo `Comparativa`.**

### Próximos pasos del pipeline HTTP (pendientes)

1. **Mapear las 5 fuentes al modelo `Comparativa` final de Beet** — bloqueado
   por decidir primero Pydantic vs dataclasses.
2. **Cruzar el staging de listado (`comparativas_staging.json`) con el
   detalle por partido** vía `external_id` — decidir si se mergean en un solo
   objeto `Comparativa` o quedan como dos etapas separadas antes del merge.
3. **Definir `estrella`/`hit_mercado_resaltado` formalmente** — candidatos
   naturales: `chances[].chance` y `quickStats` (ambos ya traen % + cuota
   asociada). Confirmar antes por qué `chances` viene vacío en algunos
   fixtures.
4. **Correr el pipeline a mayor escala** (no solo 5 fixtures) para armar el
   dataset real — vigilar rate-limiting/bloqueos nuevos a volumen alto, no
   probado todavía más allá de una corrida chica.
5. Revisar `homestreaks`/`awaystreaks` de `comparison_stats` y el resto de
   campos de `recent_results` (fouls, shots, offsides, referee) no explorados
   en profundidad todavía — evaluar cuáles aportan a los mercados que Beet va
   a calibrar primero.

### Por qué aún no está en `beet/`

1. **Modelo `Comparativa` pendiente**: aún no se decidió si usa Pydantic o dataclasses (arrastrado desde la fase de diseño inicial). Sin eso no se puede escribir el mapeo formal.
2. **Arquitectura**: estos scripts son "código de investigación" que corre por fuera del paquete. La integración implicará mover la lógica a `beet/ingest/` o crear un nuevo módulo (ej. `beet/ingest/adamchoi_http/`) que reemplace o complemente el parser de PDFs.
3. **Decisión de merge**: aún no se define si el pipeline HTTP reemplazará por completo al pipeline de PDFs+Gemini, o si coexistirán (HTTP como fuente principal, PDF como fallback de validación).

---

## Roadmap

| Fase | Estado | Descripción |
| --- | --- | --- |
| 1 | ✅ | Core de modelos (Partido, Cuota, Historial) |
| 2 | ✅ | Ingesta con Gemini Vision + PDF nativo |
| 2b | ✅ | **Investigación: ingesta 100% HTTP desde Adam Choi (5 endpoints, scripts standalone validados)** |
| 3 | ✅ | Visor de validación de parsers (PyQt6) |
| 4 | ✅ | Datos persistentes en JSON |
| 5 | 🔲 | Motor de simulación (services/) |
| 6 | ⏳ | Calibración empírica + backtesting |
| 7 | ❌ | ~~Automatización de captura (selenium/playwright)~~ — descartada, superada por 2b (pipeline HTTP directo elimina la necesidad de capturar screenshots/PDF) |
| 7b | ⏳ | Integrar pipeline HTTP al paquete `beet/` (reemplazar o complementar PDFs) |
| 8 | ✅ | API Keys fuera del código (`~/.beet/config.json` + diálogo inicial) |

## Licencia

MIT