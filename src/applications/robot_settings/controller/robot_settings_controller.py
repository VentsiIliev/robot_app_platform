import logging

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.styled_message_box import show_warning, ask_yes_no
from src.applications.robot_settings.model.mapper import RobotCalibrationMapper, RobotSettingsMapper
from src.applications.robot_settings.model.robot_settings_model import RobotSettingsModel
from src.applications.robot_settings.view.robot_settings_view import RobotSettingsView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.declarations import MovementGroupType
from src.shared_contracts.events.robot_events import RobotTopics


class RobotSettingsController(IApplicationController, BackgroundWorker):

    def __init__(self, model: RobotSettingsModel, view: RobotSettingsView,
                 messaging: IMessagingService):
        BackgroundWorker.__init__(self)
        self._model    = model
        self._view     = view
        self._logger   = logging.getLogger(self.__class__.__name__)
        self._messaging = messaging

        self._view.save_requested.connect(self._on_save)
        self._view.remove_group_requested.connect(self._on_remove_group)
        self._view.set_current_requested.connect(self._on_set_current)
        self._view.move_to_requested.connect(self._on_move_to)
        self._view.execute_requested.connect(self._on_execute)
        self._view.targeting_changed.connect(self._on_targeting_changed)
        self._view.destroyed.connect(self.stop)



    def load(self) -> None:
        config, calibration, targeting_definitions = self._model.load()
        flat = {
            **RobotSettingsMapper.to_flat_dict(config),
            **RobotCalibrationMapper.to_flat_dict(calibration),
        }
        self._view.load_config(flat)
        self._view.load_targeting_definitions(targeting_definitions)

        self._view.load_movement_groups(
            self._model.get_expected_movement_groups(),
            definitions=self._model.get_movement_group_definitions(),
        )

    def stop(self) -> None:
        self._stop_threads()

    def _on_save(self, _values: dict) -> None:
        try:
            flat            = self._view.get_values()
            movement_groups = self._view.get_movement_groups()
            targeting_definitions = self._view.get_targeting_definitions()
            self._logger.debug("Saving %d fields, %d movement groups", len(flat), len(movement_groups))
            self._model.save(flat, movement_groups, targeting_definitions)
            self._publish_targeting_changed(targeting_definitions)
            self._logger.info("Robot settings saved")
        except Exception:
            self._logger.exception("Failed to save robot settings")

    def _on_set_current(self, group_name: str) -> None:
        position = self._model.get_current_position()
        if position is None:
            show_warning(self._view, "Set Current Position",
                         "Could not read robot position.\n"
                         "Make sure the robot is connected.")
            return

        position_str = "[" + ", ".join(f"{v:.3f}" for v in position) + "]"
        widget = self._view.get_group_widget(group_name)
        if widget is None:
            return

        from src.applications.robot_settings.view.movement_groups_tab import MovementGroupType
        if widget._def.group_type == MovementGroupType.SINGLE_POSITION:
            widget.set_position(position_str)
            self._logger.info("Set position for '%s': %s", group_name, position_str)
        else:
            widget.add_point(position_str)
            self._logger.info("Added point to '%s': %s", group_name, position_str)

    def _on_remove_group(self, name: str) -> None:
        if not ask_yes_no(self._view, "Remove Group",
                          f"Remove movement group '{name}'?\n\nThis cannot be undone until you save."):
            return
        self._view.remove_movement_group(name)
        self._logger.info("Removed movement group '%s'", name)

    def _on_move_to(self, group_name: str, point_str) -> None:
        self._auto_save()
        if point_str is None:
            widget = self._view.get_group_widget(group_name)
            if widget is not None and widget._def.group_type == MovementGroupType.MULTI_POSITION:
                show_warning(self._view, "Move To",
                             "No point selected.\nSelect a point from the list first.")
                return
            fn = lambda: self._model.move_to_group(group_name)
            label = f"Move To — {group_name}"
        else:
            fn = lambda: self._model.move_to_point(group_name, point_str)
            label = f"Move To point in {group_name}"
        self._run_blocking(fn=fn, label=label)

    def _on_execute(self, group_name: str) -> None:
        self._auto_save()
        self._run_blocking(
            fn=lambda: self._model.execute_group(group_name),
            label=f"Execute — {group_name}",
        )

    def _on_targeting_changed(self) -> None:
        try:
            self._model.save(
                self._view.get_values(),
                self._view.get_movement_groups(),
                self._view.get_targeting_definitions(),
            )
            self._publish_targeting_changed(self._view.get_targeting_definitions())
            self._logger.debug("Auto-saved targeting definitions")
        except Exception:
            self._logger.exception("Auto-save targeting definitions failed")

    def _auto_save(self) -> None:
        """Flush current movement groups to disk before any motion — NavigationService reads from settings."""
        try:
            self._model.save(
                self._view.get_values(),
                self._view.get_movement_groups(),
                self._view.get_targeting_definitions(),
            )
            self._publish_targeting_changed(self._view.get_targeting_definitions())
            self._logger.debug("Auto-saved before motion")
        except Exception:
            self._logger.exception("Auto-save before motion failed")

    def _publish_targeting_changed(self, targeting_definitions: dict | None) -> None:
        if self._messaging is None:
            return
        try:
            self._messaging.publish(
                RobotTopics.TARGETING_DEFINITIONS_CHANGED,
                targeting_definitions or {},
            )
        except Exception:
            self._logger.debug("Failed to publish targeting-definitions change event", exc_info=True)

    def _run_blocking(self, fn, label: str) -> None:
        self._run_in_thread(
            fn=fn,
            on_done=lambda result: self._on_motion_done(result, label),
        )

    def _on_motion_done(self, result, label: str) -> None:
        ok, reason = result if isinstance(result, tuple) else (bool(result), "")
        if not ok:
            msg = reason or (
                f"Motion failed for '{label}'.\n"
                "Check the robot is connected and the group has a position configured."
            )
            show_warning(self._view, label, msg)
        else:
            self._logger.info("%s completed successfully", label)
