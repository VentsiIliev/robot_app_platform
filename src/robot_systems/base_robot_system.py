from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional, Type, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from src.engine.repositories.interfaces import ISettingsSerializer, ISettingsRepository, ISettingsService
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


@dataclass(frozen=True)
class ShellSetup:
    folders: List[FolderSpec] = field(default_factory=list)
    applications: List[ApplicationSpec] = field(default_factory=list)


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