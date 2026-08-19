from __future__ import annotations

import logging
from enum import Enum
from typing import Callable

from src.applications.dryer_settings.service.i_dryer_settings_service import IDryerSettingsService
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.dryer.interfaces.i_dryer_controller import IDryerController
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_state import DryerState
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData
from src.engine.hardware.dryer.modbus.modbus_dryer_factory import build_modbus_dryer_controller
from src.engine.repositories.interfaces.i_settings_service import ISettingsService


class DryerSettingsApplicationService(IDryerSettingsService):
    """
    Runtime adapter for dryer settings screens.

    It reads the robot system's current Modbus settings for each action so
    settings edits outside this screen are respected without keeping stale
    Modbus transport objects alive.
    """

    def __init__(
        self,
        settings_service: ISettingsService,
        dryer_config_key: Enum,
        modbus_config_key: Enum,
        controller_factory: Callable[[ModbusConfig, DryerConfig], IDryerController] = build_modbus_dryer_controller,
    ) -> None:
        self._settings = settings_service
        self._dryer_config_key = dryer_config_key
        self._modbus_config_key = modbus_config_key
        self._controller_factory = controller_factory
        self._logger = logging.getLogger(self.__class__.__name__)

    def load_config(self) -> DryerConfig:
        return self._settings.get(self._dryer_config_key)

    def save_config(self, config: DryerConfig) -> None:
        self._settings.save(self._dryer_config_key, config)

    def get_state(self, config: DryerConfig) -> DryerState:
        return self._build_controller(config).get_state()

    def move_servos(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._build_controller(config).move_servos(data)

    def open_plate(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._build_controller(config).open_plate(data)

    def next_position(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._build_controller(config).next_position(data)

    def _build_controller(self, dryer_config: DryerConfig) -> IDryerController:
        modbus_config = self._settings.get(self._modbus_config_key)
        self._logger.debug(
            "Building dryer controller port=%s slave=%s baud=%s",
            modbus_config.port,
            modbus_config.slave_address,
            modbus_config.baudrate,
        )
        return self._controller_factory(modbus_config, dryer_config)
