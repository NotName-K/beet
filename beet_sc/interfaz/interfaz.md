# ⚽ BEET Visor 
Visor gráfico para el pipeline de ingesta de datos de fútbol "BEET" . Permite listar los partidos del día (o de mañana si no hay partidos hoy), procesar cada fixture (scraping + ingesta + persistencia) y abrir una ventana de detalle con estadísticas, cuotas, historial cara a cara y datos crudos persistidos.

---

## 📁 Estructura del proyecto
beet_sc/
├── interfaz/                     # Interfaz gráfica (visores)
│   ├── __init__.py               # Exporta clases principales
│   ├── estilos.py                # Paleta de colores, QSS global, constantes de estado
│   ├── componentes.py            # Widgets reutilizables: labels, separadores, badges
│   ├── recursos.py               # Descarga y cache de banderas, logos, escudos, íconos SVG
│   ├── datos_fixture.py          # Funciones de lectura de staging y SQLite (.db)
│   ├── tarjeta_fixture.py        # Tarjeta individual de un fixture (estilo SofaScore)
│   ├── ventana_fixture.py        # Diálogo de detalle con pestañas (clasif., H2H, cuotas, etc.)
│   ├── visor_fixtures.py         # Vista principal: lista de tarjetas + lógica de procesamiento
│   ├── visor_datos.py            # Visor independiente de las 8 tablas persistidas (debug)
│   └── visor.py                  # Punto de entrada: ventana principal (VisorBeet)
├── pipeline/                     # Orquestador del pipeline (procesar_fixture)
├── scraping/                     # Módulo de obtención de fixtures y estadísticas
├── persistencia/                 # Modelos SQLAlchemy y acceso a bases SQLite
├── db/                           # Archivos .db individuales por fixture
└── visor.bat                     # Lanzador para Windows


---

## 📄 Archivos principales y su función

### `visor.py` – Entrada principal
- Verifica e instala dependencias dinámicamente (`PyQt6`, `requests`) al inicio de la ejecución mediante un subproceso.
- Registra fuentes tipográficas propias embebidas en el proyecto (como `Manrope[wght].ttf`) para uso en la interfaz.
- Crea la ventana principal (`VisorBeet`) con un tamaño mínimo de 1050x640 y aplica el QSS global.
- Muestra una barra superior con el título "⚽ BEET" e instancia el widget `VisorFixtures` que ocupa el resto de la ventana.
- Define un manejador de excepciones global (`excepthook`) para imprimir errores no capturados en la consola.

### `visor_fixtures.py` – Vista de fixtures
- Contiene la clase `VisorFixtures` que muestra una cuadrícula (`QGridLayout`) de 2 columnas con tarjetas de fixtures.
- Implementa pestañas de estado interactivas superiores ("Próximos", "Finalizados", "En vivo") para filtrar dinámicamente los partidos.
- Muestra bloques colapsables agrupados primero por día ("HOY" y "MAÑANA") y luego por país (ordenado alfabéticamente).
- Descarga asíncronamente las banderas de los países para mostrarlas en los encabezados colapsables de los grupos.
- Si el archivo de staging es viejo o no tiene partidos de hoy/mañana, dispara automáticamente la obtención de fixtures en un hilo de fondo.
- Recalcula periódicamente (cada 60 segundos) el estado de los partidos (pendiente, en curso, finalizado) y actualiza la lista si cambia el día.
- Cada tarjeta tiene un botón que dispara el procesamiento (`orquestador.procesar_fixture`) en un hilo paralelo y emite resultados al visor.
- Contiene la clase `VentanaLog`, una ventana flotante para mostrar el log de procesamiento con colores según el estado.

