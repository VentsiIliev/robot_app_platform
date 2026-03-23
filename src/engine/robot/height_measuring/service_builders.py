from __future__ import annotations

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.height_measuring.height_measuring_service import HeightMeasuringService
from src.engine.robot.height_measuring.laser_calibration_service import LaserCalibrationService
from src.engine.robot.height_measuring.laser_detection_service import LaserDetectionService
from src.engine.robot.height_measuring.laser_detector import LaserDetector


def build_robot_system_height_measuring_services(robot_system):
    """Build the standard height-measuring service trio for a robot system."""

    provider = robot_system.get_height_measuring_provider()
    if provider is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} requires a height-measuring provider "
            "to build height-measuring services. Install a provider that implements "
            "build_laser_control()."
        )

    settings = robot_system.get_settings(CommonSettingsID.HEIGHT_MEASURING_SETTINGS)
    robot_config = robot_system.get_settings(CommonSettingsID.ROBOT_CONFIG)
    calib_repo = robot_system.get_settings_repo(CommonSettingsID.HEIGHT_MEASURING_CALIBRATION)
    if calib_repo is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build height-measuring services "
            "without a repository for CommonSettingsID.HEIGHT_MEASURING_CALIBRATION."
        )
    depth_map_repo = robot_system.get_settings_repo(CommonSettingsID.DEPTH_MAP_DATA)
    if depth_map_repo is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build height-measuring services "
            "without a repository for CommonSettingsID.DEPTH_MAP_DATA."
        )

    robot_service = getattr(robot_system, "_robot", None)
    if robot_service is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build height-measuring services "
            "before the runtime robot service is loaded on robot_system._robot."
        )

    vision_service = getattr(robot_system, "_vision", None)
    if vision_service is None:
        raise RuntimeError(
            f"{robot_system.__class__.__name__} cannot build height-measuring services "
            "without a runtime vision service on robot_system._vision."
        )

    detector = LaserDetector(settings.detection)
    detection_svc = LaserDetectionService(
        detector=detector,
        laser=provider.build_laser_control(),
        vision_service=vision_service,
        config=settings.detection,
        exposure_control=vision_service,
    )
    calibration_svc = LaserCalibrationService(
        laser_service=detection_svc,
        robot_service=robot_service,
        repository=calib_repo,
        config=settings.calibration,
        tool=robot_config.robot_tool,
        user=robot_config.robot_user,
    )
    measuring_svc = HeightMeasuringService(
        laser_service=detection_svc,
        robot_service=robot_service,
        repository=calib_repo,
        config=settings.measuring,
        tool=robot_config.robot_tool,
        user=robot_config.robot_user,
        depth_map_repository=depth_map_repo,
    )
    return measuring_svc, calibration_svc, detection_svc
