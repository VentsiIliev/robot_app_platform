import logging
from typing import List, Optional

from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
from src.engine.hardware.communication.modbus.modbus import ModbusConfig, ModbusSlaveConfig
from src.applications.base.i_application_model import IApplicationModel
from src.applications.modbus_settings.model.mapper import ModbusSettingsMapper
from src.applications.modbus_settings.service.i_modbus_settings_service import IModbusSettingsService


class ModbusSettingsModel(IApplicationModel):

    def __init__(self, settings_service: IModbusSettingsService, action_service: IModbusActionService):
        self._settings = settings_service
        self._actions  = action_service
        self._config: Optional[ModbusConfig] = None
        self._logger   = logging.getLogger(self.__class__.__name__)

    def load(self) -> ModbusConfig:
        self._config = self._settings.load_config()
        self._logger.debug("Modbus config loaded")
        return self._config

    def save(self, flat: dict, **kwargs) -> None:
        base    = self._config if self._config is not None else ModbusConfig()
        updated = ModbusSettingsMapper.from_flat_dict(flat, base)
        self._settings.save_config(updated)
        self._config = updated
        self._logger.info("Modbus config saved")

    def save_profiles(self, profiles: dict[str, dict]) -> None:
        config = self._config if self._config is not None else ModbusConfig()
        existing_profiles = {
            name: config.get_profile(name)
            for name in config.profile_names()
        }
        config.devices = {}
        config.profiles = {}
        for name, flat in profiles.items():
            base = existing_profiles.get(name, existing_profiles['default'])
            config.set_profile(name, ModbusSettingsMapper.device_from_flat_dict(flat, base))
        self._settings.save_config(config)
        self._config = config
        self._logger.info("Modbus device profiles saved: %s", list(profiles))

    def save_all(self, profiles: dict[str, dict], slaves: dict[str, dict]) -> None:
        """Persist profiles and slave assignments as one configuration snapshot."""
        config = self._config if self._config is not None else ModbusConfig()
        profile_names = {"default", *profiles}
        invalid = {
            name: values.get("profile_name")
            for name, values in slaves.items()
            if values.get("profile_name", "default") not in profile_names
        }
        if invalid:
            raise ValueError(f"Slaves reference unknown profiles: {invalid}")

        existing_profiles = {
            name: config.get_profile(name)
            for name in config.profile_names()
        }
        config.devices = {}
        config.profiles = {}
        for name, flat in profiles.items():
            base = existing_profiles.get(name, existing_profiles['default'])
            config.set_profile(name, ModbusSettingsMapper.device_from_flat_dict(flat, base))

        existing_slaves = {
            name: config.get_slave(name)
            for name in config.slave_names()
            if name != "default"
        }
        config.slaves = {}
        for name, values in slaves.items():
            current = existing_slaves.get(name, ModbusSlaveConfig())
            config.set_slave(name, ModbusSlaveConfig(
                slave_address=int(values.get("slave_address", current.slave_address)),
                profile_name=str(values.get("profile_name", current.profile_name)),
                transport_type=str(values.get("transport_type", current.transport_type)),
                max_retries=int(values.get("max_retries", current.max_retries)),
            ))

        self._settings.save_config(config)
        self._config = config
        self._logger.info(
            "Modbus config saved: profiles=%s slaves=%s",
            list(profiles), list(slaves),
        )

    def save_slaves(self, slaves: dict[str, dict]) -> None:
        config = self._config if self._config is not None else ModbusConfig()
        existing_slaves = {
            name: config.get_slave(name)
            for name in config.slave_names()
            if name != "default"
        }
        config.slaves = {}
        for name, values in slaves.items():
            current = existing_slaves.get(name, ModbusSlaveConfig())
            config.set_slave(name, ModbusSlaveConfig(
                slave_address=int(values.get("slave_address", current.slave_address)),
                profile_name=str(values.get("profile_name", current.profile_name)),
                transport_type=str(values.get("transport_type", current.transport_type)),
                max_retries=int(values.get("max_retries", current.max_retries)),
            ))
        self._settings.save_config(config)
        self._config = config
        self._logger.info("Modbus slaves saved: %s", list(slaves))

    def detect_ports(self) -> List[str]:
        return self._actions.detect_ports()

    def test_connection(self, config: ModbusConfig) -> bool:
        return self._actions.test_connection(config)

    def grant_serial_port_permissions(self) -> List[str]:
        return self._actions.grant_serial_port_permissions()

    def config_from_flat(self, flat: dict) -> ModbusConfig:
        base = self._config if self._config is not None else ModbusConfig()
        return ModbusSettingsMapper.from_flat_dict(flat, base)