### `tarjeta_fixture.py` – Tarjeta individual
- Clase `TarjetaFixture` diseñada para un grid, con ancho mínimo de 320px y esquinas altamente redondeadas.
- Presenta una insignia de liga/división en la esquina superior izquierda y el estado de tiempo (ej. "● VIVO", "FIN" o "1T/HT/2T") arriba a la derecha.
- Muestra un diseño central con los escudos de ambos equipos, el logo de la liga en el medio, y la hora local del evento.
- Incluye un contenedor estilo "píldora" en la parte inferior para mostrar cuotas 1X2, el cual se hace visible tras cargar los datos del medio.
- Carga de forma asíncrona mediante hilos los logos de los equipos, el logo de la liga y las cuotas de la base SQLite.
- El botón de acción cambia su estado visual, tooltip y función dependiendo de si el partido ya está persistido (muestra un trofeo y abre detalles) o está pendiente (muestra una flecha y ejecuta procesamiento).

### `ventana_fixture.py` – Detalle del fixture
- Diálogo `VentanaDatosFixture` que muestra una cabecera con escudos, banderas, liga, marcador, fecha y árbitro.
- **CLASIFICACIÓN**: Muestra estadísticas resumidas de los equipos (puntos, partidos jugados, diferencia de gol) y la racha de últimos resultados, permitiendo alternar entre el contexto de local/visitante y general.
- **PARTIDOS RECIENTES**: Muestra el historial reciente de los equipos mediante una lista desplazable, con soporte para alternar entre partidos como local/visita o en general.
- **CARA A CARA**: Exhibe el historial de enfrentamientos directos entre ambos equipos, incluyendo filtros ("TODOS", "COMO LOCAL", "ESTE TORNEO") e insignias que totalizan victorias y empates.
- **CUOTAS**: Enumera las cuotas agrupadas por mercado persistidas en la base de datos.
- **DATOS CRUDOS**: Pestaña subdividida para inspeccionar gráficamente (mediante `QTableWidget`) las tablas persistidas en la base SQLite del partido.

### `datos_fixture.py` – Acceso a datos
- `_cargar_staging`: Lee el archivo JSON de staging con los fixtures del día.
- `_estado_partido` y `_periodo_partido`: Calculan heurísticamente el estado ("pendiente", "en_curso", "finalizado") y el tiempo de juego ("1T", "HT", "2T") usando una estimación de duración de 2 horas y 20 minutos.
- `_hora_local` y `_fecha_local`: Calculan y formatean la hora con zona horaria UTC-5.
- `_leer_datos_fixture` y `_leer_datos_medio_tarjeta`: Acceden directamente a la base de datos SQLite del partido y estructuran los resultados usando `sqlalchemy`.
- Incluye métodos funcionales para parsear el historial de partidos, filtrar resultados directos (Cara a Cara) y leer información sobre rachas en formato JSON.

### `recursos.py` – Imágenes e íconos
- Define el diccionario `_PAIS_A_ISO2` para mapear nombres de países desde el origen de datos a códigos ISO2 y descargar la bandera correcta desde `flagcdn.com`.
- Gestiona la concurrencia y caché en memoria/disco con hilos (`threading.Lock`) tanto para las banderas como para los logos de equipos.
- Genera escudos de equipos por defecto (usando iniciales del nombre y paletas de colores basadas en un hash) en caso de no disponer de logo.
- Renderiza SVG dinámicamente en un `QPixmap` usando `QSvgRenderer` (íconos de flecha y copa) y aplica recoloración para coincidir con la UI.

### `componentes.py` – Widgets reutilizables
- `lbl`: Construye una etiqueta con control sobre la pila de fuentes UI (`FONT_UI_STACK`) o la variante para datos monoespaciados (`FONT_MONO_STACK`).
- `section_title`, `hline`, `vline`: Componentes estandarizados para espaciado y títulos delgados.
- `pill`: Define una etiqueta estilo píldora usando `QFrame` para renderizado consistente del fondo y las esquinas.
- `badge_resultado`: Componente visual complejo para mostrar un resultado (V/E/D) usando un contenedor redondeado, con colores específicos y la opción de aplicar un subrayado.
- `_fila_racha`: Agrupa múltiples badges en una disposición horizontal para representar secuencias de victorias, empates o derrotas.

