from __future__ import annotations
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
import logging

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.applications.device_control.model.device_control_model import DeviceControlModel
from src.applications.device_control.view.device_control_view import DeviceControlView


class _DeviceUiRelay(QObject):
    action_finished = pyqtSignal(str, bool)
    enabled_finished = pyqtSignal(str, bool)
    states_finished = pyqtSignal(object)

    def __init__(self, on_action_finished, on_states_finished) -> None:
        super().__init__()
        self._on_action_finished = on_action_finished
        self._on_states_finished = on_states_finished
        self.action_finished.connect(self._dispatch_action_finished)
        self.states_finished.connect(self._dispatch_states_finished)

    @pyqtSlot(str, bool)
    def _dispatch_action_finished(self, device_key: str, ok: bool) -> None:
        self._on_action_finished(device_key, ok)

    @pyqtSlot(object)
    def _dispatch_states_finished(self, states: object) -> None:
        self._on_states_finished(states)


class DeviceControlController(IApplicationController, BackgroundWorker):
    _FAILED_ENABLE_ROLLBACK_MS = 500

    def __init__(
        self,
        model: DeviceControlModel,
        view: DeviceControlView,
        dryer_view=None,
        dryer_controller=None,
    ) -> None:
        BackgroundWorker.__init__(self)
        self._model  = model
        self._view   = view
        self._logger = logging.getLogger(self.__class__.__name__)
        self._dryer_view = dryer_view
        self._dryer_controller = dryer_controller
        self._device_poll_in_flight = False
        self._device_action_in_flight = False
        self._pending_device_enabled: dict[str, bool] = {}
        self._device_stopped = False
        self._device_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="DeviceControlIO",
        )
        self._device_relay = _DeviceUiRelay(
            self._on_device_action_done,
            self._on_device_states_read,
        )
        self._device_relay.enabled_finished.connect(self._on_device_enabled_done)

        view.laser_on_requested.connect(self._on_laser_on)
        view.laser_off_requested.connect(self._on_laser_off)
        view.vacuum_pump_on_requested.connect(self._on_vacuum_pump_on)
        view.vacuum_pump_off_requested.connect(self._on_vacuum_pump_off)
        view.motor_on_requested.connect(self._on_motor_on)
        view.motor_off_requested.connect(self._on_motor_off)
        view.generator_on_requested.connect(self._on_generator_on)
        view.generator_off_requested.connect(self._on_generator_off)
        view.device_action_requested.connect(self._on_device_action)
        view.device_enabled_requested.connect(self._on_device_enabled)

    def load(self) -> None:
        self._view.setup_devices(self._model.get_devices())
        if self._dryer_view is not None:
            self._view.set_device_panel("dryer", self._dryer_view)
        if self._dryer_controller is not None:
            self._dryer_controller.load()
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
        self._device_stopped = True
        self._device_executor.shutdown(wait=False, cancel_futures=True)
        if self._dryer_controller is not None:
            self._dryer_controller.stop()
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

    # ── Configuration-driven devices ─────────────────────────────────

    def _on_device_action(self, device_key: str, action: str) -> None:
        if self._device_stopped or self._device_action_in_flight:
            self._logger.debug("Ignoring overlapping device action %s.%s", device_key, action)
            return
        self._device_action_in_flight = True
        self._view.set_device_busy(device_key, True)
        self._logger.info("Device action started: %s.%s", device_key, action)
        future = self._device_executor.submit(
            self._model.execute_device_action,
            device_key,
            action,
        )
        future.add_done_callback(partial(self._emit_device_action_result, device_key))

    def _emit_device_action_result(self, device_key: str, future: Future) -> None:
        if self._device_stopped:
            return
        try:
            ok = bool(future.result())
        except Exception:
            self._logger.exception("Device action worker failed: %s", device_key)
            ok = False
        self._device_relay.action_finished.emit(device_key, ok)

    def _on_device_action_done(self, device_key: str, ok: bool) -> None:
        self._device_action_in_flight = False
        self._view.set_device_busy(device_key, False)
        self._view.set_device_action_result(device_key, ok)
        self._logger.info("Device action completed: %s ok=%s", device_key, ok)
        if not ok:
            self._view.set_device_state(device_key, {"healthy": False, "error": "Command failed"})
        self._on_device_state_poll(device_key)

    def _on_device_enabled(self, device_key: str, enabled: bool) -> None:
        if self._device_stopped or self._device_action_in_flight:
            self._view.set_device_enabled(device_key, self._model.is_device_enabled(device_key))
            return
        self._device_action_in_flight = True
        self._pending_device_enabled[device_key] = bool(enabled)
        # Reflect the user's requested state immediately. The completion path
        # reconciles this optimistic state with the device's actual state and
        # rolls it back when enabling fails.
        self._view.set_device_enabled(device_key, bool(enabled))
        self._view.set_device_busy(device_key, True)
        future = self._device_executor.submit(
            self._model.set_device_enabled,
            device_key,
            enabled,
        )
        future.add_done_callback(partial(self._emit_device_enabled_result, device_key))

    def _emit_device_enabled_result(self, device_key: str, future: Future) -> None:
        if self._device_stopped:
            return
        try:
            future.result()
            enabled = self._model.is_device_enabled(device_key)
        except Exception:
            self._logger.exception("Device lifecycle worker failed: %s", device_key)
            enabled = False
        self._device_relay.enabled_finished.emit(device_key, enabled)

    def _on_device_enabled_done(self, device_key: str, enabled: bool) -> None:
        requested = self._pending_device_enabled.pop(device_key, enabled)
        if requested and not enabled:
            QTimer.singleShot(
                self._FAILED_ENABLE_ROLLBACK_MS,
                partial(self._finish_device_enabled, device_key, enabled, requested),
            )
            return
        self._finish_device_enabled(device_key, enabled, requested)

    def _finish_device_enabled(
        self,
        device_key: str,
        enabled: bool,
        requested: bool,
    ) -> None:
        if self._device_stopped:
            return
        self._device_action_in_flight = False
        self._view.set_device_busy(device_key, False)
        self._view.set_device_enabled(device_key, enabled)
        self._view.set_device_action_result(device_key, enabled == requested)
        self._view.set_device_state(
            device_key,
            {"enabled": enabled, "healthy": None},
        )
        if enabled:
            self._on_device_state_poll()

    def _on_device_state_poll(self, device_key: str | None = None) -> None:
        if self._device_stopped or self._device_poll_in_flight or self._device_action_in_flight:
            return
        devices = self._model.get_devices()
        if not devices:
            return
        device_keys = (
            [device_key]
            if device_key is not None
            else [device.key for device in devices]
        )
        self._device_poll_in_flight = True
        future = self._device_executor.submit(self._read_device_states, device_keys)
        future.add_done_callback(self._emit_device_states_result)

    def _emit_device_states_result(self, future: Future) -> None:
        if self._device_stopped:
            return
        try:
            states = future.result()
        except Exception:
            self._logger.exception("Device state worker failed")
            states = {}
        self._device_relay.states_finished.emit(states)

    def _read_device_states(self, device_keys: list[str]) -> dict[str, dict[str, object]]:
        return {
            device_key: dict(self._model.read_device_state(device_key))
            for device_key in device_keys
        }

    def _on_device_states_read(self, states: dict[str, dict[str, object]]) -> None:
        self._device_poll_in_flight = False
        for device_key, state in states.items():
            self._view.set_device_state(device_key, state)

    # ── Helpers ───────────────────────────────────────────────────────

    def _run(self, fn, on_done) -> None:
        self._run_in_thread(fn=fn, on_done=on_done)
