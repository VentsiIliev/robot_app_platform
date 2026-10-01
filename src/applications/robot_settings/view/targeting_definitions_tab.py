from __future__ import annotations

from copy import deepcopy
from typing import List

from PyQt6.QtCore import QCoreApplication, QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, BG_COLOR, BORDER, GHOST_BTN_STYLE, LABEL_STYLE,
    PRIMARY, SECONDARY_BG, TEXT_COLOR,
)
from src.applications.base.app_dialog import AppDialog, DIALOG_CHECKBOX_STYLE, DIALOG_INPUT_STYLE
from src.applications.base.styled_message_box import ask_yes_no, show_warning
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardLineEdit
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField


def _t(text: str) -> str:
    translated = QCoreApplication.translate("RobotSettings", text)
    return translated or text


_TARGET_CARD_STYLE = f"""
QFrame#targetCard {{ background: white; border: 1px solid {BORDER}; border-radius: 14px; }}
QLabel#targetCardHeader {{
    background: {SECONDARY_BG}; color: {PRIMARY};
    border-bottom: 1px solid {BORDER}; padding: 10px 16px;
    border-top-left-radius: 14px; border-top-right-radius: 14px;
    font-size: 10pt; font-weight: bold;
}}
QWidget#targetCardContent {{
    background: white; border-bottom-left-radius: 14px;
    border-bottom-right-radius: 14px;
}}
"""
_TARGET_BODY_STYLE = "QGroupBox { background: white; border: none; margin: 0; padding: 0; }"
_TARGET_INPUT_STYLE = f"""
QLineEdit, QComboBox {{
    background: white; color: {TEXT_COLOR}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 0 12px; min-height: 44px; font-size: 11pt;
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 32px; }}
"""
_TARGET_TABLE_STYLE = f"""
QTableWidget {{
    background: white; alternate-background-color: {BG_COLOR};
    color: {TEXT_COLOR}; border: 1px solid {BORDER}; border-radius: 8px;
    gridline-color: {BORDER}; font-size: 11pt;
}}
QHeaderView::section {{
    background: {PRIMARY}; color: white; border: none;
    padding: 8px 10px; font-size: 10pt; font-weight: bold;
}}
QTableWidget::item:selected {{ background: {SECONDARY_BG}; color: {PRIMARY}; }}
"""


def _calibration_choice(frame: dict) -> str:
    profile_id = str(frame.get("calibration_profile", "") or "").strip()
    if not profile_id:
        return "none"
    return "global" if profile_id == "global" else "local"


def _apply_calibration_choice(frame: dict, choice: str) -> dict:
    result = dict(frame)
    area_id = str(result.get("work_area_id", "") or "").strip()
    if choice == "global":
        result.update(
            calibration_profile="global",
            calibration_reference_frame="",
            calibration_matrix_path="",
        )
    elif choice == "local" and area_id:
        result.update(
            calibration_profile=f"{area_id}_local",
            calibration_reference_frame=area_id.lower(),
            calibration_matrix_path=f"calibrations/{area_id}/camera_to_robot.npy",
        )
    else:
        result.update(
            calibration_profile="",
            calibration_reference_frame="",
            calibration_matrix_path="",
        )
    return result


