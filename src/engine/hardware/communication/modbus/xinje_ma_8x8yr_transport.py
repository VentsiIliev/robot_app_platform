from __future__ import annotations

import logging
import os
import select
import struct
import time
from typing import Any, List

import serial
import termios

from src.engine.hardware.communication.modbus.modbus_register_transport import (
    ModbusRegisterTransport,
)
from src.engine.hardware.communication.modbus.serial_bus import (
    get_serial_bus_lock,
    serial_bus_session,
)

_logger = logging.getLogger(__name__)
_MA_OUTPUT_START = 128
_MA_OUTPUT_COUNT = 16
_MA_OUTPUT_SHADOWS: dict[tuple[object, ...], list[int]] = {}


def _write_fd_bounded(fd: int, data: bytes, timeout: float) -> None:
    """Write a complete RTU frame without allowing the driver to block."""
    deadline = time.monotonic() + max(0.001, float(timeout))
    offset = 0
    was_blocking = os.get_blocking(fd)
    os.set_blocking(fd, False)
    try:
        while offset < len(data):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise serial.SerialTimeoutException("Timed out writing Xinje RTU frame")
            _, writable, _ = select.select([], [fd], [], remaining)
            if not writable:
                raise serial.SerialTimeoutException("Timed out waiting for writable Xinje serial port")
            try:
                written = os.write(fd, data[offset:])
            except BlockingIOError:
                continue
            if written <= 0:
                raise serial.SerialException("Xinje serial write returned zero bytes")
            offset += written
    finally:
        os.set_blocking(fd, was_blocking)


class ModbusExceptionResponse(RuntimeError):
    """Raised when the Xinje slave returns a Modbus exception response."""


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 0x0001 else crc >> 1
    return crc


