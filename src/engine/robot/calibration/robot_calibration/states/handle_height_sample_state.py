import logging

_logger = logging.getLogger(__name__)

from src.engine.robot.calibration.robot_calibration.RobotCalibrationContext import RobotCalibrationContext
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates


def handle_height_sample_state(context: RobotCalibrationContext):
    if context.height_measuring_service is None:
        _logger.warning("No HeightMeasuringService provided — skipping height sample")
        return RobotCalibrationStates.DONE

    _logger.info("Handling HEIGHT_SAMPLE state...")
    hms = context.height_measuring_service
    rs = context.calibration_robot_controller.robot_service
    current_position = rs.get_current_position()
    _logger.debug(f"Current Position: {current_position}")
    height_mm = hms.measure_at(current_position[0], current_position[1])
    _logger.info(f"Measured height at position {current_position}: {height_mm} mm")
    return RobotCalibrationStates.DONE