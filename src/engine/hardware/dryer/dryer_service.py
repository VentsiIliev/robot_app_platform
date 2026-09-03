from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from src.engine.hardware.dryer.interfaces.i_dryer_controller import IDryerController
from src.engine.hardware.dryer.interfaces.i_dryer_service import IDryerService
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_state import DryerState
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData


class DryerService(IDryerService):
    """Keeps a stable service reference while dryer hardware is cycled."""

    def __init__(
        self,
        controller_factory: Callable[[DryerConfig], IDryerController],
        config: DryerConfig,
    ) -> None:
        self._controller_factory = controller_factory
        self._config = config
        self._controller: IDryerController | None = None
        self._initializing_controller: IDryerController | None = None
        self._initialization_thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._generation = 0
        self._enabled_requested = False
        self._last_error: str | None = None
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def enable(self) -> bool:
        generation = self._begin_enable()
        return self._initialize(generation)

    def enable_async(self) -> bool:
        """Schedule initialization and return as soon as the worker starts."""
        generation = self._begin_enable()
        thread = threading.Thread(
            target=self._initialize,
            args=(generation,),
            name="DryerInitialization",
            daemon=True,
        )
        with self._lock:
            if generation != self._generation or not self._enabled_requested:
                return False
            self._initialization_thread = thread
        thread.start()
        self._logger.info("Dryer initialization started asynchronously")
        return True

    def _begin_enable(self) -> int:
        self.disable()
        with self._lock:
            self._generation += 1
            self._enabled_requested = True
            self._last_error = "Dryer initialization is in progress"
            return self._generation

    def _initialize(self, generation: int) -> bool:
        controller: IDryerController | None = None
        try:
            controller = self._controller_factory(self._config)
            with self._lock:
                if generation != self._generation or not self._enabled_requested:
                    controller.shutdown()
                    return False
                self._initializing_controller = controller
            initialized = controller.initialize()
            with self._lock:
                if generation != self._generation or not self._enabled_requested:
                    return False
            if not initialized:
                raise RuntimeError("Dryer initialization or next-position verification failed")
            with self._lock:
                if generation != self._generation or not self._enabled_requested:
                    return False
                self._controller = controller
                self._initializing_controller = None
                self._last_error = None
            self._logger.info("Dryer initialization completed successfully")
            return True
        except Exception as exc:
            with self._lock:
                owns_controller = self._initializing_controller is controller
                if owns_controller:
                    self._initializing_controller = None
                if generation == self._generation:
                    self._enabled_requested = False
                    self._last_error = str(exc)
            if controller is not None and owns_controller:
                try:
                    controller.shutdown()
                except Exception:
                    self._logger.exception("Failed to clean up dryer after initialization error")
            self._logger.exception("Dryer could not be enabled")
            return False
        finally:
            with self._lock:
                if self._initialization_thread is threading.current_thread():
                    self._initialization_thread = None

    def disable(self) -> None:
        with self._lock:
            self._generation += 1
            self._enabled_requested = False
            controllers = tuple(
                controller
                for controller in (self._controller, self._initializing_controller)
                if controller is not None
            )
            self._controller = None
            self._initializing_controller = None
        for controller in dict.fromkeys(controllers):
            try:
                controller.shutdown()
            except Exception:
                self._logger.exception("Dryer shutdown failed")

    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled_requested

    def is_healthy(self) -> bool:
        with self._lock:
            return self._controller is not None and self._last_error is None

    def initialize(self) -> bool:
        return self.enable()

    def shutdown(self) -> None:
        self.disable()

    def disconnect(self) -> None:
        self.disable()

    def update_config(self, config: DryerConfig) -> None:
        with self._lock:
            self._config = config
            controller = self._controller
        if controller is not None:
            controller.update_config(config)

    def write_data(self, data: DryerWriteData) -> bool:
        return self._call("write_data", data)

    def get_state(self) -> DryerState:
        with self._lock:
            controller = self._controller
        if controller is None:
            return DryerState(is_healthy=False, communication_errors=[self._unavailable_error()])
        return controller.get_state()

    def move_servos(self, data: DryerWriteData | None = None) -> bool:
        return self._call("move_servos", data)

    def eject(self, data: DryerWriteData | None = None) -> bool:
        return self._call("eject", data)

    def open_plate(self, data: DryerWriteData | None = None) -> bool:
        return self._call("open_plate", data)

    def close_plate(self, data: DryerWriteData | None = None) -> bool:
        return self._call("close_plate", data)

    def next_position(self, data: DryerWriteData | None = None) -> bool:
        return self._call("next_position", data)

    def execute_command(self, command: int, data: DryerWriteData | None = None) -> bool:
        with self._lock:
            controller = self._controller
        if controller is None:
            error = self._unavailable_error()
            self._logger.error(error)
            return False
        return bool(controller.execute_command(int(command), data))

    def _call(self, method_name: str, data: DryerWriteData | None) -> bool:
        with self._lock:
            controller = self._controller
        if controller is None:
            error = self._unavailable_error()
            self._logger.error(error)
            return False
        return bool(getattr(controller, method_name)(data))

    def _unavailable_error(self) -> str:
        with self._lock:
            return self._last_error or "Dryer is disabled or unavailable"
