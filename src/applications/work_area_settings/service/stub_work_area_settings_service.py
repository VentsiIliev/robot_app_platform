from __future__ import annotations

import logging

from src.applications.work_area_settings.service.i_work_area_settings_service import (
    IWorkAreaSettingsService,
)

_logger = logging.getLogger(__name__)


class StubWorkAreaSettingsService(IWorkAreaSettingsService):
    def __init__(self) -> None:
        self._active_area_id = ""
        self._areas: dict[str, list[tuple[float, float]]] = {}

    def get_active_work_area_id(self) -> str:
        return self._active_area_id

    def set_active_work_area_id(self, area_id: str) -> None:
        self._active_area_id = str(area_id or "")
        _logger.info("StubWorkAreaSettingsService: active_area=%s", self._active_area_id)

    def save_work_area(
        self,
        area_key: str,
        normalized_points: list[tuple[float, float]],
    ) -> tuple[bool, str]:
        self._areas[str(area_key)] = list(normalized_points)
        _logger.info("StubWorkAreaSettingsService: save_work_area %s %s", area_key, normalized_points)
        return True, f"Stub: {area_key} saved"

    def get_work_area(
        self,
        area_key: str,
    ) -> tuple[bool, str, list[tuple[float, float]] | None]:
        _logger.info("StubWorkAreaSettingsService: get_work_area %s", area_key)
        return True, f"Stub: loaded {area_key}", self._areas.get(str(area_key))
