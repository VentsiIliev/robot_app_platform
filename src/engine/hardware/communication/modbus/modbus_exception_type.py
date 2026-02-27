from enum import Enum


class ModbusExceptionType(Enum):
    MODBUS_EXCEPTION       = "ModbusException"
    INVALID_RESPONSE_ERROR = "InvalidResponseError"
    NO_RESPONSE_ERROR      = "NoResponseError"
    LOCAL_ECHO_ERROR       = "LocalEchoError"
    ILLEGAL_REQUEST_ERROR  = "IllegalRequestError"
    IO_ERROR               = "IOError"
    SERIAL_ERROR           = "SerialException"
    TIMEOUT_ERROR          = "timeout"
    CONNECTION_ERROR       = "connection"
    CHECKSUM_ERROR         = "Checksum error in rtu mode"

    def description(self) -> str:
        return {
            ModbusExceptionType.MODBUS_EXCEPTION:       "General Modbus protocol exception",
            ModbusExceptionType.INVALID_RESPONSE_ERROR: "Invalid response from device",
            ModbusExceptionType.NO_RESPONSE_ERROR:      "No response from device",
            ModbusExceptionType.LOCAL_ECHO_ERROR:       "Local echo error in serial communication",
            ModbusExceptionType.ILLEGAL_REQUEST_ERROR:  "Illegal function request",
            ModbusExceptionType.IO_ERROR:               "Input/Output error",
            ModbusExceptionType.SERIAL_ERROR:           "Serial port error — port unavailable or misconfigured",
            ModbusExceptionType.TIMEOUT_ERROR:          "Communication timeout",
            ModbusExceptionType.CONNECTION_ERROR:       "Failed to establish connection",
            ModbusExceptionType.CHECKSUM_ERROR:         "Checksum error — data corruption detected",
        }.get(self, "Unknown Modbus exception")

    @classmethod
    def from_exception(cls, exc: Exception) -> "ModbusExceptionType":
        s, name = str(exc), type(exc).__name__
        if "Checksum error in rtu mode" in s: return cls.CHECKSUM_ERROR
        if "timeout"    in s.lower():         return cls.TIMEOUT_ERROR
        if "connection" in s.lower():         return cls.CONNECTION_ERROR
        for member in cls:
            if member.value in name:
                return member
        return cls.MODBUS_EXCEPTION