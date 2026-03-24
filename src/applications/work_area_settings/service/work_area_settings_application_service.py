from __future__ import annotations

from src.applications.work_area_settings.service.i_work_area_settings_service import (
    IWorkAreaSettingsService,
)
from src.engine.vision.i_vision_service import IVisionService
from src.engine.work_areas.i_work_area_service import IWorkAreaService


class WorkAreaSettingsApplicationService(IWorkAreaSettingsService):
    def __init__(
        self,
        work_area_service: IWorkAreaService,
        vision_service: IVisionService | None = None,
    ) -> None:
        self._work_area_service = work_area_service
        self._vision_service = vision_service

    def get_active_work_area_id(self) -> str:
        return self._work_area_service.get_active_area_id() or ""

    def set_active_work_area_id(self, area_id: str) -> None:
        self._work_area_service.set_active_area_id(area_id)
        if self._vision_service is not None:
            self._vision_service.set_active_work_area(area_id)

    def save_work_area(
        self,
        area_key: str,
        normalized_points: list[tuple[float, float]],
    ) -> tuple[bool, str]:
        return self._work_area_service.save_work_area(area_key, normalized_points)

    def get_work_area(
        self,
        area_key: str,
    ) -> tuple[bool, str, list[tuple[float, float]] | None]:
        points = self._work_area_service.get_work_area(area_key)
        if points is None:
            return True, f"No saved points for {area_key}", None
        return True, f"Work area points retrieved for {area_key}", points
