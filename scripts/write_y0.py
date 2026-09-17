import logging
import sys

from src.engine.hardware.communication.modbus.modbus_register_transport import (
    ModbusRegisterTransport,
)

PORT = "/dev/ttyUSB0"
SLAVE_ID = 10
ADDRESS = 1


class ScriptModbusTransport(ModbusRegisterTransport):
    """Standard Modbus RTU transport used by this diagnostic script."""


if len(sys.argv) == 2:
    requested_value = sys.argv[1]
else:
    requested_value = input(f"Enter a value for address {ADDRESS}: ").strip()

if requested_value not in {"0", "1","2","3","4","5","6","7","8","9"}:
    raise SystemExit("Invalid value: enter only a digit from 0 to 9")

value = int(requested_value)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
)

transport = ScriptModbusTransport(
    port=PORT,
    slave_address=SLAVE_ID,
    baudrate=57600,
    bytesize=8,
    stopbits=1,
    parity="N",  # Change to "E" if the device uses even parity
    timeout=0.5,
)

try:
    print(f"Writing FC16: slave={SLAVE_ID}, address={ADDRESS}, value={value}")
    transport.write_registers(ADDRESS, [value])
    print("FC16 write acknowledged by the slave")

    actual_value = transport.read_register(ADDRESS)
    print(f"Y0 readback: {actual_value} ({'ON' if actual_value else 'OFF'})")
finally:
    transport.disconnect()
