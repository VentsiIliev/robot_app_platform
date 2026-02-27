from enum import Enum


class GlueMotorErrorCode(Enum):
    """
    Error codes reported by the Modbus motor controller board used in the
    glue robot system. Specific to this board's firmware — do not use in
    generic motor logic.
    """
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
            GlueMotorErrorCode.MOTOR_1_MISSING:              "Motor 1 missing",
            GlueMotorErrorCode.MOTOR_2_MISSING:              "Motor 2 missing",
            GlueMotorErrorCode.MOTOR_3_MISSING:              "Motor 3 missing",
            GlueMotorErrorCode.MOTOR_4_MISSING:              "Motor 4 missing",
            GlueMotorErrorCode.MOTOR_1_SHORT:                "Motor 1 short circuit",
            GlueMotorErrorCode.MOTOR_2_SHORT:                "Motor 2 short circuit",
            GlueMotorErrorCode.MOTOR_3_SHORT:                "Motor 3 short circuit",
            GlueMotorErrorCode.MOTOR_4_SHORT:                "Motor 4 short circuit",
            GlueMotorErrorCode.MOTOR_1_DRIVER_OVERHEAT:      "Motor 1 driver overheat",
            GlueMotorErrorCode.MOTOR_2_DRIVER_OVERHEAT:      "Motor 2 driver overheat",
            GlueMotorErrorCode.MOTOR_3_DRIVER_OVERHEAT:      "Motor 3 driver overheat",
            GlueMotorErrorCode.MOTOR_4_DRIVER_OVERHEAT:      "Motor 4 driver overheat",
            GlueMotorErrorCode.MOTOR_1_DRIVER_COMMUNICATION: "Motor 1 driver communication error",
            GlueMotorErrorCode.MOTOR_2_DRIVER_COMMUNICATION: "Motor 2 driver communication error",
            GlueMotorErrorCode.MOTOR_3_DRIVER_COMMUNICATION: "Motor 3 driver communication error",
            GlueMotorErrorCode.MOTOR_4_DRIVER_COMMUNICATION: "Motor 4 driver communication error",
        }.get(self, "Unknown error")

    @classmethod
    def from_code(cls, code: int) -> "GlueMotorErrorCode | None":
        try:
            return cls(code)
        except ValueError:
            return None