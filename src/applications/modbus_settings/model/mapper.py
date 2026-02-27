from copy import deepcopy

from src.engine.hardware.communication.modbus.modbus import ModbusConfig


class ModbusSettingsMapper:

    @staticmethod
    def to_flat_dict(config: ModbusConfig) -> dict:
        # baudrate/bytesize/stopbits are stored as int but displayed in combo widgets.
        # combo set_value calls str() on the value, so int works fine for population.
        # combo get_value always returns str, so from_flat_dict converts back.
        return {
            "port":          config.port,
            "baudrate":      config.baudrate,
            "bytesize":      config.bytesize,
            "stopbits":      config.stopbits,
            "parity":        config.parity,
            "timeout":       config.timeout,
            "slave_address": config.slave_address,
            "max_retries":   config.max_retries,
        }

    @staticmethod
    def from_flat_dict(flat: dict, base: ModbusConfig) -> ModbusConfig:
        c = deepcopy(base)
        c.port          = flat.get("port",          c.port)
        c.baudrate      = int(flat.get("baudrate",      c.baudrate))
        c.bytesize      = int(flat.get("bytesize",      c.bytesize))
        c.stopbits      = int(flat.get("stopbits",      c.stopbits))
        c.parity        = flat.get("parity",        c.parity)
        c.timeout       = float(flat.get("timeout",       c.timeout))
        c.slave_address = int(flat.get("slave_address", c.slave_address))
        c.max_retries   = int(flat.get("max_retries",   c.max_retries))
        return c