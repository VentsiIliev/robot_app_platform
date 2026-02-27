from src.engine.hardware.motor.interfaces.i_motor_error_decoder import IMotorErrorDecoder
from src.robot_systems.glue.motor.glue_motor_error_codes import GlueMotorErrorCode


class GlueMotorErrorDecoder(IMotorErrorDecoder):
    """
    IMotorErrorDecoder for the Modbus motor controller board used in the
    glue robot system. Inject into build_modbus_motor_controller() when
    wiring the glue system's motor controller.
    """

    def decode(self, error_code: int) -> str:
        mc = GlueMotorErrorCode.from_code(error_code)
        return mc.description() if mc else f"unknown error code {error_code}"