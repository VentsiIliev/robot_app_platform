from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock

from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.robot_systems.paint.component_ids import SettingsID
from src.robot_systems.paint.processes.paint.config import PaintProcessConfig


class IPaintProcessConfigService(ABC):
    @abstractmethod
    def get_snapshot(self) -> PaintProcessConfig: ...

    @abstractmethod
    def reload(self) -> PaintProcessConfig: ...

    @abstractmethod
    def save(self, settings: PaintProcessConfig) -> None: ...


class PaintProcessConfigService(IPaintProcessConfigService):
    """Runtime access point for persisted Paint process settings."""

    def __init__(self, settings_service: ISettingsService):
        self._settings_service = settings_service
        self._lock = RLock()
        self._snapshot: PaintProcessConfig = self._settings_service.get(SettingsID.PAINT_PROCESS_CONFIG)

    def get_snapshot(self) -> PaintProcessConfig:
        with self._lock:
            return self._snapshot

    def reload(self) -> PaintProcessConfig:
        settings = self._settings_service.reload(SettingsID.PAINT_PROCESS_CONFIG)
        with self._lock:
            self._snapshot = settings
            return self._snapshot

    def save(self, settings: PaintProcessConfig) -> None:
        self._settings_service.save(SettingsID.PAINT_PROCESS_CONFIG, settings)
        with self._lock:
            self._snapshot = settings
