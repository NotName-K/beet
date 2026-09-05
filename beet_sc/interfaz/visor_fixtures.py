"""
interfaz/visor_fixtures.py
Vista de fixtures: grid de tarjetas (3 columnas), escaneo en lote, log.
"""

import threading
from datetime import date, timedelta
from pathlib import Path
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QScrollArea,
    QTextEdit, QLabel, QFrame
)
from PyQt6.QtGui import QColor, QTextCursor, QPixmap
from .estilos import BG_ITEM, BORDER, MUTED, TEXT, ACCENT, ACCENT2, GREEN, RED
from .componentes import lbl, section_title
from .recursos import _icono_flecha_header, _sin_acentos, _descargar_bandera, _codigo_pais
from .tarjeta_fixture import TarjetaFixture
from .datos_fixture import _cargar_staging, _estado_partido, _hora_local, _fecha_local
import sqlite_store
import obtener_fixtures_dia

STAT_TYPES_STAGING = ["BTTS"]
STAGING_PATH = Path(__file__).resolve().parent.parent / "scraping" / "comparativas_staging.json"

# Cantidad de tarjetas por fila en el grid principal
NUM_COLUMNAS = 4

# Pestañas de estado.
TABS = (
    ("en_curso", "En vivo", RED),
    ("pendiente", "Próximos", ACCENT),
    ("finalizado", "Finalizados", MUTED),
)

ALTURA_TAB = 34
RADIO_TAB = ALTURA_TAB // 2


class _BotonTab(QFrame):
    clicked = pyqtSignal()

    def __init__(self, texto_base: str, parent=None):
        super().__init__(parent)
        self.setObjectName("frame_tab")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(ALTURA_TAB)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 18, 0)
        self.lbl_texto = lbl(texto_base, 11, bold=False, color=MUTED)
        self.lbl_texto.setStyleSheet("background:transparent;")
        lay.addWidget(self.lbl_texto)
        self.set_activo(False, MUTED)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def set_texto(self, texto: str):
        self.lbl_texto.setText(texto)

    def set_activo(self, activo: bool, color_activo: str):
        if activo:
            bg = color_activo if color_activo == RED else "#ffffff"
            fg = TEXT if color_activo == RED else "#111111"
            peso = "font-weight:700;"
        else:
            bg, fg, peso = BG_ITEM, "#c7cbd4", ""
        self.setStyleSheet(f"QFrame#frame_tab {{ background:{bg}; border-radius:{RADIO_TAB}px; }}")
        self.lbl_texto.setStyleSheet(f"color:{fg}; background:transparent; {peso}")


