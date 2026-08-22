from __future__ import annotations

import logging
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
        self._last_error: str | None = None
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def enable(self) -> bool:
        self.disable()
        controller: IDryerController | None = None
        try:
            controller = self._controller_factory(self._config)
            if not controller.initialize():
                raise RuntimeError("Dryer initialization write failed")
            self._controller = controller
            self._last_error = None
            return True
        except Exception as exc:
            if controller is not None:
                try:
                    controller.shutdown()
                except Exception:
                    self._logger.exception("Failed to clean up dryer after initialization error")
            self._last_error = str(exc)
            self._logger.exception("Dryer could not be enabled")
            self._controller = None
            return False

    def disable(self) -> None:
        controller, self._controller = self._controller, None
        if controller is not None:
            try:
                controller.shutdown()
            except Exception:
                self._logger.exception("Dryer shutdown failed")

    def is_enabled(self) -> bool:
        return self._controller is not None

    def is_healthy(self) -> bool:
        return self._controller is not None and self._last_error is None

    def initialize(self) -> bool:
        return self.enable()

    def shutdown(self) -> None:
        self.disable()

    def disconnect(self) -> None:
        self.disable()

    def update_config(self, config: DryerConfig) -> None:
        self._config = config
        if self._controller is not None:
            self._controller.update_config(config)

    def write_data(self, data: DryerWriteData) -> bool:
        return self._call("write_data", data)

    def get_state(self) -> DryerState:
        if self._controller is None:
            return DryerState(is_healthy=False, communication_errors=[self._unavailable_error()])
        return self._controller.get_state()

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
        if self._controller is None:
            self._last_error = self._unavailable_error()
            self._logger.error(self._last_error)
            return False
        return bool(self._controller.execute_command(int(command), data))

    def _call(self, method_name: str, data: DryerWriteData | None) -> bool:
        if self._controller is None:
            self._last_error = self._unavailable_error()
            self._logger.error(self._last_error)
            return False
        return bool(getattr(self._controller, method_name)(data))

    def _unavailable_error(self) -> str:
        return self._last_error or "Dryer is disabled or unavailable"
