import time
import minimalmodbus
import logging

from src.engine.hardware.communication.modbus.modbus_exception_type import ModbusExceptionType
from src.robot_systems.paint.domain.vacuum_pump.modbus_lock import modbus_lock


class ModbusClient:
    """
    ModbusClient class provides functionality to communicate with a Modbus slave device
    using the Modbus RTU protocol via a serial connection. It allows for reading and
    writing registers on the Modbus slave device.

    Attributes:
        slave (int): The Modbus slave address (default is 10).
        client (minimalmodbus.Instrument): An instance of the minimalmodbus Instrument class
                                           used for Modbus communication.
    """
    def __init__(self, slave=10, port='COM5', baudrate=115200, bytesize=8,
                 stopbits=1, timeout=0.01, parity=minimalmodbus.serial.PARITY_NONE):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.slave = slave

        try:
            # Create instrument - this opens the serial port with defaults
            self.client = minimalmodbus.Instrument(port, self.slave, debug=False)

            # Reconfigure the open serial port with correct settings
            self.client.serial.baudrate = baudrate
            self.client.serial.bytesize = bytesize
            self.client.serial.stopbits = stopbits
            self.client.serial.parity = parity
            self.client.serial.timeout = timeout

            # RS485 control - disable RTS/DTR for proper half-duplex operation
            self.client.serial.rts = False
            self.client.serial.dtr = False

            # Flush any pending data to ensure clean state
            self.client.serial.reset_input_buffer()
            self.client.serial.reset_output_buffer()

            # Critical minimalmodbus settings for RS485
            self.client.close_port_after_each_call = False
            self.client.clear_buffers_before_each_transaction = True

            self.logger.info(f"ModbusClient initialized: port={port}, baud={baudrate}, parity={parity}, timeout={timeout}")

        except Exception as e:
            raise Exception(f"Could not open port {port}. Please check the connection and port settings.") from e

    def writeRegister(self, register, value, signed=False):
        maxAttempts = 30
        attempts = 0
        while attempts < maxAttempts:
            with modbus_lock:
                try:
                    self.client.write_register(register, value, signed=signed)
                    print(f"ModbusClient.writeRegister - > Wrote {value} to register {register}")
                    return None  # Success
                except Exception as e:
                    modbus_error = ModbusExceptionType.from_exception(e)
                    print(f"ModbusClient.writeRegister -> Error writing register {register}: {e} - {modbus_error.name}: {modbus_error.description()}")
                    # if modbus_error == ModbusExceptionType.CHECKSUM_ERROR:
                    #     return modbus_error  # Don't retry checksum errors
                    import traceback
                    traceback.print_exc()
                    attempts += 1
                    if attempts < maxAttempts:
                        time.sleep(0.1)
                    else:
                        return modbus_error  # Return the error type after max attempts
        
        return ModbusExceptionType.MODBUS_EXCEPTION  # Fallback

    def writeRegisters(self, start_register, values):
        maxAttempts = 30
        attempts = 0
        while attempts < maxAttempts:
            with modbus_lock:
                try:
                    # print(f"Writing registers starting from {start_register} with values: {values} Attempt {attempts+1}")
                    self.client.write_registers(start_register, values)
                    time.sleep(0.02)
                    # print("Written registers successfully")
                    return None  # Success
                except Exception as e:
                    modbus_error = ModbusExceptionType.from_exception(e)

                    # if modbus_error != ModbusExceptionType.CHECKSUM_ERROR:
                    import traceback
                    traceback.print_exc()

                    attempts += 1
                    if attempts >= maxAttempts:
                        return modbus_error  # Return error after max attempts



        return ModbusExceptionType.MODBUS_EXCEPTION  # Fallback

    def readRegisters(self, start_register, count):
        maxAttempts = 30
        attempts = 0
        while attempts < maxAttempts:
            with modbus_lock:
                try:
                    # print(f"Read {count} registers starting from register: {start_register}")
                    values = self.client.read_registers(start_register, count)
                    return values, None  # Success - return values and no error
                except Exception as e:
                    print(f"ModbusClient.readRegisters -> Error reading registers: {e}")
                    modbus_error = ModbusExceptionType.from_exception(e)
                    
                    # if modbus_error == ModbusExceptionType.CHECKSUM_ERROR:
                    #     return None, modbus_error  # Return None values with error
                    
                    attempts += 1
                    if attempts >= maxAttempts:
                        return None, modbus_error  # Return error after max attempts
        
        return None, ModbusExceptionType.MODBUS_EXCEPTION  # Fallback

    def read(self, register):
        maxAttempts = 30
        attempts = 0
        while attempts < maxAttempts:
            with modbus_lock:
                try:
                    value = self.client.read_register(register)
                    # print(f"Read value: {value} from register: {register}")
                    return value, None  # Success - return value and no error
                except Exception as e:
                    modbus_error = ModbusExceptionType.from_exception(e)
                    
                    if modbus_error == ModbusExceptionType.CHECKSUM_ERROR:
                        return None, modbus_error  # Return None value with error
                    
                    attempts += 1
                    if attempts >= maxAttempts:
                        return None, modbus_error  # Return error after max attempts
        
        return None, ModbusExceptionType.MODBUS_EXCEPTION  # Fallback

    def readBit(self,address,functioncode=1):
        with modbus_lock:
            return self.client.read_bit(address,functioncode=functioncode)

    def writeBit(self,address,value):
        """Write a bit/coil. For write-only devices, suppress response errors."""
        maxAttempts = 3  # Reduced from 30 since we know it's write-only
        attempts = 0
        while attempts < maxAttempts:
            with modbus_lock:
                try:
                    self.client.write_bit(address, value)
                    # Success - relay accepted command
                    return True
                except minimalmodbus.NoResponseError:
                    # Write-only relay - command was sent but no response
                    # This is NORMAL for some relay modules
                    if attempts == 0:
                        # First attempt - assume it worked since device is write-only
                        return True
                    attempts += 1
                except minimalmodbus.ModbusException as e:
                    if "Checksum error" in str(e):
                        import traceback
                        traceback.print_exc()
                        break
                    else:
                        import traceback
                        traceback.print_exc()
                    attempts += 1
                    time.sleep(0.1)
        return False

    def writeBits(self, address, values):
        """
        Write multiple coils using Function Code 15.

        WORKAROUND for CH340 USB-RS485 converter bug:
        - Byte 0x80 corrupts to 0x00 (bit 7 issue)
        - Use address 296 (0x0128) instead of 128 (0x80)
        - Use NONE parity instead of EVEN to avoid CRC corruption

        Args:
            address: Starting coil address
            values: List of boolean values to write

        Returns:
            True if successful, False otherwise
        """
        with modbus_lock:
            try:
                import struct
                import serial as pyserial

                # Build Modbus FC15 frame manually
                slave_id = self.slave
                function_code = 0x0F
                address_hi = (address >> 8) & 0xFF
                address_lo = address & 0xFF
                count = len(values)
                count_hi = (count >> 8) & 0xFF
                count_lo = count & 0xFF
                byte_count = (count + 7) // 8

                # Convert boolean list to bytes
                data_byte = 0
                for i, val in enumerate(values):
                    if val:
                        data_byte |= (1 << i)

                # Build frame (without CRC)
                frame = bytes([slave_id, function_code, address_hi, address_lo,
                              count_hi, count_lo, byte_count, data_byte])

                # Calculate CRC16 Modbus
                crc = 0xFFFF
                for byte in frame:
                    crc ^= byte
                    for _ in range(8):
                        if crc & 0x0001:
                            crc = (crc >> 1) ^ 0xA001
                        else:
                            crc >>= 1

                # Append CRC (little-endian)
                crc_bytes = struct.pack('<H', crc)
                full_frame = frame + crc_bytes


                # Close minimalmodbus port, send via direct pySerial, then reopen
                port_name = self.client.serial.port
                port_settings = {
                    'baudrate': self.client.serial.baudrate,
                    'bytesize': self.client.serial.bytesize,
                    'parity': self.client.serial.parity,
                    'stopbits': self.client.serial.stopbits,
                    'timeout': 0.001  # 20ms timeout like mb2hal
                }

                self.client.serial.close()

                # Open direct pySerial port and force RAW mode
                direct_port = pyserial.Serial(port=port_name, **port_settings)

                # Force TTY to RAW mode to prevent byte manipulation
                import termios
                tty_attrs = termios.tcgetattr(direct_port.fileno())
                tty_attrs[0] = 0  # iflag
                tty_attrs[1] = 0  # oflag
                tty_attrs[2] |= (termios.CLOCAL | termios.CREAD)
                tty_attrs[3] = 0  # lflag
                termios.tcsetattr(direct_port.fileno(), termios.TCSANOW, tty_attrs)

                direct_port.rts = False
                direct_port.dtr = False

                # Send frame
                direct_port.write(full_frame)
                direct_port.flush()

                # mb2hal uses SERIAL_DELAY_MS=20
                import time
                time.sleep(0.020)

                # Read relay response BEFORE closing port
                try:
                    response = direct_port.read(8)
                except:
                    pass

                direct_port.close()

                # Reopen minimalmodbus port
                self.client.serial.open()

                return True

            except Exception as e:
                print(f"[ModbusClient] Error writing bits at {address}: {e}")
                return False

    def writeBit(self, address, value):
        """
        Write single coil using Function Code 05 (Write Single Coil).
        Some Modbus devices only support FC05, not FC15.

        Args:
            address: Coil address
            value: Boolean value to write

        Returns:
            True if successful, False otherwise
        """
        with modbus_lock:
            try:
                import struct
                import serial as pyserial

                # Build Modbus FC05 frame
                slave_id = self.slave
                function_code = 0x05  # Write Single Coil
                address_hi = (address >> 8) & 0xFF
                address_lo = address & 0xFF
                # WORKAROUND: CH340 corrupts 0xFF to 0x7F (strips bit 7)
                # Try using 0x7F as the ON value since that's what gets transmitted
                # Standard Modbus: 0xFF00 = ON, 0x0000 = OFF
                # CH340 reality: 0x7F00 gets sent when we request 0xFF00
                value_hi = 0xFF if value else 0x00  # Will corrupt to 0x7F but try anyway
                value_lo = 0x00

                # Build frame (without CRC)
                frame = bytes([slave_id, function_code, address_hi, address_lo, value_hi, value_lo])

                # Calculate CRC16
                crc = 0xFFFF
                for byte in frame:
                    crc ^= byte
                    for _ in range(8):
                        if crc & 0x0001:
                            crc = (crc >> 1) ^ 0xA001
                        else:
                            crc >>= 1

                crc_bytes = struct.pack('<H', crc)
                full_frame = frame + crc_bytes

                # Send via direct pySerial
                port_name = self.client.serial.port
                port_settings = {
                    'baudrate': self.client.serial.baudrate,
                    'bytesize': self.client.serial.bytesize,
                    'parity': self.client.serial.parity,
                    'stopbits': self.client.serial.stopbits,
                    'timeout': 0.001  # 20ms timeout like mb2hal
                }

                self.client.serial.close()
                direct_port = pyserial.Serial(port=port_name, **port_settings)

                # Force RAW mode
                import termios
                tty_attrs = termios.tcgetattr(direct_port.fileno())
                tty_attrs[0] = 0
                tty_attrs[1] = 0
                tty_attrs[2] |= (termios.CLOCAL | termios.CREAD)
                tty_attrs[3] = 0
                termios.tcsetattr(direct_port.fileno(), termios.TCSANOW, tty_attrs)

                direct_port.rts = False
                direct_port.dtr = False

                # Send and wait for response
                direct_port.write(full_frame)
                direct_port.flush()

                import time
                time.sleep(0.020)

                try:
                    response = direct_port.read(8)
                except:
                    pass

                direct_port.close()
                self.client.serial.open()

                return True

            except Exception as e:
                print(f"[ModbusClient] Error writing bit at {address}: {e}")
                return False

    def close(self):
        self.client.serial.close()