class XinjeMA8X8YRTransport(ModbusRegisterTransport):
    """Modbus RTU transport for Xinje MA-8X8YR relay/I/O modules.

    The MA output image is written as one FC15 block at addresses K128-K143.
    Other coil addresses use FC5. Raw writes use a directly configured serial
    port because some USB-RS485 adapters do not reliably preserve the serial
    line settings through minimalmodbus.
    """

    def __init__(self, *args, write_retry_delay_s: float = 0.02, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._write_retry_delay_s = max(0.0, float(write_retry_delay_s))
        shadow_key = (
            self._port,
            self._slave_address,
            self._baudrate,
            self._bytesize,
            self._parity,
            self._stopbits,
        )
        with get_serial_bus_lock(self._port):
            self._ma_output_shadow = _MA_OUTPUT_SHADOWS.setdefault(
                shadow_key,
                [0] * _MA_OUTPUT_COUNT,
            )

    def write_register(self, address: int, value: int) -> None:
        if _MA_OUTPUT_START <= address < _MA_OUTPUT_START + _MA_OUTPUT_COUNT:
            self._write_ma_output(address, bool(value))
            return
        self._write_single_coil(address, bool(value))

    def write_registers(self, address: int, values: List[int]) -> None:
        self.write_coils_fc15(address, [1 if value else 0 for value in values])

    def write_coil_fc5(self, address: int, value: bool) -> None:
        self._write_single_coil(address, value)

    def write_coils_fc15(self, address: int, values: List[int]) -> None:
        self._write_bits(address, values)

    def write_register_fc6(self, address: int, value: int) -> None:
        frame = bytes([
            self._slave_address, 6,
            (address >> 8) & 0xFF, address & 0xFF,
            (value >> 8) & 0xFF, value & 0xFF,
        ])
        self._write_raw_frame(address, frame)

    def write_registers_fc16(self, address: int, values: List[int]) -> None:
        data_bytes = []
        for value in values:
            data_bytes.extend([(value >> 8) & 0xFF, value & 0xFF])
        frame = bytes([
            self._slave_address, 16,
            (address >> 8) & 0xFF, address & 0xFF,
            (len(values) >> 8) & 0xFF, len(values) & 0xFF,
            len(data_bytes),
        ] + data_bytes)
        self._write_raw_frame(address, frame)

    def _write_single_coil(self, address: int, value: bool) -> None:
        coil_value = 0xFF00 if value else 0x0000
        frame = bytes([
            self._slave_address, 5,
            (address >> 8) & 0xFF, address & 0xFF,
            (coil_value >> 8) & 0xFF, coil_value & 0xFF,
        ])
        self._write_raw_frame(address, frame)

    def _write_bits(self, address: int, values: List[int]) -> None:
        count = len(values)
        byte_count = (count + 7) // 8
        data_bytes = [0] * byte_count
        for index, value in enumerate(values):
            if value:
                data_bytes[index // 8] |= 1 << (index % 8)
        frame = bytes([
            self._slave_address, 15,
            (address >> 8) & 0xFF, address & 0xFF,
            (count >> 8) & 0xFF, count & 0xFF,
            byte_count,
        ] + data_bytes)
        self._write_raw_frame(address, frame)

    def _write_ma_output(self, address: int, value: bool) -> None:
        index = address - _MA_OUTPUT_START
        with serial_bus_session(self._port, self._timeout):
            previous = list(self._ma_output_shadow)
            self._ma_output_shadow[index] = 1 if value else 0
            try:
                self._write_bits(_MA_OUTPUT_START, self._ma_output_shadow)
            except Exception:
                self._ma_output_shadow[:] = previous
                raise

    def _write_raw_frame(self, address: int, frame: bytes) -> None:
        full_frame = frame + struct.pack("<H", _crc16(frame))
        _logger.debug("Xinje raw write frame=%s", full_frame.hex())
        for attempt in range(1, 4):
            try:
                self._raw_send(full_frame)
                return
            except ModbusExceptionResponse:
                _logger.exception("Xinje coil/register write rejected by slave")
                raise
            except Exception:
                _logger.exception("Xinje write attempt %d/3 failed", attempt)
                if attempt < 3:
                    time.sleep(self._write_retry_delay_s)
        raise RuntimeError(f"Xinje write to {address} failed after 3 attempts")

    def _raw_send(self, full_frame: bytes) -> bytes:
        # Several configured peripherals may share one RS-485 port. Keep the
        # complete request/response exchange atomic across transport instances.
        with serial_bus_session(self._port, self._timeout):
            _logger.debug("Xinje bus acquired port=%s slave=%d", self._port, self._slave_address)
            direct = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                bytesize=self._bytesize,
                parity=self._parity,
                stopbits=self._stopbits,
                timeout=max(0.001, self._timeout),
                write_timeout=max(0.001, self._timeout),
                rtscts=False,
                dsrdtr=False,
                xonxoff=False,
            )
            try:
                _logger.debug("Xinje serial opened port=%s", self._port)
                tty_attrs = termios.tcgetattr(direct.fileno())
                tty_attrs[0] = 0
                tty_attrs[1] = 0
                tty_attrs[2] |= termios.CLOCAL | termios.CREAD
                if hasattr(termios, "CRTSCTS"):
                    tty_attrs[2] &= ~termios.CRTSCTS
                tty_attrs[3] = 0
                termios.tcsetattr(direct.fileno(), termios.TCSANOW, tty_attrs)
                direct.rts = False
                direct.dtr = False
                _logger.debug("Xinje writing %d bytes port=%s", len(full_frame), self._port)
                _write_fd_bounded(direct.fileno(), full_frame, self._timeout)
                # Do not call pyserial.flush() here. On some USB-RS485
                # drivers tcdrain() can wait indefinitely when the adapter
                # loses its line state. write_timeout already bounds write().
                time.sleep(0.02)
                _logger.debug("Xinje waiting for response port=%s", self._port)
                response = direct.read(8)
                _logger.debug("Xinje response received bytes=%d port=%s", len(response), self._port)
                self._validate_response(response, full_frame)
                return response
            finally:
                try:
                    direct.close()
                except Exception:
                    pass

    def _validate_response(self, response: bytes, request: bytes) -> None:
        response = self._normalize_response(response)
        if not response:
            return
        if len(response) >= 5 and response[0] == request[0] and response[1] == (request[1] | 0x80):
            raise ModbusExceptionResponse(
                f"Modbus exception response for function {request[1]}: "
                f"code={response[2]} response={response.hex()}"
            )
        if len(response) < 8:
            raise RuntimeError(f"Short Modbus response: {response.hex()}")
        payload = response[:-2]
        expected_crc = struct.pack("<H", _crc16(payload))
        if response[-2:] != expected_crc:
            raise RuntimeError(f"Bad Modbus response CRC: {response.hex()}")

    def _normalize_response(self, response: bytes) -> bytes:
        if not response:
            return response
        for index in range(len(response) - 4):
            if response[index] == self._slave_address and response[index + 1] >= 0x80:
                candidate = response[index:index + 5]
                payload = candidate[:-2]
                if candidate[-2:] == struct.pack("<H", _crc16(payload)):
                    return candidate
        return response

    def read_register(self, address: int) -> int:
        with serial_bus_session(self._port, self._timeout):
            with self._session() as inst:
                return int(inst.read_bit(address, functioncode=1))

    def read_registers(self, address: int, count: int) -> List[int]:
        with serial_bus_session(self._port, self._timeout):
            with self._session() as inst:
                return [int(value) for value in inst.read_bits(address, count, functioncode=1)]

    def read_input(self, address: int) -> int:
        """Read one Xinje X point through the MA coil-read function.

        MA-8X8YR firmware exposes the X image through FC1; FC2 returns
        exception code 1 (illegal function) on this module.
        """
        with serial_bus_session(self._port, self._timeout):
            with self._session() as inst:
                return int(inst.read_bit(address, functioncode=1))

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
