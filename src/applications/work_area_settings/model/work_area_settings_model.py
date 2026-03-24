from __future__ import annotations

from src.applications.base.i_application_model import IApplicationModel
from src.applications.work_area_settings.service.i_work_area_settings_service import (
    IWorkAreaSettingsService,
)


class WorkAreaSettingsModel(IApplicationModel):
    def __init__(self, service: IWorkAreaSettingsService):
        self._service = service
        self._active_area_id = ""

    def load(self) -> str:
        self._active_area_id = self._service.get_active_work_area_id()
        return self._active_area_id

    def save(self, area_id: str) -> None:
        self._active_area_id = str(area_id or "")
        self._service.set_active_work_area_id(self._active_area_id)

    def get_active_work_area_id(self) -> str:
        return self._active_area_id or self._service.get_active_work_area_id()

    def set_active_work_area_id(self, area_id: str) -> None:
        self._active_area_id = str(area_id or "")
        self._service.set_active_work_area_id(area_id)

    def save_work_area(self, area_key: str, normalized_points: list) -> tuple[bool, str]:
        return self._service.save_work_area(area_key, normalized_points)

    def get_work_area(self, area_key: str) -> list[tuple[float, float]]:
        ok, _, normalized_points = self._service.get_work_area(area_key)
        if not ok or normalized_points is None:
            return []
        return [(float(x), float(y)) for x, y in normalized_points]
