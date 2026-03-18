import logging

_logger = logging.getLogger(__name__)

from src.engine.robot.calibration.robot_calibration.RobotCalibrationContext import RobotCalibrationContext
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates


def handle_height_sample_state(context: RobotCalibrationContext):
    if not getattr(context, "run_height_measurement", True):
        _logger.info("Height measurement disabled for this robot calibration run — skipping height sample")
        return RobotCalibrationStates.DONE

    if context.height_measuring_service is None:
        _logger.warning("No HeightMeasuringService provided — skipping height sample")
        return RobotCalibrationStates.DONE

    _logger.info("Handling HEIGHT_SAMPLE state...")
    hms = context.height_measuring_service
    rs = context.calibration_robot_controller.robot_service
    current_position = rs.get_current_position()
    _logger.debug(f"Current Position: {current_position}")

    height_mm = hms.measure_at(current_position[0], current_position[1])

    if height_mm is None:
        _logger.warning("Height measurement returned None at position %s — skipping sample", current_position)
    else:
        sample = [current_position[0], current_position[1], height_mm]
        context.height_map_samples.append(sample)
        _logger.info(
            "Height sample #%d stored: x=%.3f y=%.3f z=%.4f mm",
            len(context.height_map_samples), sample[0], sample[1], sample[2],
        )

    return RobotCalibrationStates.DONE