class TargetingDefinitionsTab(QWidget):
    definitions_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: List[dict] = []
        self._global_points: List[dict] = []
        self._area_points: dict[str, List[dict]] = {}
        self._visible_point_area = ""
        self._point_mode = "global"
        self._tcp_global: dict = {}
        self._tcp_original_global: dict = {}
        self._tcp_by_area: dict[str, dict] = {}
        self._tcp_mode = "global"
        self._tcp_dirty = False
        self._frames: List[dict] = []
        self._protected_points: set[str] = set()
        self._protected_frames: set[str] = set()
        self._coordinate_calibration_mode = "global"
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        root.addWidget(self._card(self._build_points_box()))
        root.addWidget(self._card(self._build_tcp_box(), translated=True))
        root.addWidget(self._card(self._build_frames_box()))
        root.addStretch()

    def _card(self, box: QGroupBox, *, translated: bool = False) -> QFrame:
        title = box.title()
        box.setTitle("")
        box.setStyleSheet(_TARGET_BODY_STYLE)
        card = QFrame()
        card.setObjectName("targetCard")
        card.setStyleSheet(_TARGET_CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QLabel(title.upper())
        header.setObjectName("targetCardHeader")
        layout.addWidget(header)
        body = QWidget()
        body.setObjectName("targetCardContent")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 12, 16, 16)
        body_layout.addWidget(box)
        layout.addWidget(body)
        if translated:
            self._tcp_card_header = header
        return card

    @staticmethod
    def _style_table(table: QTableWidget) -> None:
        table.setStyleSheet(_TARGET_TABLE_STYLE)
        table.setAlternatingRowColors(True)
        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(56)

    @staticmethod
    def _size_table(table: QTableWidget) -> None:
        table.setFixedHeight(38 + 56 * min(max(table.rowCount(), 1), 5))

    def _build_points_box(self) -> QGroupBox:
        box = QGroupBox("Target Points")
        layout = QVBoxLayout(box)

        desc = QLabel("Measured XY references in robot coordinates. The active robot system can resolve offsets from these named points.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555;")
        layout.addWidget(desc)

        self._per_area_points = QCheckBox(_t("Use per-area target points"))
        self._per_area_points.setStyleSheet(DIALOG_CHECKBOX_STYLE)
        self._per_area_points.toggled.connect(self._on_point_scope_changed)
        layout.addWidget(self._per_area_points)
        scope_row = QHBoxLayout()
        self._point_scope_label = QLabel(_t("Edit points for"))
        scope_row.addWidget(self._point_scope_label)
        self._point_area = QComboBox()
        self._point_area.setStyleSheet(_TARGET_INPUT_STYLE)
        self._point_area.currentIndexChanged.connect(self._show_point_scope)
        scope_row.addWidget(self._point_area)
        self._local_points = QCheckBox(_t("Use local points for this area"))
        self._local_points.toggled.connect(self._on_local_points_changed)
        scope_row.addWidget(self._local_points)
        layout.addLayout(scope_row)

        self._points_table = QTableWidget(0, 5)
        self._points_table.setColumnCount(4)
        self._points_table.setHorizontalHeaderLabels(["Name", "Label", "X (mm)", "Y (mm)"])
        self._points_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._points_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._points_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._points_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._style_table(self._points_table)
        self._points_table.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self._points_table)

        row = QHBoxLayout()
        self._add_point_btn = QPushButton("Add Point")
        self._edit_point_btn = QPushButton("Edit Point")
        self._remove_point_btn = QPushButton("Remove Point")
        self._add_point_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._edit_point_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._remove_point_btn.setStyleSheet(GHOST_BTN_STYLE)
        for btn in (self._add_point_btn, self._edit_point_btn, self._remove_point_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        self._add_point_btn.clicked.connect(self._on_add_point)
        self._edit_point_btn.clicked.connect(self._on_edit_point)
        self._remove_point_btn.clicked.connect(self._on_remove_point)
        return box

    def _build_tcp_box(self) -> QGroupBox:
        box = QGroupBox(_t("Camera-to-TCP calibration"))
        self._tcp_box = box
        layout = QVBoxLayout(box)
        self._tcp_help = QLabel(_t(
            "Automatic mode uses these offsets. Manual mode uses the target points."
        ))
        self._tcp_help.setWordWrap(True)
        layout.addWidget(self._tcp_help)
        self._per_area_tcp = QCheckBox(_t("Use per-area camera-to-TCP calibration"))
        self._per_area_tcp.setStyleSheet(DIALOG_CHECKBOX_STYLE)
        self._per_area_tcp.toggled.connect(self._on_tcp_scope_changed)
        layout.addWidget(self._per_area_tcp)
        row = QHBoxLayout()
        self._tcp_scope_label = QLabel(_t("Edit calibration for"))
        row.addWidget(self._tcp_scope_label)
        self._tcp_area = QComboBox()
        self._tcp_area.setStyleSheet(_TARGET_INPUT_STYLE)
        self._tcp_area.currentIndexChanged.connect(self._show_tcp_scope)
        row.addWidget(self._tcp_area)
        self._local_tcp = QCheckBox(_t("Use local calibration for this area"))
        self._local_tcp.toggled.connect(self._on_local_tcp_changed)
        row.addWidget(self._local_tcp)
        layout.addLayout(row)
        values = QHBoxLayout()
        self._tcp_x = KeyboardNumberField(decimal=True)
        self._tcp_y = KeyboardNumberField(decimal=True)
        for edit in (self._tcp_x, self._tcp_y):
            edit.setRange(-1_000_000.0, 1_000_000.0)
            edit.setDecimals(3)
            edit.setSingleStep(0.1)
        self._tcp_x_label = QLabel(_t("X (mm)"))
        self._tcp_y_label = QLabel(_t("Y (mm)"))
        for label, edit in ((self._tcp_x_label, self._tcp_x), (self._tcp_y_label, self._tcp_y)):
            values.addWidget(label)
            values.addWidget(edit)
            edit.valueChanged.connect(self._on_tcp_value_changed)
        self._tcp_residual_count = QLabel()
        values.addWidget(self._tcp_residual_count)
        layout.addLayout(values)
        return box

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._per_area_points.setText(_t("Use per-area target points"))
            self._point_scope_label.setText(_t("Edit points for"))
            self._local_points.setText(_t("Use local points for this area"))
            self._per_area_tcp.setText(_t("Use per-area camera-to-TCP calibration"))
            self._tcp_card_header.setText(_t("Camera-to-TCP calibration").upper())
            self._tcp_help.setText(_t(
                "Automatic mode uses these offsets. Manual mode uses the target points."
            ))
            self._tcp_scope_label.setText(_t("Edit calibration for"))
            self._local_tcp.setText(_t("Use local calibration for this area"))
            self._tcp_x_label.setText(_t("X (mm)"))
            self._tcp_y_label.setText(_t("Y (mm)"))
            self._point_area.setItemText(0, _t("Global"))
            self._tcp_area.setItemText(0, _t("Global"))
            self._show_tcp_scope()
        super().changeEvent(event)

    def _build_frames_box(self) -> QGroupBox:
        box = QGroupBox("Frames")
        layout = QVBoxLayout(box)

        desc = QLabel("Named coordinate planes. Optional navigation groups define a rigid mapper. Height correction applies only when enabled.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555;")
        layout.addWidget(desc)

        self._per_area_calibration = QCheckBox(_t("Use per-area vision calibration"))
        self._per_area_calibration.setStyleSheet(DIALOG_CHECKBOX_STYLE)
        self._per_area_calibration.toggled.connect(self._on_calibration_mode_changed)
        layout.addWidget(self._per_area_calibration)

        self._frames_table = QTableWidget(0, 6)
        self._frames_table.setHorizontalHeaderLabels([
            _t("Name"), _t("Work Area"), _t("Source Group"), _t("Target Group"),
            _t("Height Correction"), _t("Vision Calibration"),
        ])
        self._frames_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._frames_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._frames_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._frames_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._style_table(self._frames_table)
        self._frames_table.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self._frames_table)

        row = QHBoxLayout()
        self._add_frame_btn = QPushButton("Add Frame")
        self._edit_frame_btn = QPushButton("Edit Frame")
        self._remove_frame_btn = QPushButton("Remove Frame")
        self._add_frame_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._edit_frame_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._remove_frame_btn.setStyleSheet(GHOST_BTN_STYLE)
        for btn in (self._add_frame_btn, self._edit_frame_btn, self._remove_frame_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

        self._add_frame_btn.clicked.connect(self._on_add_frame)
        self._edit_frame_btn.clicked.connect(self._on_edit_frame)
        self._remove_frame_btn.clicked.connect(self._on_remove_frame)
        return box

    def load(self, data: dict | None) -> None:
        payload = data or {}
        self._global_points = deepcopy(payload.get("points", []))
        self._area_points = deepcopy(payload.get("area_points", {}))
        self._point_mode = str(payload.get("point_mode", "global"))
        self._visible_point_area = ""
        self._points = self._global_points
        self._frames = [dict(item) for item in payload.get("frames", [])]
        self._tcp_global = deepcopy(payload.get("camera_to_tcp_global", {}))
        self._tcp_original_global = deepcopy(self._tcp_global)
        self._tcp_by_area = deepcopy(payload.get("camera_to_tcp_by_area", {}))
        self._tcp_mode = str(payload.get("camera_to_tcp_mode", "global"))
        self._tcp_dirty = False
        area_ids = sorted({
            str(frame.get("work_area_id", "") or "").strip()
            for frame in self._frames if str(frame.get("work_area_id", "") or "").strip()
        })
        for combo in (self._point_area, self._tcp_area):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(_t("Global"), "")
            for area in area_ids:
                combo.addItem(area, area)
            combo.blockSignals(False)
        self._per_area_points.blockSignals(True)
        self._per_area_points.setChecked(self._point_mode == "per_area")
        self._per_area_points.blockSignals(False)
        self._per_area_tcp.blockSignals(True)
        self._per_area_tcp.setChecked(self._tcp_mode == "per_area")
        self._per_area_tcp.blockSignals(False)
        self._show_point_scope()
        self._show_tcp_scope()
        self._protected_points = {
            str(name).strip().lower() for name in payload.get("protected_points", [])
        }
        self._protected_frames = {
            str(name).strip().lower() for name in payload.get("protected_frames", [])
        }
        self._coordinate_calibration_mode = str(
            payload.get("coordinate_calibration_mode", "global") or "global"
        )
        self._per_area_calibration.blockSignals(True)
        self._per_area_calibration.setChecked(
            self._coordinate_calibration_mode == "per_area"
        )
        self._per_area_calibration.blockSignals(False)
        self._reload_points_table()
        self._reload_frames_table()
        self._update_buttons()

    def get_values(self) -> dict:
        return {
            "points": deepcopy(self._global_points),
            "point_mode": self._point_mode,
            "area_points": deepcopy(self._area_points),
            "camera_to_tcp_mode": self._tcp_mode,
            "camera_to_tcp_global": deepcopy(self._tcp_global),
            "camera_to_tcp_global_changed": self._tcp_global != self._tcp_original_global,
            "camera_to_tcp_by_area": deepcopy(self._tcp_by_area),
            "camera_to_tcp_changed": self._tcp_dirty,
            "frames": [dict(item) for item in self._frames],
            "protected_points": sorted(self._protected_points),
            "protected_frames": sorted(self._protected_frames),
            "coordinate_calibration_mode": self._coordinate_calibration_mode,
        }

    def _selected_area(self, combo: QComboBox, mode: str) -> str:
        return str(combo.currentData() or "").strip() if mode == "per_area" else ""

    def _show_point_scope(self) -> None:
        area = self._selected_area(self._point_area, self._point_mode)
        self._point_area.setEnabled(self._point_mode == "per_area")
        self._local_points.setVisible(bool(area))
        self._local_points.blockSignals(True)
        self._local_points.setChecked(area in self._area_points if area else False)
        self._local_points.blockSignals(False)
        self._visible_point_area = area
        self._points = self._area_points.get(area, self._global_points)
        editable = not area or area in self._area_points
        for button in (self._add_point_btn, self._edit_point_btn, self._remove_point_btn):
            button.setVisible(editable)
        self._reload_points_table()
        self._update_buttons()

    def _on_point_scope_changed(self, _value=None) -> None:
        self._point_mode = "per_area" if self._per_area_points.isChecked() else "global"
        self._show_point_scope()
        self.definitions_changed.emit()

    def _on_local_points_changed(self, enabled: bool) -> None:
        area = self._selected_area(self._point_area, self._point_mode)
        if not area:
            return
        if enabled:
            self._area_points[area] = deepcopy(self._global_points)
        else:
            self._area_points.pop(area, None)
        self._show_point_scope()
        self.definitions_changed.emit()

    def _tcp_values(self) -> dict:
        area = self._selected_area(self._tcp_area, self._tcp_mode)
        return self._tcp_by_area.get(area, self._tcp_global)

    def _show_tcp_scope(self) -> None:
        area = self._selected_area(self._tcp_area, self._tcp_mode)
        self._tcp_area.setEnabled(self._tcp_mode == "per_area")
        self._local_tcp.setVisible(bool(area))
        self._local_tcp.blockSignals(True)
        self._local_tcp.setChecked(area in self._tcp_by_area if area else False)
        self._local_tcp.blockSignals(False)
        values = self._tcp_values()
        for edit, key in ((self._tcp_x, "x_mm"), (self._tcp_y, "y_mm")):
            edit.blockSignals(True)
            edit.setValue(float(values.get(key, 0.0)))
            edit.setReadOnly(bool(area and area not in self._tcp_by_area))
            edit.blockSignals(False)
        self._tcp_residual_count.setText(
            _t("Rotation residuals: {count}").format(
                count=len(values.get("rotation_residuals", []))
            )
        )

    def _on_tcp_scope_changed(self, _value=None) -> None:
        self._tcp_mode = "per_area" if self._per_area_tcp.isChecked() else "global"
        self._show_tcp_scope()
        self._tcp_dirty = True
        self.definitions_changed.emit()
        self._tcp_dirty = False

    def _on_local_tcp_changed(self, enabled: bool) -> None:
        area = self._selected_area(self._tcp_area, self._tcp_mode)
        if not area:
            return
        if enabled:
            self._tcp_by_area[area] = deepcopy(self._tcp_global)
        else:
            self._tcp_by_area.pop(area, None)
        self._show_tcp_scope()
        self._tcp_dirty = True
        self.definitions_changed.emit()
        self._tcp_dirty = False

    def _on_tcp_value_changed(self) -> None:
        values = self._tcp_values()
        x_mm = self._tcp_x.value()
        y_mm = self._tcp_y.value()
        if values.get("x_mm") == x_mm and values.get("y_mm") == y_mm:
            return
        values["x_mm"] = x_mm
        values["y_mm"] = y_mm
        self._tcp_dirty = True
        self.definitions_changed.emit()
        if values is self._tcp_global:
            self._tcp_original_global = deepcopy(self._tcp_global)
        self._tcp_dirty = False

    def _reload_points_table(self) -> None:
        self._points_table.setRowCount(0)
        for point in self._points:
            row = self._points_table.rowCount()
            self._points_table.insertRow(row)
            self._points_table.setItem(row, 0, QTableWidgetItem(str(point.get("name", ""))))
            self._points_table.setItem(row, 1, QTableWidgetItem(str(point.get("display_name", point.get("name", "")))))
            self._points_table.setItem(row, 2, QTableWidgetItem(f"{float(point.get('x_mm', 0.0)):.3f}"))
            self._points_table.setItem(row, 3, QTableWidgetItem(f"{float(point.get('y_mm', 0.0)):.3f}"))
        self._size_table(self._points_table)

    def _reload_frames_table(self) -> None:
        self._frames_table.setRowCount(0)
        for frame in self._frames:
            row = self._frames_table.rowCount()
            self._frames_table.insertRow(row)
            self._frames_table.setItem(row, 0, QTableWidgetItem(str(frame.get("name", ""))))
            self._frames_table.setItem(row, 1, QTableWidgetItem(str(frame.get("work_area_id", ""))))
            self._frames_table.setItem(row, 2, QTableWidgetItem(str(frame.get("source_navigation_group", ""))))
            self._frames_table.setItem(row, 3, QTableWidgetItem(str(frame.get("target_navigation_group", ""))))
            self._frames_table.setItem(row, 4, QTableWidgetItem("Yes" if frame.get("use_height_correction", False) else "No"))
            choice_labels = {
                "none": _t("Not configured"),
                "global": _t("Global"),
                "local": _t("Local"),
            }
            self._frames_table.setItem(
                row, 5, QTableWidgetItem(choice_labels[_calibration_choice(frame)])
            )
        self._size_table(self._frames_table)

    def _on_calibration_mode_changed(self, enabled: bool) -> None:
        self._coordinate_calibration_mode = "per_area" if enabled else "global"
        self.definitions_changed.emit()

    def _selected_point_index(self) -> int | None:
        row = self._points_table.currentRow()
        return row if row >= 0 else None

    def _selected_frame_index(self) -> int | None:
        row = self._frames_table.currentRow()
        return row if row >= 0 else None

    def _update_buttons(self) -> None:
        point_idx = self._selected_point_index()
        frame_idx = self._selected_frame_index()
        self._edit_point_btn.setEnabled(point_idx is not None)
        self._remove_point_btn.setEnabled(point_idx is not None)
        self._edit_frame_btn.setEnabled(frame_idx is not None)
        self._remove_frame_btn.setEnabled(frame_idx is not None)

    def _on_add_point(self) -> None:
        dlg = _PointDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        point = dlg.get_values()
        if self._find_point(point["name"]) is not None:
            show_warning(
                self,
                _t("Add Point"),
                _t("Point '{name}' already exists.").format(name=point["name"]),
            )
            return
        self._points.append(point)
        self._points.sort(key=lambda item: item["name"])
        self._reload_points_table()
        self.definitions_changed.emit()

    def _on_edit_point(self) -> None:
        idx = self._selected_point_index()
        if idx is None:
            return
        point = self._points[idx]
        dlg = _PointDialog(
            point,
            protected_name=str(point.get("name", "")) in self._protected_points,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dlg.get_values()
        existing = self._find_point(updated["name"])
        if existing is not None and existing != idx:
            show_warning(
                self,
                _t("Edit Point"),
                _t("Point '{name}' already exists.").format(name=updated["name"]),
            )
            return
        self._points[idx] = updated
        self._points.sort(key=lambda item: item["name"])
        self._reload_points_table()
        self.definitions_changed.emit()

    def _on_remove_point(self) -> None:
        idx = self._selected_point_index()
        if idx is None:
            return
        name = str(self._points[idx].get("name", ""))
        if name in self._protected_points:
            show_warning(
                self,
                _t("Remove Point"),
                _t("Point '{name}' is marked as required and cannot be removed.").format(name=name),
            )
            return
        if not ask_yes_no(self, _t("Remove Point"), _t("Remove point '{name}'?").format(name=name)):
            return
        self._points.pop(idx)
        self._reload_points_table()
        self.definitions_changed.emit()

    def _on_add_frame(self) -> None:
        dlg = _FrameDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        frame = dlg.get_values()
        if self._find_frame(frame["name"]) is not None:
            show_warning(
                self,
                _t("Add Frame"),
                _t("Frame '{name}' already exists.").format(name=frame["name"]),
            )
            return
        self._frames.append(frame)
        self._frames.sort(key=lambda item: item["name"])
        self._reload_frames_table()
        self.definitions_changed.emit()

    def _on_edit_frame(self) -> None:
        idx = self._selected_frame_index()
        if idx is None:
            return
        dlg = _FrameDialog(self._frames[idx], parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dlg.get_values()
        existing = self._find_frame(updated["name"])
        if existing is not None and existing != idx:
            show_warning(
                self,
                _t("Edit Frame"),
                _t("Frame '{name}' already exists.").format(name=updated["name"]),
            )
            return
        self._frames[idx] = updated
        self._frames.sort(key=lambda item: item["name"])
        self._reload_frames_table()
        self.definitions_changed.emit()

    def _on_remove_frame(self) -> None:
        idx = self._selected_frame_index()
        if idx is None:
            return
        name = str(self._frames[idx].get("name", ""))
        if name in self._protected_frames:
            show_warning(
                self,
                _t("Remove Frame"),
                _t("Frame '{name}' is marked as required and cannot be removed.").format(name=name),
            )
            return
        if not ask_yes_no(self, _t("Remove Frame"), _t("Remove frame '{name}'?").format(name=name)):
            return
        self._frames.pop(idx)
        self._reload_frames_table()
        self.definitions_changed.emit()

    def _find_point(self, name: str) -> int | None:
        normalized = str(name).strip().lower()
        for idx, point in enumerate(self._points):
            if point.get("name") == normalized:
                return idx
        return None

    def _find_frame(self, name: str) -> int | None:
        normalized = str(name).strip().lower()
        for idx, frame in enumerate(self._frames):
            if frame.get("name") == normalized:
                return idx
        return None


class _PointDialog(AppDialog):
    def __init__(self, data: dict | None = None, protected_name: bool = False, parent=None):
        super().__init__("Target Point", min_width=420, parent=parent)
        data = data or {}
        self._protected_name = bool(protected_name)
        self._virtual_keyboard_dock_window = parent.window() if parent is not None else None
        self._keyboard_scroll_area: QScrollArea | None = None
        self._keyboard_bottom_spacer: QWidget | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        form_host = QWidget(self)
        form = QFormLayout(form_host)
        form.setSpacing(12)
        self._name = self._line_edit(str(data.get("name", "")))
        self._display_name = self._line_edit(str(data.get("display_name", data.get("name", ""))))
        self._x = self._line_edit(str(data.get("x_mm", 0.0)))
        self._y = self._line_edit(str(data.get("y_mm", 0.0)))
        self._name.setReadOnly(self._protected_name)
        if self._protected_name:
            self._name.setToolTip("This is a required system target id. Change Label instead.")
        form.addRow(self._label("Name"), self._name)
        form.addRow(self._label("Label"), self._display_name)
        form.addRow(self._label("X (mm)"), self._x)
        form.addRow(self._label("Y (mm)"), self._y)
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
        self._reserve_keyboard_space(keyboard_rect)

    def _on_virtual_keyboard_hidden(self) -> None:
        if self._keyboard_bottom_spacer is not None:
            self._keyboard_bottom_spacer.setFixedHeight(0)

    def _reserve_keyboard_space(self, keyboard_rect) -> None:
        if self._keyboard_scroll_area is None:
            return

        viewport = self._keyboard_scroll_area.viewport()
        overlap = viewport.mapToGlobal(viewport.rect().bottomLeft()).y() - keyboard_rect.top() + 24
        if self._keyboard_bottom_spacer is not None:
            self._keyboard_bottom_spacer.setFixedHeight(max(0, overlap))

        focused = self.focusWidget()
        if focused is not None:
            QTimer.singleShot(
                0,
                lambda: self._keyboard_scroll_area.ensureWidgetVisible(focused, 12, 12),
            )

    def get_values(self) -> dict:
        return {
            "name": self._name.text().strip().lower(),
            "display_name": self._display_name.text().strip() or self._name.text().strip().lower(),
            "x_mm": float(self._x.text().strip() or 0.0),
            "y_mm": float(self._y.text().strip() or 0.0),
        }

    def accept(self) -> None:
        if not self._name.text().strip():
            show_warning(self, _t("Target Point"), _t("Name cannot be empty."))
            return
        try:
            float(self._x.text().strip() or 0.0)
            float(self._y.text().strip() or 0.0)
        except ValueError:
            show_warning(self, _t("Target Point"), _t("X and Y must be valid numbers."))
            return
        super().accept()

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(LABEL_STYLE)
        return label

    @staticmethod
    def _line_edit(value: str) -> QLineEdit:
        edit = KeyboardLineEdit(value)
        edit.setStyleSheet(DIALOG_INPUT_STYLE)
        return edit


class _FrameDialog(AppDialog):
    def __init__(self, data: dict | None = None, parent=None):
        super().__init__("Target Frame", min_width=440, parent=parent)
        data = data or {}
        self._virtual_keyboard_dock_window = parent.window() if parent is not None else None
        self._keyboard_scroll_area: QScrollArea | None = None
        self._keyboard_bottom_spacer: QWidget | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        form_host = QWidget(self)
        form = QFormLayout(form_host)
        form.setSpacing(12)
        self._name = self._line_edit(str(data.get("name", "")))
        self._source = self._line_edit(str(data.get("source_navigation_group", "")))
        self._target = self._line_edit(str(data.get("target_navigation_group", "")))
        self._height = QCheckBox("Use height correction")
        self._height.setChecked(bool(data.get("use_height_correction", False)))
        self._height.setStyleSheet(DIALOG_CHECKBOX_STYLE)
        form.addRow(self._label("Name"), self._name)
        form.addRow(self._label("Source Group"), self._source)
        form.addRow(self._label("Target Group"), self._target)
        form.addRow(QLabel(""), self._height)
        self._work_area = self._line_edit(str(data.get("work_area_id", "")))
        self._work_area.setReadOnly(True)
        self._calibration_choice = QComboBox()
        self._calibration_choice.setStyleSheet(DIALOG_INPUT_STYLE)
        self._calibration_choice.addItem(_t("Not configured"), "none")
        self._calibration_choice.addItem(_t("Global"), "global")
        self._calibration_choice.addItem(_t("Local"), "local")
        choice_index = self._calibration_choice.findData(_calibration_choice(data))
        self._calibration_choice.setCurrentIndex(max(0, choice_index))
        form.addRow(self._label(_t("Work Area")), self._work_area)
        form.addRow(self._label(_t("Vision Calibration")), self._calibration_choice)
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
        self._reserve_keyboard_space(keyboard_rect)

    def _on_virtual_keyboard_hidden(self) -> None:
        if self._keyboard_bottom_spacer is not None:
            self._keyboard_bottom_spacer.setFixedHeight(0)

    def _reserve_keyboard_space(self, keyboard_rect) -> None:
        if self._keyboard_scroll_area is None:
            return

        viewport = self._keyboard_scroll_area.viewport()
        overlap = viewport.mapToGlobal(viewport.rect().bottomLeft()).y() - keyboard_rect.top() + 24
        if self._keyboard_bottom_spacer is not None:
            self._keyboard_bottom_spacer.setFixedHeight(max(0, overlap))

        focused = self.focusWidget()
        if focused is not None:
            QTimer.singleShot(
                0,
                lambda: self._keyboard_scroll_area.ensureWidgetVisible(focused, 12, 12),
            )

    def get_values(self) -> dict:
        values = {
            "name": self._name.text().strip().lower(),
            "source_navigation_group": self._source.text().strip(),
            "target_navigation_group": self._target.text().strip(),
            "use_height_correction": self._height.isChecked(),
            "work_area_id": self._work_area.text().strip(),
        }
        return _apply_calibration_choice(
            values,
            str(self._calibration_choice.currentData() or "none"),
        )

    def accept(self) -> None:
        if not self._name.text().strip():
            show_warning(self, _t("Target Frame"), _t("Name cannot be empty."))
            return
        if self._calibration_choice.currentData() == "local" and not self._work_area.text().strip():
            show_warning(
                self,
                _t("Target Frame"),
                _t("Local calibration requires a work area."),
            )
            return
        super().accept()

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(LABEL_STYLE)
        return label

    @staticmethod
    def _line_edit(value: str) -> QLineEdit:
        edit = KeyboardLineEdit(value)
        edit.setStyleSheet(DIALOG_INPUT_STYLE)
        return edit
