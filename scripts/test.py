import time

import minimalmodbus

PORT = "/dev/ttyUSB0"
SLAVE_ID = 10
BAUDRATE = 57600
PARITY = "N"

instrument = minimalmodbus.Instrument(PORT, SLAVE_ID)
instrument.serial.baudrate = BAUDRATE
instrument.serial.bytesize = 8
instrument.serial.parity = PARITY
instrument.serial.stopbits = 1
instrument.serial.timeout = 0.5
instrument.mode = minimalmodbus.MODE_RTU
instrument.debug = True

"""XINJE SLAVE 1"""
#
# COIL_ADDRESS_0 = 130  # Xinje Y2: Y0=128, Y1=129, Y2=130
# COIL_ADDRESS_1 = 131  # Xinje Y2: Y0=128, Y1=129, Y2=130
# COIL_ADDRESS_2 = 128  # Xinje Y2: Y0=128, Y1=129, Y2=130
# COIL_ADDRESS_3 = 129  # Xinje Y2: Y0=128, Y1=129, Y2=130

# HOLD_SECONDS = 30
# try:
#     # minimalmodbus.write_bit(..., functioncode=5) sends Write Single Coil.
#     # instrument.write_bit(COIL_ADDRESS_0, 1, functioncode=5)
#     # instrument.write_bit(COIL_ADDRESS_1, 1, functioncode=5)
#     instrument.write_bit(COIL_ADDRESS_2, 1, functioncode=5)
#     instrument.write_bit(COIL_ADDRESS_3, 1, functioncode=5)
#     print(f"Coil ON; holding for {HOLD_SECONDS}s")
#     result_1 = instrument.read_bit(COIL_ADDRESS_2, functioncode=1)
#     result_2 = instrument.read_bit(COIL_ADDRESS_3, functioncode=1)
#     print(f"Result 1: {result_1}")
#     print(f"Result 2: {result_2}")
#
#     time.sleep(HOLD_SECONDS)
# finally:
#     # instrument.write_bit(COIL_ADDRESS_0, 0, functioncode=5)
#     # instrument.write_bit(COIL_ADDRESS_1, 0, functioncode=5)
#     instrument.write_bit(COIL_ADDRESS_2, 0, functioncode=5)
#     instrument.write_bit(COIL_ADDRESS_3, 0, functioncode=5)
#     print("Coil OFF")


"""SLAVE 10"""

# instrument.write_register(1,2)
time.sleep(5)
instrument.write_register(1,0)
