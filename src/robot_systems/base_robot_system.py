from __future__ import annotations

import logging
import os
import sys
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, Type, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from src.engine.repositories.interfaces import ISettingsSerializer, ISettingsRepository, ISettingsService
from src.engine.robot.targeting.jog_frame_pose_resolver import JogFramePoseResolver
from src.engine.robot.targeting.vision_target_resolver import VisionTargetResolver
from src.engine.vision.homography_transformer import HomographyTransformer
if TYPE_CHECKING:
    from src.engine.process.service_health_registry import ServiceHealthRegistry

# ---------------------------------------------------------------------------
# Metadata primitives
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FolderSpec:
    folder_id: int
    name: str
    display_name: str
    translation_key: str = ""

    def __post_init__(self):
        object.__setattr__(
            self, "translation_key",
            self.translation_key or f"folder.{self.name.lower()}"
        )


@dataclass(frozen=True)
class ApplicationSpec:
    name: str
    folder_id: int
    icon: str = "fa5s.cog"
    factory: Optional[Callable] = field(default=None, compare=False)
    app_id: str = ""    # stable snake_case key used in permissions — set once, never change

    def __post_init__(self):
        if not self.app_id:
            object.__setattr__(self, "app_id", self.name.lower().replace(" ", "_"))


@dataclass(frozen=True)
class ShellSetup:
    folders: List[FolderSpec] = field(default_factory=list)
    applications: List[ApplicationSpec] = field(default_factory=list)


@dataclass(frozen=True)
class RolePolicy:
    role_values: List[str] = field(default_factory=list)
    admin_role_value: str = "Admin"
    default_permission_role_values: List[str] = field(default_factory=list)
    protected_app_role_values: Dict[str, List[str]] = field(default_factory=dict)

    def __post_init__(self):
        role_values = [str(role) for role in self.role_values]
        admin_role_value = str(self.admin_role_value)
        default_roles = [str(role) for role in self.default_permission_role_values]
        protected = {
            str(app_id): [str(role) for role in role_values]
            for app_id, role_values in self.protected_app_role_values.items()
        }
        object.__setattr__(self, "role_values", role_values)
        object.__setattr__(self, "admin_role_value", admin_role_value)
        object.__setattr__(self, "default_permission_role_values", default_roles)
        object.__setattr__(self, "protected_app_role_values", protected)

        known_roles = set(role_values)
        if role_values and admin_role_value not in known_roles:
            raise ValueError(
                f"RolePolicy admin_role_value '{admin_role_value}' must be present in role_values"
            )
        if any(role not in known_roles for role in default_roles):
            raise ValueError("RolePolicy default_permission_role_values must all be present in role_values")
        for app_id, required_roles in protected.items():
            if any(role not in known_roles for role in required_roles):
                raise ValueError(
                    f"RolePolicy protected_app_role_values for '{app_id}' contains unknown roles"
                )


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    service_type: Type
    required: bool = True
    description: str = ""
    builder: Optional[Callable] = field(default=None, compare=False)



@dataclass(frozen=True)
class SystemMetadata:
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    settings_root: str = os.path.join("storage", "settings")  # base dir: "storage/settings/glue/" resolved at build time
    translations_root: str = os.path.join("storage", "translations")

@dataclass(frozen=True)
class SettingsSpec:
    name: str                          # key to retrieve via get_settings("robot_config")
    serializer: ISettingsSerializer    # knows the type, default, and how to serialize
    storage_key: str                   # relative filename: "robot/config.json"
    required: bool = True

# ---------------------------------------------------------------------------
# Base vision_service
# ---------------------------------------------------------------------------

class BaseRobotSystem(ABC):
    """
    Subclasses declare:
        metadata: SystemMetadata       — identity
        services: list[ServiceSpec] — required/optional service contracts

    Platform calls vision_service.start(services_dict) to resolve and inject.
    """

    metadata: ClassVar[SystemMetadata] = SystemMetadata(name="UnnamedSystem")
    services: ClassVar[List[ServiceSpec]] = []
    settings_specs: ClassVar[List[SettingsSpec]] = []
    shell: ClassVar[ShellSetup] = ShellSetup()
    role_policy: ClassVar[RolePolicy] = RolePolicy()

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._resolved: Dict[Enum, Any] = {}
        self._settings_service:  Optional[ISettingsService] = None
        self._messaging_service: Optional[Any] = None
        self._system_manager:    Optional[Any] = None
        self._health_registry:   Optional[Any] = None
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
        self.on_stop()
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
