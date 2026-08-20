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
from src.engine.hardware.dryer.modbus.modbus_plate_dryer_factory import (
    build_modbus_plate_dryer_controller,
)
from src.engine.hardware.peripherals import PeripheralBinding, PeripheralConfig
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
        peripherals_config_key: Enum | None = None,
        controller_factory: Callable[[ModbusConfig, DryerConfig], IDryerController] = build_modbus_dryer_controller,
    ) -> None:
        self._settings = settings_service
        self._dryer_config_key = dryer_config_key
        self._modbus_config_key = modbus_config_key
        self._peripherals_config_key = peripherals_config_key
        self._controller_factory = controller_factory
        self._logger = logging.getLogger(self.__class__.__name__)

    def load_config(self) -> DryerConfig:
        config = self._settings.get(self._dryer_config_key)
        if self._peripherals_config_key is None:
            return config
        peripherals = self._settings.get(self._peripherals_config_key)
        if not isinstance(peripherals, PeripheralConfig):
            return config
        binding = peripherals.get("dryer")
        if binding is None:
            return config
        values = config.to_dict()
        values["plate_register"] = int(binding.outputs.get("plate", config.plate_register))
        values["open_plate_value"] = int(binding.commands.get("open_plate", config.open_plate_value))
        values["close_plate_value"] = int(binding.commands.get("close_plate", config.close_plate_value))
        return DryerConfig.from_dict(values)

    def save_config(self, config: DryerConfig) -> None:
        self._settings.save(self._dryer_config_key, config)
        if self._peripherals_config_key is None:
            return
        peripherals = self._settings.get(self._peripherals_config_key)
        if not isinstance(peripherals, PeripheralConfig):
            return
        current = peripherals.peripherals.get("dryer")
        if current is None:
            return
        updated = PeripheralBinding(
            enabled=current.enabled,
            slave_id=current.slave_id,
            inputs=current.inputs,
            outputs={**current.outputs, "plate": str(config.plate_register)},
            commands={
                **current.commands,
                "open_plate": config.open_plate_value,
                "close_plate": config.close_plate_value,
            },
        )
        self._settings.save(
            self._peripherals_config_key,
            PeripheralConfig(peripherals={**peripherals.peripherals, "dryer": updated}),
        )

    def get_state(self, config: DryerConfig) -> DryerState:
        return self._build_controller(config).get_state()

    def move_servos(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._build_controller(config).move_servos(data)

    def open_plate(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._build_controller(config).open_plate(data)

    def close_plate(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._build_controller(config).close_plate(data)

    def next_position(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._build_controller(config).next_position(data)

    def _build_controller(self, dryer_config: DryerConfig) -> IDryerController:
        modbus_config = self._settings.get(self._modbus_config_key)
        if self._peripherals_config_key is not None:
            peripherals = self._settings.get(self._peripherals_config_key)
            if isinstance(peripherals, PeripheralConfig):
                binding = peripherals.get("dryer")
                if binding is not None:
                    slave_name = modbus_config.find_slave_name(binding.slave_id)
                    plate_register = int(
                        binding.outputs.get("plate", dryer_config.plate_register)
                    )
                    open_value = int(
                        binding.commands.get("open_plate", dryer_config.open_plate_value)
                    )
                    close_value = int(
                        binding.commands.get("close_plate", dryer_config.close_plate_value)
                    )
                    connection = modbus_config.get_connection(slave_name)
                    slave = modbus_config.get_slave(slave_name)
                    self._logger.debug(
                        "Building configured dryer controller peripheral=dryer "
                        "slave_name=%s slave_id=%d profile=%s transport=%s "
                        "register=%d port=%s serial=%d,%d%s%d timeout=%s",
                        slave_name,
                        binding.slave_id,
                        slave.profile_name,
                        slave.transport_type,
                        plate_register,
                        connection.port,
                        connection.baudrate,
                        connection.bytesize,
                        connection.parity,
                        connection.stopbits,
                        connection.timeout,
                    )
                    return build_modbus_plate_dryer_controller(
                        modbus_config=modbus_config,
                        slave_name=slave_name,
                        plate_register=plate_register,
                        open_value=open_value,
                        close_value=close_value,
                    )
        self._logger.debug(
            "Building dryer controller port=%s slave=%s baud=%s",
            modbus_config.port,
            modbus_config.slave_address,
            modbus_config.baudrate,
        )
        return self._controller_factory(modbus_config, dryer_config)
