from __future__ import annotations

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.calibration.robot_calibration.config_helpers import (
    RobotCalibrationConfig,
    RobotCalibrationEventsConfig,
)
from src.engine.robot.calibration.robot_calibration_service import RobotCalibrationService
from src.shared_contracts.events.robot_events import RobotCalibrationTopics


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

    events_config = RobotCalibrationEventsConfig(
        broker=messaging_service,
        calibration_start_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_START,
        calibration_stop_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_STOP,
        calibration_image_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_IMAGE,
        calibration_log_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_LOG,
    )

    config = RobotCalibrationConfig(
        vision_service=vision_service,
        robot_service=robot_service,
        navigation_service=provider.build_calibration_navigation(),
        height_measuring_service=height_service,
        required_ids=calib_settings.required_ids,
        z_target=calib_settings.z_target,
        robot_tool=robot_settings.robot_tool,
        robot_user=robot_settings.robot_user,
        velocity=calib_settings.velocity,
        acceleration=calib_settings.acceleration,
        run_height_measurement=calib_settings.run_height_measurement,
        settings_service=settings_service,
        calibration_settings_key=CommonSettingsID.ROBOT_CALIBRATION,
        robot_config=robot_settings,
        robot_config_key=CommonSettingsID.ROBOT_CONFIG,
        camera_tcp_offset_config=calib_settings.camera_tcp_offset,
        axis_mapping_config=calib_settings.axis_mapping,
        use_ransac=True,
        use_marker_centre=True,
    )

    return RobotCalibrationService(
        config=config,
        adaptive_config=calib_settings.adaptive_movement,
        events_config=events_config,
    )
