from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from threading import RLock
from typing import Callable

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

    def __init__(
        self,
        settings_service: ISettingsService,
        *,
        allowed_dropoff_strategies: tuple[str, ...] = (
            "movement_group",
            "plate_layout",
        ),
    ):
        self._settings_service = settings_service
        self._allowed_dropoff_strategies = tuple(allowed_dropoff_strategies)
        if not self._allowed_dropoff_strategies:
            raise ValueError("At least one dropoff strategy must be allowed")
        self._lock = RLock()
        self._snapshot: PaintProcessConfig = self._settings_service.get(SettingsID.PAINT_PROCESS_CONFIG)
        self._validate_dropoff_strategy(self._snapshot)
        self._change_listeners: list[Callable[[PaintProcessConfig], None]] = []

    def get_snapshot(self) -> PaintProcessConfig:
        with self._lock:
            return self._snapshot

    def reload(self) -> PaintProcessConfig:
        settings = self._settings_service.reload(SettingsID.PAINT_PROCESS_CONFIG)
        self._validate_dropoff_strategy(settings)
        with self._lock:
            self._snapshot = settings
            return self._snapshot

    def save(self, settings: PaintProcessConfig) -> None:
        self._validate_dropoff_strategy(settings)
        self._settings_service.save(SettingsID.PAINT_PROCESS_CONFIG, settings)
        with self._lock:
            self._snapshot = settings
            listeners = tuple(self._change_listeners)
        for listener in listeners:
            try:
                listener(settings)
            except Exception:
                logging.getLogger(__name__).exception(
                    "Paint process live-settings listener failed"
                )

    def _validate_dropoff_strategy(self, settings: PaintProcessConfig) -> None:
        strategy = str(settings.dropoff.strategy or "").strip().lower()
        if strategy not in self._allowed_dropoff_strategies:
            allowed = ", ".join(self._allowed_dropoff_strategies)
            raise ValueError(
                f"Dropoff strategy '{strategy}' is not available for this paint system. "
                f"Allowed strategies: {allowed}"
            )

    def add_change_listener(self, listener: Callable[[PaintProcessConfig], None]) -> None:
        """Notify a runtime consumer immediately after settings are saved in memory."""
        with self._lock:
            if listener not in self._change_listeners:
                self._change_listeners.append(listener)
