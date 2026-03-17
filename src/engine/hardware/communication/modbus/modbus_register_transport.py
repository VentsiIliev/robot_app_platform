from __future__ import annotations
import logging
from typing import Any, List, Optional

from src.engine.hardware.communication.i_register_transport import IRegisterTransport


class _Session:
    """Per-call or persistent Modbus instrument session."""

    def __init__(self, transport: ModbusRegisterTransport) -> None:
        self._transport = transport
        self._inst: Any = None
        self._owns = False

    def __enter__(self) -> Any:
        if self._transport._persistent is not None:
            return self._transport._persistent
        self._inst  = self._transport._make_instrument()
        self._owns  = True
        return self._inst

    def __exit__(self, *_: Any) -> None:
        if self._owns and self._inst is not None:
            try:
                self._inst.serial.close()
            except Exception:
                pass


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
        timeout:       float = 0.03,
    ) -> None:
        self._port          = port
        self._slave_address = slave_address
        self._baudrate      = baudrate
        self._bytesize      = bytesize
        self._stopbits      = stopbits
        self._parity        = parity
        self._timeout       = timeout
        self._persistent: Optional[Any] = None
        self._logger        = logging.getLogger(self.__class__.__name__)

    # ── IRegisterTransport ────────────────────────────────────────────

    def read_register(self, address: int) -> int:
        with self._session() as inst:
            self._logger.debug(f"Reading register {address} ...")
            return int(inst.read_register(address, functioncode=3))

    def read_registers(self, address: int, count: int) -> List[int]:
        with self._session() as inst:
            self._logger.debug(f"Reading starting register {address} (count={count})")
            return list(inst.read_registers(address, count, functioncode=3))

    def write_register(self, address: int, value: int) -> None:
        with self._session() as inst:
            self._logger.debug(f"Writing register {address} (value={value})")
            inst.write_register(address, value, functioncode=6)

    def write_registers(self, address: int, values: List[int]) -> None:
        with self._session() as inst:
            self._logger.debug(f"Writing starting register {address} (values={values})")
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

    def _session(self) -> _Session:
        return _Session(self)

    def _make_instrument(self) -> Any:
        import minimalmodbus
        inst                = minimalmodbus.Instrument(self._port, self._slave_address)
        inst.serial.baudrate = self._baudrate
        inst.serial.bytesize = self._bytesize
        inst.serial.stopbits = self._stopbits
        inst.serial.parity   = self._parity
        inst.serial.timeout  = self._timeout
        inst.mode            = minimalmodbus.MODE_RTU
        return inst