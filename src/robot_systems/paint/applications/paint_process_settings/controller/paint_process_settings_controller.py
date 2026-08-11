from PyQt6.QtCore import QCoreApplication

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.styled_message_box import show_warning
from src.robot_systems.paint.applications.paint_process_settings.mapper import (
    PaintProcessSettingsMapper,
)
from src.robot_systems.paint.applications.paint_process_settings.model.paint_process_settings_model import (
    PaintProcessSettingsModel,
)
from src.robot_systems.paint.applications.paint_process_settings.view.paint_process_settings_view import (
    PaintProcessSettingsView,
)


class PaintProcessSettingsController(IApplicationController, BackgroundWorker):
    def __init__(self, model: PaintProcessSettingsModel, view: PaintProcessSettingsView):
        BackgroundWorker.__init__(self)
        self._model = model
        self._view = view
        self._reverting_invalid_dropoff_strategy = False
        self._reverting_invalid_safe_travel = False

    def load(self) -> None:
        settings = self._model.load()
        self._view.set_values(PaintProcessSettingsMapper.to_flat_dict(settings))
        self._view.value_changed.connect(self._on_value_changed)
        self._view.save_requested.connect(self._on_save)
        self._view.set_safe_travel_current_requested.connect(self._on_set_safe_travel_current)
        self._view.set_dropoff_safe_travel_current_requested.connect(self._on_set_dropoff_safe_travel_current)
        self._view.move_to_safe_travel_waypoint_requested.connect(self._on_move_to_safe_travel_waypoint)

    def stop(self) -> None:
        self._stop_threads()
        try:
            self._view.value_changed.disconnect(self._on_value_changed)
        except Exception:
            pass
        try:
            self._view.save_requested.disconnect(self._on_save)
        except Exception:
            pass
        try:
            self._view.set_safe_travel_current_requested.disconnect(self._on_set_safe_travel_current)
        except Exception:
            pass
        try:
            self._view.set_dropoff_safe_travel_current_requested.disconnect(self._on_set_dropoff_safe_travel_current)
        except Exception:
            pass
        try:
            self._view.move_to_safe_travel_waypoint_requested.disconnect(self._on_move_to_safe_travel_waypoint)
        except Exception:
            pass

    def _on_save(self, flat: dict) -> None:
        if not self._dropoff_strategy_is_allowed(flat):
            self._reject_movement_group_dropoff()
            return
        if not self._safe_travel_is_allowed(flat):
            self._reject_safe_travel_pose()
            return
        if not self._dropoff_safe_travel_is_allowed(flat):
            self._reject_dropoff_safe_travel_pose()
            return
        updated = PaintProcessSettingsMapper.from_flat_dict(flat, self._model.current_settings)
        self._model.save(updated)
        self._view.set_status(self._t("Saved. Changes will be used by the next Paint cycle."))

    def _on_value_changed(self, key: str, value: object) -> None:
        if self._reverting_invalid_safe_travel:
            return
        if key == "safe_travel_enabled" and bool(value):
            if not self._safe_travel_is_allowed(self._view.values()):
                self._reject_safe_travel_pose()
            return
        if key == "dropoff_safe_travel_enabled" and bool(value):
            if not self._dropoff_safe_travel_is_allowed(self._view.values()):
                self._reject_dropoff_safe_travel_pose()
            return
        if self._reverting_invalid_dropoff_strategy:
            return
        if key != "dropoff_strategy" or str(value).strip().lower() != "movement_group":
            return
        if self._model.is_dropoff_movement_group_configured():
            return
        self._reject_movement_group_dropoff()

    def _dropoff_strategy_is_allowed(self, flat: dict) -> bool:
        strategy = str(flat.get("dropoff_strategy", self._model.current_settings.dropoff.strategy)).strip().lower()
        return strategy != "movement_group" or self._model.is_dropoff_movement_group_configured()

    def _safe_travel_is_allowed(self, flat: dict) -> bool:
        if not bool(flat.get("safe_travel_enabled", self._model.current_settings.safe_travel.enabled)):
            return True
        return bool(self._normalize_poses(flat.get("safe_travel_positions", [])))

    def _dropoff_safe_travel_is_allowed(self, flat: dict) -> bool:
        if not bool(
            flat.get(
                "dropoff_safe_travel_enabled",
                self._model.current_settings.dropoff_safe_travel.enabled,
            )
        ):
            return True
        return bool(self._normalize_poses(flat.get("dropoff_safe_travel_positions", [])))

    def _reject_movement_group_dropoff(self) -> None:
        reason = self._model.dropoff_movement_group_configuration_error()
        message = self._t(
            "Set and save the Dropoff movement group in Robot Settings before using movement-group dropoff."
        )
        if reason:
            message = f"{message}\n\n{self._t('Reason')}: {reason}"
        show_warning(
            self._view,
            self._t("Dropoff Not Configured"),
            message,
        )
        flat = PaintProcessSettingsMapper.to_flat_dict(self._model.current_settings)
        if not self._model.is_dropoff_movement_group_configured():
            flat["dropoff_strategy"] = "pickup_origin"
        self._reverting_invalid_dropoff_strategy = True
        try:
            self._view.set_values(flat)
        finally:
            self._reverting_invalid_dropoff_strategy = False
        self._view.set_status(reason or self._t("Dropoff movement group is not configured."))

    def _on_set_safe_travel_current(self) -> None:
        position = self._model.get_current_robot_position()
        if position is None:
            show_warning(
                self._view,
                self._t("Robot Position Not Available"),
                self._t("Could not read the current robot position for the safe travel pose."),
            )
            return
        self._view.set_safe_travel_position(position)
        self._view.set_status(
            self._t("Safe travel pose set. Waypoint added from current robot position. Save settings to keep it.")
        )

    def _on_set_dropoff_safe_travel_current(self) -> None:
        position = self._model.get_current_robot_position()
        if position is None:
            show_warning(
                self._view,
                self._t("Robot Position Not Available"),
                self._t("Could not read the current robot position for the paint-to-dropoff safe travel pose."),
            )
            return
        self._view.set_dropoff_safe_travel_position(position)
        self._view.set_status(
            self._t("Paint-to-dropoff safe travel pose set. Waypoint added from current robot position. Save settings to keep it.")
        )

    def _on_move_to_safe_travel_waypoint(self, waypoint: dict) -> None:
        normalized = self._normalize_waypoint(waypoint)
        if normalized is None:
            show_warning(
                self._view,
                self._t("Safe Travel Waypoint Invalid"),
                self._t("The selected safe travel waypoint is not valid."),
            )
            return
        self._view.set_status(self._t("Moving to selected safe travel waypoint..."))
        self._run_in_thread(
            fn=lambda: self._model.move_to_waypoint(normalized),
            on_done=self._on_move_to_safe_travel_done,
            on_error=self._on_move_to_safe_travel_failed,
        )

    def _on_move_to_safe_travel_done(self, success: bool) -> None:
        if bool(success):
            self._view.set_status(self._t("Moved to selected safe travel waypoint."))
            return
        show_warning(
            self._view,
            self._t("Move Failed"),
            self._t("Robot move to the selected safe travel waypoint failed."),
        )
        self._view.set_status(self._t("Move to selected safe travel waypoint failed."))

    def _on_move_to_safe_travel_failed(self, message: str) -> None:
        show_warning(
            self._view,
            self._t("Move Failed"),
            message or self._t("Robot move to the selected safe travel waypoint failed."),
        )
        self._view.set_status(self._t("Move to selected safe travel waypoint failed."))

    def _reject_safe_travel_pose(self) -> None:
        show_warning(
            self._view,
            self._t("Safe Travel Waypoints Not Set"),
            self._t(
                "Add at least one safe travel waypoint before enabling calibration-to-paint safe travel."
            ),
        )
        flat = PaintProcessSettingsMapper.to_flat_dict(self._model.current_settings)
        flat["safe_travel_enabled"] = False
        self._reverting_invalid_safe_travel = True
        try:
            self._view.set_values(flat)
        finally:
            self._reverting_invalid_safe_travel = False
        self._view.set_status(self._t("Safe travel pose is not set. Add at least one waypoint."))

    def _reject_dropoff_safe_travel_pose(self) -> None:
        show_warning(
            self._view,
            self._t("Paint-to-Dropoff Safe Travel Waypoints Not Set"),
            self._t(
                "Add at least one paint-to-dropoff safe travel waypoint before enabling paint-to-dropoff safe travel."
            ),
        )
        flat = PaintProcessSettingsMapper.to_flat_dict(self._model.current_settings)
        flat["dropoff_safe_travel_enabled"] = False
        self._reverting_invalid_safe_travel = True
        try:
            self._view.set_values(flat)
        finally:
            self._reverting_invalid_safe_travel = False
        self._view.set_status(self._t("Paint-to-dropoff safe travel pose is not set. Add at least one waypoint."))

    @staticmethod
    def _normalize_pose(value: object) -> list[float] | None:
        if isinstance(value, dict):
            value = value.get("position", value.get("pose", []))
        if isinstance(value, str):
            parts = [part.strip() for part in value.replace("[", "").replace("]", "").split(",")]
        else:
            try:
                parts = list(value)
            except TypeError:
                return None
        try:
            pose = [float(part) for part in parts[:6]]
        except (TypeError, ValueError):
            return None
        return pose if len(pose) >= 6 else None

    @classmethod
    def _normalize_waypoint(cls, value: object) -> dict | None:
        pose = cls._normalize_pose(value)
        if pose is None:
            return None
        if isinstance(value, dict):
            try:
                vel = float(value.get("vel_percent", 0.0))
                acc = float(value.get("acc_percent", 0.0))
                blend_r = float(value.get("blendR", value.get("blend_r", 0.0)))
            except (TypeError, ValueError):
                return None
        else:
            try:
                raw = list(value)
                vel = float(raw[6]) if len(raw) >= 8 else 50.0
                acc = float(raw[7]) if len(raw) >= 8 else 20.0
                blend_r = float(raw[9]) if len(raw) >= 10 else 0.0
            except (TypeError, ValueError):
                vel = 50.0
                acc = 20.0
                blend_r = 0.0
        if not 0.0 <= vel <= 100.0 or not 0.0 <= acc <= 100.0 or blend_r < 0.0:
            return None
        motion_type = "ptp"
        if isinstance(value, dict):
            raw_type = value.get("motion_type", value.get("type", "ptp"))
        else:
            try:
                raw = list(value)
                raw_type = raw[8] if len(raw) >= 9 else "ptp"
            except TypeError:
                raw_type = "ptp"
        candidate = str(raw_type or "ptp").strip().lower()
        if candidate in {"ptp", "linear"}:
            motion_type = candidate
        return {"position": pose, "vel_percent": vel, "acc_percent": acc, "motion_type": motion_type, "blendR": blend_r}

    @classmethod
    def _normalize_poses(cls, value: object) -> list[list[float]]:
        if not value:
            return []
        if isinstance(value, str):
            pose = cls._normalize_pose(value)
            return [pose] if pose is not None else []
        try:
            items = list(value)
        except TypeError:
            return []
        poses = []
        for item in items:
            waypoint = cls._normalize_waypoint(item)
            if waypoint is not None:
                poses.append(waypoint["position"])
        return poses

    @staticmethod
    def _t(text: str) -> str:
        translated = QCoreApplication.translate("PaintProcessSettings", text)
        return translated or text