### `estilos.py` – Paleta y QSS
- Proporciona la paleta de colores del diseño "SofaScore" (`BG`, `ACCENT`, `GREEN`, `RED`, `MUTED`, `BG_CARD_DOCK`, etc.).
- Define pilas tipográficas ordenadas y fallbacks (`Manrope`, `Segoe UI`, `Consolas`, `JetBrains Mono`).
- Alberga el código QSS global en multilínea (`QSS`) con reglas específicas para barras de scroll, menús de pestañas (`QTabBar`), y botones interactivos (como el selector `[estado="persistido"]`).
- `ACENTO_ESTADO_PARTIDO` y `_ESTADO_DISPLAY`: Centralizan la lógica visual para asociar estados del pipeline (ej. `ingested`, `failed_scraping`) o del partido (`en_curso`) con colores e íconos específicos.

### `visor_datos.py` – Visor de tablas persistidas (independiente)
- Permite la visualización cruda de bases de datos de fixtures SQLite independientes mediante la clase `VisorDatos`.
- Utiliza la expresión regular `^(\d+)\.db$` para escanear y listar los archivos ubicados en el directorio `db/`.
- Expone sub-pestañas para las siguientes 8 tablas relacionales: `fixture_metadata`, `raw_odds`, `raw_match_history`, `fixture_match_history_refs`, `team_record_summaries`, `team_standings_rows`, `validation_errors`, y `fixture_pipeline_status`.
- Ordena los archivos listados por su fecha de modificación, mostrando primero los más recientes.

---

## 🚀 Uso

### Lanzar el visor
- En Windows: ejecutar `visor.bat` desde la raíz del proyecto.

El visor abrirá la lista de fixtures del día. Si no existe el archivo `scraping/comparativas_staging.json` o está vacío/desactualizado, se descargarán automáticamente los partidos de hoy (y de mañana como fallback).

### Procesar un fixture
1. Localizar el partido en la lista usando las pestañas de estado (Próximos/Finalizados/En vivo).
2. Hacer clic en el botón de la flecha de la tarjeta.
3. El pipeline se ejecuta en segundo plano: scraping → ingesta → persistencia sin bloquear la UI.
4. Al finalizar, si fue exitoso (✅), se abre automáticamente la ventana de detalle.
5. Si falla (❌), se muestra el error en el log y se abre automáticamente la ventana del log.

### Navegación y Filtros
- Alternar entre partidos usando los botones superiores ("Próximos", "Finalizados", "En vivo").
- Hacer clic en los encabezados de grupo para expandir o colapsar fechas (HOY/MAÑANA) o países completos.

### Ver log de procesamiento
- Hacer clic en el botón superior **"📋 Log"** para desplegar el historial de ejecución y errores en una ventana flotante separada.

### Re-escanear fixtures
- Hacer clic en **"🔄 Scan"** para recargar y parsear nuevamente la lista desde el archivo staging, reevaluando fechas y estados.

### Abrir detalle de un fixture ya persistido
- Si la tarjeta muestra el ícono de copa junto a la flecha, un clic en el botón abre directamente la ventana de detalle con las estadísticas persistidas sin requerir reprocesamiento.

---

## 📦 Dependencias

- **Python 3.10+**
- **PyQt6** – Interfaz gráfica (se instala automáticamente si falta en el primer inicio).
- **requests** – Descarga de banderas, logos y datos del pipeline (se instala automáticamente si falta).
- **sqlalchemy** – Acceso local estructurado a las bases SQLite (.db).

---

## 🔧 Notas técnicas

- La vista de fixtures se presenta en una grilla fija de 2 columnas que se reparten equitativamente el ancho de la ventana.
- El procesamiento se ejecuta en hilos independientes para evitar congelar el hilo principal gráfico.
- La reclasificación temporal de partidos y cambio de día detectado (pendiente → en_curso → finalizado) corre sobre un iterador `QTimer` que verifica actualizaciones cada 60 segundos.
- Las banderas descargadas quedan almacenadas de manera estática en memoria RAM y en un diccionario protegido por semáforos/locks para todo el ciclo de ejecución.

---

## 📝 Créditos

Desarrollado para el proyecto **Beet** – pipeline de ingesta de datos de fútbol.