from __future__ import annotations

import logging
import os
import sys
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, TYPE_CHECKING
from src.engine.repositories.interfaces import ISettingsRepository, ISettingsService
from src.engine.robot.targeting.jog_frame_pose_resolver import JogFramePoseResolver
from src.engine.robot.targeting.vision_target_resolver import VisionTargetResolver
from src.engine.vision.homography_transformer import HomographyTransformer
from src.shared_contracts.declarations import (
    DispenseChannelDefinition,
    MovementGroupDefinition,
    RemoteTcpDefinition,
    RolePolicy,
    ServiceSpec,
    SettingsSpec,
    ShellSetup,
    SystemMetadata,
    TargetFrameDefinition,
    ToolDefinition,
    ToolSlotDefinition,
    WorkAreaDefinition,
    WorkAreaObserverBinding,
)
if TYPE_CHECKING:
    from src.engine.process.service_health_registry import ServiceHealthRegistry

# ---------------------------------------------------------------------------
# Base vision_service
# ---------------------------------------------------------------------------

class BaseRobotSystem(ABC):
    """
    Subclasses declare:
        metadata: SystemMetadata — identity
        services: list[ServiceSpec] — required/optional service contracts

    Platform calls vision_service.start(services_dict) to resolve and inject.
    """

    metadata: ClassVar[SystemMetadata] = SystemMetadata(name="UnnamedSystem")
    services: ClassVar[List[ServiceSpec]] = []
    settings_specs: ClassVar[List[SettingsSpec]] = []
    work_areas: ClassVar[List[WorkAreaDefinition]] = []
    movement_groups: ClassVar[List[MovementGroupDefinition]] = []
    dispense_channels: ClassVar[List[DispenseChannelDefinition]] = []
    tools: ClassVar[List[ToolDefinition]] = []
    tool_slots: ClassVar[List[ToolSlotDefinition]] = []
    target_points: ClassVar[List[RemoteTcpDefinition]] = []
    target_frames: ClassVar[List[TargetFrameDefinition]] = []
    work_area_observers: ClassVar[List[WorkAreaObserverBinding]] = []
    default_active_work_area_id: ClassVar[str] = ""
    shell: ClassVar[ShellSetup] = ShellSetup()
    role_policy: ClassVar[RolePolicy] = RolePolicy()

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._resolved: Dict[Enum, Any] = {}
        self._settings_service:  Optional[ISettingsService] = None
        self._messaging_service: Optional[Any] = None
        self._system_manager:    Optional[Any] = None
        self._health_registry:   Optional[Any] = None
        self._managed_resources: List[tuple[str, Any]] = []
        self._running = False

    @property
    def system_manager(self):
        return self._system_manager

    @property
    def health_registry(self):
        return self._health_registry
    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def get_settings(self, name: Enum) -> Any:
        if self._settings_service is None:
            raise RuntimeError(
                f"[{self.metadata.name}] No settings service available. "
                f"Ensure settings_specs are declared and SystemBuilder is used."
            )
        return self._settings_service.get(name)

    def get_settings_repo(self, name: Enum) -> ISettingsRepository:
        if self._settings_service is None:
            raise RuntimeError(f"[{self.metadata.name}] No settings service available.")
        return self._settings_service.get_repo(name)

    # ------------------------------------------------------------------
    # Service accessors
    # ------------------------------------------------------------------

    def get_service(self, name: Enum) -> Any:
        if not isinstance(name, Enum):
            raise TypeError(
              f"Service name must be an Enum value, got {type(name).__name__!r}. "
            )
        service = self._resolved.get(name)
        if service is None:
            raise RuntimeError(
                f"[{self.metadata.name}] Service '{name}' not resolved. "
                f"Ensure it is declared in `services` and provided at startup."
            )
        return service

    def get_optional_service(self, name: Enum) -> Optional[Any]:
        if not isinstance(name, Enum):
            raise TypeError(
                f"Service name must be an Enum value, got {type(name).__name__!r}. "
            )
        return self._resolved.get(name)

    def get_targeting_provider(self):
        return getattr(self, "_targeting_provider", None)

    def get_work_area_definitions(self) -> List[WorkAreaDefinition]:
        return list(self.__class__.work_areas)

    def get_movement_group_definitions(self) -> List[MovementGroupDefinition]:
        return list(self.__class__.movement_groups)

    def get_dispense_channel_definitions(self) -> List[DispenseChannelDefinition]:
        return list(self.__class__.dispense_channels)

    def get_dispense_channel_definition(self, channel_id: str) -> DispenseChannelDefinition | None:
        normalized = str(channel_id or "").strip()
        if not normalized:
            return None
        for definition in self.__class__.dispense_channels:
            if str(definition.id).strip() == normalized:
                return definition
        return None

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return list(self.__class__.tools)

    def get_tool_slot_definitions(self) -> List[ToolSlotDefinition]:
        return list(self.__class__.tool_slots)

    def get_tool_slot_definition(self, slot_id: int) -> ToolSlotDefinition | None:
        for definition in self.__class__.tool_slots:
            if int(definition.id) == int(slot_id):
                return definition
        return None

    def get_tool_slot_definition_for_tool(self, tool_id: int) -> ToolSlotDefinition | None:
        for definition in self.__class__.tool_slots:
            if definition.tool_id is not None and int(definition.tool_id) == int(tool_id):
                return definition
        return None

    def get_target_point_definitions(self) -> List[RemoteTcpDefinition]:
        return list(self.__class__.target_points)

    def get_target_point_definition(self, name: str) -> RemoteTcpDefinition | None:
        normalized = str(name or "").strip().lower()
        if not normalized:
            return None
        for definition in self.__class__.target_points:
            if str(definition.name).strip().lower() == normalized:
                return definition
        return None

    def get_target_frame_definitions(self) -> List[TargetFrameDefinition]:
        return list(self.__class__.target_frames)

    def get_target_frame_definition(self, name: str) -> TargetFrameDefinition | None:
        normalized = str(name or "").strip().lower()
        if not normalized:
            return None
        for definition in self.__class__.target_frames:
            if str(definition.name).strip().lower() == normalized:
                return definition
        return None

    def get_target_frame_for_work_area(self, work_area_id: str) -> TargetFrameDefinition | None:
        normalized = str(work_area_id or "").strip()
        if not normalized:
            return None
        for definition in self.__class__.target_frames:
            if str(definition.work_area_id).strip() == normalized:
                return definition
        return None

    def get_work_area_observer_bindings(self) -> List[WorkAreaObserverBinding]:
        return list(self.__class__.work_area_observers)

    def get_default_active_work_area_id(self) -> str:
        return str(self.__class__.default_active_work_area_id or "").strip()

    def get_observer_group_for_area(self, area_id: str) -> str | None:
        area_id = str(area_id or "").strip()
        if not area_id:
            return None
        for binding in self.__class__.work_area_observers:
            if binding.area_id == area_id:
                return binding.movement_group_id
        return None

    def get_observed_area_for_group(self, movement_group_id: str) -> str | None:
        movement_group_id = str(movement_group_id or "").strip()
        if not movement_group_id:
            return None
        for binding in self.__class__.work_area_observers:
            if binding.movement_group_id == movement_group_id:
                return binding.area_id
        return None

    def get_calibration_provider(self):
        return getattr(self, "_calibration_provider", None)

    def get_height_measuring_provider(self):
        return getattr(self, "_height_measuring_provider", None)

    def get_shared_vision_resolver(self):
        provider = self.get_targeting_provider()
        if provider is None:
            return None, None
        cached_transformer = getattr(self, "_vision_base_transformer", None)
        cached_resolver = getattr(self, "_vision_target_resolver", None)
        if cached_transformer is not None and cached_resolver is not None:
            return cached_transformer, cached_resolver
        transformer = self._build_shared_base_transformer()
        if transformer is None:
            return None, None
        tcp_x, tcp_y = self._get_camera_to_tcp_offsets()
        resolver = VisionTargetResolver(
            base_transformer=transformer,
            registry=provider.build_point_registry(),
            camera_to_tcp_x_offset=tcp_x,
            camera_to_tcp_y_offset=tcp_y,
            frames=provider.build_frames(),
        )
        self._vision_base_transformer = transformer
        self._vision_target_resolver = resolver
        return transformer, resolver

    def invalidate_shared_vision_resolver(self) -> None:
        self._vision_base_transformer = None
        self._vision_target_resolver = None

    def build_robot_system_jog_pose_resolver(self, reference_rz_provider=None):
        provider = self.get_targeting_provider()
        if provider is None:
            return None
        tcp_x, tcp_y = self._get_camera_to_tcp_offsets()
        return JogFramePoseResolver(
            registry=provider.build_point_registry(),
            camera_to_tcp_x_offset=tcp_x,
            camera_to_tcp_y_offset=tcp_y,
            reference_rz_provider=reference_rz_provider,
        )

    def _build_shared_base_transformer(self):
        vision_service = getattr(self, "_vision", None)
        if vision_service is None:
            return None
        robot_config = getattr(self, "_robot_config", None)
        if robot_config is None:
            return HomographyTransformer(vision_service.camera_to_robot_matrix_path)
        return HomographyTransformer(
            vision_service.camera_to_robot_matrix_path,
            camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", 0.0)),
            camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", 0.0)),
        )

    def _get_camera_to_tcp_offsets(self) -> tuple[float, float]:
        robot_config = getattr(self, "_robot_config", None)
        if robot_config is None:
            return 0.0, 0.0
        return (
            float(getattr(robot_config, "camera_to_tcp_x_offset", 0.0)),
            float(getattr(robot_config, "camera_to_tcp_y_offset", 0.0)),
        )

    @classmethod
    def package_root(cls) -> str:
        module = sys.modules.get(cls.__module__)
        module_file = getattr(module, "__file__", None)
        if not module_file:
            raise RuntimeError(f"[{cls.metadata.name}] Cannot resolve package root for '{cls.__module__}'")
        return os.path.dirname(os.path.abspath(module_file))

    @classmethod
    def storage_path(cls, *parts: str) -> str:
        return os.path.join(cls.package_root(), "storage", *parts)

    @classmethod
    def workpieces_storage_path(cls) -> str:
        return cls.storage_path("workpieces")

    @classmethod
    def users_storage_path(cls) -> str:
        return cls.storage_path("users", "users.csv")

    @classmethod
    def permissions_storage_path(cls) -> str:
        return cls.storage_path("settings", "permissions.json")

    # ------------------------------------------------------------------
    # Managed resources
    # ------------------------------------------------------------------

    def register_managed_resource(self, resource: Any, cleanup: Any = None) -> Any:
        """Register a generic runtime resource for automatic shutdown.

        Resources are cleaned up in reverse registration order after on_stop().
        If cleanup is provided it is called directly. Otherwise the resource is
        inspected for stop/close/disconnect in that order.
        """
        if resource is None:
            return None
        label = self._managed_resource_label(resource, cleanup)
        entry = (label, cleanup if cleanup is not None else resource)
        if entry not in self._managed_resources:
            self._managed_resources.append(entry)
        return resource

    def unregister_managed_resource(self, resource: Any) -> None:
        self._managed_resources = [
            entry
            for entry in self._managed_resources
            if entry[1] is not resource
        ]

    def _cleanup_managed_resources(self) -> None:
        for label, cleanup_target in reversed(self._managed_resources):
            try:
                self._cleanup_managed_resource(cleanup_target)
            except Exception:
                self._logger.exception(
                    "Managed resource cleanup failed for %s in %s",
                    label,
                    self.metadata.name,
                )
        self._managed_resources.clear()

    @staticmethod
    def _managed_resource_label(resource: Any, cleanup: Any) -> str:
        target = cleanup if cleanup is not None else resource
        if callable(target):
            return getattr(target, "__name__", repr(target))
        return type(target).__name__

    def _cleanup_managed_resource(self, resource: Any) -> None:
        if callable(resource):
            resource()
            return
        for method_name in ("stop", "close", "disconnect"):
            method = getattr(resource, method_name, None)
            if callable(method):
                method()
                return

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
            self,
            services:          Dict[str, Any],
            settings_service   = None,
            system_manager     = None,
            messaging_service  = None,
    ) -> None:
        self._logger.info("Starting %s v%s", self.metadata.name, self.metadata.version)
        self._settings_service  = settings_service
        self._messaging_service = messaging_service
        self._system_manager    = system_manager
        self._validate_and_inject(services)
        self._health_registry   = self._build_health_registry()
        self._running = True
        self.on_start()
        self._logger.info("%s started", self.metadata.name)

    def stop(self) -> None:
        if not self._running:
            return
        self._logger.info("Stopping %s", self.metadata.name)
        try:
            self.on_stop()
        finally:
            try:
                self._cleanup_managed_resources()
            finally:
                self._running = False
                self._logger.info("%s stopped", self.metadata.name)

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Abstract hooks
    # ------------------------------------------------------------------

    @abstractmethod
    def on_start(self) -> None:
        ...

    @abstractmethod
    def on_stop(self) -> None:
        ...

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @classmethod
    def describe(cls) -> str:
        lines = [
            f"System    : {cls.metadata.name} v{cls.metadata.version}",
            f"Desc   : {cls.metadata.description}",
            f"Author : {cls.metadata.author}",
            f"Storage: {cls.metadata.settings_root}/{cls.metadata.name.lower()}/",
            "Settings:",
        ]
        for spec in cls.settings_specs:
            tag = "required" if spec.required else "optional"
            lines.append(f"  [{tag}] {spec.name} → {spec.storage_key}")
        if not cls.settings_specs:
            lines.append("  (none declared)")
        lines.append("Services:")
        for spec in cls.services:
            tag = "required" if spec.required else "optional"
            lines.append(f"  [{tag}] {spec.name}: {spec.service_type.__name__}")
            if spec.description:
                lines.append(f"          ↳ {spec.description}")
        if not cls.services:
            lines.append("  (none declared)")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_health_registry(self) -> ServiceHealthRegistry:
        """
        Auto-derives a ServiceHealthRegistry from the vision_service's resolved services.
        Services implementing IHealthCheckable are registered via is_healthy().
        Services without health semantics are registered as always available.
        No manual wiring needed — the vision_service already owns the name → service mapping.
        """
        from src.engine.process.service_health_registry import ServiceHealthRegistry
        registry = ServiceHealthRegistry()
        for name, service in self._resolved.items():
            registry.register_service(name, service)
        return registry


    def _validate_and_inject(self, services: Dict[Enum, Any]) -> None:
        missing: List[Enum] = []

        for spec in self.services:
            provided = services.get(spec.name)

            if provided is None:
                if spec.required:
                    missing.append(spec.name)
                else:
                    self._logger.debug("Optional service '%s' not provided — skipping", spec.name)
                continue

            if not isinstance(provided, spec.service_type):
                raise TypeError(
                    f"[{self.metadata.name}] '{spec.name}' expected "
                    f"{spec.service_type.__name__}, got {type(provided).__name__}"
                )

            self._resolved[spec.name] = provided
            self._logger.debug("Injected '%s' (%s)", spec.name, type(provided).__name__)

        if missing:
            raise RuntimeError(
                f"[{self.metadata.name}] Cannot start — missing required services: {missing}"
            )
