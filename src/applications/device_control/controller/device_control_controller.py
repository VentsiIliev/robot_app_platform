from __future__ import annotations
from functools import partial
import logging

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.applications.device_control.model.device_control_model import DeviceControlModel
from src.applications.device_control.view.device_control_view import DeviceControlView


class DeviceControlController(IApplicationController, BackgroundWorker):

    def __init__(self, model: DeviceControlModel, view: DeviceControlView) -> None:
        BackgroundWorker.__init__(self)
        self._model  = model
        self._view   = view
        self._logger = logging.getLogger(self.__class__.__name__)

        view.laser_on_requested.connect(self._on_laser_on)
        view.laser_off_requested.connect(self._on_laser_off)
        view.vacuum_pump_on_requested.connect(self._on_vacuum_pump_on)
        view.vacuum_pump_off_requested.connect(self._on_vacuum_pump_off)
        view.motor_on_requested.connect(self._on_motor_on)
        view.motor_off_requested.connect(self._on_motor_off)
        view.generator_on_requested.connect(self._on_generator_on)
        view.generator_off_requested.connect(self._on_generator_off)

    def load(self) -> None:
        motors = self._model.get_motors()
        self._view.setup_motors(motors)

        self._view.set_device_available("laser",       self._model.is_laser_available())
        self._view.set_device_available("vacuum_pump", self._model.is_vacuum_pump_available())
        self._view.set_device_available("generator",   self._model.is_generator_available())

        if self._model.is_motor_available():
            self._run(self._model.get_motor_health_snapshot, self._on_motor_health_snapshot)
        else:
            self._view.set_motors_available(False)

    def _on_motor_health_snapshot(self, snapshot: dict) -> None:
        for address, healthy in snapshot.items():
            self._view.set_device_available(f"motor_{address}", healthy)

    def stop(self) -> None:
        self._stop_threads()

    # ── Laser ─────────────────────────────────────────────────────────

    def _on_laser_on(self) -> None:
        self._run(self._model.laser_on, self._on_laser_on_done)

    def _on_laser_off(self) -> None:
        self._run(self._model.laser_off, self._on_laser_off_done)

    def _on_laser_on_done(self, _) -> None:
        self._view.set_device_active("laser", True)

    def _on_laser_off_done(self, _) -> None:
        self._view.set_device_active("laser", False)

    # ── Vacuum pump ───────────────────────────────────────────────────

    def _on_vacuum_pump_on(self) -> None:
        self._run(self._model.vacuum_pump_on, self._on_vacuum_pump_on_done)

    def _on_vacuum_pump_off(self) -> None:
        self._run(self._model.vacuum_pump_off, self._on_vacuum_pump_off_done)

    def _on_vacuum_pump_on_done(self, ok: bool) -> None:
        self._view.set_device_active("vacuum_pump", ok)

    def _on_vacuum_pump_off_done(self, ok: bool) -> None:
        self._view.set_device_active("vacuum_pump", not ok)

    # ── Motor ─────────────────────────────────────────────────────────

    def _on_motor_on(self, address: int) -> None:
        self._run(
            partial(self._model.motor_on, address),
            partial(self._on_motor_on_done, address),
        )

    def _on_motor_off(self, address: int) -> None:
        self._run(
            partial(self._model.motor_off, address),
            partial(self._on_motor_off_done, address),
        )

    def _on_motor_on_done(self, address: int, ok: bool) -> None:
        self._view.set_device_active(f"motor_{address}", ok)

    def _on_motor_off_done(self, address: int, ok: bool) -> None:
        self._view.set_device_active(f"motor_{address}", not ok)

    # ── Generator ─────────────────────────────────────────────────────

    def _on_generator_on(self) -> None:
        self._run(self._model.generator_on, self._on_generator_on_done)

    def _on_generator_off(self) -> None:
        self._run(self._model.generator_off, self._on_generator_off_done)

    def _on_generator_on_done(self, ok: bool) -> None:
        self._view.set_device_active("generator", ok)

    def _on_generator_off_done(self, ok: bool) -> None:
        self._view.set_device_active("generator", not ok)

    # ── Helpers ───────────────────────────────────────────────────────

    def _run(self, fn, on_done) -> None:
        self._run_in_thread(fn=fn, on_done=on_done)
