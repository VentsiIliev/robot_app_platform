from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import ACTION_BTN_STYLE, GHOST_BTN_STYLE, GROUP_STYLE, LABEL_STYLE
from src.applications.base.app_dialog import AppDialog, DIALOG_CHECKBOX_STYLE, DIALOG_INPUT_STYLE
from src.applications.base.styled_message_box import ask_yes_no, show_warning


class TargetingDefinitionsTab(QWidget):
    definitions_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: List[dict] = []
        self._frames: List[dict] = []
        self._protected_points: set[str] = set()
        self._protected_frames: set[str] = set()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        root.addWidget(self._build_points_box())
        root.addWidget(self._build_frames_box())
        root.addStretch()

    def _build_points_box(self) -> QGroupBox:
        box = QGroupBox("Target Points")
        box.setStyleSheet(GROUP_STYLE)
        layout = QVBoxLayout(box)

        desc = QLabel("Measured XY references in robot coordinates. The active robot system can resolve offsets from these named points.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555;")
        layout.addWidget(desc)

        self._points_table = QTableWidget(0, 5)
        self._points_table.setHorizontalHeaderLabels(["Name", "Label", "X (mm)", "Y (mm)", "Aliases"])
        self._points_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._points_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._points_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._points_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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

    def _build_frames_box(self) -> QGroupBox:
        box = QGroupBox("Frames")
        box.setStyleSheet(GROUP_STYLE)
        layout = QVBoxLayout(box)

        desc = QLabel("Named coordinate planes. Optional navigation groups define a rigid mapper. Height correction applies only when enabled.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #555;")
        layout.addWidget(desc)

        self._frames_table = QTableWidget(0, 4)
        self._frames_table.setHorizontalHeaderLabels(["Name", "Source Group", "Target Group", "Height Correction"])
        self._frames_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._frames_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._frames_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._frames_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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
        self._points = [dict(item) for item in payload.get("points", [])]
        self._frames = [dict(item) for item in payload.get("frames", [])]
        self._protected_points = {
            str(name).strip().lower() for name in payload.get("protected_points", [])
        }
        self._protected_frames = {
            str(name).strip().lower() for name in payload.get("protected_frames", [])
        }
        self._reload_points_table()
        self._reload_frames_table()
        self._update_buttons()

    def get_values(self) -> dict:
        return {
            "points": [dict(item) for item in self._points],
            "frames": [dict(item) for item in self._frames],
            "protected_points": sorted(self._protected_points),
            "protected_frames": sorted(self._protected_frames),
        }

    def _reload_points_table(self) -> None:
        self._points_table.setRowCount(0)
        for point in self._points:
            row = self._points_table.rowCount()
            self._points_table.insertRow(row)
            self._points_table.setItem(row, 0, QTableWidgetItem(str(point.get("name", ""))))
            self._points_table.setItem(row, 1, QTableWidgetItem(str(point.get("display_name", point.get("name", "")))))
            self._points_table.setItem(row, 2, QTableWidgetItem(f"{float(point.get('x_mm', 0.0)):.3f}"))
            self._points_table.setItem(row, 3, QTableWidgetItem(f"{float(point.get('y_mm', 0.0)):.3f}"))
            aliases = ", ".join(point.get("aliases", []))
            self._points_table.setItem(row, 4, QTableWidgetItem(aliases))

    def _reload_frames_table(self) -> None:
        self._frames_table.setRowCount(0)
        for frame in self._frames:
            row = self._frames_table.rowCount()
            self._frames_table.insertRow(row)
            self._frames_table.setItem(row, 0, QTableWidgetItem(str(frame.get("name", ""))))
            self._frames_table.setItem(row, 1, QTableWidgetItem(str(frame.get("source_navigation_group", ""))))
            self._frames_table.setItem(row, 2, QTableWidgetItem(str(frame.get("target_navigation_group", ""))))
            self._frames_table.setItem(row, 3, QTableWidgetItem("Yes" if frame.get("use_height_correction", False) else "No"))

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
            show_warning(self, "Add Point", f"Point '{point['name']}' already exists.")
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
            show_warning(self, "Edit Point", f"Point '{updated['name']}' already exists.")
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
            show_warning(self, "Remove Point", f"Point '{name}' is marked as required and cannot be removed.")
            return
        if not ask_yes_no(self, "Remove Point", f"Remove point '{name}'?"):
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
            show_warning(self, "Add Frame", f"Frame '{frame['name']}' already exists.")
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
            show_warning(self, "Edit Frame", f"Frame '{updated['name']}' already exists.")
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
            show_warning(self, "Remove Frame", f"Frame '{name}' is marked as required and cannot be removed.")
            return
        if not ask_yes_no(self, "Remove Frame", f"Remove frame '{name}'?"):
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

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(12)
        self._name = self._line_edit(str(data.get("name", "")))
        self._display_name = self._line_edit(str(data.get("display_name", data.get("name", ""))))
        self._x = self._line_edit(str(data.get("x_mm", 0.0)))
        self._y = self._line_edit(str(data.get("y_mm", 0.0)))
        self._aliases = self._line_edit(", ".join(data.get("aliases", [])))
        self._name.setReadOnly(self._protected_name)
        if self._protected_name:
            self._name.setToolTip("This is a required system target id. Change Label instead.")
        form.addRow(self._label("Name"), self._name)
        form.addRow(self._label("Label"), self._display_name)
        form.addRow(self._label("X (mm)"), self._x)
        form.addRow(self._label("Y (mm)"), self._y)
        form.addRow(self._label("Aliases"), self._aliases)
        root.addLayout(form)
        root.addWidget(self._build_button_row(ok_label="Save"))

    def get_values(self) -> dict:
        aliases = [
            alias.strip().lower()
            for alias in self._aliases.text().split(",")
            if alias.strip()
        ]
        return {
            "name": self._name.text().strip().lower(),
            "display_name": self._display_name.text().strip() or self._name.text().strip().lower(),
            "x_mm": float(self._x.text().strip() or 0.0),
            "y_mm": float(self._y.text().strip() or 0.0),
            "aliases": aliases,
        }

    def accept(self) -> None:
        if not self._name.text().strip():
            show_warning(self, "Target Point", "Name cannot be empty.")
            return
        try:
            float(self._x.text().strip() or 0.0)
            float(self._y.text().strip() or 0.0)
        except ValueError:
            show_warning(self, "Target Point", "X and Y must be valid numbers.")
            return
        super().accept()

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(LABEL_STYLE)
        return label

    @staticmethod
    def _line_edit(value: str) -> QLineEdit:
        edit = QLineEdit(value)
        edit.setStyleSheet(DIALOG_INPUT_STYLE)
        return edit


class _FrameDialog(AppDialog):
    def __init__(self, data: dict | None = None, parent=None):
        super().__init__("Target Frame", min_width=440, parent=parent)
        data = data or {}

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        form = QFormLayout()
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
        root.addLayout(form)
        root.addWidget(self._build_button_row(ok_label="Save"))

    def get_values(self) -> dict:
        return {
            "name": self._name.text().strip().lower(),
            "source_navigation_group": self._source.text().strip(),
            "target_navigation_group": self._target.text().strip(),
            "use_height_correction": self._height.isChecked(),
        }

    def accept(self) -> None:
        if not self._name.text().strip():
            show_warning(self, "Target Frame", "Name cannot be empty.")
            return
        super().accept()

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(LABEL_STYLE)
        return label

    @staticmethod
    def _line_edit(value: str) -> QLineEdit:
        edit = QLineEdit(value)
        edit.setStyleSheet(DIALOG_INPUT_STYLE)
        return edit
