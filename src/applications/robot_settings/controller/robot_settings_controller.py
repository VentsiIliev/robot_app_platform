import logging

from PyQt6.QtWidgets import QDialog, QLineEdit, QComboBox, QCheckBox, QVBoxLayout, QLabel

from src.applications.base.app_dialog import (
    AppDialog, DIALOG_INPUT_STYLE, DIALOG_COMBO_STYLE, DIALOG_CHECKBOX_STYLE,
)
from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.styled_message_box import show_warning, ask_yes_no
from src.applications.robot_settings.model.mapper import RobotCalibrationMapper, RobotSettingsMapper
from src.applications.robot_settings.model.robot_settings_model import RobotSettingsModel
from src.applications.robot_settings.view.movement_groups_tab import MovementGroupDef, MovementGroupType
from src.applications.robot_settings.view.robot_settings_view import RobotSettingsView
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.robot.configuration import MovementGroup


class RobotSettingsController(IApplicationController, BackgroundWorker):

    def __init__(self, model: RobotSettingsModel, view: RobotSettingsView,
                 messaging: IMessagingService):
        BackgroundWorker.__init__(self)
        self._model    = model
        self._view     = view
        self._logger   = logging.getLogger(self.__class__.__name__)

        self._view.save_requested.connect(self._on_save)
        self._view.add_group_requested.connect(self._on_add_group)
        self._view.remove_group_requested.connect(self._on_remove_group)
        self._view.set_current_requested.connect(self._on_set_current)
        self._view.move_to_requested.connect(self._on_move_to)
        self._view.execute_requested.connect(self._on_execute)
        self._view.destroyed.connect(self.stop)



    def load(self) -> None:
        config, calibration = self._model.load()
        flat = {
            **RobotSettingsMapper.to_flat_dict(config),
            **RobotCalibrationMapper.to_flat_dict(calibration),
        }
        self._view.load_config(flat)

        extra_defs = {}
        for slot_id, tool_name in self._model.get_slot_info():
            if tool_name is None:
                continue
            for suffix in ("PICKUP", "DROPOFF"):
                key = f"SLOT {slot_id} {suffix}"
                extra_defs[key] = MovementGroupDef(
                    name                     = key,
                    group_type               = MovementGroupType.MULTI_POSITION,
                    has_trajectory_execution = True,
                    display_name             = f"Slot {slot_id} {suffix.capitalize()} — {tool_name}",
                )

        self._view.load_movement_groups(
            self._model.get_expected_movement_groups(),
            extra_defs=extra_defs,
        )

    def stop(self) -> None:
        self._stop_threads()

    def _on_save(self, _values: dict) -> None:
        try:
            flat            = self._view.get_values()
            movement_groups = self._view.get_movement_groups()
            self._logger.debug("Saving %d fields, %d movement groups", len(flat), len(movement_groups))
            self._model.save(flat, movement_groups)
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

    def _on_add_group(self) -> None:
        dlg = _AddGroupDialog(parent=self._view)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, defn = dlg.get_values()
        if not name:
            show_warning(self._view, "Add Group", "Group name cannot be empty.")
            return
        existing = self._view.get_movement_groups()
        if name in existing:
            show_warning(self._view, "Add Group", f"A group named '{name}' already exists.")
            return
        self._view.add_movement_group(name, defn, MovementGroup())
        self._logger.info("Added movement group '%s'", name)

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

    def _auto_save(self) -> None:
        """Flush current movement groups to disk before any motion — NavigationService reads from settings."""
        try:
            self._model.save(self._view.get_values(), self._view.get_movement_groups())
            self._logger.debug("Auto-saved before motion")
        except Exception:
            self._logger.exception("Auto-save before motion failed")

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

class _AddGroupDialog(AppDialog):

    _TYPE_OPTIONS = [
        ("Single Position", MovementGroupType.SINGLE_POSITION),
        ("Multi Position",  MovementGroupType.MULTI_POSITION),
        ("Velocity Only",   MovementGroupType.VELOCITY_ONLY),
    ]

    def __init__(self, parent=None):
        super().__init__("Add Movement Group", min_width=420, parent=parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # Name
        root.addWidget(self._label("Group Name"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. HOME, ROBOT_CALIBRATION, SLOT 2 PICKUP")
        self._name_edit.setStyleSheet(DIALOG_INPUT_STYLE)
        root.addWidget(self._name_edit)

        # Type
        root.addWidget(self._label("Type"))
        self._type_combo = QComboBox()
        self._type_combo.setStyleSheet(DIALOG_COMBO_STYLE)
        for label, _ in self._TYPE_OPTIONS:
            self._type_combo.addItem(label)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        root.addWidget(self._type_combo)

        # Options
        self._iterations_cb = QCheckBox("Has Iterations")
        self._iterations_cb.setStyleSheet(DIALOG_CHECKBOX_STYLE)
        root.addWidget(self._iterations_cb)

        self._trajectory_cb = QCheckBox("Has Trajectory Execution")
        self._trajectory_cb.setStyleSheet(DIALOG_CHECKBOX_STYLE)
        root.addWidget(self._trajectory_cb)

        root.addStretch()
        root.addWidget(self._build_button_row(ok_label="Add"))
        self._on_type_changed(0)

    @staticmethod
    def _label(text: str) -> QLabel:
        from PyQt6.QtWidgets import QLabel
        from pl_gui.settings.settings_view.styles import LABEL_STYLE
        lbl = QLabel(text)
        lbl.setStyleSheet(LABEL_STYLE)
        return lbl

    def _on_type_changed(self, idx: int) -> None:
        gtype = self._TYPE_OPTIONS[idx][1]
        self._iterations_cb.setVisible(gtype == MovementGroupType.MULTI_POSITION)
        self._trajectory_cb.setVisible(gtype != MovementGroupType.VELOCITY_ONLY)

    def get_values(self):
        idx  = self._type_combo.currentIndex()
        gtype = self._TYPE_OPTIONS[idx][1]
        name  = self._name_edit.text().strip().upper()
        defn  = MovementGroupDef(
            name                     = name,
            group_type               = gtype,
            has_iterations           = self._iterations_cb.isChecked(),
            has_trajectory_execution = self._trajectory_cb.isChecked(),
        )
        return name, defn
