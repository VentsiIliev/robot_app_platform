import logging

from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import (
    RobotCalibrationStates,
)
from src.engine.robot.calibration.robot_calibration.tcp_offset_capture import (
    capture_tcp_offset_for_current_marker,
    should_capture_tcp_offset_for_current_marker,
)


_logger = logging.getLogger(__name__)


def handle_capture_tcp_offset_state(context) -> RobotCalibrationStates:
    if not should_capture_tcp_offset_for_current_marker(context):
        return RobotCalibrationStates.SAMPLE_HEIGHT
    if context.stop_event.is_set():
        return RobotCalibrationStates.CANCELLED
    ok = capture_tcp_offset_for_current_marker(context)
    if context.stop_event.is_set():
        return RobotCalibrationStates.CANCELLED
    if not ok:
        _logger.warning(
            "Skipping TCP offset capture for marker index %s: %s",
            context.progress.current_marker_id,
            context.calibration_error_message or "unknown TCP offset capture failure",
        )
    return RobotCalibrationStates.SAMPLE_HEIGHT
