from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.core.messaging_service import MessagingService

from src.engine.repositories.settings_service_factory import build_from_specs
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.features.tool_service import RobotToolService
from src.engine.robot.interfaces.i_motion_service import IMotionService
from src.engine.robot.interfaces.i_robot import IRobot
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.engine.robot.safety.safety_checker import SafetyChecker
from src.engine.robot.services.motion_service import MotionService
from src.engine.robot.services.robot_service import RobotService
from src.engine.robot.services.robot_state_manager import RobotStateManager
from src.engine.robot.services.robot_state_publisher import RobotStatePublisher
from src.robot_systems.base_robot_system import BaseRobotSystem

T = TypeVar("T", bound=BaseRobotSystem)
_LOGGER = logging.getLogger("SystemBuilder")


@dataclass
class _BuildContext:
    robot: IRobot
    motion: IMotionService
    settings: Any
    tool_changer: Any
    messaging_service: IMessagingService       # ← added


ServiceBuilderFn = Callable[[_BuildContext], Optional[Any]]


# ---------------------------------------------------------------------------
# Default builders
# ---------------------------------------------------------------------------

def _build_robot_service(ctx: _BuildContext) -> IRobotService:
    publisher = RobotStatePublisher(ctx.messaging_service)   # ← wired here
    state = RobotStateManager(ctx.robot, publisher=publisher)
    state.start_monitoring()
    return RobotService(motion=ctx.motion, robot=ctx.robot, state_provider=state)


def _build_navigation(ctx: _BuildContext) -> NavigationService:
    return NavigationService(motion=ctx.motion, settings_service=ctx.settings)


def _build_tool_service(ctx: _BuildContext) -> Optional[IToolService]:
    if ctx.tool_changer is None:
        _LOGGER.debug("IToolService declared but no tool_changer provided — skipping")
        return None
    if ctx.settings is None:
        _LOGGER.debug("IToolService declared but no settings provided — skipping")
        return None
    return RobotToolService(
        motion_service=ctx.motion,
        robot_config=ctx.settings.get_robot_config(),
        tool_changer=ctx.tool_changer,
    )


_DEFAULT_REGISTRY: Dict[Type, ServiceBuilderFn] = {
    IRobotService:     _build_robot_service,
    NavigationService: _build_navigation,
    IToolService:      _build_tool_service,
}


# ---------------------------------------------------------------------------
# SystemBuilder
# ---------------------------------------------------------------------------

class SystemBuilder:

    def __init__(self) -> None:
        self._robot: Optional[IRobot] = None
        self._settings: Any = None
        self._tool_changer: Any = None
        self._messaging_service: Optional[IMessagingService] = None   # ← no default
        self._registry: Dict[Type, ServiceBuilderFn] = dict(_DEFAULT_REGISTRY)

    def with_robot(self, robot: IRobot) -> SystemBuilder:
        self._robot = robot
        return self

    def with_settings(self, settings_service) -> SystemBuilder:
        self._settings = settings_service
        return self

    def with_tool_changer(self, tool_changer) -> SystemBuilder:
        self._tool_changer = tool_changer
        return self

    def with_messaging_service(self, messaging_service: IMessagingService) -> AppBuilder:
        self._messaging_service = messaging_service
        return self

    def register(self, service_type: Type, builder: ServiceBuilderFn) -> AppBuilder:
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

        settings_service = None
        if system_class.settings_specs:
            settings_service = build_from_specs(
                specs=system_class.settings_specs,
                settings_root=system_class.metadata.settings_root,
                system_class=system_class,
            )

        motion = MotionService(self._robot, SafetyChecker(self._settings))
        ctx = _BuildContext(
            robot=self._robot,
            motion=motion,
            settings=settings_service,
            tool_changer=self._tool_changer,
            messaging_service=self._messaging_service,
        )

        # merge app-level per-spec builders into registry (override defaults)
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
        from src.engine.application.application_manager import ApplicationManager
        application_manager = ApplicationManager(self._messaging_service)
        system.start(
            services,
            settings_service=settings_service,
            application_manager=application_manager,
        )
        return system


