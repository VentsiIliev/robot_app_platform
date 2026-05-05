import minimalmodbus
from enum import Enum
from dataclasses import dataclass

from src.robot_systems.paint.domain.vacuum_pump.ModbusClient import ModbusClient


class ModbusParity(Enum):
    NONE = minimalmodbus.serial.PARITY_NONE
    EVEN = minimalmodbus.serial.PARITY_EVEN
    ODD = minimalmodbus.serial.PARITY_ODD

@dataclass
class ModbusClientConfig:
    enabled: bool
    slave_id: int
    port: str
    baudrate: int
    byte_size: int
    parity: ModbusParity
    stop_bits: int
    timeout: float
    inter_byte_timeout: float

config = ModbusClientConfig(
    enabled=False,
    slave_id=1,  # mb2hal uses ID 1
    port="/dev/ttyUSB0",
    baudrate=57600,  # mb2hal baudrate
    byte_size=8,
    parity=ModbusParity.EVEN,  # mb2hal parity
    stop_bits=1,
    timeout=0.001,  # 20ms timeout like mb2hal
    inter_byte_timeout=0.01
)

class XinjeRelayController:
    """
    Controller for Xinje MA-8X8YR relay module.

    Based on working mb2hal configuration:
    - Y0-Y7 outputs: Modbus coil addresses 128-135 (FIRST_ELEMENT=128)
    - X0-X7 inputs: Modbus coil addresses 0-7 (FIRST_ELEMENT=0)
    - Slave ID: 8
    - Baudrate: 19200
    - Parity: EVEN
    - Function Code 05: Write Single Coil
    - Function Code 15: Write Multiple Coils (for batch operations)
    - Function Code 01: Read Coil Status
    - Function Code 02: Read Input Status
    """

    def __init__(self, modbus_client=None):
        self.client = modbus_client
        self.output_base_address = 128
        self.input_base_address = 0

    def read_input(self, input_number):
        """Read single digital input (0-7)"""
        if not self.client:
            print("[XinjeRelay] Modbus client not initialized")
            return False

        try:
            address = self.input_base_address + input_number
            value = self.client.readBit(address, functioncode=2)
            return bool(value)
        except Exception as e:
            print(f"[XinjeRelay] Error reading input {input_number}: {e}")
            return False

    def read_all_inputs(self):
        """Read all 8 digital inputs"""
        return [self.read_input(i) for i in range(8)]

    def write_output(self, output_number, value):
        """Write single relay output (0-7) using Function Code 15 like mb2hal"""
        if not self.client:
            print("[XinjeRelay] Modbus client not initialized")
            return False

        if output_number < 0 or output_number > 7:
            print(f"[XinjeRelay] Invalid output number: {output_number}. Must be 0-7")
            return False

        try:
            address = self.output_base_address + output_number
            # Use FC15 (Write Multiple Coils) with bitmap - avoids 0xFF00 format
            # FC15 uses: [0x01] for ON, [0x00] for OFF in data byte
            success = self.client.writeBits(address, [int(value)])

            import time
            time.sleep(0.020)

            return success
        except Exception as e:
            print(f"[XinjeRelay] Error writing Y{output_number}: {e}")
            return False

    def read_output(self, output_number):
        """Read single relay output status (0-7)"""
        if not self.client:
            print("[XinjeRelay] Modbus client not initialized")
            return False

        if output_number < 0 or output_number > 7:
            print(f"[XinjeRelay] Invalid output number: {output_number}. Must be 0-7")
            return False

        try:
            address = self.output_base_address + output_number
            value = self.client.readBit(address, functioncode=1)
            return bool(value)
        except Exception as e:
            print(f"[XinjeRelay] Error reading Y{output_number}: {e}")
            return False

    def read_all_outputs(self):
        """Read all 8 relay outputs"""
        return [self.read_output(i) for i in range(8)]

class ModbusController:
    _instance = None
    _relay_controller = None

    @classmethod
    def initialize(cls, settings_dict):
        """Initialize modbus with settings from UI"""
        global config

        if not settings_dict.get('enabled', False):
            print("[ModbusController] Modbus disabled in settings")
            config.enabled = False
            cls._relay_controller = None
            return

        # Update config from settings
        config.enabled = settings_dict['enabled']
        config.slave_id = settings_dict['slave_id']
        config.port = settings_dict['port']
        config.baudrate = settings_dict['baudrate']
        config.byte_size = settings_dict['byte_size']

        parity_str = settings_dict['parity']
        if parity_str == 'NONE':
            config.parity = ModbusParity.NONE
        elif parity_str == 'EVEN':
            config.parity = ModbusParity.EVEN
        elif parity_str == 'ODD':
            config.parity = ModbusParity.ODD

        config.stop_bits = settings_dict['stop_bits']
        config.timeout = settings_dict['timeout']

        print(f"[ModbusController] Initialized with: port={config.port}, baudrate={config.baudrate}, slave_id={config.slave_id}")

        # Create relay controller with modbus client
        try:
            client = cls.getModbusClient(config.slave_id)
            print(f"[ModbusController] Created client with: baudrate={client.client.serial.baudrate}, "
                  f"parity={client.client.serial.parity}, timeout={client.client.serial.timeout}")
            cls._relay_controller = XinjeRelayController(client)
            print("[ModbusController] Xinje relay controller initialized successfully")
        except Exception as e:
            print(f"[ModbusController] Error initializing relay controller: {e}")
            cls._relay_controller = None

    @classmethod
    def get_relay_controller(cls):
        """Get the Xinje relay controller instance"""
        return cls._relay_controller

    @classmethod
    def getModbusClient(cls, slaveId=None):
        if slaveId is None:
            slaveId = config.slave_id

        port = config.port

        # Create ModbusClient with all settings passed to constructor
        client = ModbusClient(
            slave=slaveId,
            port=port,
            baudrate=config.baudrate,
            bytesize=config.byte_size,
            stopbits=config.stop_bits,
            timeout=config.timeout,
            parity=config.parity.value
        )

        # Set additional minimalmodbus properties on the underlying client
        client.client.clear_buffers_before_each_transaction = True
        client.client.mode = minimalmodbus.MODE_RTU

        return client
