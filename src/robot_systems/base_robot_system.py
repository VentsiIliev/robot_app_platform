from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Optional, Type, Callable
from dataclasses import dataclass, field
from typing import List
from src.engine.repositories.interfaces import ISettingsSerializer, ISettingsRepository, ISettingsService


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
class PluginSpec:
    name: str
    folder_id: int
    icon: str = "fa5s.cog"
    factory: Optional[Callable] = field(default=None, compare=False)


@dataclass(frozen=True)
class ShellSetup:
    folders: List[FolderSpec] = field(default_factory=list)
    plugins: List[PluginSpec] = field(default_factory=list)


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
# Base application
# ---------------------------------------------------------------------------

class BaseRobotSystem(ABC):
    """
    Subclasses declare:
        metadata: AppMetadata       — identity
        services: list[ServiceSpec] — required/optional service contracts

    Platform calls app.start(services_dict) to resolve and inject.
    """

    metadata: ClassVar[SystemMetadata] = SystemMetadata(name="UnnamedApp")
    services: ClassVar[List[ServiceSpec]] = []
    settings_specs: ClassVar[List[SettingsSpec]] = []
    shell: ClassVar[ShellSetup] = ShellSetup()

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._resolved: Dict[str, Any] = {}
        self._settings_service: Optional[ISettingsService] = None
        self._application_manager: Optional[Any] = None
        self._running = False

    @property
    def application_manager(self):
        return self._application_manager

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def get_settings(self, name: str) -> Any:
        if self._settings_service is None:
            raise RuntimeError(
                f"[{self.metadata.name}] No settings service available. "
                f"Ensure settings_specs are declared and AppBuilder is used."
            )
        return self._settings_service.get(name)

    def get_settings_repo(self, name: str) -> ISettingsRepository:
        if self._settings_service is None:
            raise RuntimeError(f"[{self.metadata.name}] No settings service available.")
        return self._settings_service.get_repo(name)

    # ------------------------------------------------------------------
    # Service accessors
    # ------------------------------------------------------------------

    def get_service(self, name: str) -> Any:
        service = self._resolved.get(name)
        if service is None:
            raise RuntimeError(
                f"[{self.metadata.name}] Service '{name}' not resolved. "
                f"Ensure it is declared in `services` and provided at startup."
            )
        return service

    def get_optional_service(self, name: str) -> Optional[Any]:
        return self._resolved.get(name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    # Update start() to also accept and store the settings service:
    def start(
            self,
            services: Dict[str, Any],
            settings_service: Optional[ISettingsService] = None,
            application_manager=None,
    ) -> None:
        self._logger.info("Starting %s v%s", self.metadata.name, self.metadata.version)
        self._settings_service = settings_service
        self._application_manager = application_manager
        self._validate_and_inject(services)
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
            f"App    : {cls.metadata.name} v{cls.metadata.version}",
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

    def _validate_and_inject(self, services: Dict[str, Any]) -> None:
        missing: List[str] = []

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