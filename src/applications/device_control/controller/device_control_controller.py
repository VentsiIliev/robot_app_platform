import logging
from typing import List, Tuple

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.device_control.model.device_control_model import DeviceControlModel
from src.applications.device_control.view.device_control_view import DeviceControlView


class _Worker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        self.finished.emit(self._fn())


class DeviceControlController(IApplicationController):

    def __init__(self, model: DeviceControlModel, view: DeviceControlView) -> None:
        self._model  = model
        self._view   = view
        self._logger = logging.getLogger(self.__class__.__name__)
        self._active: List[Tuple[QThread, _Worker]] = []

        self._view.laser_on_requested.connect(self._on_laser_on)
        self._view.laser_off_requested.connect(self._on_laser_off)
        self._view.vacuum_pump_on_requested.connect(self._on_vacuum_pump_on)
        self._view.vacuum_pump_off_requested.connect(self._on_vacuum_pump_off)
        self._view.motor_on_requested.connect(self._on_motor_on)
        self._view.motor_off_requested.connect(self._on_motor_off)
        self._view.generator_on_requested.connect(self._on_generator_on)
        self._view.generator_off_requested.connect(self._on_generator_off)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        self._model.load()
        self._view.set_device_available("laser",       self._model.is_laser_available())
        self._view.set_device_available("vacuum_pump", self._model.is_vacuum_pump_available())
        self._view.set_device_available("motor",       self._model.is_motor_available())
        self._view.set_device_available("generator",   self._model.is_generator_available())

    def stop(self) -> None:
        for thread, _ in self._active:
            thread.quit()
            thread.wait(3000)
        self._active.clear()

    # ── Internal thread runner ────────────────────────────────────────

    def _run(self, fn, on_done):
        thread = QThread()
        worker = _Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_done)
        worker.finished.connect(thread.quit)
        self._active.append((thread, worker))
        thread.start()

    def _cleanup_threads(self, _=None):
        self._active = [(t, w) for t, w in self._active if t.isRunning()]

    # ── Laser ─────────────────────────────────────────────────────────

    def _on_laser_on(self) -> None:
        self._run(self._model.laser_on, self._on_laser_on_done)

    def _on_laser_off(self) -> None:
        self._run(self._model.laser_off, self._on_laser_off_done)

    def _on_laser_on_done(self, _) -> None:
        self._cleanup_threads()
        self._view.set_device_active("laser", True)

    def _on_laser_off_done(self, _) -> None:
        self._cleanup_threads()
        self._view.set_device_active("laser", False)

    # ── Vacuum pump ───────────────────────────────────────────────────

    def _on_vacuum_pump_on(self) -> None:
        self._run(self._model.vacuum_pump_on, self._on_vacuum_pump_on_done)

    def _on_vacuum_pump_off(self) -> None:
        self._run(self._model.vacuum_pump_off, self._on_vacuum_pump_off_done)

    def _on_vacuum_pump_on_done(self, ok) -> None:
        self._cleanup_threads()
        self._view.set_device_active("vacuum_pump", bool(ok))

    def _on_vacuum_pump_off_done(self, _) -> None:
        self._cleanup_threads()
        self._view.set_device_active("vacuum_pump", False)

    # ── Motor ─────────────────────────────────────────────────────────

    def _on_motor_on(self) -> None:
        self._run(self._model.motor_on, self._on_motor_on_done)

    def _on_motor_off(self) -> None:
        self._run(self._model.motor_off, self._on_motor_off_done)

    def _on_motor_on_done(self, ok) -> None:
        self._cleanup_threads()
        self._view.set_device_active("motor", bool(ok))

    def _on_motor_off_done(self, _) -> None:
        self._cleanup_threads()
        self._view.set_device_active("motor", False)

    # ── Generator ─────────────────────────────────────────────────────

    def _on_generator_on(self) -> None:
        self._run(self._model.generator_on, self._on_generator_on_done)

    def _on_generator_off(self) -> None:
        self._run(self._model.generator_off, self._on_generator_off_done)

    def _on_generator_on_done(self, ok) -> None:
        self._cleanup_threads()
        self._view.set_device_active("generator", bool(ok))

    def _on_generator_off_done(self, _) -> None:
        self._cleanup_threads()
        self._view.set_device_active("generator", False)
