from __future__ import annotations

import logging
import struct
import time
from typing import Any, List

import serial
import termios

from src.engine.hardware.communication.modbus.modbus_register_transport import ModbusRegisterTransport
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_transport import IVacuumPumpTransport

_logger = logging.getLogger(__name__)


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


class ModbusVacuumPumpTransport(ModbusRegisterTransport, IVacuumPumpTransport):
    """Modbus RTU transport for vacuum-pump relay boards.

    Coil writes bypass minimalmodbus and use direct pyserial with
    RTS=False/DTR=False and CLOCAL|CREAD.  This works around CH340
    USB-RS485 converter quirks that cause minimalmodbus transactions
    to fail silently on some relay boards.
    """

    def __init__(
        self,
        *args,
        write_retry_delay_s: float = 0.02,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._write_retry_delay_s = max(0.0, float(write_retry_delay_s))

    # ── Coil writes (bypass minimalmodbus) ─────────────────────────────

    def write_register(self, address: int, value: int) -> None:
        self._write_bits(address, [1 if value else 0])

    def write_registers(self, address: int, values: List[int]) -> None:
        self._write_bits(address, [1 if value else 0 for value in values])

    def _write_bits(self, address: int, values: List[int]) -> None:
        """Send FC 15 frame via direct pyserial with RS485-safe settings."""
        slave_id = self._slave_address
        count = len(values)
        byte_count = (count + 7) // 8

        data_byte = 0
        for i, val in enumerate(values):
            if val:
                data_byte |= 1 << i

        frame = bytes([
            slave_id, 15,
            (address >> 8) & 0xFF, address & 0xFF,
            (count >> 8) & 0xFF, count & 0xFF,
            byte_count, data_byte,
        ])
        full_frame = frame + struct.pack("<H", _crc16(frame))

        self._logger.debug("Coil write raw frame=%s", full_frame.hex())

        for attempt in range(1, 4):
            try:
                self._raw_send(full_frame)
                return
            except Exception:
                _logger.exception("Coil write attempt %d/3 failed", attempt)
                if attempt < 3:
                    time.sleep(self._write_retry_delay_s)
        raise RuntimeError(f"Coil write to {address} failed after 3 attempts")

    def _raw_send(self, full_frame: bytes) -> None:
        """Open a direct serial port, configure for RS485, send, close."""
        direct = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            bytesize=self._bytesize,
            parity=self._parity,
            stopbits=self._stopbits,
            timeout=0.001,
        )
        try:
            tty_attrs = termios.tcgetattr(direct.fileno())
            tty_attrs[0] = 0
            tty_attrs[1] = 0
            tty_attrs[2] = tty_attrs[2] | termios.CLOCAL | termios.CREAD
            tty_attrs[3] = 0
            termios.tcsetattr(direct.fileno(), termios.TCSANOW, tty_attrs)

            direct.rts = False
            direct.dtr = False

            direct.write(full_frame)
            direct.flush()
            time.sleep(0.02)
            direct.read(8)
        finally:
            try:
                direct.close()
            except Exception:
                pass

    # ── Coil reads (via minimalmodbus) ─────────────────────────────────

    def read_register(self, address: int) -> int:
        with self._session() as inst:
            self._logger.debug("Reading coil %s", address)
            return int(inst.read_bit(address, functioncode=1))

    def read_registers(self, address: int, count: int) -> List[int]:
        with self._session() as inst:
            self._logger.debug("Reading coils from %s (count=%s)", address, count)
            return [int(value) for value in inst.read_bits(address, count, functioncode=1)]

    # ── Instrument factory (configure RS485-safe serial) ───────────────

    def _make_instrument(self) -> Any:
        import minimalmodbus
        inst = minimalmodbus.Instrument(self._port, self._slave_address)
        inst.serial.baudrate = self._baudrate
        inst.serial.bytesize = self._bytesize
        inst.serial.stopbits = self._stopbits
        inst.serial.parity = self._parity
        inst.serial.timeout = self._timeout
        inst.mode = minimalmodbus.MODE_RTU
        inst.serial.rts = False
        inst.serial.dtr = False
        return inst