class VentanaLog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("⚽  BEET — Log de procesamiento")
        self.resize(460, 680)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)
        lay.addWidget(section_title("Log de procesamiento"))

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("El log de cada 'Procesar' aparecerá acá…")
        lay.addWidget(self.txt_log)

    def append_log(self, texto, color):
        cursor = self.txt_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = cursor.charFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(texto + "\n")
        self.txt_log.setTextCursor(cursor)
        self.txt_log.ensureCursorVisible()

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class VisorFixtures(QWidget):
    log_signal = pyqtSignal(str, str)
    fixture_procesado = pyqtSignal(int, dict)
    staging_fetch_terminado = pyqtSignal(bool, str)
    bandera_header_cargada = pyqtSignal(object, bytes)
    lote_terminado = pyqtSignal(str) 
    historico_cargado = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tarjetas: dict[int, TarjetaFixture] = {}
        self.ventana_log = VentanaLog()
        self._filas_actuales: list[dict] = []
        self._filas_db: list[dict] = []
        self._fecha_referencia: date | None = None  
        self._colapsado: dict[str, bool] = {}  
        self._tab_actual: str = "pendiente"  
        self.historico_cargado.connect(self._on_historico_cargado)
        
        # Animación Spinner
        self._escaneando: set[str] = set()
        self._labels_spinner: dict[str, QLabel] = {}
        self._spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spinner_idx = 0

        self._timer_spinner = QTimer(self)
        self._timer_spinner.setInterval(80) 
        self._timer_spinner.timeout.connect(self._animar_spinner)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)
        
        self.marco_kpi = QFrame()
        self.marco_kpi.setObjectName("marco_kpi")
        self.marco_kpi.setFixedHeight(40)
        self.marco_kpi.setStyleSheet(
            f"QFrame#marco_kpi {{ background:{BG_ITEM}; border:1px solid {BORDER}; border-radius:12px; }}"
        )
        lay_kpi = QHBoxLayout(self.marco_kpi)
        lay_kpi.setContentsMargins(18, 0, 18, 0)
        
        self.lbl_kpi_historico = lbl("📚 Histórico BD: --", 11, bold=True, color=TEXT)
        self.lbl_kpi_staging = lbl("📅 Staging (48h): --", 11, bold=True, color=TEXT)
        self.lbl_kpi_cobertura = lbl("⚡ Escaneados: --%", 11, bold=True, color=ACCENT)
        
        lay_kpi.addWidget(self.lbl_kpi_historico)
        lay_kpi.addStretch()
        lay_kpi.addWidget(self.lbl_kpi_staging)
        lay_kpi.addStretch()
        lay_kpi.addWidget(self.lbl_kpi_cobertura)
        
        lay.addWidget(self.marco_kpi)

        fila_tabs = QHBoxLayout()
        fila_tabs.setSpacing(8)
        self.btn_tabs: dict[str, _BotonTab] = {}
        for clave, etiqueta, color in TABS:
            btn = _BotonTab(etiqueta)
            btn.clicked.connect(lambda clave=clave: self._cambiar_tab(clave))
            fila_tabs.addWidget(btn)
            self.btn_tabs[clave] = btn
        fila_tabs.addStretch()
        btn_ver_log = QPushButton("📋  Log")
        btn_ver_log.setObjectName("btn_secondary")
        btn_ver_log.clicked.connect(self._mostrar_ventana_log)
        fila_tabs.addWidget(btn_ver_log)
        btn_refrescar = QPushButton("🔄  Scan")
        btn_refrescar.setObjectName("btn_secondary")
        btn_refrescar.clicked.connect(self._verificar_y_cargar)
        fila_tabs.addWidget(btn_refrescar)
        lay.addLayout(fila_tabs)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.contenedor = QWidget()
        self.lay_tarjetas = QGridLayout(self.contenedor)
        self.lay_tarjetas.setContentsMargins(6, 6, 18, 6)
        self.lay_tarjetas.setHorizontalSpacing(14)
        self.lay_tarjetas.setVerticalSpacing(14)
        for c in range(NUM_COLUMNAS):
            self.lay_tarjetas.setColumnStretch(c, 1)
        self.scroll.setWidget(self.contenedor)

        lay.addWidget(self.scroll, stretch=1)

        self.log_signal.connect(self.ventana_log.append_log)
        self.fixture_procesado.connect(self._on_fixture_procesado)
        self.staging_fetch_terminado.connect(self._on_staging_fetch_terminado)
        self.bandera_header_cargada.connect(self._mostrar_bandera_header)
        self.lote_terminado.connect(self._on_lote_terminado)

        self._timer_reclasificar = QTimer(self)
        self._timer_reclasificar.setInterval(60_000)
        self._timer_reclasificar.timeout.connect(self._tick)
        self._timer_reclasificar.start()

        self._verificar_y_cargar()

    def _actualizar_kpis(self, filas_staging: list[dict], estados: dict):
        # 1. Total BD (histórico)
        total_bd = len(self._filas_db)
        
        # 2. Total Staging (Hoy/Mañana)
        hoy = date.today()
        manana = hoy + timedelta(days=1)
        
        filas_hoy = obtener_fixtures_dia.filter_by_date(filas_staging, hoy, hoy)
        filas_manana = obtener_fixtures_dia.filter_by_date(filas_staging, manana, manana)
        total_staging = len(filas_hoy) + len(filas_manana)
        
        # 3. Cobertura de persistencia
        persisted = 0
        for f in filas_hoy + filas_manana:
            eid = f.get("external_id")
            if eid and estados.get(eid, {}).get("status") == "persisted":
                persisted += 1
                
        pct = (persisted / total_staging * 100) if total_staging > 0 else 0
        
        self.lbl_kpi_historico.setText(f"📚 Histórico BD: {total_bd}")
        self.lbl_kpi_staging.setText(f"📅 Staging (48h): {total_staging}")
        
        # Color semafórico
        color_pct = GREEN if pct >= 90 else (ACCENT if pct >= 50 else RED)
        self.lbl_kpi_cobertura.setText(f"⚡ Escaneados: {pct:.1f}%")
        self.lbl_kpi_cobertura.setStyleSheet(f"color: {color_pct}; background: transparent; font-weight: bold;")
        
    def _animar_spinner(self):
        if not self._escaneando:
            self._timer_spinner.stop()
            return
        
        self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_frames)
        caracter = self._spinner_frames[self._spinner_idx]
        
        for clave in list(self._labels_spinner.keys()):
            if clave in self._escaneando:
                lbl_spin = self._labels_spinner[clave]
                try:
                    lbl_spin.setText(caracter)
                except RuntimeError:
                    pass

    def _procesar_lote_secuencial(self, external_ids: list[int], clave_grupo: str):
        import time, orquestador
        try:
            for eid in external_ids:
                self._log(f"▶ Procesando fixture en lote: {eid} …", MUTED)
                try:
                    resultado = orquestador.procesar_fixture(eid)
                except Exception as e:
                    import traceback
                    error_msg = traceback.format_exc()
                    resultado = {"fixture_id": eid, "status": "failed_persistencia", "error": error_msg}
                
                self.fixture_procesado.emit(eid, resultado)
                time.sleep(1.5)  
        except Exception as err_fatal:
            self._log(f"❌ Error fatal en el hilo: {err_fatal}", RED)
        finally:
            self.lote_terminado.emit(clave_grupo)

    def _on_lote_terminado(self, clave_grupo: str):
        self._log(f"✅ División escaneada completamente.", GREEN)
        self._escaneando.discard(clave_grupo)
        self._labels_spinner.pop(clave_grupo, None)
        
        if not self._escaneando:
            self._timer_spinner.stop()

        self._colapsado[clave_grupo] = False
        self._mostrar(self._filas_actuales, silencioso=True)

    def _on_fixture_procesado(self, external_id: int, resultado: dict):
        try:
            status = resultado.get("status")
            color = GREEN if status == "persisted" else RED
            if status == "persisted":
                self._log(
                    f"✅ fixture {external_id}: persisted "
                    f"({resultado.get('total_errores', 0)} errores de validación)",
                    color,
                )
            else:
                self._log(f"❌ fixture {external_id}: {status} — {resultado.get('error', '')}", color)
                if not self.ventana_log.isVisible():
                    self._mostrar_ventana_log()

            tarjeta = self.tarjetas.get(external_id)
            if tarjeta is not None:
                tarjeta.set_resultado(resultado)
        except Exception as e:
            import traceback
            print(f"❌ Error en _on_fixture_procesado: {traceback.format_exc()}")
            self._log(f"Error interno al procesar resultado: {e}", RED)
            
    def _mostrar_ventana_log(self):
        self.ventana_log.show()
        self.ventana_log.raise_()
        self.ventana_log.activateWindow()

    def _log(self, texto, color=TEXT):
        self.log_signal.emit(texto, color)

    def _tick(self):
        if not self._filas_actuales:
            return
        hoy_real = date.today()
        if self._fecha_referencia is not None and hoy_real > self._fecha_referencia:
            self._log("Cambio de día detectado — recargando fixtures…", MUTED)
            self._verificar_y_cargar()
            return
        self._mostrar(self._filas_actuales, silencioso=True)
    
    def _cargar_historico_hilo(self):
        try:
            filas = sqlite_store.obtener_historico_db(limite_dias=30)
            self.historico_cargado.emit(filas)
        except Exception:
            pass

    def _on_historico_cargado(self, filas: list[dict]):
        self._filas_db = filas
        # Si ya estábamos parados en la pestaña, repintamos la pantalla
        if self._tab_actual == "finalizado":
            self._mostrar(self._filas_actuales, silencioso=True)
        else:
            # Si no, solo actualizamos los numeritos de los tabs
            if self._filas_actuales:
                hoy = date.today()
                manana = hoy + timedelta(days=1)
                
                f_hoy = obtener_fixtures_dia.filter_by_date(self._filas_actuales, hoy, hoy)
                f_man = obtener_fixtures_dia.filter_by_date(self._filas_actuales, manana, manana)
                counts = self._contar_por_estado(f_hoy, f_man, self._filas_db)
                self._refrescar_estilo_tabs(counts)
                
                ids_staging = [r["external_id"] for r in self._filas_actuales if r.get("external_id")]
                ids_db = [r["external_id"] for r in self._filas_db if r.get("external_id")]
                estados = sqlite_store.listar_estados_pipeline_multi(ids_staging + ids_db)
                self._actualizar_kpis(self._filas_actuales, estados)
                
    def _verificar_y_cargar(self):
        threading.Thread(target=self._cargar_historico_hilo, daemon=True).start()
        hoy = date.today()
        manana = hoy + timedelta(days=1)
        rows = _cargar_staging(STAGING_PATH)
        if not rows:
            self._log(f"No existe {STAGING_PATH.name} — generándolo (hoy + mañana)…", MUTED)
            self._disparar_fetch()
            return
        rows_combinados = obtener_fixtures_dia.filter_by_date(rows, hoy, manana)
        if rows_combinados:
            self._fecha_referencia = hoy
            self._mostrar(rows_combinados)
            return
        self._log(f"{STAGING_PATH.name} es viejo (sin partidos de hoy ni de mañana) — actualizando…", MUTED)
        self._disparar_fetch()

    def _disparar_fetch(self):
        self._mostrar_placeholder("Descargando fixtures de hoy y mañana…")
        threading.Thread(target=self._fetch_en_hilo, daemon=True).start()

    def _fetch_en_hilo(self):
        hoy = date.today()
        manana = hoy + timedelta(days=1)
        try:
            obtener_fixtures_dia.run(
                stat_types=STAT_TYPES_STAGING,
                out_path=str(STAGING_PATH),
                fecha_desde=hoy,
                fecha_hasta=manana,
            )
            ok, msg = True, ""
        except Exception as e:
            ok, msg = False, str(e)
        self.staging_fetch_terminado.emit(ok, msg)

    def _on_staging_fetch_terminado(self, ok: bool, msg: str):
        if not ok:
            self._log(f"❌ Error descargando fixtures: {msg}", RED)
            self._mostrar_placeholder(f"Error al descargar fixtures: {msg}")
            return
        hoy = date.today()
        manana = hoy + timedelta(days=1)
        rows = _cargar_staging(STAGING_PATH)
        filtradas = obtener_fixtures_dia.filter_by_date(rows, hoy, manana)

        self._fecha_referencia = hoy
        if filtradas:
            self._log(f"✅ {len(filtradas)} fixtures descargados (hoy + mañana).", GREEN)
            self._mostrar(filtradas)
        else:
            self._log("No hay partidos ni hoy ni mañana.", MUTED)
            self._mostrar_placeholder("No hay partidos ni hoy ni mañana.")

    def _limpiar_tarjetas(self):
        while self.lay_tarjetas.count():
            item = self.lay_tarjetas.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for f in range(self.lay_tarjetas.rowCount()):
            self.lay_tarjetas.setRowStretch(f, 0)
        self.tarjetas.clear()

    def _mostrar_placeholder(self, texto: str):
        self._limpiar_tarjetas()
        self.lay_tarjetas.addWidget(lbl(texto, 10, color=MUTED), 0, 0, 1, NUM_COLUMNAS)

    def _cambiar_tab(self, clave: str):
        if self._tab_actual == clave:
            return
        self._tab_actual = clave
        self._mostrar(self._filas_actuales, silencioso=True)

    def _contar_por_estado(self, filas_hoy: list[dict], filas_manana: list[dict], filas_db: list[dict]) -> dict[str, int]:
        # El número de finalizados ahora es 100% fiel a lo guardado en BD
        counts = {"en_curso": 0, "pendiente": 0, "finalizado": len(filas_db)}
        for row in filas_hoy + filas_manana:
            if not row.get("external_id"):
                continue
            estado = _estado_partido(row.get("kickoff_epoch_ms"))
            if estado in counts and estado != "finalizado":
                counts[estado] += 1
        return counts

    def _refrescar_estilo_tabs(self, counts: dict[str, int]):
        for clave, etiqueta, color in TABS:
            btn = self.btn_tabs[clave]
            # Inciso 5: Puntito rojo visual para En vivo
            prefix = "🔴 " if clave == "en_curso" and counts.get(clave, 0) > 0 else ""
            btn.set_texto(f"{prefix}{etiqueta}  ({counts.get(clave, 0)})")
            btn.set_activo(clave == self._tab_actual, color)

    def _mostrar(self, rows: list[dict], silencioso: bool = False):
        self._filas_actuales = rows
        self._limpiar_tarjetas()

        hoy = date.today()
        manana = hoy + timedelta(days=1)
        filas_hoy = obtener_fixtures_dia.filter_by_date(rows, hoy, hoy)
        filas_manana = obtener_fixtures_dia.filter_by_date(rows, manana, manana)

        # Necesitamos el status del pipeline de todo lo que vayamos a pintar
        ids_staging = [r["external_id"] for r in rows if r.get("external_id")]
        ids_db = [r["external_id"] for r in self._filas_db if r.get("external_id")]
        estados = sqlite_store.listar_estados_pipeline_multi(ids_staging + ids_db)
        self._actualizar_kpis(rows, estados)
        
        counts = self._contar_por_estado(filas_hoy, filas_manana, self._filas_db)
        self._refrescar_estilo_tabs(counts)

        fila_actual = 0
        
        
        # BIFURCACIÓN DE FUENTES SEGÚN LA PESTAÑA
        if self._tab_actual == "finalizado":
            # Agrupar el histórico por fechas
            grupos_fecha = {}
            for row in self._filas_db:
                # Convertir el epoch a fecha local
                epoch_ms = row.get("kickoff_epoch_ms")
                if not epoch_ms:
                    continue
                    
                import datetime
                dt = datetime.datetime.fromtimestamp(epoch_ms / 1000.0)
                fecha_str = dt.strftime("%Y-%m-%d")
                grupos_fecha.setdefault(fecha_str, []).append(row)
                
            # Ordenar las fechas de la más reciente a la más antigua
            fechas_ordenadas = sorted(grupos_fecha.keys(), reverse=True)
            
            for fecha_str in fechas_ordenadas:
                filas_grupo = grupos_fecha[fecha_str]
                
                # Etiquetado amigable (Ayer, o el nombre del día)
                dt_grupo = date.fromisoformat(fecha_str)
                diferencia_dias = (hoy - dt_grupo).days
                
                if diferencia_dias == 0:
                    titulo_bloque = "📅 HOY"
                elif diferencia_dias == 1:
                    titulo_bloque = "📅 AYER"
                else:
                    # Ej: 📅 MARTES 18
                    dias_es = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
                    nombre_dia = dias_es[dt_grupo.weekday()]
                    titulo_bloque = f"📅 {nombre_dia} {dt_grupo.day}"
                    
                # Reutilizamos _agregar_bloque_dia (pasando el string de la fecha como id)
                fila_actual = self._agregar_bloque_dia(titulo_bloque, fecha_str, filas_grupo, estados, fila_actual)
                
        else:
            fila_actual = self._agregar_bloque_dia("📅 HOY", "hoy", filas_hoy, estados, fila_actual)
            fila_actual = self._agregar_bloque_dia("📅 MAÑANA", "manana", filas_manana, estados, fila_actual)
        
        if counts.get(self._tab_actual, 0) == 0:
            etiqueta_tab = next(et for clv, et, _ in TABS if clv == self._tab_actual)
            self.lay_tarjetas.addWidget(
                lbl(f"No hay partidos en «{etiqueta_tab}».", 10, color=MUTED),
                fila_actual, 0, 1, NUM_COLUMNAS,
            )
            fila_actual += 1
        else:
            # EL RESORTE: empuja todo el contenido hacia arriba cuando se colapsan los headers
            from PyQt6.QtWidgets import QSpacerItem, QSizePolicy
            resorte = QSpacerItem(10, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
            self.lay_tarjetas.addItem(resorte, fila_actual, 0, 1, NUM_COLUMNAS)
            self.lay_tarjetas.setRowStretch(fila_actual, 1)

        if not silencioso:
            self._log(
                f"Mostrando {counts['en_curso']} en vivo, {counts['pendiente']} próximos "
                f"y {counts['finalizado']} finalizados.",
                MUTED,
            )
            
    def _toggle_seccion(self, clave: str, grupo_ids: list[int] | None = None):
        estaba_colapsado = self._colapsado.get(clave, True)

        if not estaba_colapsado:
            self._colapsado[clave] = True
            self._mostrar(self._filas_actuales, silencioso=True)
            return

        if clave.startswith("liga:") and grupo_ids:
            estados = sqlite_store.listar_estados_pipeline_multi(grupo_ids)
            pendientes = [
                eid for eid in grupo_ids 
                if (estados.get(eid) or {}).get("status") != "persisted"
            ]

            if pendientes:
                self._log(f"\n[Cola] Escaneando {len(pendientes)} partidos de la división...", ACCENT)
                
                self._escaneando.add(clave)
                if not self._timer_spinner.isActive():
                    self._timer_spinner.start()
                
                self._mostrar(self._filas_actuales, silencioso=True)
                import threading
                threading.Thread(
                    target=self._procesar_lote_secuencial, 
                    args=(pendientes, clave), 
                    daemon=True
                ).start()
                return

        self._colapsado[clave] = False
        self._mostrar(self._filas_actuales, silencioso=True)

    def _cargar_bandera_header_en_hilo(self, codigo: str, label: QLabel):
        data = _descargar_bandera(codigo)
        if data:
            self.bandera_header_cargada.emit(label, data)

    def _mostrar_bandera_header(self, label: QLabel, data: bytes):
        pix = QPixmap()
        if pix.loadFromData(data):
            pix = pix.scaled(
                20, 14,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(pix)
        else:
            label.setVisible(False)

    def _crear_header_colapsable(
        self, texto: str, color: str, clave: str, tamano_fuente: int = 10,
        codigo_pais: str | None = None, grupo_ids: list[int] | None = None,
        indentar: bool = False
    ) -> QWidget:
        colapsado = self._colapsado.get(clave, True)
        esta_escaneando = clave in self._escaneando

        contenedor = QWidget()
        contenedor.setCursor(
            Qt.CursorShape.ArrowCursor if esta_escaneando else Qt.CursorShape.PointingHandCursor
        )
        
        from PyQt6.QtWidgets import QSizePolicy
        contenedor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        fila = QHBoxLayout(contenedor)
        
        # Inciso 2: Sangría de 28px si es una liga para jerarquizar debajo de HOY/MAÑANA
        margen_izq = 28 if indentar else 0
        fila.setContentsMargins(margen_izq, 4, 0, 4)
        fila.setSpacing(6)

        if codigo_pais:
            lbl_bandera = QLabel()
            lbl_bandera.setFixedSize(20, 14)
            lbl_bandera.setStyleSheet("background:transparent;")
            fila.addWidget(lbl_bandera, alignment=Qt.AlignmentFlag.AlignVCenter)
            import threading
            threading.Thread(
                target=self._cargar_bandera_header_en_hilo,
                args=(codigo_pais, lbl_bandera),
                daemon=True,
            ).start()

        fila.addWidget(lbl(texto, tamano_fuente, bold=True, color=color))
        fila.addStretch()

        if esta_escaneando:
            lbl_spin = lbl(self._spinner_frames[self._spinner_idx], tamano_fuente + 4, bold=True, color=ACCENT2)
            lbl_spin.setStyleSheet("background:transparent;")
            fila.addWidget(lbl_spin, alignment=Qt.AlignmentFlag.AlignVCenter)
            self._labels_spinner[clave] = lbl_spin
        else:
            lbl_flecha = QLabel()
            lbl_flecha.setPixmap(_icono_flecha_header(colapsado, tamano_fuente + 3, color))
            lbl_flecha.setStyleSheet("background:transparent;")
            fila.addWidget(lbl_flecha, alignment=Qt.AlignmentFlag.AlignVCenter)

        def _on_click(_event, clv=clave, gids=grupo_ids):
            if clv in self._escaneando:
                return
            self._toggle_seccion(clv, gids)

        contenedor.mousePressEvent = _on_click
        return contenedor

    def _agregar_bloque_dia(
        self, titulo_dia: str, dia_id: str, filas: list[dict], estados: dict, fila_actual: int,
    ) -> int:
        
        if dia_id == "historico":
            filas_tab = [r for r in filas if r.get("external_id")]
        else:
            filas_tab = [
                row for row in filas
                if row.get("external_id")
                and _estado_partido(row.get("kickoff_epoch_ms")) == self._tab_actual
            ]
            
        if not filas_tab:
            return fila_actual

        clave_dia = f"dia:{self._tab_actual}:{dia_id}"
        if clave_dia not in self._colapsado:
            self._colapsado[clave_dia] = False  
        header_dia = self._crear_header_colapsable(
            f"{titulo_dia}  ({len(filas_tab)})", TEXT, clave_dia, tamano_fuente=12,
        )
        self.lay_tarjetas.addWidget(header_dia, fila_actual, 0, 1, NUM_COLUMNAS)
        fila_actual += 1

        if self._colapsado.get(clave_dia, False):
            return fila_actual

        grupos_liga: dict[tuple[str, str], list[dict]] = {}
        for row in filas_tab:
            pais = str(row.get("country", "?"))
            liga = str(row.get("league_name", "?"))
            grupos_liga.setdefault((pais, liga), []).append(row)

        orden_asc = self._tab_actual != "finalizado"
        def clave_orden(tupla_k):
            p, l = tupla_k
            return (_sin_acentos(p), _sin_acentos(l))

        for (pais, liga) in sorted(grupos_liga.keys(), key=clave_orden):
            grupo = grupos_liga[(pais, liga)]
            grupo.sort(key=lambda r: r.get("kickoff_epoch_ms") or 0, reverse=not orden_asc)

            clave_toggle = f"liga:{self._tab_actual}:{dia_id}:{pais}:{liga}"
            codigo_pais = _codigo_pais(grupo[0])
            
            # Inciso 1: Limpiamos el texto, solo mostramos el nombre de la liga (sin país y sin el guion)
            titulo_seccion = f"- {liga}"
            
            fila_actual = self._agregar_seccion(
                titulo_seccion, TEXT, grupo, estados, self._tab_actual, clave_toggle, fila_actual,
                codigo_pais=codigo_pais,
            )

        return fila_actual

    def _agregar_seccion(
        self, titulo_seccion: str, color_seccion: str, grupo: list[dict],
        estados: dict, estado_partido_clave: str, clave_toggle: str, fila_actual: int,
        codigo_pais: str | None = None,
    ) -> int:
        
        grupo_ids = [r["external_id"] for r in grupo if r.get("external_id")]
        
        if clave_toggle not in self._colapsado:
            self._colapsado[clave_toggle] = True
        
        header = self._crear_header_colapsable(
            f"{titulo_seccion}  ({len(grupo)})", color_seccion, clave_toggle,
            codigo_pais=codigo_pais, grupo_ids=grupo_ids, indentar=True
        )
        self.lay_tarjetas.addWidget(header, fila_actual, 0, 1, NUM_COLUMNAS)
        fila_actual += 1

        if self._colapsado.get(clave_toggle, True):
            return fila_actual

        columna = 0
        for row in grupo:
            eid = row["external_id"]
            tarjeta = TarjetaFixture(row, estados.get(eid), estado_partido=estado_partido_clave)
            self.lay_tarjetas.addWidget(tarjeta, fila_actual, columna)
            self.tarjetas[eid] = tarjeta

            columna += 1
            if columna >= NUM_COLUMNAS:
                columna = 0
                fila_actual += 1

        if columna != 0:
            fila_actual += 1

        return fila_actual