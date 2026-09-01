from PyQt6.QtCore import QCoreApplication, QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QComboBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view import widget_factory
from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    GHOST_BTN_STYLE,
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_LIGHT,
    TEXT_COLOR,
)
from pl_gui.settings.settings_view.widget_factory import WidgetHandler
from src.applications.base.app_dialog import AppDialog, DIALOG_INPUT_STYLE
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.keyboard_settings_view import KeyboardSettingsView
from src.applications.base.styled_message_box import show_warning
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardLineEdit
from src.robot_systems.paint.applications.paint_process_settings.view.paint_process_settings_schema import (
    build_paint_process_settings_tabs,
)
from src.robot_systems.paint.processes.paint.config import (
    MAGAZINE_PICKUP_MODE_FIXED_GROUP_SENSOR_CONTROLLED_FAST_LIN,
    MAGAZINE_PICKUP_MODE_VISION_SENSOR_CONTROLLED_FAST_LIN,
    PICKUP_CONTACT_MODE_SENSOR_CONTROLLED_FAST_LIN,
)


_MAGAZINE_PICKUP_MODE_KEY = "magazine_pickup_mode"
_PICKUP_CONTACT_MODE_KEY = "pickup_contact_mode"
_DROPOFF_STRATEGY_KEY = "dropoff_strategy"
_SENSOR_CONTROLLED_FAST_LIN_KEYS = {
    "pickup_servo_contact_min_z_mm",
    "pickup_servo_contact_fast_lin_velocity_percent",
    "pickup_servo_contact_fast_lin_acceleration_percent",
    "pickup_servo_contact_timeout_s",
    "pickup_servo_contact_poll_interval_s",
    "pickup_servo_contact_preflight_read_attempts",
    "pickup_servo_contact_read_failure_limit",
    "pickup_servo_contact_fallback_to_planned_descend",
    "pickup_servo_contact_dummy_sensor_enabled",
    "pickup_servo_contact_dummy_detect_after_s",
}
_FIXED_MAGAZINE_ONLY_KEYS = {
    "magazine_fixed_pickup_group_id",
    "magazine_fixed_pickup_position_tolerance_mm",
    "magazine_fixed_pickup_orientation_tolerance_deg",
}
_VISION_MAGAZINE_ONLY_KEYS = {
    "magazine_camera_settle_s",
}
_PLATE_DROPOFF_ONLY_KEYS = {
    "dropoff_plate_bottom_left", "dropoff_plate_capture_bottom_left",
    "dropoff_plate_bottom_right", "dropoff_plate_capture_bottom_right",
    "dropoff_plate_top_right", "dropoff_plate_capture_top_right",
    "dropoff_plate_top_left", "dropoff_plate_capture_top_left",
    "dropoff_plate_robot_frame", "dropoff_plate_motion_profiles",
    "dropoff_plate_release_z_offset_mm", "dropoff_plate_approach_clearance_mm",
    "dropoff_plate_margin_left_mm", "dropoff_plate_margin_right_mm",
    "dropoff_plate_margin_bottom_mm", "dropoff_plate_margin_top_mm",
    "dropoff_plate_spacing_x_mm", "dropoff_plate_spacing_y_mm",
}
_MOVEMENT_GROUP_DROPOFF_ONLY_KEYS = {
    "dropoff_allow_sub_zero", "dropoff_sub_zero_approach_z_mm",
    "dropoff_corridor_x_margin_mm", "dropoff_corridor_y_margin_mm",
    "dropoff_corridor_z_tolerance_mm", "dropoff_corridor_entry_z_max_mm",
    "dropoff_corridor_maximum_velocity_percent",
    "dropoff_corridor_maximum_acceleration_percent",
}
_NON_PLATE_DROPOFF_KEYS = {
    "dropoff_motion_profiles", "dropoff_safe_travel_enabled",
    "dropoff_safe_travel_positions",
}


def _t(text: str) -> str:
    translated = QCoreApplication.translate("PaintProcessSettings", text)
    return translated or text


