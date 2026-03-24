from __future__ import annotations
import logging
from typing import Iterable, Optional

import numpy as np

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.work_areas.i_work_area_service import IWorkAreaService
from src.shared_contracts.declarations import WorkAreaDefinition
from src.engine.work_areas.work_area_settings import (
    NormalizedPolygon,
    WorkAreaConfig,
    WorkAreaSettings,
)


class WorkAreaService(IWorkAreaService):
    def __init__(
        self,
        settings_service: ISettingsService,
        definitions: Iterable[WorkAreaDefinition] = (),
        default_active_area_id: str = "",
    ) -> None:
        self._settings = settings_service
        self._definitions = {definition.id: definition for definition in definitions}
        self._active_area_id = self._resolve_default_active_area(default_active_area_id)
        self._logger = logging.getLogger(self.__class__.__name__)

    def get_active_area_id(self) -> Optional[str]:
        # self._logger.debug(f"Active area: {self._active_area_id}")
        return self._active_area_id

    def set_active_area_id(self, area_id: str | None) -> None:
        if not area_id:
            self._active_area_id = None
            return
        area_id = str(area_id).strip()
        if not area_id:
            self._active_area_id = None
            return
        if self._definitions and area_id not in self._definitions:
            raise KeyError(
                f"Unknown work area '{area_id}'. Available: {sorted(self._definitions.keys())}"
            )
        self._active_area_id = area_id

    def get_area_config(self, area_id: str) -> WorkAreaConfig | None:
        if not area_id:
            return None
        settings = self._load()
        config = settings.areas.get(area_id)
        return config if config is not None else None

    def get_area_definition(self, area_id: str) -> WorkAreaDefinition | None:
        if not area_id:
            return None
        return self._definitions.get(area_id)

    def save_work_area(self, area_key: str, normalized_points: NormalizedPolygon) -> tuple[bool, str]:
        area_id, field_name = self._parse_area_key(area_key)
        if area_id is None or field_name is None:
            return False, f"Unknown work area key '{area_key}'"

        settings = self._load()
        config = settings.areas.get(area_id) or WorkAreaConfig()
        setattr(config, field_name, [list(point) for point in normalized_points])
        settings.areas[area_id] = config
        self._save(settings)
        return True, f"Saved {field_name} for {area_id}"

    def get_work_area(self, area_key: str) -> NormalizedPolygon | None:
        area_id, field_name = self._parse_area_key(area_key)
        if area_id is None or field_name is None:
            return None
        config = self.get_area_config(area_id)
        if config is None:
            return None
        points = getattr(config, field_name, None)
        return [list(point) for point in points] if points else None

    def get_detection_roi_pixels(self, area_id: str, width: int, height: int):
        return self._to_pixels(self.get_work_area(area_id), width, height)

    def get_brightness_roi_pixels(self, area_id: str, width: int, height: int):
        points = self.get_work_area(f"{area_id}__brightness")
        if not points:
            points = self.get_work_area(area_id)
        return self._to_pixels(points, width, height)

    def _resolve_default_active_area(self, default_active_area_id: str) -> Optional[str]:
        default_active_area_id = str(default_active_area_id or "").strip()
        if default_active_area_id:
            return default_active_area_id
        if self._definitions:
            return next(iter(self._definitions.keys()))
        return None

    def _load(self) -> WorkAreaSettings:
        return self._settings.get(CommonSettingsID.WORK_AREA_SETTINGS)

    def _save(self, settings: WorkAreaSettings) -> None:
        self._settings.save(CommonSettingsID.WORK_AREA_SETTINGS, settings)

    def _parse_area_key(self, area_key: str) -> tuple[str | None, str | None]:
        key = str(area_key or "").strip()
        if not key:
            return None, None

        suffix_map = {
            "__brightness": "brightness_roi",
            "__height_mapping": "height_mapping_roi",
        }
        for suffix, field_name in suffix_map.items():
            if key.endswith(suffix):
                area_id = key[: -len(suffix)]
                if self._definitions and area_id not in self._definitions:
                    return None, None
                return area_id, field_name

        if self._definitions and key not in self._definitions:
            return None, None
        return key, "detection_roi"

    @staticmethod
    def _to_pixels(points: NormalizedPolygon | None, width: int, height: int):
        if not points:
            return None
        return np.array(
            [(int(float(x) * float(width)), int(float(y) * float(height))) for x, y in points],
            dtype=np.float32,
        )
