#!/usr/bin/env python3
"""Minimal direct Xinje X4 read diagnostic."""

import minimalmodbus


PORT = "/dev/ttyUSB0"
SLAVE_ID = 1
BAUDRATE = 57600
PARITY = "E"
TIMEOUT_S = 0.5
X4_ADDRESS = 2


instrument = minimalmodbus.Instrument(PORT, SLAVE_ID)
instrument.serial.baudrate = BAUDRATE
instrument.serial.bytesize = 8
instrument.serial.parity = PARITY
instrument.serial.stopbits = 1
instrument.serial.timeout = TIMEOUT_S
instrument.mode = minimalmodbus.MODE_RTU
instrument.serial.rts = False
instrument.serial.dtr = False

print(
    f"Reading X4 address={X4_ADDRESS} on {PORT} "
    f"slave={SLAVE_ID} {BAUDRATE},8{PARITY}1 using FC1"
)
# value = instrument.read_bit(X4_ADDRESS, functioncode=1)
value = instrument.read_register(X4_ADDRESS, functioncode=3, number_of_decimals=0)
print(f"X4 raw={value} pressed={bool(value)}")
