from enum import Enum


class ModbusExceptionType(Enum):
    MODBUS_EXCEPTION         = "ModbusException"
    INVALID_RESPONSE_ERROR   = "InvalidResponseError"
    NO_RESPONSE_ERROR        = "NoResponseError"
    LOCAL_ECHO_ERROR         = "LocalEchoError"
    ILLEGAL_REQUEST_ERROR    = "IllegalRequestError"
    IO_ERROR                 = "IOError"
    TIMEOUT_ERROR            = "timeout"
    CONNECTION_ERROR         = "connection"
    CHECKSUM_ERROR           = "Checksum error in rtu mode"

    def description(self) -> str:
        return {
            ModbusExceptionType.MODBUS_EXCEPTION:       "General Modbus protocol exception",
            ModbusExceptionType.INVALID_RESPONSE_ERROR: "Invalid response from device",
            ModbusExceptionType.NO_RESPONSE_ERROR:      "No response from device",
            ModbusExceptionType.LOCAL_ECHO_ERROR:       "Local echo error in serial communication",
            ModbusExceptionType.ILLEGAL_REQUEST_ERROR:  "Illegal function request",
            ModbusExceptionType.IO_ERROR:               "Input/Output error",
            ModbusExceptionType.TIMEOUT_ERROR:          "Communication timeout",
            ModbusExceptionType.CONNECTION_ERROR:       "Failed to establish connection",
            ModbusExceptionType.CHECKSUM_ERROR:         "Checksum error — data corruption detected",
        }.get(self, "Unknown Modbus exception")

    @classmethod
    def from_exception(cls, exc: Exception) -> "ModbusExceptionType":
        s     = str(exc)
        name  = type(exc).__name__
        if "Checksum error in rtu mode" in s:   return cls.CHECKSUM_ERROR
        if "timeout" in s.lower():              return cls.TIMEOUT_ERROR
        if "connection" in s.lower():           return cls.CONNECTION_ERROR
        for member in cls:
            if member.value in name:
                return member
        return cls.MODBUS_EXCEPTION


class MotorErrorCode(Enum):
    MOTOR_1_MISSING              = 11
    MOTOR_2_MISSING              = 21
    MOTOR_3_MISSING              = 31
    MOTOR_4_MISSING              = 41
    MOTOR_1_SHORT                = 12
    MOTOR_2_SHORT                = 22
    MOTOR_3_SHORT                = 32
    MOTOR_4_SHORT                = 42
    MOTOR_1_DRIVER_OVERHEAT      = 13
    MOTOR_2_DRIVER_OVERHEAT      = 23
    MOTOR_3_DRIVER_OVERHEAT      = 33
    MOTOR_4_DRIVER_OVERHEAT      = 43
    MOTOR_1_DRIVER_COMMUNICATION = 14
    MOTOR_2_DRIVER_COMMUNICATION = 24
    MOTOR_3_DRIVER_COMMUNICATION = 34
    MOTOR_4_DRIVER_COMMUNICATION = 44

    def description(self) -> str:
        return {
            MotorErrorCode.MOTOR_1_MISSING:              "Motor 1 missing",
            MotorErrorCode.MOTOR_2_MISSING:              "Motor 2 missing",
            MotorErrorCode.MOTOR_3_MISSING:              "Motor 3 missing",
            MotorErrorCode.MOTOR_4_MISSING:              "Motor 4 missing",
            MotorErrorCode.MOTOR_1_SHORT:                "Motor 1 short circuit",
            MotorErrorCode.MOTOR_2_SHORT:                "Motor 2 short circuit",
            MotorErrorCode.MOTOR_3_SHORT:                "Motor 3 short circuit",
            MotorErrorCode.MOTOR_4_SHORT:                "Motor 4 short circuit",
            MotorErrorCode.MOTOR_1_DRIVER_OVERHEAT:      "Motor 1 driver overheat",
            MotorErrorCode.MOTOR_2_DRIVER_OVERHEAT:      "Motor 2 driver overheat",
            MotorErrorCode.MOTOR_3_DRIVER_OVERHEAT:      "Motor 3 driver overheat",
            MotorErrorCode.MOTOR_4_DRIVER_OVERHEAT:      "Motor 4 driver overheat",
            MotorErrorCode.MOTOR_1_DRIVER_COMMUNICATION: "Motor 1 driver communication error",
            MotorErrorCode.MOTOR_2_DRIVER_COMMUNICATION: "Motor 2 driver communication error",
            MotorErrorCode.MOTOR_3_DRIVER_COMMUNICATION: "Motor 3 driver communication error",
            MotorErrorCode.MOTOR_4_DRIVER_COMMUNICATION: "Motor 4 driver communication error",
        }.get(self, "Unknown error")

    @classmethod
    def from_code(cls, code: int) -> "MotorErrorCode | None":
        try:
            return cls(code)
        except ValueError:
            return None