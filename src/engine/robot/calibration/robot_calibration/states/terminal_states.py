import logging

from src.engine.robot.calibration.robot_calibration.states.error_handling import (
    build_error_notification,
)
from src.engine.robot.calibration.robot_calibration.states.fallback_targets import (
    get_target_marker_ids,
)
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import (
    RobotCalibrationStates,
)
from src.engine.robot.calibration.robot_calibration.tcp_offset_capture import (
    finalize_tcp_offset_calibration,
)


_logger = logging.getLogger(__name__)


def handle_done_state(context) -> RobotCalibrationStates:
    target_ids = get_target_marker_ids(context)
    progress = context.progress
    current_marker_id = progress.current_marker_id
    if current_marker_id < len(target_ids) - 1:
        progress.current_marker_id += 1
        return RobotCalibrationStates.ALIGN_ROBOT

    if context.height_measuring_service and context.height_map_samples:
        _logger.info("Saving height map: %d samples", len(context.height_map_samples))
        context.height_measuring_service.save_height_map(context.height_map_samples)
    cfg = context.camera_tcp_offset_config
    if cfg is not None and getattr(cfg, "run_during_robot_calibration", False):
        ok, message = finalize_tcp_offset_calibration(context)
        if ok:
            _logger.info("Saved camera TCP offsets from main robot calibration: %s", message)
        else:
            _logger.warning("Camera TCP offset capture did not produce a saved result: %s", message)
    _logger.info("All markers processed. Calibration complete.")
    return RobotCalibrationStates.DONE


def handle_error_state(context) -> RobotCalibrationStates:
    progress = context.progress
    artifacts = context.artifacts
    error_message = context.calibration_error_message or "An unknown error occurred during calibration"

    _logger.error("CALIBRATION FAILED: %s", error_message)

    total_targets = len(get_target_marker_ids(context))
    _logger.error(
        "Calibration context: Current marker: %s/%s, Iteration: %s/%s, Markers successfully calibrated: %s",
        progress.current_marker_id,
        total_targets,
        progress.iteration_count,
        progress.max_iterations,
        len(artifacts.robot_positions_for_calibration),
    )

    if context.broadcast_events and context.broker and hasattr(context, "CALIBRATION_STOP_TOPIC"):
        try:
            context.broker.publish(context.CALIBRATION_STOP_TOPIC, build_error_notification(context))
            _logger.info("Error notification sent to UI via topic: %s", context.CALIBRATION_STOP_TOPIC)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            _logger.error("Failed to send error notification to UI: %s", exc)

    return RobotCalibrationStates.ERROR
