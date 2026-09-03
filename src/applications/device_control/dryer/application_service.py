from __future__ import annotations

from enum import Enum

from src.applications.device_control.dryer.service import IDryerControlService
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
from src.engine.hardware.dryer.dryer_controller import DryerController
from src.engine.hardware.dryer.interfaces.i_dryer_service import IDryerService
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_state import DryerState
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData
from src.engine.hardware.dryer.models.dryer_modbus_registers import DryerRegisterMap
from src.engine.hardware.peripherals import PeripheralConfig
from src.engine.repositories.interfaces.i_settings_service import ISettingsService


class DryerControlService(IDryerControlService):
    """Persists dryer defaults and builds controllers from current system settings."""

    def __init__(
        self,
        settings_service: ISettingsService,
        dryer_config_key: Enum,
        modbus_config_key: Enum,
        peripherals_config_key: Enum,
        live_controller: IDryerService | None = None,
    ) -> None:
        self._settings = settings_service
        self._dryer_config_key = dryer_config_key
        self._modbus_config_key = modbus_config_key
        self._peripherals_config_key = peripherals_config_key
        self._live_controller = live_controller

    def load_config(self) -> DryerConfig:
        config = self._settings.get(self._dryer_config_key)
        if not isinstance(config, DryerConfig):
            raise TypeError("Dryer settings are unavailable")
        return config

    def save_config(self, config: DryerConfig) -> None:
        self._settings.save(self._dryer_config_key, config)
        if self._live_controller is not None:
            self._live_controller.update_config(config)

    def get_state(self, config: DryerConfig) -> DryerState:
        return self._controller_for(config).get_state()

    def move_servos(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._controller_for(config).move_servos(data)

    def open_plate(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._controller_for(config).open_plate(data)

    def close_plate(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._controller_for(config).close_plate(data)

    def next_position(self, config: DryerConfig, data: DryerWriteData) -> bool:
        return self._controller_for(config).next_position(data)

    def _controller_for(self, config: DryerConfig):
        if self._live_controller is not None:
            self._live_controller.update_config(config)
            return self._live_controller
        return self._build_controller(config)

    def _build_controller(self, config: DryerConfig) -> DryerController:
        modbus = self._settings.get(self._modbus_config_key)
        if not isinstance(modbus, ModbusConfig):
            raise TypeError("Modbus settings are unavailable")
        binding = self._dryer_binding()
        slave_name = modbus.find_slave_name(binding.slave_id)
        transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus, slave_name)
        register_map = DryerRegisterMap.from_mapping({**binding.inputs, **binding.outputs})
        return DryerController(
            transport,
            config,
            register_map,
            commands=binding.commands,
            statuses=binding.statuses,
        )  # type: ignore[arg-type]

    def _peripherals(self) -> PeripheralConfig:
        peripherals = self._settings.get(self._peripherals_config_key)
        if not isinstance(peripherals, PeripheralConfig):
            raise TypeError("Peripheral settings are unavailable")
        return peripherals

    def _dryer_binding(self):
        peripherals = self._peripherals()
        binding = peripherals.get("dryer")
        if binding is None:
            raise ValueError("Dryer peripheral is unavailable or disabled")
        return binding
