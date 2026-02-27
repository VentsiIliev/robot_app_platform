from __future__ import annotations
import logging
from contextlib import contextmanager
from typing import List

from src.engine.hardware.communication.i_register_transport import IRegisterTransport


class ModbusRegisterTransport(IRegisterTransport):
    """
    Shared Modbus RTU implementation of IRegisterTransport via minimalmodbus.

    All four register operations are overridden for native batch efficiency.
    Supports both per-call and persistent connections — call connect() /
    disconnect() to keep a session open for hot-path callers.

    Do not instantiate directly — subclass for your device:
        class ModbusMotorTransport(ModbusRegisterTransport, IMotorTransport): pass
        class ModbusGeneratorTransport(ModbusRegisterTransport, IGeneratorTransport): pass
    """

    def __init__(
        self,
        port:          str,
        slave_address: int,
        baudrate:      int   = 115200,
        bytesize:      int   = 8,
        stopbits:      int   = 1,
        parity:        str   = "N",
        timeout:       float = 0.01,
    ) -> None:
        self._port          = port
        self._slave_address = slave_address
        self._baudrate      = baudrate
        self._bytesize      = bytesize
        self._stopbits      = stopbits
        self._parity        = parity
        self._timeout       = timeout
        self._persistent    = None
        self._logger        = logging.getLogger(self.__class__.__name__)

    # ── IRegisterTransport ────────────────────────────────────────────

    def read_register(self, address: int) -> int:
        with self._session() as inst:
            return int(inst.read_register(address, functioncode=3))

    def read_registers(self, address: int, count: int) -> List[int]:
        with self._session() as inst:
            return list(inst.read_registers(address, count, functioncode=3))

    def write_register(self, address: int, value: int) -> None:
        with self._session() as inst:
            inst.write_register(address, value, functioncode=6)

    def write_registers(self, address: int, values: List[int]) -> None:
        with self._session() as inst:
            inst.write_registers(address, values)

    # ── Persistent connection ─────────────────────────────────────────

    def connect(self) -> None:
        if self._persistent is None:
            self._logger.debug("Connecting to %s (slave=%s) ...", self._port, self._slave_address)
            self._persistent = self._make_instrument()
            self._logger.info("Connected to %s (slave=%s)", self._port, self._slave_address)

    def disconnect(self) -> None:
        if self._persistent is not None:
            try:
                self._persistent.serial.close()
            except Exception:
                pass
            self._persistent = None
            self._logger.info("Persistent connection closed")

    # ── Internal ──────────────────────────────────────────────────────

    @contextmanager
    def _session(self):
        if self._persistent is not None:
            yield self._persistent
        else:
            inst = self._make_instrument()
            try:
                yield inst
            finally:
                try:
                    inst.serial.close()
                except Exception:
                    pass

    def _make_instrument(self):
        import minimalmodbus
        inst                = minimalmodbus.Instrument(self._port, self._slave_address)
        inst.serial.baudrate = self._baudrate
        inst.serial.bytesize = self._bytesize
        inst.serial.stopbits = self._stopbits
        inst.serial.parity   = self._parity
        inst.serial.timeout  = self._timeout
        inst.mode            = minimalmodbus.MODE_RTU
        return inst