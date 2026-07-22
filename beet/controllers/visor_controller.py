import sys
import traceback
import time
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


class WorkerSignals(QObject):
    """Señales que expone un Worker en ejecución dentro del QThreadPool."""

    finished = pyqtSignal()
    error = pyqtSignal(tuple)      # (exctype, value, traceback_str)
    result = pyqtSignal(object)    # resultado de la función
    tiempo = pyqtSignal(float)     # tiempo de ejecución en ms


class Worker(QRunnable):
    """
    Ejecuta una función arbitraria en un hilo del QThreadPool.

    NOTA: QThreadPool.start() requiere una instancia de QRunnable (no QObject
    puro), por eso Worker hereda de QRunnable y delega las señales a un
    WorkerSignals(QObject) interno — QRunnable no puede emitir señales por sí
    mismo.
    """

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
    """
    Orquesta la interacción entre la UI y los servicios de ingesta.
    Ejecuta los parsers en hilos de fondo (QThreadPool) para no bloquear
    la interfaz, y comunica resultados a la UI vía señales.
    """

    lotes_cargados = pyqtSignal(dict)            # {clave: LoteIngesta}
    historial_listo = pyqtSignal(object, float)  # ResultadoParseoImagen, tiempo_ms
    cuotas_listo = pyqtSignal(object, float)      # ResultadoParseoPDF, tiempo_ms
    error_ocurrido = pyqtSignal(str)              # mensaje de error
    log_mensaje = pyqtSignal(str)                 # mensaje para el log

    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        self.lotes: dict[str, LoteIngesta] = {}
        # Acumula resultado/tiempo por worker mientras llegan sus señales,
        # ya que result y tiempo se emiten por separado y no en el mismo
        # instante (result primero, tiempo después).
        self._pendientes: dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Carga de carpeta
    # ------------------------------------------------------------------
    def cargar_carpeta(self, ruta: str):
        self.log_mensaje.emit(f"Escaneando carpeta: {ruta}")
        try:
            self.lotes = agrupar_lote(ruta)
        except Exception:
            tb = traceback.format_exc()
            self.log_mensaje.emit(tb)
            self.error_ocurrido.emit(
                f"No se pudo agrupar el lote en '{ruta}':\n{tb}"
            )
            return

        self.log_mensaje.emit(
            f"Se encontraron {len(self.lotes)} partido(s) en '{ruta}'"
        )
        self.lotes_cargados.emit(self.lotes)

    # ------------------------------------------------------------------
    # Procesamiento de un partido seleccionado
    # ------------------------------------------------------------------
    def procesar_partido(self, clave: str, lote: LoteIngesta):
        self.log_mensaje.emit(f"Procesando partido: {clave}")

        if getattr(lote, "imagen_corners", None):
            self._ejecutar_worker(
                fn=parsear_imagen_historial,
                args=(lote.imagen_corners,),
                on_success=self._on_historial_result,
                on_error=self._on_historial_error,
                descripcion=f"historial ({clave})",
            )

        if getattr(lote, "pdf_odds", None):
            self._ejecutar_worker(
                fn=parsear_pdf_cuotas,
                args=(lote.pdf_odds,),
                on_success=self._on_cuotas_result,
                on_error=self._on_cuotas_error,
                descripcion=f"cuotas ({clave})",
            )

    # ------------------------------------------------------------------
    # Factory de workers
    # ------------------------------------------------------------------
    def _ejecutar_worker(self, fn, args, on_success, on_error, descripcion: str):
        worker = Worker(fn, *args)
        clave_worker = id(worker)
        self._pendientes[clave_worker] = {}

        def _guardar_resultado(resultado):
            self._pendientes[clave_worker]["resultado"] = resultado
            self._intentar_completar(clave_worker, on_success)

        def _guardar_tiempo(ms):
            self._pendientes[clave_worker]["tiempo_ms"] = ms
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
        """Llama on_success(resultado, tiempo_ms) solo cuando ya llegaron
        tanto el resultado como el tiempo de ejecución del worker."""
        estado = self._pendientes.get(clave_worker)
        if estado is None:
            return
        if "resultado" in estado and "tiempo_ms" in estado:
            self._pendientes.pop(clave_worker, None)
            on_success(estado["resultado"], estado["tiempo_ms"])

    # ------------------------------------------------------------------
    # Callbacks finales — resultados de historial (imagen)
    # ------------------------------------------------------------------
    def _on_historial_result(self, resultado: ResultadoParseoImagen, tiempo_ms: float):
        self.historial_listo.emit(resultado, tiempo_ms)

    def _on_historial_error(self, error_tuple):
        exctype, value, tb = error_tuple
        self.log_mensaje.emit(tb)
        self.error_ocurrido.emit(f"Error al parsear historial:\n{tb}")

    # ------------------------------------------------------------------
    # Callbacks finales — resultados de cuotas (PDF)
    # ------------------------------------------------------------------
    def _on_cuotas_result(self, resultado: ResultadoParseoPDF, tiempo_ms: float):
        self.cuotas_listo.emit(resultado, tiempo_ms)

    def _on_cuotas_error(self, error_tuple):
        exctype, value, tb = error_tuple
        self.log_mensaje.emit(tb)
        self.error_ocurrido.emit(f"Error al parsear cuotas:\n{tb}")
