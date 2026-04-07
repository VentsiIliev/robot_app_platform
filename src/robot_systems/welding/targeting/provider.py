from __future__ import annotations

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.height_measuring.height_correction_service import HeightCorrectionService
from src.engine.robot.targeting.robot_system_targeting_provider import RobotSystemTargetingProvider
from src.robot_systems.welding.targeting.frames import build_welding_target_frames
from src.robot_systems.welding.targeting.registry import build_welding_point_registry


class WeldingRobotSystemTargetingProvider(RobotSystemTargetingProvider):
    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def _settings_service(self):
        return getattr(self._robot_system, "_settings_service", None)

    def _robot_config(self):
        return getattr(self._robot_system, "_robot_config", None)

    def _targeting_settings(self):
        settings_service = self._settings_service()
        if settings_service is not None:
            return settings_service.get(CommonSettingsID.TARGETING)
        return getattr(self._robot_system, "_welding_targeting", None)

    def _frame_definitions(self):
        settings = self._targeting_settings()
        persisted_by_name = {
            str(frame.name).strip().lower(): frame
            for frame in ((settings.frames if settings is not None else None) or [])
        }
        merged = []
        for definition in self._robot_system.get_target_frame_definitions():
            persisted = persisted_by_name.get(str(definition.name).strip().lower())
            if persisted is None:
                merged.append(definition)
                continue
            merged.append(
                type(definition)(
                    name=definition.name,
                    work_area_id=definition.work_area_id,
                    source_navigation_group=persisted.source_navigation_group or definition.source_navigation_group,
                    target_navigation_group=persisted.target_navigation_group or definition.target_navigation_group,
                    use_height_correction=bool(persisted.use_height_correction),
                    display_name=definition.display_name,
                )
            )
        for name, persisted in persisted_by_name.items():
            if any(str(definition.name).strip().lower() == name for definition in merged):
                continue
            merged.append(persisted)
        return merged

    def _point_definitions(self):
        settings = self._targeting_settings()
        persisted_points = {
            str(point.name).strip().lower(): point
            for point in ((settings.points if settings is not None else None) or [])
        }
        point_definitions = []
        for definition in self._robot_system.get_target_point_definitions():
            persisted = persisted_points.get(str(definition.name).strip().lower())
            point_definitions.append(
                {
                    "name": definition.name,
                    "display_name": (
                        str(getattr(persisted, "display_name", "")).strip()
                        or str(definition.display_name or definition.name).strip()
                    ),
                    "x_mm": float(getattr(persisted, "x_mm", 0.0)),
                    "y_mm": float(getattr(persisted, "y_mm", 0.0)),
                }
            )
        for name, persisted in persisted_points.items():
            if any(str(item["name"]).strip().lower() == name for item in point_definitions):
                continue
            point_definitions.append(
                {
                    "name": persisted.name,
                    "display_name": str(persisted.display_name or persisted.name).strip(),
                    "x_mm": float(persisted.x_mm),
                    "y_mm": float(persisted.y_mm),
                }
            )
        return point_definitions

    def build_point_registry(self):
        return build_welding_point_registry(self._point_definitions())

    def build_frames(self):
        height_service = getattr(self._robot_system, "_height_measuring_service", None)
        height_correction = (
            (lambda area_id="": HeightCorrectionService(height_service, area_id=area_id))
            if height_service is not None else None
        )
        return build_welding_target_frames(
            self._frame_definitions(),
            getattr(self._robot_system, "_navigation", None),
            height_correction,
        )

    def get_frame_for_work_area(self, work_area_id: str):
        area_id = str(work_area_id or "").strip()
        if not area_id:
            return None
        for frame in self.build_frames().values():
            if frame.work_area_id == area_id:
                return frame
        return None

    def get_work_area_for_frame(self, frame_name: str) -> str | None:
        frame = self.build_frames().get(str(frame_name or "").strip().lower())
        if frame is None:
            return None
        return frame.work_area_id or None

    def get_target_options(self) -> list[tuple[str, str]]:
        return [
            (str(point["display_name"] or point["name"]), str(point["name"]))
            for point in self._point_definitions()
        ]

    def get_default_target_name(self) -> str:
        definitions = self._robot_system.get_target_point_definitions()
        if definitions:
            return str(definitions[0].name)
        points = self._point_definitions()
        if points:
            return str(points[0]["name"])
        return ""
