from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.core.messaging_service import MessagingService

from src.engine.repositories.settings_service_factory import build_from_specs
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.interfaces.i_motion_service import IMotionService
from src.engine.robot.interfaces.i_robot import IRobot
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.safety.safety_checker import SafetyChecker
from src.engine.robot.services.motion_service import MotionService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.engine.vision.i_vision_service import IVisionService
from src.robot_systems.base_robot_system import BaseRobotSystem
from src.robot_systems.default_service_builders import DEFAULT_SERVICE_BUILDERS

T = TypeVar("T", bound=BaseRobotSystem)
_LOGGER = logging.getLogger("SystemBuilder")


@dataclass
class _BuildContext:
    robot: IRobot
    motion: IMotionService
    settings: Any
    tool_changer: Any
    messaging_service: IMessagingService
    system_class: Type[BaseRobotSystem]


ServiceBuilderFn = Callable[[_BuildContext], Optional[Any]]


# ---------------------------------------------------------------------------
# SystemBuilder
# ---------------------------------------------------------------------------

class SystemBuilder:

    def __init__(self) -> None:
        self._robot: Optional[IRobot] = None
        self._settings: Any = None
        self._tool_changer: Any = None
        self._messaging_service: Optional[IMessagingService] = None   # ← no default
        self._registry: Dict[Type, ServiceBuilderFn] = dict(DEFAULT_SERVICE_BUILDERS)

    def with_robot(self, robot: IRobot) -> SystemBuilder:
        self._robot = robot
        return self

    def with_settings(self, settings_service) -> SystemBuilder:
        self._settings = settings_service
        return self

    def with_tool_changer(self, tool_changer) -> SystemBuilder:
        self._tool_changer = tool_changer
        return self

    def with_messaging_service(self, messaging_service: IMessagingService) -> SystemBuilder:
        self._messaging_service = messaging_service
        return self

    def register(self, service_type: Type, builder: ServiceBuilderFn) -> SystemBuilder:
        self._registry[service_type] = builder
        return self

    def build(self, system_class: Type[T]) -> T:
        if self._robot is None:
            raise ValueError("SystemBuilder.with_robot() is required")
        if self._messaging_service is None:
            raise ValueError(
                "SystemBuilder.with_messaging_service() is required — "
                "pass the IMessagingService from EngineContext"
            )

        _LOGGER.debug("Building %s", system_class.metadata.name)
        self._validate_default_service_requirements(system_class)

        settings_service = None
        if system_class.settings_specs:
            settings_service = build_from_specs(
                specs=system_class.settings_specs,
                settings_root=system_class.metadata.settings_root,
                system_class=system_class,
            )

        motion = MotionService(self._robot, SafetyChecker(CommonSettingsID.ROBOT_CONFIG, settings_service))
        ctx = _BuildContext(
            robot=self._robot,
            motion=motion,
            settings=settings_service,
            tool_changer=self._tool_changer,
            messaging_service=self._messaging_service,
            system_class=system_class,
        )

        # merge vision_service-level per-spec builders into registry (override defaults)
        registry = dict(self._registry)
        for spec in system_class.services:
            if spec.builder is not None:
                registry[spec.service_type] = spec.builder

        services: Dict[str, Any] = {}

        for spec in system_class.services:
            builder = registry.get(spec.service_type)

            if builder is None:
                if spec.required:
                    raise RuntimeError(
                        f"No builder registered for required service "
                        f"'{spec.name}' ({spec.service_type.__name__}). "
                        f"Use SystemBuilder.register() to add one."
                    )
                _LOGGER.debug("No builder for optional '%s' — skipping", spec.name)
                continue

            instance = builder(ctx)

            if instance is None:
                if spec.required:
                    raise RuntimeError(f"Builder for required service '{spec.name}' returned None.")
                _LOGGER.debug("Builder for optional '%s' returned None — skipping", spec.name)
                continue

            services[spec.name] = instance
            _LOGGER.debug("Built '%s' → %s", spec.name, type(instance).__name__)

        system = system_class()
        from src.engine.system.system_manager import SystemManager
        system_manager = SystemManager(self._messaging_service)
        system.start(
            services,
            settings_service  = settings_service,
            system_manager    = system_manager,
            messaging_service = self._messaging_service,
        )
        return system

    @staticmethod
    def _validate_default_service_requirements(system_class: Type[BaseRobotSystem]) -> None:
        declared_service_types = {spec.service_type for spec in system_class.services}
        declared_settings = {spec.name for spec in system_class.settings_specs}

        has_vision_service = IVisionService in declared_service_types
        has_vision_settings = CommonSettingsID.VISION_CAMERA_SETTINGS in declared_settings
        has_tool_service = IToolService in declared_service_types
        has_tool_settings = CommonSettingsID.TOOL_CHANGER_CONFIG in declared_settings
        has_robot_config = CommonSettingsID.ROBOT_CONFIG in declared_settings
        has_navigation_service = NavigationService in declared_service_types
        has_robot_calibration = CommonSettingsID.ROBOT_CALIBRATION in declared_settings
        has_height_settings = CommonSettingsID.HEIGHT_MEASURING_SETTINGS in declared_settings
        has_height_calibration = CommonSettingsID.HEIGHT_MEASURING_CALIBRATION in declared_settings
        has_depth_map = CommonSettingsID.DEPTH_MAP_DATA in declared_settings

        if has_vision_service and not has_vision_settings:
            raise RuntimeError(
                f"{system_class.__name__} declares IVisionService but does not declare "
                "CommonSettingsID.VISION_CAMERA_SETTINGS in settings_specs. "
                "Add the common camera settings spec or remove the IVisionService declaration."
            )
        if has_vision_settings and not has_vision_service:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.VISION_CAMERA_SETTINGS but does not declare "
                "IVisionService in services. Add the IVisionService ServiceSpec or remove the unused camera settings spec."
            )
        if has_tool_service and not has_tool_settings:
            raise RuntimeError(
                f"{system_class.__name__} declares IToolService but does not declare "
                "CommonSettingsID.TOOL_CHANGER_CONFIG in settings_specs. "
                "Add the common tool changer settings spec or remove the IToolService declaration."
            )
        if has_tool_service and not has_robot_config:
            raise RuntimeError(
                f"{system_class.__name__} declares IToolService but does not declare "
                "CommonSettingsID.ROBOT_CONFIG in settings_specs. "
                "The default tool builder requires robot configuration to resolve tool/user motion settings."
            )
        if has_tool_settings and not has_tool_service:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.TOOL_CHANGER_CONFIG but does not declare "
                "IToolService in services. Add the IToolService ServiceSpec or remove the unused tool changer settings spec."
            )
        if has_robot_calibration and not has_robot_config:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.ROBOT_CALIBRATION but does not declare "
                "CommonSettingsID.ROBOT_CONFIG in settings_specs. "
                "Robot calibration requires the common robot config for tool/user and TCP-offset persistence."
            )
        if has_robot_calibration and IRobotService not in declared_service_types:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.ROBOT_CALIBRATION but does not declare "
                "IRobotService in services. Robot calibration requires a robot service."
            )
        if has_robot_calibration and not has_vision_service:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.ROBOT_CALIBRATION but does not declare "
                "IVisionService in services. Robot calibration requires a vision service."
            )
        if has_robot_calibration and not has_navigation_service:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.ROBOT_CALIBRATION but does not declare "
                "NavigationService in services. Robot calibration requires navigation to the CALIBRATION group."
            )
        if has_height_settings and not has_robot_config:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.HEIGHT_MEASURING_SETTINGS but does not declare "
                "CommonSettingsID.ROBOT_CONFIG in settings_specs. "
                "Height measuring requires the common robot config for tool/user motion parameters."
            )
        if has_height_settings and IRobotService not in declared_service_types:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.HEIGHT_MEASURING_SETTINGS but does not declare "
                "IRobotService in services. Height measuring requires a robot service."
            )
        if has_height_settings and not has_height_calibration:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.HEIGHT_MEASURING_SETTINGS but does not declare "
                "CommonSettingsID.HEIGHT_MEASURING_CALIBRATION in settings_specs. "
                "The shared height-measuring builder requires persisted laser calibration data."
            )
        if has_height_settings and not has_depth_map:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.HEIGHT_MEASURING_SETTINGS but does not declare "
                "CommonSettingsID.DEPTH_MAP_DATA in settings_specs. "
                "The shared height-measuring builder requires persisted depth-map storage."
            )
        if has_height_settings and not has_vision_service:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.HEIGHT_MEASURING_SETTINGS but does not declare "
                "IVisionService in services. Height measuring requires a vision service."
            )
        if has_height_calibration and not has_height_settings:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.HEIGHT_MEASURING_CALIBRATION but does not declare "
                "CommonSettingsID.HEIGHT_MEASURING_SETTINGS in settings_specs. "
                "Add the common height-measuring settings spec or remove the unused calibration data spec."
            )
        if has_depth_map and not has_height_settings:
            raise RuntimeError(
                f"{system_class.__name__} declares CommonSettingsID.DEPTH_MAP_DATA but does not declare "
                "CommonSettingsID.HEIGHT_MEASURING_SETTINGS in settings_specs. "
                "Add the common height-measuring settings spec or remove the unused depth-map data spec."
            )
