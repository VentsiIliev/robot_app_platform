from __future__ import annotations

import os

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.calibration.robot_calibration.config_helpers import (
    RobotCalibrationConfig,
    RobotCalibrationEventsConfig,
)
from src.engine.robot.calibration.robot_calibration_service import RobotCalibrationService
from src.shared_contracts.events.robot_events import RobotCalibrationTopics


class _CalibrationArtifactVisionProxy:
    """Delegate vision operations while routing calibration output to the selected profile."""

    def __init__(self, vision_service, settings_service):
        self._vision_service = vision_service
        self._settings_service = settings_service
        self._locked_matrix_path = None
        self._locked_target_area_id = None

    def __getattr__(self, name):
        return getattr(self._vision_service, name)

    @property
    def camera_to_robot_matrix_path(self) -> str:
        if self._locked_matrix_path is not None:
            return self._locked_matrix_path
        return self._resolve_matrix_path()

    def begin_calibration(self) -> None:
        if self._locked_matrix_path is not None:
            raise RuntimeError("A calibration artifact destination is already locked")
        self._locked_target_area_id = self._selected_target_area_id()
        self._locked_matrix_path = self._resolve_matrix_path(self._locked_target_area_id)

    def end_calibration(self) -> None:
        self._locked_matrix_path = None
        self._locked_target_area_id = None

    def get_calibration_target_area_id(self) -> str:
        if self._locked_target_area_id is None:
            return self._selected_target_area_id()
        return self._locked_target_area_id

    def _selected_target_area_id(self) -> str:
        settings = self._settings_service.get(CommonSettingsID.CALIBRATION_VISION_SETTINGS)
        return str(
            getattr(settings, "calibration_target_work_area", "global") or "global"
        ).strip()

    def _resolve_matrix_path(self, area_id=None) -> str:
        global_path = self._vision_service.camera_to_robot_matrix_path
        settings = self._settings_service.get(CommonSettingsID.CALIBRATION_VISION_SETTINGS)
        area_id = str(area_id or self._selected_target_area_id()).strip()
        if area_id == "global":
            return global_path
        profile_id = (getattr(settings, "work_area_calibration_profiles", {}) or {}).get(area_id)
        if not profile_id:
            raise RuntimeError(f"Calibration destination {area_id!r} has no assigned profile")
        if profile_id == "global":
            raise RuntimeError(
                f"Calibration destination {area_id!r} uses the shared global profile; "
                "assign a dedicated profile before calibrating this area"
            )
        profile = (getattr(settings, "coordinate_calibration_profiles", {}) or {}).get(profile_id)
        if profile is None:
            raise RuntimeError(f"Calibration profile {profile_id!r} is not defined")
        configured_path = str(getattr(profile, "matrix_path", "") or "").strip()
        if not configured_path:
            raise RuntimeError(f"Calibration profile {profile_id!r} has no matrix path")
        if os.path.isabs(configured_path):
            resolved = configured_path
        else:
            resolved = os.path.normpath(os.path.join(os.path.dirname(global_path), configured_path))
        parent = os.path.dirname(resolved)
        if parent:
            os.makedirs(parent, exist_ok=True)
        return resolved


