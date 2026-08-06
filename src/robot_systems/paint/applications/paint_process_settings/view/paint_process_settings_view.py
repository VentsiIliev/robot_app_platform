from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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

        self._table = QTableWidget(0, 9)
        self._table.setHorizontalHeaderLabels(["#", "X", "Y", "Z", "RX", "RY", "RZ", "Vel %", "Acc %"])
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
        self._delete_btn = QPushButton("Delete")
        self._up_btn = QPushButton("Up")
        self._down_btn = QPushButton("Down")
        self._add_current_btn.setProperty("request_key", self._label)
        self._add_current_btn.setStyleSheet(ACTION_BTN_STYLE)
        for btn in (self._add_manual_btn, self._edit_btn, self._delete_btn, self._up_btn, self._down_btn):
            btn.setStyleSheet(GHOST_BTN_STYLE)
        for btn in (
            self._add_current_btn,
            self._add_manual_btn,
            self._edit_btn,
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

    def _on_edit(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        dialog = _WaypointDialog(self._waypoints[index], self._default_vel, self._default_acc, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._waypoints[index] = dialog.waypoint()
        self._reload(select_row=index)
        self._emit(self.get_waypoints())

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
        if isinstance(value, dict):
            try:
                vel = float(value.get("vel_percent", default_vel))
                acc = float(value.get("acc_percent", default_acc))
            except (TypeError, ValueError):
                vel = float(default_vel)
                acc = float(default_acc)
        else:
            try:
                raw = list(value)
                if len(raw) >= 8:
                    vel = float(raw[6])
                    acc = float(raw[7])
            except (TypeError, ValueError):
                pass
        return {"position": pose, "vel_percent": vel, "acc_percent": acc}


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
            normalized = {"position": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "vel_percent": default_vel, "acc_percent": default_acc}
        values = list(normalized["position"]) + [normalized["vel_percent"], normalized["acc_percent"]]
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
        return {
            "position": values[:6],
            "vel_percent": values[6],
            "acc_percent": values[7],
        }

    def accept(self) -> None:
        try:
            waypoint = self.waypoint()
        except ValueError:
            show_warning(self, "Waypoint", "All waypoint values must be valid numbers.")
            return
        if not 0.0 <= waypoint["vel_percent"] <= 100.0 or not 0.0 <= waypoint["acc_percent"] <= 100.0:
            show_warning(self, "Waypoint", "Velocity and acceleration must be between 0 and 100 percent.")
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

    def __init__(self, parent=None):
        self.settings_view: KeyboardSettingsView | None = None
        self._status_label: QLabel | None = None
        self._layout: QVBoxLayout | None = None
        self._current_values: dict = {}
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
        pass

    def set_values(self, values: dict) -> None:
        self._current_values = dict(values)
        if self.settings_view is not None:
            self.settings_view.set_values(values)

    def set_safe_travel_position(self, position: list[float]) -> None:
        self._append_waypoint("safe_travel_positions", position)

    def set_dropoff_safe_travel_position(self, position: list[float]) -> None:
        self._append_waypoint("dropoff_safe_travel_positions", position)

    def values(self) -> dict:
        if self.settings_view is None:
            return dict(self._current_values)
        return self.settings_view.get_values()

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
        original_handler = widget_factory._REGISTRY.get("paint_action_button")
        original_pose_handler = widget_factory._REGISTRY.get("paint_pose_display")
        original_waypoint_handler = widget_factory._REGISTRY.get("paint_waypoint_table")
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
        try:
            for title, groups in build_paint_process_settings_tabs():
                self.settings_view.add_tab(title, groups)
        finally:
            if original_handler is None:
                widget_factory._REGISTRY.pop("paint_action_button", None)
            else:
                widget_factory._REGISTRY["paint_action_button"] = original_handler
            if original_pose_handler is None:
                widget_factory._REGISTRY.pop("paint_pose_display", None)
            else:
                widget_factory._REGISTRY["paint_pose_display"] = original_pose_handler
            if original_waypoint_handler is None:
                widget_factory._REGISTRY.pop("paint_waypoint_table", None)
            else:
                widget_factory._REGISTRY["paint_waypoint_table"] = original_waypoint_handler
        self.settings_view.value_changed_signal.connect(self._on_value_changed)
        self.settings_view.save_requested.connect(self._on_save_requested)
        self._layout.insertWidget(0, self.settings_view)

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
        if key == "safe_travel_positions" and value == "safe_travel_positions_add_current":
            self.set_safe_travel_current_requested.emit()
            return
        if key == "dropoff_safe_travel_positions" and value == "dropoff_safe_travel_positions_add_current":
            self.set_dropoff_safe_travel_current_requested.emit()
            return
        self._current_values = self.values()
        self.value_changed.emit(key, value)

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
