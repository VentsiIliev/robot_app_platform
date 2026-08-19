from dataclasses import dataclass, asdict, field
from copy import deepcopy
from typing import Any, Dict

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


@dataclass
class ModbusDeviceConfig:
    """Complete serial and slave configuration for one Modbus device."""

    port: str = 'COM5'
    baudrate: int = 115200
    bytesize: int = 8
    stopbits: int = 1
    parity: str = 'N'
    timeout: float = 0.01
    slave_address: int = 10
    max_retries: int = 30

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModbusDeviceConfig':
        return cls(
            port=data.get('port', 'COM5'),
            baudrate=int(data.get('baudrate', 115200)),
            bytesize=int(data.get('bytesize', 8)),
            stopbits=int(data.get('stopbits', 1)),
            parity=str(data.get('parity', 'N')),
            timeout=float(data.get('timeout', 0.01)),
            slave_address=int(data.get('slave_address', 10)),
            max_retries=int(data.get('max_retries', 30)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModbusSlaveConfig:
    """A Modbus slave ID assigned to a serial connection profile."""

    slave_address: int = 10
    profile_name: str = 'default'
    transport_type: str = 'modbus_register'
    max_retries: int = 30

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModbusSlaveConfig':
        return cls(
            slave_address=int(data.get('slave_address', 10)),
            profile_name=str(data.get('profile_name', 'default')),
            transport_type=str(data.get('transport_type', 'modbus_register')),
            max_retries=int(data.get('max_retries', 30)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModbusConfig(ModbusDeviceConfig):
    """Legacy default profile plus optional named device profiles.

    The inherited fields remain the default profile for existing consumers.
    ``devices`` contains additional profiles keyed by a stable device name.
    """

    devices: Dict[str, ModbusDeviceConfig] = field(default_factory=dict)
    profiles: Dict[str, ModbusDeviceConfig] = field(default_factory=dict)
    slaves: Dict[str, ModbusSlaveConfig] = field(default_factory=dict)

    port: str = 'COM5'
    baudrate: int = 115200
    bytesize: int = 8
    stopbits: int = 1
    parity: str = 'N'
    timeout: float = 0.01
    slave_address: int = 10
    max_retries: int = 30

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModbusConfig':
        devices = {
            str(name): ModbusDeviceConfig.from_dict(profile)
            for name, profile in data.get('devices', {}).items()
        }
        profiles = {
            str(name): ModbusDeviceConfig.from_dict(profile)
            for name, profile in data.get('profiles', {}).items()
        }
        slaves = {
            str(name): ModbusSlaveConfig.from_dict(slave)
            for name, slave in data.get('slaves', {}).items()
        }
        return cls(
            port=data.get('port', 'COM5'),
            baudrate=int(data.get('baudrate', 115200)),
            bytesize=int(data.get('bytesize', 8)),
            stopbits=int(data.get('stopbits', 1)),
            parity=str(data.get('parity', 'N')),
            timeout=float(data.get('timeout', 0.01)),
            slave_address=int(data.get('slave_address', 10)),
            max_retries=int(data.get('max_retries', 30)),
            devices=devices,
            profiles=profiles,
            slaves=slaves,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = {
            'port': self.port,
            'baudrate': self.baudrate,
            'bytesize': self.bytesize,
            'stopbits': self.stopbits,
            'parity': self.parity,
            'timeout': self.timeout,
            'slave_address': self.slave_address,
            'max_retries': self.max_retries,
        }
        if self.devices:
            data['devices'] = {
                name: profile.to_dict() for name, profile in self.devices.items()
            }
        if self.profiles:
            data['profiles'] = {
                name: profile.to_dict() for name, profile in self.profiles.items()
            }
        if self.slaves:
            data['slaves'] = {
                name: slave.to_dict() for name, slave in self.slaves.items()
            }
        return data

    def get_profile(
        self,
        name: str = 'default',
        fallback_to_default: bool = False,
    ) -> ModbusDeviceConfig:
        """Return a copy so callers cannot mutate settings accidentally."""
        if name == 'default':
            return ModbusDeviceConfig(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                stopbits=self.stopbits,
                parity=self.parity,
                timeout=self.timeout,
                slave_address=self.slave_address,
                max_retries=self.max_retries,
            )
        try:
            return deepcopy(self.profiles[name])
        except KeyError as exc:
            if name in self.devices:
                return deepcopy(self.devices[name])
            if fallback_to_default:
                return self.get_profile('default')
            raise KeyError(f"Unknown Modbus device profile: {name}") from exc

    def set_profile(self, name: str, profile: ModbusDeviceConfig) -> None:
        if name == 'default':
            self.port = profile.port
            self.baudrate = profile.baudrate
            self.bytesize = profile.bytesize
            self.stopbits = profile.stopbits
            self.parity = profile.parity
            self.timeout = profile.timeout
            self.slave_address = profile.slave_address
            self.max_retries = profile.max_retries
        else:
            self.profiles[name] = deepcopy(profile)

    def profile_names(self) -> list[str]:
        names = list(self.profiles.keys())
        if not names:
            names = list(self.devices.keys())
        return ['default', *names]

    def slave_names(self) -> list[str]:
        if self.slaves:
            return ['default', *self.slaves.keys()]
        return ['default', *self.devices.keys()]

    def get_slave(self, name: str = 'default') -> ModbusSlaveConfig:
        if name == 'default':
            return ModbusSlaveConfig(
                slave_address=self.slave_address,
                profile_name='default',
                max_retries=self.max_retries,
            )
        if name in self.slaves:
            return deepcopy(self.slaves[name])
        if name in self.devices:
            legacy = self.devices[name]
            return ModbusSlaveConfig(
                slave_address=legacy.slave_address,
                profile_name=name,
                transport_type='xinje_ma_8x8yr' if name == 'xinje_ma' else 'modbus_register',
                max_retries=legacy.max_retries,
            )
        raise KeyError(f"Unknown Modbus slave: {name}")

    def set_slave(self, name: str, slave: ModbusSlaveConfig) -> None:
        if name == 'default':
            self.slave_address = slave.slave_address
            self.max_retries = slave.max_retries
        else:
            self.slaves[name] = deepcopy(slave)

    def find_slave_name(self, slave_address: int) -> str:
        """Return the configured slave name for a numeric slave address."""
        address = int(slave_address)
        names = [*self.slaves.keys(), "default"] if self.slaves else self.slave_names()
        for name in names:
            if self.get_slave(name).slave_address == address:
                return name
        raise KeyError(f"No Modbus slave configured for address {address}")

    def get_connection(self, slave_name: str = 'default') -> ModbusDeviceConfig:
        """Resolve a slave ID and its assigned serial profile."""
        slave = self.get_slave(slave_name)
        profile = self.get_profile(slave.profile_name, fallback_to_default=True)
        return ModbusDeviceConfig(
            port=profile.port,
            baudrate=profile.baudrate,
            bytesize=profile.bytesize,
            stopbits=profile.stopbits,
            parity=profile.parity,
            timeout=profile.timeout,
            slave_address=slave.slave_address,
            max_retries=slave.max_retries,
        )

    def update_field(self, field: str, value: Any) -> None:
        if hasattr(self, field):
            setattr(self, field, value)
        else:
            raise ValueError(f"Invalid field: {field}")


class ModbusConfigSerializer(ISettingsSerializer[ModbusConfig]):

    @property
    def settings_type(self) -> str:
        return "modbus_config"

    def get_default(self) -> ModbusConfig:
        return ModbusConfig()

    def to_dict(self, settings: ModbusConfig) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> ModbusConfig:
        return ModbusConfig.from_dict(data)
