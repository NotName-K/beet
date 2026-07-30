import sys
import traceback
import time
import itertools
from typing import Optional
from PyQt6.QtCore import QThreadPool, QRunnable, QObject, pyqtSignal, pyqtSlot

from beet.ingest import (
    agrupar_lote,
    parsear_imagen_historial,
    parsear_pdf_cuotas,
    LoteIngesta,
)
from beet.ingest.parsers.imagen import ResultadoParseoImagen
from beet.ingest.parsers.pdf import ResultadoParseoPDF
from beet.data import guardar_partido, cargar_partido, partido_procesado

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    tiempo = pyqtSignal(float)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        t0 = time.perf_counter()
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            t1 = time.perf_counter()
            self.signals.tiempo.emit((t1 - t0) * 1000)
            self.signals.finished.emit()

class VisorController(QObject):
    lotes_cargados = pyqtSignal(dict)
    # Llevan `clave` para que quien escuche pueda descartar resultados de
    # partidos que no son el que está seleccionado en pantalla — antes el
    # auto-escaneo en background pisaba lo que se estaba viendo cuando
    # terminaba de procesar OTRO partido distinto al seleccionado.
    historial_goles_listo = pyqtSignal(str, object, float)
    historial_corners_listo = pyqtSignal(str, object, float)
    cuotas_listo = pyqtSignal(str, object, float)
    error_ocurrido = pyqtSignal(str)
    log_mensaje = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        # Limitamos la concurrencia: solo hay 2 API keys de Gemini rotando,
        # lanzar 20-30 workers en paralelo durante el auto-escaneo satura
        # la cuota y provoca fallos silenciosos que quedaban cacheados como
        # "procesado" sin datos.
        self.threadpool.setMaxThreadCount(3)
        self.lotes: dict[str, LoteIngesta] = {}
        self._pendientes: dict[int, dict] = {}
        # Contador incremental para identificar cada worker de forma única.
        # NUNCA usar id(worker) para esto: los Worker son QRunnable con
        # autoDelete=True, así que QThreadPool los destruye apenas
        # terminan — y con el auto-escaneo lanzando muchos workers
        # seguidos, Python reutiliza esa misma dirección de memoria para
        # el próximo Worker que se crea. Dos workers distintos terminaban
        # compartiendo la misma "clave_worker" y pisándose el estado en
        # self._pendientes, lo que producía un KeyError al llegar tarde
        # la señal de uno de ellos — y esa excepción, al escapar de un
        # slot de Qt, crasheaba la app entera en vez de solo loguear un
        # error.
        self._contador_workers = itertools.count()

    @staticmethod
    def _resultado_tiene_datos(resultado) -> bool:
        """
        True si el resultado cacheado realmente tiene historial parseado.
        Antes, un resultado_goles guardado con historial_local=None /
        historial_visitante=None (por un fallo de parseo que no lanzó
        excepción, o que sí la lanzó y quedó en 'errores') se trataba como
        'ya resuelto' y nunca se reintentaba.
        """
        if resultado is None:
            return False
        local = getattr(resultado, "historial_local", None)
        visitante = getattr(resultado, "historial_visitante", None)
        n = (len(local.partidos) if local else 0) + (len(visitante.partidos) if visitante else 0)
        return n > 0

    def cargar_carpeta(self, ruta: str):
        self.log_mensaje.emit(f"Escaneando carpeta: {ruta}")
        try:
            self.lotes = agrupar_lote(ruta)
        except Exception:
            tb = traceback.format_exc()
            self.log_mensaje.emit(tb)
            self.error_ocurrido.emit(f"No se pudo agrupar el lote en '{ruta}':\n{tb}")
            return
        self.log_mensaje.emit(f"Se encontraron {len(self.lotes)} partido(s) en '{ruta}'")
        self.lotes_cargados.emit(self.lotes)
        
        # Auto-escaneo
        self.log_mensaje.emit("Iniciando escaneo automático de todos los partidos...")
        for clave, lote in self.lotes.items():
            self.procesar_partido(clave, lote)

    def procesar_partido(self, clave: str, lote: LoteIngesta):
        self.log_mensaje.emit(f"Verificando partido: {clave}")
        
        datos_existentes = cargar_partido(clave) or {}
        
        archivos_faltantes = lote.archivos_faltantes()
        if archivos_faltantes:
            self.log_mensaje.emit(f"⚠️ {clave}: Faltan archivos: {', '.join(archivos_faltantes)}")

        # GOLES
        goles_cache = datos_existentes.get("goles")
        goles_valido = self._resultado_tiene_datos(goles_cache)
        if not goles_valido and getattr(lote, "imagen_resultado", None):
            if goles_cache is not None:
                self.log_mensaje.emit(
                    f"⟳ Goles cacheados sin datos (posible error previo) para {clave}, reprocesando..."
                )
                if goles_cache.errores:
                    self.log_mensaje.emit(f"   Errores previos: {'; '.join(goles_cache.errores)}")
            self._ejecutar_worker(
                fn=parsear_imagen_historial,
                args=(lote.imagen_resultado,),
                on_success=lambda r, t: self._on_goles_result(clave, r, t),
                on_error=self._on_goles_error,
                descripcion=f"goles ({clave})",
            )
        elif goles_valido:
            self.log_mensaje.emit(f"✓ Goles ya en datos persistentes: {clave}")
            self.historial_goles_listo.emit(clave, goles_cache, 0.0)
        else:
            self.log_mensaje.emit(f"⚠️ No se puede procesar goles: falta archivo en {clave}")

        # CORNERS
        corners_cache = datos_existentes.get("corners")
        corners_valido = self._resultado_tiene_datos(corners_cache)
        if not corners_valido and getattr(lote, "imagen_corners", None):
            if corners_cache is not None:
                self.log_mensaje.emit(
                    f"⟳ Corners cacheados sin datos (posible error previo) para {clave}, reprocesando..."
                )
                if corners_cache.errores:
                    self.log_mensaje.emit(f"   Errores previos: {'; '.join(corners_cache.errores)}")
            self._ejecutar_worker(
                fn=parsear_imagen_historial,
                args=(lote.imagen_corners,),
                on_success=lambda r, t: self._on_corners_result(clave, r, t),
                on_error=self._on_corners_error,
                descripcion=f"corners ({clave})",
            )
        elif corners_valido:
            self.log_mensaje.emit(f"✓ Corners ya en datos persistentes: {clave}")
            self.historial_corners_listo.emit(clave, corners_cache, 0.0)
        else:
            self.log_mensaje.emit(f"⚠️ No se puede procesar corners: falta archivo en {clave}")

        # CUOTAS
        cuotas_cache = datos_existentes.get("cuotas")
        cuotas_valido = bool(cuotas_cache and getattr(cuotas_cache, "cuotas", None))
        if not cuotas_valido and getattr(lote, "pdf_odds", None):
            if cuotas_cache is not None:
                self.log_mensaje.emit(
                    f"⟳ Cuotas cacheadas sin datos (posible error previo) para {clave}, reprocesando..."
                )
            self._ejecutar_worker(
                fn=parsear_pdf_cuotas,
                args=(lote.pdf_odds,),
                on_success=lambda r, t: self._on_cuotas_result(clave, r, t),
                on_error=self._on_cuotas_error,
                descripcion=f"cuotas ({clave})",
            )
        elif cuotas_valido:
            self.log_mensaje.emit(f"✓ Cuotas ya en datos persistentes: {clave}")
            self.cuotas_listo.emit(clave, cuotas_cache, 0.0)
        else:
            self.log_mensaje.emit(f"️ No se puede procesar cuotas: falta archivo en {clave}")

    def _ejecutar_worker(self, fn, args, on_success, on_error, descripcion: str):
        worker = Worker(fn, *args)
        clave_worker = next(self._contador_workers)
        self._pendientes[clave_worker] = {}
        
        def _guardar_resultado(resultado):
            estado = self._pendientes.get(clave_worker)
            if estado is None:
                # Llegó una señal tardía para un worker cuya entrada ya se
                # había completado o descartado — no hay nada seguro que
                # hacer con esto, se ignora en vez de crashear.
                return
            estado["resultado"] = resultado
            self._intentar_completar(clave_worker, on_success)
        
        def _guardar_tiempo(ms):
            estado = self._pendientes.get(clave_worker)
            if estado is None:
                return
            estado["tiempo_ms"] = ms
            self._intentar_completar(clave_worker, on_success)
        
        def _manejar_error(error_tuple):
            self._pendientes.pop(clave_worker, None)
            on_error(error_tuple)

        worker.signals.result.connect(_guardar_resultado)
        worker.signals.tiempo.connect(_guardar_tiempo)
        worker.signals.error.connect(_manejar_error)
        worker.signals.finished.connect(
            lambda: self.log_mensaje.emit(f"Finalizado: {descripcion}")
        )
        self.log_mensaje.emit(f"Iniciando en background: {descripcion}")
        self.threadpool.start(worker)

    def _intentar_completar(self, clave_worker: int, on_success):
        estado = self._pendientes.get(clave_worker)
        if estado is None:
            return
        if "resultado" in estado and "tiempo_ms" in estado:
            self._pendientes.pop(clave_worker, None)
            on_success(estado["resultado"], estado["tiempo_ms"])

    def _on_goles_result(self, clave: str, resultado: ResultadoParseoImagen, tiempo_ms: float):
        guardar_partido(clave, resultado_goles=resultado)
        self.historial_goles_listo.emit(clave, resultado, tiempo_ms)

    def _on_goles_error(self, error_tuple):
        exctype, value, tb = error_tuple
        self.log_mensaje.emit(tb)
        self.error_ocurrido.emit(f"Error al parsear goles:\n{tb}")

    def _on_corners_result(self, clave: str, resultado: ResultadoParseoImagen, tiempo_ms: float):
        guardar_partido(clave, resultado_corners=resultado)
        self.historial_corners_listo.emit(clave, resultado, tiempo_ms)

    def _on_corners_error(self, error_tuple):
        exctype, value, tb = error_tuple
        self.log_mensaje.emit(tb)
        self.error_ocurrido.emit(f"Error al parsear corners:\n{tb}")

    def _on_cuotas_result(self, clave: str, resultado: ResultadoParseoPDF, tiempo_ms: float):
        guardar_partido(clave, resultado_cuotas=resultado)
        self.cuotas_listo.emit(clave, resultado, tiempo_ms)

    def _on_cuotas_error(self, error_tuple):
        exctype, value, tb = error_tuple
        self.log_mensaje.emit(tb)
        self.error_ocurrido.emit(f"Error al parsear cuotas:\n{tb}")