def build_robot_system_calibration_service(robot_system) -> RobotCalibrationService:
    """Build a standard RobotCalibrationService from robot-system runtime state."""

    provider = robot_system.get_calibration_provider()
    if provider is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} requires a calibration provider "
            "to build the calibration service. Install a provider that implements "
            "build_calibration_navigation()."
        )

    calib_settings = getattr(robot_system, "_robot_calibration", None)
    if calib_settings is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build calibration service "
            "before robot calibration settings are loaded on robot_system._robot_calibration."
        )

    robot_settings = getattr(robot_system, "_robot_config", None)
    if robot_settings is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build calibration service "
            "before robot config is loaded on robot_system._robot_config."
        )

    robot_service = getattr(robot_system, "_robot", None)
    if robot_service is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build calibration service "
            "before the runtime robot service is loaded on robot_system._robot."
        )

    vision_service = getattr(robot_system, "_vision", None)
    if vision_service is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build calibration service "
            "without a runtime vision service on robot_system._vision. "
            "Declare IVisionService and ensure it is resolved before on_start() builds calibration."
        )
    height_service = getattr(robot_system, "_height_measuring_service", None)
    settings_service = getattr(robot_system, "_settings_service", None)
    if settings_service is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build calibration service "
            "without a settings service. Ensure SystemBuilder is used and settings_specs are declared."
        )
    messaging_service = getattr(robot_system, "_messaging_service", None)
    if messaging_service is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build calibration service "
            "without a messaging service. Ensure EngineContext and SystemBuilder wiring are used."
        )

    vision_calib_settings = settings_service.get(CommonSettingsID.CALIBRATION_VISION_SETTINGS)
    if vision_calib_settings is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build calibration service "
            "without calibration vision settings. Ensure CommonSettingsID.CALIBRATION_VISION_SETTINGS is declared and loaded."
        )

    calibration_vision_service = _CalibrationArtifactVisionProxy(
        vision_service,
        settings_service,
    )
    events_config = RobotCalibrationEventsConfig(
        broker=messaging_service,
        calibration_start_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_START,
        calibration_stop_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_STOP,
        calibration_image_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_IMAGE,
        calibration_log_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_LOG,
    )

    config = RobotCalibrationConfig(
        vision_service=calibration_vision_service,
        robot_service=robot_service,
        navigation_service=provider.build_calibration_navigation(
            calibration_target_area_id_getter=calibration_vision_service.get_calibration_target_area_id,
        ),
        height_measuring_service=height_service,
        required_ids=calib_settings.required_ids,
        candidate_ids=getattr(calib_settings, "candidate_ids", []),
        min_target_separation_px=float(getattr(calib_settings, "min_target_separation_px", 120.0)),
        homography_target_count=int(getattr(calib_settings, "homography_target_count", 16)),
        residual_target_count=int(getattr(calib_settings, "residual_target_count", 14)),
        validation_target_count=int(getattr(calib_settings, "validation_target_count", 6)),
        test_target_count=int(getattr(calib_settings, "test_target_count", 10)),
        auto_skip_known_unreachable_markers=bool(
            getattr(calib_settings, "auto_skip_known_unreachable_markers", True)
        ),
        unreachable_marker_failure_threshold=int(
            getattr(calib_settings, "unreachable_marker_failure_threshold", 1)
        ),
        known_unreachable_marker_ids=list(
            getattr(calib_settings, "known_unreachable_marker_ids", []) or []
        ),
        unreachable_marker_failure_counts=dict(
            getattr(calib_settings, "unreachable_marker_failure_counts", {}) or {}
        ),
        z_target=calib_settings.z_target,
        robot_tool=robot_settings.robot_tool,
        robot_user=robot_settings.robot_user,
        velocity=calib_settings.velocity,
        acceleration=calib_settings.acceleration,
        travel_velocity=int(getattr(calib_settings, "travel_velocity", calib_settings.velocity)),
        travel_acceleration=int(getattr(calib_settings, "travel_acceleration", calib_settings.acceleration)),
        iterative_velocity=int(getattr(calib_settings, "iterative_velocity", calib_settings.velocity)),
        iterative_acceleration=int(getattr(calib_settings, "iterative_acceleration", calib_settings.acceleration)),
        run_height_measurement=calib_settings.run_height_measurement,
        settings_service=settings_service,
        calibration_settings_key=CommonSettingsID.ROBOT_CALIBRATION,
        vision_calibration_settings_key=CommonSettingsID.CALIBRATION_VISION_SETTINGS,
        robot_config=robot_settings,
        robot_config_key=CommonSettingsID.ROBOT_CONFIG,
        camera_tcp_offset_config=calib_settings.camera_tcp_offset,
        axis_mapping_config=calib_settings.axis_mapping,
        chessboard_width=getattr(vision_calib_settings, "chessboard_width", None),
        chessboard_height=getattr(vision_calib_settings, "chessboard_height", None),
        chessboard_square_size_mm=getattr(vision_calib_settings, "square_size_mm", None),
        reference_board_mode=str(getattr(vision_calib_settings, "reference_board_mode", "auto") or "auto"),
        charuco_board_width=getattr(vision_calib_settings, "charuco_board_width", None),
        charuco_board_height=getattr(vision_calib_settings, "charuco_board_height", None),
        charuco_square_size_mm=getattr(vision_calib_settings, "charuco_square_size_mm", None),
        charuco_marker_size_mm=getattr(vision_calib_settings, "charuco_marker_size_mm", None),
        use_ransac=False,
        use_marker_centre=True,
        perspective_matrix=None,
    )

    return RobotCalibrationService(
        config=config,
        adaptive_config=calib_settings.adaptive_movement,
        events_config=events_config,
    )