class _WaypointTable(QWidget):
    def __init__(self, label: str, emit, default_vel: float = 50.0, default_acc: float = 20.0, parent=None):
        super().__init__(parent)
        self._label = label
        self._emit = emit
        self._default_vel = float(default_vel)
        self._default_acc = float(default_acc)
        self._waypoints: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self._table = QTableWidget(0, 11)
        self._table.setHorizontalHeaderLabels(["#", "X", "Y", "Z", "RX", "RY", "RZ", "Vel %", "Acc %", "Type", "BlendR"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemSelectionChanged.connect(self._update_buttons)
        self._table.setMinimumHeight(180)
        self._table.setStyleSheet(self._table_style())
        root.addWidget(self._table)

        row = QHBoxLayout()
        self._add_current_btn = QPushButton("Add Current")
        self._add_manual_btn = QPushButton("Add")
        self._edit_btn = QPushButton("Edit")
        self._move_to_btn = QPushButton("Move To")
        self._delete_btn = QPushButton("Delete")
        self._up_btn = QPushButton("Up")
        self._down_btn = QPushButton("Down")
        self._add_current_btn.setProperty("request_key", self._label)
        self._add_current_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._move_to_btn.setStyleSheet(ACTION_BTN_STYLE)
        for btn in (self._add_manual_btn, self._edit_btn, self._delete_btn, self._up_btn, self._down_btn):
            btn.setStyleSheet(GHOST_BTN_STYLE)
        for btn in (
            self._add_current_btn,
            self._add_manual_btn,
            self._edit_btn,
            self._move_to_btn,
            self._delete_btn,
            self._up_btn,
            self._down_btn,
        ):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(btn)
        row.addStretch()
        root.addLayout(row)

        self._add_current_btn.clicked.connect(self._on_add_current)
        self._add_manual_btn.clicked.connect(self._on_add_manual)
        self._edit_btn.clicked.connect(self._on_edit)
        self._move_to_btn.clicked.connect(self._on_move_to)
        self._delete_btn.clicked.connect(self._on_delete)
        self._up_btn.clicked.connect(self._on_move_up)
        self._down_btn.clicked.connect(self._on_move_down)
        self._update_buttons()

    def set_waypoints(self, value: object) -> None:
        self._waypoints = self._normalize_waypoints(value, self._default_vel, self._default_acc)
        self._reload()

    def get_waypoints(self) -> list[dict]:
        return [
            {
                "position": list(waypoint["position"]),
                "vel_percent": float(waypoint["vel_percent"]),
                "acc_percent": float(waypoint["acc_percent"]),
                "motion_type": str(waypoint["motion_type"]),
                "blendR": float(waypoint["blendR"]),
            }
            for waypoint in self._waypoints
        ]

    def add_waypoint(self, pose: list[float]) -> None:
        normalized = self._normalize_waypoint(pose, self._default_vel, self._default_acc)
        if normalized is None:
            return
        self._waypoints.append(normalized)
        self._reload(select_row=len(self._waypoints) - 1)
        self._emit(self.get_waypoints())

    def _reload(self, select_row: int | None = None) -> None:
        self._table.setRowCount(0)
        for index, pose in enumerate(self._waypoints):
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(index + 1)))
            values = list(pose["position"]) + [pose["vel_percent"], pose["acc_percent"]]
            for col, value in enumerate(values, start=1):
                self._table.setItem(row, col, QTableWidgetItem(f"{float(value):.3f}"))
            self._table.setItem(row, 9, QTableWidgetItem(str(pose["motion_type"]).upper()))
            self._table.setItem(row, 10, QTableWidgetItem(f"{float(pose['blendR']):.3f}"))
        if select_row is not None and 0 <= select_row < self._table.rowCount():
            self._table.selectRow(select_row)
        self._update_buttons()

    def _selected_index(self) -> int | None:
        row = self._table.currentRow()
        return row if 0 <= row < len(self._waypoints) else None

    def _update_buttons(self) -> None:
        index = self._selected_index()
        has_selection = index is not None
        self._edit_btn.setEnabled(has_selection)
        self._move_to_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)
        self._up_btn.setEnabled(has_selection and index > 0)
        self._down_btn.setEnabled(has_selection and index < len(self._waypoints) - 1)

    def _on_add_manual(self) -> None:
        dialog = _WaypointDialog(default_vel=self._default_vel, default_acc=self._default_acc, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._waypoints.append(dialog.waypoint())
        self._reload(select_row=len(self._waypoints) - 1)
        self._emit(self.get_waypoints())

    def _on_add_current(self) -> None:
        self._emit(f"{self._label}_add_current")

    def _on_edit(self, *_args) -> None:
        index = self._selected_index()
        if index is None:
            return
        dialog = _WaypointDialog(self._waypoints[index], self._default_vel, self._default_acc, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._waypoints[index] = dialog.waypoint()
        self._reload(select_row=index)
        self._emit(self.get_waypoints())

    def _on_move_to(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        self._emit({"action": "move_to", "waypoint": self.get_waypoints()[index]})

    def _on_delete(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        self._waypoints.pop(index)
        self._reload(select_row=min(index, len(self._waypoints) - 1))
        self._emit(self.get_waypoints())

    def _move_selected(self, delta: int) -> None:
        index = self._selected_index()
        if index is None:
            return
        new_index = index + int(delta)
        if not 0 <= new_index < len(self._waypoints):
            return
        self._waypoints[index], self._waypoints[new_index] = self._waypoints[new_index], self._waypoints[index]
        self._reload(select_row=new_index)
        self._emit(self.get_waypoints())

    def _on_move_up(self) -> None:
        self._move_selected(-1)

    def _on_move_down(self) -> None:
        self._move_selected(1)

    @staticmethod
    def _table_style() -> str:
        return f"""
        QTableWidget {{
            background: white;
            alternate-background-color: {BG_COLOR};
            color: {TEXT_COLOR};
            border: 2px solid {BORDER};
            border-radius: 8px;
            gridline-color: {BORDER};
            selection-background-color: {PRIMARY};
            selection-color: white;
        }}
        QTableWidget::item {{
            border-bottom: 1px solid {BORDER};
            border-right: 1px solid {BORDER};
            padding: 8px 10px;
        }}
        QTableWidget::item:selected {{
            background: {PRIMARY};
            color: white;
        }}
        QHeaderView::section {{
            background: {BG_COLOR};
            color: {TEXT_COLOR};
            border: none;
            border-right: 1px solid {BORDER};
            border-bottom: 2px solid {BORDER};
            padding: 8px 10px;
            font-size: 10pt;
            font-weight: bold;
        }}
        QTableCornerButton::section {{
            background: {BG_COLOR};
            border: none;
            border-right: 1px solid {BORDER};
            border-bottom: 2px solid {BORDER};
        }}
        QTableWidget:focus {{
            border: 2px solid {PRIMARY};
        }}
        QScrollBar:vertical {{
            background: {BG_COLOR};
            width: 12px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {BORDER};
            border-radius: 6px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {PRIMARY_LIGHT};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        """

    @classmethod
    def _normalize_waypoints(cls, value: object, default_vel: float = 50.0, default_acc: float = 20.0) -> list[dict]:
        if not value:
            return []
        if isinstance(value, str):
            waypoint = cls._normalize_waypoint(value, default_vel, default_acc)
            return [waypoint] if waypoint is not None else []
        try:
            items = list(value)
        except TypeError:
            return []
        waypoints = []
        for item in items:
            waypoint = cls._normalize_waypoint(item, default_vel, default_acc)
            if waypoint is not None:
                waypoints.append(waypoint)
        return waypoints

    @staticmethod
    def _normalize_pose(value: object) -> list[float] | None:
        if isinstance(value, dict):
            value = value.get("position", value.get("pose", []))
        if isinstance(value, str):
            raw = [part.strip() for part in value.replace("[", "").replace("]", "").split(",")]
        else:
            try:
                raw = list(value)
            except TypeError:
                return None
        try:
            pose = [float(item) for item in raw[:6]]
        except (TypeError, ValueError):
            return None
        return pose if len(pose) >= 6 else None

    @classmethod
    def _normalize_waypoint(cls, value: object, default_vel: float = 50.0, default_acc: float = 20.0) -> dict | None:
        pose = cls._normalize_pose(value)
        if pose is None:
            return None
        vel = float(default_vel)
        acc = float(default_acc)
        motion_type = "ptp"
        blend_r = 0.0
        if isinstance(value, dict):
            try:
                vel = float(value.get("vel_percent", default_vel))
                acc = float(value.get("acc_percent", default_acc))
                motion_type = cls._normalize_motion_type(value.get("motion_type", value.get("type", "ptp")))
                blend_r = float(value.get("blendR", value.get("blend_r", 0.0)))
            except (TypeError, ValueError):
                vel = float(default_vel)
                acc = float(default_acc)
        else:
            try:
                raw = list(value)
                if len(raw) >= 8:
                    vel = float(raw[6])
                    acc = float(raw[7])
                if len(raw) >= 9:
                    motion_type = cls._normalize_motion_type(raw[8])
                if len(raw) >= 10:
                    blend_r = float(raw[9])
            except (TypeError, ValueError):
                pass
        return {
            "position": pose,
            "vel_percent": vel,
            "acc_percent": acc,
            "motion_type": motion_type,
            "blendR": max(0.0, blend_r),
        }

    @staticmethod
    def _normalize_motion_type(value: object) -> str:
        motion_type = str(value or "ptp").strip().lower()
        return motion_type if motion_type in {"ptp", "linear", "fast_lin"} else "ptp"


class _MotionProfileTable(QWidget):
    def __init__(self, rows: list[dict], emit, parent=None):
        super().__init__(parent)
        self._rows = [self._normalize_profile(row) for row in rows]
        self._profiles = [dict(row) for row in self._rows]
        self._emit = emit
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Phase", "Vel %", "Acc %", "Type", "BlendR"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemSelectionChanged.connect(self._update_buttons)
        self._table.itemDoubleClicked.connect(self._on_edit)
        self._table.setMinimumHeight(max(150, 46 * len(self._rows) + 44))
        self._table.setStyleSheet(_WaypointTable._table_style())
        root.addWidget(self._table)

        row = QHBoxLayout()
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._edit_btn)
        row.addStretch()
        root.addLayout(row)

        self._edit_btn.clicked.connect(self._on_edit)
        self._reload()

    def set_profiles(self, value: object) -> None:
        incoming = {
            str(profile["key"]): profile
            for profile in self._normalize_profiles(value)
            if "key" in profile
        }
        self._profiles = []
        for row in self._rows:
            key = str(row["key"])
            profile = dict(row)
            profile.update(incoming.get(key, {}))
            profile["label"] = str(row["label"])
            self._profiles.append(self._normalize_profile(profile))
        self._reload()

    def get_profiles(self) -> list[dict]:
        return [dict(profile) for profile in self._profiles]

    def _reload(self, select_row: int | None = None) -> None:
        self._table.setRowCount(0)
        for profile in self._profiles:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(profile["label"])))
            self._table.setItem(row, 1, QTableWidgetItem(f"{float(profile['vel_percent']):.3f}"))
            self._table.setItem(row, 2, QTableWidgetItem(f"{float(profile['acc_percent']):.3f}"))
            self._table.setItem(row, 3, QTableWidgetItem(str(profile["motion_type"]).upper()))
            self._table.setItem(row, 4, QTableWidgetItem(f"{float(profile['blendR']):.3f}"))
        if select_row is not None and 0 <= select_row < self._table.rowCount():
            self._table.selectRow(select_row)
        self._update_buttons()

    def _selected_index(self) -> int | None:
        row = self._table.currentRow()
        return row if 0 <= row < len(self._profiles) else None

    def _update_buttons(self) -> None:
        self._edit_btn.setEnabled(self._selected_index() is not None)

    def _on_edit(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        dialog = _MotionProfileDialog(self._profiles[index], parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._profiles[index] = dialog.profile()
        self._reload(select_row=index)
        self._emit(self.get_profiles())

    @classmethod
    def _normalize_profiles(cls, value: object) -> list[dict]:
        try:
            items = list(value or [])
        except TypeError:
            return []
        result: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            result.append(cls._normalize_profile(item))
        return result

    @staticmethod
    def _normalize_profile(value: dict) -> dict:
        motion_type = str(value.get("motion_type", value.get("type", "ptp")) or "ptp").strip().lower()
        if motion_type not in {"ptp", "linear", "fast_lin"}:
            motion_type = "ptp"
        try:
            vel = float(value.get("vel_percent", 0.0))
            acc = float(value.get("acc_percent", 0.0))
            blend_r = float(value.get("blendR", value.get("blend_r", 0.0)))
        except (TypeError, ValueError):
            vel = 0.0
            acc = 0.0
            blend_r = 0.0
        return {
            "key": str(value.get("key", "")),
            "label": str(value.get("label", value.get("key", ""))),
            "vel_percent": max(0.0, min(100.0, vel)),
            "acc_percent": max(0.0, min(100.0, acc)),
            "motion_type": motion_type,
            "blendR": max(0.0, blend_r),
        }


class _MotionProfileDialog(AppDialog):
    def __init__(self, profile: dict, parent=None):
        super().__init__("Motion Profile", min_width=420, parent=parent)
        normalized = _MotionProfileTable._normalize_profile(profile)
        self._key = str(normalized["key"])
        self._label = str(normalized["label"])

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(12)

        phase = QLabel(self._label)
        phase.setStyleSheet(LABEL_STYLE)
        form.addRow("Phase", phase)

        self._vel = KeyboardLineEdit()
        self._vel.setStyleSheet(DIALOG_INPUT_STYLE)
        self._vel.setText(f"{float(normalized['vel_percent']):.3f}")
        form.addRow("Velocity %", self._vel)

        self._acc = KeyboardLineEdit()
        self._acc.setStyleSheet(DIALOG_INPUT_STYLE)
        self._acc.setText(f"{float(normalized['acc_percent']):.3f}")
        form.addRow("Acceleration %", self._acc)

        self._motion_type = QComboBox()
        self._motion_type.addItems(["PTP", "Linear", "Fast LIN"])
        self._motion_type.setCurrentText(
            {"linear": "Linear", "fast_lin": "Fast LIN"}.get(normalized["motion_type"], "PTP")
        )
        self._motion_type.setStyleSheet(DIALOG_INPUT_STYLE)
        form.addRow("Type", self._motion_type)

        self._blend_r = KeyboardLineEdit()
        self._blend_r.setStyleSheet(DIALOG_INPUT_STYLE)
        self._blend_r.setText(f"{float(normalized['blendR']):.3f}")
        form.addRow("BlendR", self._blend_r)

        root.addLayout(form)
        root.addWidget(self._build_button_row(ok_label="Save"))

    def profile(self) -> dict:
        selected_type = {
            "linear": "linear",
            "fast lin": "fast_lin",
        }.get(self._motion_type.currentText().strip().lower(), "ptp")
        return {
            "key": self._key,
            "label": self._label,
            "vel_percent": float(self._vel.text()),
            "acc_percent": float(self._acc.text()),
            "motion_type": selected_type,
            "blendR": float(self._blend_r.text()),
        }

    def accept(self) -> None:
        try:
            profile = self.profile()
        except ValueError:
            show_warning(self, _t("Motion Profile"), _t("All motion profile values must be valid numbers."))
            return
        if not 0.0 <= profile["vel_percent"] <= 100.0 or not 0.0 <= profile["acc_percent"] <= 100.0:
            show_warning(
                self,
                _t("Motion Profile"),
                _t("Velocity and acceleration must be between 0 and 100 percent."),
            )
            return
        if profile["blendR"] < 0.0:
            show_warning(self, _t("Motion Profile"), _t("BlendR must be zero or greater."))
            return
        super().accept()


class _WaypointDialog(AppDialog):
    def __init__(
        self,
        waypoint: object = None,
        default_vel: float = 50.0,
        default_acc: float = 20.0,
        parent=None,
    ):
        super().__init__("Waypoint", min_width=520, parent=parent)
        normalized = _WaypointTable._normalize_waypoint(waypoint or [], default_vel, default_acc)
        if normalized is None:
            normalized = {
                "position": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "vel_percent": default_vel,
                "acc_percent": default_acc,
                "motion_type": "ptp",
                "blendR": 0.0,
            }
        values = list(normalized["position"]) + [normalized["vel_percent"], normalized["acc_percent"]]
        motion_type = str(normalized["motion_type"])
        blend_r = float(normalized["blendR"])
        self._virtual_keyboard_dock_window = parent.window() if parent is not None else None
        self._keyboard_scroll_area: QScrollArea | None = None
        self._keyboard_bottom_spacer: QWidget | None = None
        self._keyboard_pending_visible_widget: QWidget | None = None
        self._fields: list[KeyboardLineEdit] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        form_host = QWidget(self)
        form = QFormLayout(form_host)
        form.setSpacing(12)
        for label, value in zip(("X", "Y", "Z", "RX", "RY", "RZ", "Velocity %", "Acceleration %"), values):
            edit = KeyboardLineEdit()
            edit.setStyleSheet(DIALOG_INPUT_STYLE)
            edit.setText(f"{float(value):.3f}")
            form.addRow(label, edit)
            self._fields.append(edit)
        self._motion_type = QComboBox()
        self._motion_type.addItems(["PTP", "Linear", "Fast LIN"])
        self._motion_type.setCurrentText(
            {"linear": "Linear", "fast_lin": "Fast LIN"}.get(motion_type, "PTP")
        )
        self._motion_type.setStyleSheet(DIALOG_INPUT_STYLE)
        form.addRow("Type", self._motion_type)
        self._blend_r = KeyboardLineEdit()
        self._blend_r.setStyleSheet(DIALOG_INPUT_STYLE)
        self._blend_r.setText(f"{blend_r:.3f}")
        form.addRow("BlendR", self._blend_r)
        self._fields.append(self._blend_r)
        self._keyboard_bottom_spacer = QWidget(form_host)
        self._keyboard_bottom_spacer.setFixedHeight(0)
        form.addRow("", self._keyboard_bottom_spacer)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(form_host)
        self._keyboard_scroll_area = scroll
        root.addWidget(scroll)
        root.addWidget(self._build_button_row(ok_label="Save"))

    def _on_virtual_keyboard_shown(self, keyboard_rect) -> None:
        if self._keyboard_scroll_area is None:
            return
        viewport = self._keyboard_scroll_area.viewport()
        overlap = viewport.mapToGlobal(viewport.rect().bottomLeft()).y() - keyboard_rect.top() + 24
        if self._keyboard_bottom_spacer is not None:
            self._keyboard_bottom_spacer.setFixedHeight(max(0, overlap))
        focused = self.focusWidget()
        if focused is not None:
            self._keyboard_pending_visible_widget = focused
            QTimer.singleShot(0, self._ensure_pending_widget_visible)

    def _on_virtual_keyboard_hidden(self) -> None:
        if self._keyboard_bottom_spacer is not None:
            self._keyboard_bottom_spacer.setFixedHeight(0)

    def _ensure_pending_widget_visible(self) -> None:
        if self._keyboard_scroll_area is None or self._keyboard_pending_visible_widget is None:
            return
        self._keyboard_scroll_area.ensureWidgetVisible(self._keyboard_pending_visible_widget, 12, 12)
        self._keyboard_pending_visible_widget = None

    def pose(self) -> list[float]:
        return [float(field.text()) for field in self._fields[:6]]

    def waypoint(self) -> dict:
        values = [float(field.text()) for field in self._fields]
        selected_type = {
            "linear": "linear",
            "fast lin": "fast_lin",
        }.get(self._motion_type.currentText().strip().lower(), "ptp")
        return {
            "position": values[:6],
            "vel_percent": values[6],
            "acc_percent": values[7],
            "motion_type": selected_type,
            "blendR": values[8],
        }

    def accept(self) -> None:
        try:
            waypoint = self.waypoint()
        except ValueError:
            show_warning(self, _t("Waypoint"), _t("All waypoint values must be valid numbers."))
            return
        if not 0.0 <= waypoint["vel_percent"] <= 100.0 or not 0.0 <= waypoint["acc_percent"] <= 100.0:
            show_warning(
                self,
                _t("Waypoint"),
                _t("Velocity and acceleration must be between 0 and 100 percent."),
            )
            return
        if waypoint["blendR"] < 0.0:
            show_warning(self, _t("Waypoint"), _t("BlendR must be zero or greater."))
            return
        super().accept()


class _ActionButton(QPushButton):
    def __init__(self, text: str, emit, parent=None):
        super().__init__(text, parent)
        self._emit = emit
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self._emit(True)


class PaintProcessSettingsView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_LIVE_POSITION_ENABLED = True

    save_requested = pyqtSignal(dict)
    value_changed = pyqtSignal(str, object)
    set_safe_travel_current_requested = pyqtSignal()
    set_dropoff_safe_travel_current_requested = pyqtSignal()
    capture_plate_corner_requested = pyqtSignal(str)
    move_to_safe_travel_waypoint_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        self.settings_view: KeyboardSettingsView | None = None
        self._status_label: QLabel | None = None
        self._layout: QVBoxLayout | None = None
        self._current_values: dict = {}
        self._custom_widget_original_handlers: dict[str, WidgetHandler | None] | None = None
        super().__init__("PaintProcessSettings", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._build_settings_view()
        self._status_label = QLabel()
        self._status_label.setStyleSheet(LABEL_STYLE)
        self._status_label.setContentsMargins(18, 8, 18, 8)
        self._layout.addWidget(self._status_label)
        self.retranslateUi()

    def clean_up(self) -> None:
        self._restore_custom_widget_handlers()

    def set_values(self, values: dict) -> None:
        self._current_values = dict(values)
        if self.settings_view is not None:
            self.settings_view.set_values(values)
            self._update_magazine_mode_field_visibility(
                values.get(_MAGAZINE_PICKUP_MODE_KEY, "vision_planned")
            )
            self._update_sensor_controlled_fast_lin_visibility(values)
            self._update_dropoff_strategy_visibility(values.get(_DROPOFF_STRATEGY_KEY, "pickup_origin"))

    def set_safe_travel_position(self, position: list[float]) -> None:
        self._append_waypoint("safe_travel_positions", position)

    def set_dropoff_safe_travel_position(self, position: list[float]) -> None:
        self._append_waypoint("dropoff_safe_travel_positions", position)

    def set_plate_corner(self, corner_key: str, position: list[float], tool: int, user: int) -> None:
        values = self.values()
        values[corner_key] = ", ".join(f"{float(value):.3f}" for value in position[:6])
        values["dropoff_plate_robot_tool"] = int(tool)
        values["dropoff_plate_robot_user"] = int(user)
        values["dropoff_plate_robot_frame"] = f"Tool {int(tool)}, User {int(user)}"
        self.set_values(values)

    def values(self) -> dict:
        if self.settings_view is None:
            return dict(self._current_values)
        return {**self._current_values, **self.settings_view.get_values()}

    def set_status(self, message: str) -> None:
        if self._status_label is not None:
            self._status_label.setText(message)

    def retranslateUi(self) -> None:
        if self._status_label is not None and not self._status_label.text():
            self._status_label.setText(self.tr("Changes are applied to the next Paint cycle."))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            values = self.values()
            self._rebuild_settings_view()
            self.set_values(values)
            self.retranslateUi()
            self.language_changed.emit()
        super().changeEvent(event)

    def _build_settings_view(self) -> None:
        if self._layout is None:
            return
        self.settings_view = KeyboardSettingsView(component_name="PaintProcessSettings")
        self._install_custom_widget_handlers()
        for title, groups in build_paint_process_settings_tabs():
            self.settings_view.add_tab(title, groups)
        self.settings_view.value_changed_signal.connect(self._on_value_changed)
        self.settings_view.save_requested.connect(self._on_save_requested)
        self._layout.insertWidget(0, self.settings_view)

    def _install_custom_widget_handlers(self) -> None:
        custom_types = (
            "paint_action_button",
            "paint_pose_display",
            "paint_waypoint_table",
            "paint_motion_profile_table",
        )
        if self._custom_widget_original_handlers is None:
            self._custom_widget_original_handlers = {
                widget_type: widget_factory._REGISTRY.get(widget_type)
                for widget_type in custom_types
            }
        widget_factory._REGISTRY["paint_action_button"] = WidgetHandler(
            create=self._make_action_button,
            get_value=lambda _widget: False,
            set_value=lambda _widget, _value: None,
            full_width=True,
        )
        widget_factory._REGISTRY["paint_pose_display"] = WidgetHandler(
            create=self._make_pose_display,
            get_value=lambda widget: widget.text(),
            set_value=lambda widget, value: widget.setText(str(value or self.tr("Not set"))),
            full_width=True,
        )
        widget_factory._REGISTRY["paint_waypoint_table"] = WidgetHandler(
            create=self._make_waypoint_table,
            get_value=lambda widget: widget.get_waypoints(),
            set_value=lambda widget, value: widget.set_waypoints(value),
            full_width=True,
        )
        widget_factory._REGISTRY["paint_motion_profile_table"] = WidgetHandler(
            create=self._make_motion_profile_table,
            get_value=lambda widget: widget.get_profiles(),
            set_value=lambda widget, value: widget.set_profiles(value),
            full_width=True,
        )

    def _restore_custom_widget_handlers(self) -> None:
        if self._custom_widget_original_handlers is None:
            return
        for widget_type, handler in self._custom_widget_original_handlers.items():
            current = widget_factory._REGISTRY.get(widget_type)
            if current is not None and getattr(current.create, "__self__", None) is self:
                if handler is None:
                    widget_factory._REGISTRY.pop(widget_type, None)
                else:
                    widget_factory._REGISTRY[widget_type] = handler
        self._custom_widget_original_handlers = None

    def _make_action_button(self, field, emit):
        button = _ActionButton(str(field.default or field.label), emit)
        button.setStyleSheet(GHOST_BTN_STYLE)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _make_pose_display(self, field, _emit):
        label = QLabel(str(field.default or self.tr("Not set")))
        label.setWordWrap(True)
        label.setStyleSheet(
            f"""
            QLabel {{
                background: {BG_COLOR};
                color: {TEXT_COLOR};
                border: 2px solid {BORDER};
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 11pt;
                min-height: 44px;
            }}
            """
        )
        return label

    def _make_waypoint_table(self, field, emit):
        defaults = field.default if isinstance(field.default, dict) else {}
        return _WaypointTable(
            field.key,
            emit,
            default_vel=float(defaults.get("vel_percent", 50.0)),
            default_acc=float(defaults.get("acc_percent", 20.0)),
        )

    def _make_motion_profile_table(self, field, emit):
        rows = field.default if isinstance(field.default, list) else []
        return _MotionProfileTable(rows, emit)

    def _rebuild_settings_view(self) -> None:
        if self._layout is None or self.settings_view is None:
            return
        old = self.settings_view
        try:
            old.value_changed_signal.disconnect(self._on_value_changed)
        except Exception:
            pass
        try:
            old.save_requested.disconnect(self._on_save_requested)
        except Exception:
            pass
        self._layout.removeWidget(old)
        old.deleteLater()
        self.settings_view = None
        self._build_settings_view()

    def _on_save_requested(self, values: dict) -> None:
        self._current_values = dict(values)
        self.save_requested.emit(values)

    def _on_value_changed(self, key: str, value: object, _component_name: str) -> None:
        if key == _DROPOFF_STRATEGY_KEY:
            self._update_dropoff_strategy_visibility(value)
        if key == _MAGAZINE_PICKUP_MODE_KEY:
            self._update_magazine_mode_field_visibility(value)
        if key in {_MAGAZINE_PICKUP_MODE_KEY, _PICKUP_CONTACT_MODE_KEY}:
            pending_values = self.values()
            pending_values[key] = value
            self._update_sensor_controlled_fast_lin_visibility(pending_values)
        if key == "safe_travel_positions" and value == "safe_travel_positions_add_current":
            self.set_safe_travel_current_requested.emit()
            return
        if key == "dropoff_safe_travel_positions" and value == "dropoff_safe_travel_positions_add_current":
            self.set_dropoff_safe_travel_current_requested.emit()
            return
        corner_actions = {
            "dropoff_plate_capture_bottom_left": "dropoff_plate_bottom_left",
            "dropoff_plate_capture_bottom_right": "dropoff_plate_bottom_right",
            "dropoff_plate_capture_top_right": "dropoff_plate_top_right",
            "dropoff_plate_capture_top_left": "dropoff_plate_top_left",
        }
        if key in corner_actions and bool(value):
            self.capture_plate_corner_requested.emit(corner_actions[key])
            return
        if key in {"safe_travel_positions", "dropoff_safe_travel_positions"} and isinstance(value, dict):
            if value.get("action") == "move_to":
                waypoint = value.get("waypoint", {})
                if isinstance(waypoint, dict):
                    self.move_to_safe_travel_waypoint_requested.emit(waypoint)
                return
        self._current_values = self.values()
        self.value_changed.emit(key, value)

    def _update_magazine_mode_field_visibility(self, mode: object) -> None:
        fixed_group = (
            str(mode or "").strip().lower()
            == MAGAZINE_PICKUP_MODE_FIXED_GROUP_SENSOR_CONTROLLED_FAST_LIN
        )
        self._set_setting_fields_visible(_FIXED_MAGAZINE_ONLY_KEYS, fixed_group)
        self._set_setting_fields_visible(_VISION_MAGAZINE_ONLY_KEYS, not fixed_group)

    def _update_sensor_controlled_fast_lin_visibility(self, values: dict) -> None:
        pickup_mode = str(values.get(_PICKUP_CONTACT_MODE_KEY, "")).strip().lower()
        magazine_mode = str(values.get(_MAGAZINE_PICKUP_MODE_KEY, "")).strip().lower()
        enabled = (
            pickup_mode == PICKUP_CONTACT_MODE_SENSOR_CONTROLLED_FAST_LIN
            or magazine_mode
            in {
                MAGAZINE_PICKUP_MODE_VISION_SENSOR_CONTROLLED_FAST_LIN,
                MAGAZINE_PICKUP_MODE_FIXED_GROUP_SENSOR_CONTROLLED_FAST_LIN,
            }
        )
        self._set_setting_fields_visible(_SENSOR_CONTROLLED_FAST_LIN_KEYS, enabled)

    def _update_dropoff_strategy_visibility(self, strategy: object) -> None:
        selected = str(strategy or "pickup_origin").strip().lower()
        self._set_setting_fields_visible(_PLATE_DROPOFF_ONLY_KEYS, selected == "plate_layout")
        self._set_setting_fields_visible(
            _MOVEMENT_GROUP_DROPOFF_ONLY_KEYS, selected == "movement_group"
        )
        self._set_setting_fields_visible(_NON_PLATE_DROPOFF_KEYS, selected != "plate_layout")

    def _set_setting_fields_visible(self, keys: set[str], visible: bool) -> None:
        if self.settings_view is None:
            return
        for group in self.settings_view._groups:
            inner = getattr(group, "_inner", group)
            widgets = getattr(inner, "_widgets", {})
            for key in keys:
                widget = widgets.get(key)
                if widget is None:
                    continue
                field_cell = widget.parentWidget()
                if field_cell is not None:
                    field_cell.setVisible(visible)

    def _append_waypoint(self, key: str, position: list[float]) -> None:
        values = self.values()
        default_vel, default_acc = self._waypoint_defaults_for_key(key)
        waypoints = _WaypointTable._normalize_waypoints(values.get(key, []), default_vel, default_acc)
        waypoint = _WaypointTable._normalize_waypoint(position, default_vel, default_acc)
        if waypoint is not None:
            waypoints.append(waypoint)
        values[key] = waypoints
        self.set_values(values)
        self._current_values = values
        self.value_changed.emit(key, waypoints)

    @staticmethod
    def _waypoint_defaults_for_key(key: str) -> tuple[float, float]:
        if key == "dropoff_safe_travel_positions":
            return 60.0, 40.0
        return 50.0, 20.0

    @staticmethod
    def _format_pose(position: list[float]) -> str:
        return ", ".join(f"{float(value):.3f}" for value in position[:6])
