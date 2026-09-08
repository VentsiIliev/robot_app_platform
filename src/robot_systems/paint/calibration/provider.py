from __future__ import annotations

from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.calibration.calibration_navigation_service import CalibrationNavigationService
from src.engine.robot.calibration.robot_system_calibration_provider import (
    RobotSystemCalibrationProvider,
)


class PaintRobotSystemCalibrationProvider(RobotSystemCalibrationProvider):
    """Paint adapter that supplies the paint-specific calibration move."""

    _CALIBRATION_AREA_ID = "paint"

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_calibration_navigation(self, calibration_target_area_id_getter=None):
        work_area_service = self._robot_system.get_service(CommonServiceID.WORK_AREAS)
        self._require_valid_area_id(self._CALIBRATION_AREA_ID)
        move_selection = {"area_id": ""}

        def selected_area_id() -> str:
            settings = self._robot_system._settings_service.get(
                CommonSettingsID.CALIBRATION_VISION_SETTINGS
            )
            selected_value = (
                calibration_target_area_id_getter()
                if calibration_target_area_id_getter is not None
                else getattr(settings, "calibration_target_work_area", "global")
            )
            selected = (
                str(selected_value or "global").strip()
                if isinstance(selected_value, str)
                else "global"
            )
            area_id = self._require_valid_area_id(
                self._CALIBRATION_AREA_ID if selected == "global" else selected
            )
            if selected != "global":
                profile_id = (getattr(settings, "work_area_calibration_profiles", {}) or {}).get(area_id)
                if not profile_id or profile_id == "global":
                    raise ValueError(
                        f"Calibration area {area_id!r} requires a dedicated assigned profile"
                    )
                profile = (getattr(settings, "coordinate_calibration_profiles", {}) or {}).get(profile_id)
                if profile is None:
                    raise ValueError(f"Calibration profile {profile_id!r} is not defined")
                target_frame = self._robot_system.get_target_frame_for_work_area(area_id)
                expected_reference = str(getattr(target_frame, "name", "") or "").strip().lower()
                actual_reference = str(
                    getattr(profile, "reference_frame", "") or ""
                ).strip().lower()
                if not expected_reference or actual_reference != expected_reference:
                    raise ValueError(
                        f"Calibration profile {profile_id!r} must reference frame "
                        f"{expected_reference!r} for area {area_id!r}"
                    )
            return area_id

        def selected_group() -> str:
            area_id = selected_area_id()
            move_selection["area_id"] = area_id
            movement_group = self._robot_system.get_observer_group_for_area(area_id)
            if not isinstance(movement_group, str) or not movement_group.strip():
                if area_id == self._CALIBRATION_AREA_ID:
                    return "CALIBRATION"
                raise ValueError(f"Calibration area {area_id!r} has no observer movement group")
            return movement_group.strip()

        def activate_selected_area() -> None:
            area_id = move_selection["area_id"] or selected_area_id()
            work_area_service.set_active_area_id(area_id)

        def verify_selected_area() -> None:
            area_id = move_selection["area_id"] or selected_area_id()
            work_area_service.mark_active_area_verified(area_id)

        return CalibrationNavigationService(
            self._robot_system.get_service(CommonServiceID.NAVIGATION),
            calibration_group_getter=selected_group,
            before_move=activate_selected_area,
            after_move=verify_selected_area,
        )

    def _require_valid_area_id(self, area_id: str) -> str:
        normalized = str(area_id or "").strip()
        declared_area_ids = {
            str(definition.id).strip()
            for definition in self._robot_system.get_work_area_definitions()
            if str(definition.id).strip()
        }
        if normalized not in declared_area_ids:
            raise ValueError(
                f"Calibration area '{normalized}' is not declared for "
                f"{self._robot_system.__class__.__name__}. "
                f"Declared areas: {sorted(declared_area_ids)}"
            )
        return normalized
