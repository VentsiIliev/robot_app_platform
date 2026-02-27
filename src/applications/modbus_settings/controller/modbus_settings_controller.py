import logging
from typing import List, Tuple

from PyQt6.QtCore import QThread, pyqtSignal, QObject

from src.applications.base.i_application_controller import IApplicationController
from src.applications.modbus_settings.model.modbus_settings_model import ModbusSettingsModel
from src.applications.modbus_settings.view.modbus_settings_view import ModbusSettingsView


class _Worker(QObject):
    """Runs a blocking call off the GUI thread."""
    finished = pyqtSignal(object)
    failed   = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished.emit(self._fn())
        except Exception as exc:
            self.failed.emit(str(exc))


class ModbusSettingsController(IApplicationController):

    def __init__(self, model: ModbusSettingsModel, view: ModbusSettingsView):
        self._model  = model
        self._view   = view
        self._logger = logging.getLogger(self.__class__.__name__)
        # Store (thread, worker) tuples — worker MUST be kept alive here.
        # worker is a local in _run_in_thread; without a strong reference
        # Python GC drops it immediately after the call, killing thread.started.
        self._active: List[Tuple[QThread, _Worker]] = []

        self._view.save_requested.connect(self._on_save)
        self._view.detect_ports_requested.connect(self._on_detect_ports)
        self._view.test_connection_requested.connect(self._on_test_connection)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        config = self._model.load()
        self._view.load_config(config)

    def stop(self) -> None:
        for thread, _ in self._active:
            thread.quit()
            thread.wait()
        self._active.clear()

    # ── Save ─────────────────────────────────────────────────────────────

    def _on_save(self, _values: dict) -> None:
        try:
            self._model.save(self._view.get_values())
            self._logger.info("Modbus config saved")
        except Exception:
            self._logger.exception("Failed to save modbus config")

    # ── Detect ports ──────────────────────────────────────────────────────

    def _on_detect_ports(self) -> None:
        self._view.set_busy(True)
        self._run_in_thread(
            fn       = self._model.detect_ports,
            on_done  = self._on_ports_detected,
            on_error = self._on_detect_failed,
        )

    def _on_ports_detected(self, ports: list) -> None:
        self._logger.info("Detected ports: %s", ports)
        self._view.set_detected_ports(ports)

    def _on_detect_failed(self, msg: str) -> None:
        self._logger.error("Port detection failed: %s", msg)
        self._view.set_detected_ports([])

    # ── Test connection ───────────────────────────────────────────────────

    def _on_test_connection(self) -> None:
        self._view.set_busy(True)
        flat   = self._view.get_values()
        config = self._model.config_from_flat(flat)
        self._run_in_thread(
            fn       = lambda: self._model.test_connection(config),
            on_done  = lambda ok: self._on_test_done(ok, config.port),
            on_error = self._on_test_failed,
        )

    def _on_test_done(self, success: bool, port: str) -> None:
        self._logger.info("Test connection → success=%s port=%s", success, port)
        self._view.set_connection_result(success, port)

    def _on_test_failed(self, msg: str) -> None:
        self._logger.error("Test connection failed: %s", msg)
        self._view.set_connection_result(False, "")

    # ── Thread helper ─────────────────────────────────────────────────────

    def _run_in_thread(self, fn, on_done, on_error) -> None:
        thread = QThread()
        worker = _Worker(fn)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(on_done)
        worker.failed.connect(on_error)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_thread_finished)

        self._active.append((thread, worker))   # ← strong ref keeps worker alive
        thread.start()

    def _on_thread_finished(self) -> None:
        self._active = [(t, w) for t, w in self._active if t.isRunning()]
