from copy import deepcopy
import json

from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.robot_settings.model.mapper import RobotCalibrationMapper
from src.engine.robot.height_measuring.settings import HeightMeasuringModuleSettings
from src.engine.vision.calibration_vision_settings import (
    CalibrationVisionSettings,
    CoordinateCalibrationProfile,
)


class CalibrationSettingsMapper:

    @staticmethod
    def to_flat_dict(data: CalibrationSettingsData) -> dict:
        height = data.height
        detection = height.detection
        calibration = height.calibration
        measuring = height.measuring
        return {
            "calib_vision_chessboard_width": data.vision.chessboard_width,
            "calib_vision_chessboard_height": data.vision.chessboard_height,
            "calib_vision_square_size_mm": data.vision.square_size_mm,
            "calib_vision_reference_board_mode": data.vision.reference_board_mode,
            "calib_vision_charuco_board_width": data.vision.charuco_board_width,
            "calib_vision_charuco_board_height": data.vision.charuco_board_height,
            "calib_vision_charuco_square_size_mm": data.vision.charuco_square_size_mm,
            "calib_vision_charuco_marker_size_mm": data.vision.charuco_marker_size_mm,
            "calib_vision_skip_frames": data.vision.calibration_skip_frames,
            "coordinate_calibration_mode": data.vision.coordinate_calibration_mode,
            "calibration_target_work_area": data.vision.calibration_target_work_area,
            "coordinate_calibration_profiles": json.dumps(
                {
                    profile_id: {
                        "matrix_path": profile.matrix_path,
                        "reference_frame": profile.reference_frame,
                    }
                    for profile_id, profile in data.vision.coordinate_calibration_profiles.items()
                },
                sort_keys=True,
            ),
            "work_area_calibration_profiles": json.dumps(
                data.vision.work_area_calibration_profiles,
                sort_keys=True,
            ),
            **RobotCalibrationMapper.to_flat_dict(data.robot),
            "min_intensity": detection.min_intensity,
            "blur_kernel_size": int(detection.gaussian_blur_kernel[0]),
            "gaussian_blur_sigma": detection.gaussian_blur_sigma,
            "default_axis": detection.default_axis,
            "detection_delay_ms": detection.detection_delay_ms,
            "image_capture_delay_ms": detection.image_capture_delay_ms,
            "detection_samples": detection.detection_samples,
            "max_detection_retries": detection.max_detection_retries,
            "step_size_mm": calibration.step_size_mm,
            "num_iterations": calibration.num_iterations,
            "calibration_velocity": calibration.calibration_velocity,
            "calibration_acceleration": calibration.calibration_acceleration,
            "movement_threshold": calibration.movement_threshold,
            "movement_timeout": calibration.movement_timeout,
            "cal_delay_ms": calibration.delay_between_move_detect_ms,
            "calibration_max_attempts": calibration.calibration_max_attempts,
            "max_polynomial_degree": calibration.max_polynomial_degree,
            "measurement_velocity": measuring.measurement_velocity,
            "measurement_acceleration": measuring.measurement_acceleration,
            "measurement_threshold": measuring.measurement_threshold,
            "measurement_timeout": measuring.measurement_timeout,
            "meas_delay_ms": measuring.delay_between_move_detect_ms,
        }

    @staticmethod
    def from_flat_dict(flat: dict, base: CalibrationSettingsData) -> CalibrationSettingsData:
        vision = deepcopy(base.vision)
        vision.chessboard_width = int(flat.get("calib_vision_chessboard_width", vision.chessboard_width))
        vision.chessboard_height = int(flat.get("calib_vision_chessboard_height", vision.chessboard_height))
        vision.square_size_mm = float(flat.get("calib_vision_square_size_mm", vision.square_size_mm))
        vision.reference_board_mode = str(flat.get("calib_vision_reference_board_mode", vision.reference_board_mode))
        vision.charuco_board_width = int(flat.get("calib_vision_charuco_board_width", vision.charuco_board_width))
        vision.charuco_board_height = int(flat.get("calib_vision_charuco_board_height", vision.charuco_board_height))
        vision.charuco_square_size_mm = float(
            flat.get("calib_vision_charuco_square_size_mm", vision.charuco_square_size_mm)
        )
        vision.charuco_marker_size_mm = float(
            flat.get("calib_vision_charuco_marker_size_mm", vision.charuco_marker_size_mm)
        )
        vision.calibration_skip_frames = int(
            flat.get("calib_vision_skip_frames", vision.calibration_skip_frames)
        )
        mode = str(flat.get("coordinate_calibration_mode", vision.coordinate_calibration_mode)).strip().lower()
        if mode not in {"global", "per_area"}:
            raise ValueError("Coordinate calibration mode must be 'global' or 'per_area'")
        vision.coordinate_calibration_mode = mode
        vision.calibration_target_work_area = str(
            flat.get("calibration_target_work_area", vision.calibration_target_work_area)
            or "global"
        ).strip()
        raw_profiles = CalibrationSettingsMapper._parse_json_object(
            flat.get("coordinate_calibration_profiles"),
            "Coordinate calibration profiles",
        )
        raw_assignments = CalibrationSettingsMapper._parse_json_object(
            flat.get("work_area_calibration_profiles"),
            "Work-area calibration profiles",
        )
        vision.coordinate_calibration_profiles = {
            str(profile_id).strip(): CoordinateCalibrationProfile(
                matrix_path=str(profile.get("matrix_path", "")).strip(),
                reference_frame=str(profile.get("reference_frame", "calibration")).strip().lower(),
            )
            for profile_id, profile in raw_profiles.items()
            if str(profile_id).strip() and isinstance(profile, dict)
        }
        vision.work_area_calibration_profiles = {
            str(area_id).strip(): str(profile_id).strip()
            for area_id, profile_id in raw_assignments.items()
            if str(area_id).strip() and str(profile_id).strip()
        }

        robot = RobotCalibrationMapper.from_flat_dict(flat, base.robot)

        height: HeightMeasuringModuleSettings = deepcopy(base.height)
        height.detection.min_intensity = float(flat.get("min_intensity", height.detection.min_intensity))
        kernel = int(flat.get("blur_kernel_size", height.detection.gaussian_blur_kernel[0]))
        height.detection.gaussian_blur_kernel = (kernel, kernel)
        height.detection.gaussian_blur_sigma = float(
            flat.get("gaussian_blur_sigma", height.detection.gaussian_blur_sigma)
        )
        height.detection.default_axis = str(flat.get("default_axis", height.detection.default_axis))
        height.detection.detection_delay_ms = int(
            flat.get("detection_delay_ms", height.detection.detection_delay_ms)
        )
        height.detection.image_capture_delay_ms = int(
            flat.get("image_capture_delay_ms", height.detection.image_capture_delay_ms)
        )
        height.detection.detection_samples = int(
            flat.get("detection_samples", height.detection.detection_samples)
        )
        height.detection.max_detection_retries = int(
            flat.get("max_detection_retries", height.detection.max_detection_retries)
        )

        height.calibration.step_size_mm = float(flat.get("step_size_mm", height.calibration.step_size_mm))
        height.calibration.num_iterations = int(flat.get("num_iterations", height.calibration.num_iterations))
        height.calibration.calibration_velocity = float(
            flat.get("calibration_velocity", height.calibration.calibration_velocity)
        )
        height.calibration.calibration_acceleration = float(
            flat.get("calibration_acceleration", height.calibration.calibration_acceleration)
        )
        height.calibration.movement_threshold = float(
            flat.get("movement_threshold", height.calibration.movement_threshold)
        )
        height.calibration.movement_timeout = float(
            flat.get("movement_timeout", height.calibration.movement_timeout)
        )
        height.calibration.delay_between_move_detect_ms = int(
            flat.get("cal_delay_ms", height.calibration.delay_between_move_detect_ms)
        )
        height.calibration.calibration_max_attempts = int(
            flat.get("calibration_max_attempts", height.calibration.calibration_max_attempts)
        )
        height.calibration.max_polynomial_degree = int(
            flat.get("max_polynomial_degree", height.calibration.max_polynomial_degree)
        )

        height.measuring.measurement_velocity = float(
            flat.get("measurement_velocity", height.measuring.measurement_velocity)
        )
        height.measuring.measurement_acceleration = float(
            flat.get("measurement_acceleration", height.measuring.measurement_acceleration)
        )
        height.measuring.measurement_threshold = float(
            flat.get("measurement_threshold", height.measuring.measurement_threshold)
        )
        height.measuring.measurement_timeout = float(
            flat.get("measurement_timeout", height.measuring.measurement_timeout)
        )
        height.measuring.delay_between_move_detect_ms = int(
            flat.get("meas_delay_ms", height.measuring.delay_between_move_detect_ms)
        )

        return CalibrationSettingsData(vision=vision, robot=robot, height=height)

    @staticmethod
    def _parse_json_object(value, label: str) -> dict:
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(str(value or "{}"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{label} must be a JSON object")
        return parsed
