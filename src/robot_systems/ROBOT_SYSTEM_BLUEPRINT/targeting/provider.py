from __future__ import annotations

from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.targeting.robot_system_targeting_provider import RobotSystemTargetingProvider
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.frames import build_my_target_frames
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.registry import build_my_point_registry


class MyRobotSystemTargetingProvider(RobotSystemTargetingProvider):
    """TODO: Build targeting runtime objects for the concrete robot system."""

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_point_registry(self):
        settings = self._robot_system.get_settings(CommonSettingsID.TARGETING)
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
        return build_my_point_registry(point_definitions)

    def _frame_definitions(self):
        settings = self._robot_system.get_settings(CommonSettingsID.TARGETING)
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

    def build_frames(self):
        navigation = self._robot_system.get_optional_service(CommonServiceID.NAVIGATION)
        return build_my_target_frames(self._frame_definitions(), navigation=navigation)

    def get_target_options(self) -> list[tuple[str, str]]:
        settings = self._robot_system.get_settings(CommonSettingsID.TARGETING)
        persisted_points = {
            str(point.name).strip().lower(): point
            for point in ((settings.points if settings is not None else None) or [])
        }
        options = []
        for definition in self._robot_system.get_target_point_definitions():
            persisted = persisted_points.get(str(definition.name).strip().lower())
            options.append(
                (
                    str(getattr(persisted, "display_name", "")).strip()
                    or str(definition.display_name or definition.name),
                    str(definition.name),
                )
            )
        return options

    def get_default_target_name(self) -> str:
        definitions = self._robot_system.get_target_point_definitions()
        if definitions:
            return str(definitions[0].name)
        return ""
