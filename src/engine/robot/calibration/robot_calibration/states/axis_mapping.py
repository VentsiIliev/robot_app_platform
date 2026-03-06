import time
import logging

import numpy as np

from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates
from src.engine.robot.enums.axis import ImageAxis, Direction, ImageToRobotMapping, AxisMapping
from src.engine.robot.calibration.robot_calibration.states.state_result import StateResult

_logger = logging.getLogger(__name__)

wait_to_reach_position_flag = True # set to false only for testing # FIXME: set to true after testing
def handle_axis_mapping_state(system, calibration_vision, calibration_robot_controller,
                               axis_mapping_config=None,stop_event=None):
    try:
        mapping = auto_calibrate_image_to_robot_mapping(
            system, calibration_vision, calibration_robot_controller, axis_mapping_config, stop_event)

        return StateResult(success=True, message="Axis mapping calibration successful",
                           next_state=RobotCalibrationStates.LOOKING_FOR_CHESSBOARD, data=mapping)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return StateResult(success=False, message=f"Axis mapping calibration failed: {e}",
                           next_state=RobotCalibrationStates.ERROR, data=None)



def get_marker_position(system, calibration_vision, MARKER_ID, MAX_ATTEMPTS, stop_event=None):
    for _ in range(MAX_ATTEMPTS):
        if stop_event is not None and stop_event.is_set():
            raise RuntimeError("Calibration stopped by user")
        frame = system.get_latest_frame()
        if frame is None:
            continue
        result = calibration_vision.detect_specific_marker(frame, MARKER_ID)
        if result.found and result.aruco_ids is not None:
            ids = np.array(result.aruco_ids).flatten()
            if MARKER_ID in ids:
                idx = np.where(ids == MARKER_ID)[0][0]
                corner = result.aruco_corners[idx][0]
                corner = np.asarray(corner).flatten()
                x_px, y_px = float(corner[0]), float(corner[1])
                return x_px, y_px
    raise RuntimeError(f"Marker {MARKER_ID} not found during axis mapping.")



def auto_calibrate_image_to_robot_mapping(system, calibration_vision,
                                           calibration_robot_controller,
                                           axis_mapping_config=None,
                                          stop_event=None):
    from src.engine.robot.configuration import AxisMappingConfig
    cfg = axis_mapping_config or AxisMappingConfig()

    MARKER_ID = cfg.marker_id
    MOVE_MM = cfg.move_mm
    MAX_ATTEMPTS = cfg.max_attempts
    DELAY = cfg.delay_after_move_s

    def _check_stop():
        if stop_event is not None and stop_event.is_set():
            raise RuntimeError("Calibration stopped by user")

    _check_stop()
    before_x, before_y = get_marker_position(system, calibration_vision, MARKER_ID, MAX_ATTEMPTS)

    _check_stop()
    ret = calibration_robot_controller.move_x_relative(MOVE_MM, blocking=wait_to_reach_position_flag)

    if not ret:
        raise RuntimeError(f"Robot failed to move X {MOVE_MM}")

    time.sleep(DELAY)
    _check_stop()
    after_x, after_y = get_marker_position(system, calibration_vision, MARKER_ID, MAX_ATTEMPTS)
    dx_img_xmove = after_x - before_x
    dy_img_xmove = after_y - before_y

    _check_stop()
    calibration_robot_controller.move_x_relative(-MOVE_MM, blocking=wait_to_reach_position_flag)

    _check_stop()
    before_y_x, before_y_y = get_marker_position(system, calibration_vision, MARKER_ID, MAX_ATTEMPTS)
    ret = calibration_robot_controller.move_y_relative(-MOVE_MM, blocking=wait_to_reach_position_flag)
    if not ret:
        raise RuntimeError(f"Robot failed to move Y {-MOVE_MM}")

    time.sleep(DELAY)

    _check_stop()
    after_y_x, after_y_y = get_marker_position(system, calibration_vision, MARKER_ID, MAX_ATTEMPTS)
    dx_img_ymove = after_y_x - before_y_x
    dy_img_ymove = after_y_y - before_y_y

    _check_stop()
    calibration_robot_controller.move_y_relative(MOVE_MM, blocking=wait_to_reach_position_flag)

    def compute_axis_mapping(dx, dy, robot_move_mm):
        if abs(dx) > abs(dy):
            image_axis = ImageAxis.X
            img_delta = dx
        else:
            image_axis = ImageAxis.Y
            img_delta = dy
        direction = Direction.PLUS if robot_move_mm * img_delta < 0 else Direction.MINUS
        return image_axis, direction

    robot_x_image_axis, robot_x_direction = compute_axis_mapping(dx_img_xmove, dy_img_xmove, MOVE_MM)
    robot_y_image_axis, robot_y_direction = compute_axis_mapping(dx_img_ymove, dy_img_ymove, -MOVE_MM)

    image_to_robot_mapping = ImageToRobotMapping(
        robot_x=AxisMapping(image_axis=robot_x_image_axis, direction=robot_x_direction),
        robot_y=AxisMapping(image_axis=robot_y_image_axis, direction=robot_y_direction),
    )

    log_message = f"""
=== Axis Mapping Calibration Summary ===
Marker ID used: {MARKER_ID}
Movement distance (mm): {MOVE_MM}

-- Robot X Move (+X) --
Initial marker: (x={before_x:.2f}, y={before_y:.2f})
After move: (x={after_x:.2f}, y={after_y:.2f})
Image delta: dx={dx_img_xmove:.2f}, dy={dy_img_xmove:.2f}
Mapped to image axis: {robot_x_image_axis.name}
Direction: {robot_x_direction.name}

-- Robot Y Move (-Y) --
Initial marker: (x={before_y_x:.2f}, y={before_y_y:.2f})
After move: (x={after_y_x:.2f}, y={after_y_y:.2f})
Image delta: dx={dx_img_ymove:.2f}, dy={dy_img_ymove:.2f}
Mapped to image axis: {robot_y_image_axis.name}
Direction: {robot_y_direction.name}

Final Image-to-Robot Mapping Object:
Robot X: {image_to_robot_mapping.robot_x}
Robot Y: {image_to_robot_mapping.robot_y}
========================================
"""
    _logger.info(log_message)
    return image_to_robot_mapping
