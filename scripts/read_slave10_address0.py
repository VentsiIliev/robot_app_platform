import logging

from src.engine.hardware.communication.modbus.modbus_register_transport import (
    ModbusRegisterTransport,
)


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
)

transport = ModbusRegisterTransport(
    port="/dev/ttyUSB0",
    slave_address=10,
    baudrate=57600,
    bytesize=8,
    stopbits=1,
    parity="N",
    timeout=0.5,
)

try:
    value = transport.read_register(0)
    print(f"Slave 10, address 0: {value}")
finally:
    transport.disconnect()
