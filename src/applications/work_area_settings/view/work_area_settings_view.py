from __future__ import annotations

import cv2
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    GHOST_BTN_STYLE,
    GROUP_STYLE,
    LABEL_STYLE,
    PRIMARY,
)
from pl_gui.utils.utils_widgets.camera_view import CameraView
from src.applications.base.i_application_view import IApplicationView
from src.shared_contracts.declarations import WorkAreaDefinition

_STATE_COLORS = {
    "IDLE": ("#8888AA", "#1A1A2E"),
    "INITIALIZING": ("#00CCFF", "#0D1B2A"),
    "STARTED": ("#44FF88", "#0D1F18"),
    "PAUSED": ("#FFCC00", "#1F1A00"),
    "STOPPED": ("#FF8C32", "#1F1000"),
    "ERROR": ("#FF4466", "#1F0010"),
    "UNKNOWN": ("#555577", "#12121F"),
}
_STATE_LABEL_STYLE = """
    QLabel {{
        color: {fg};
        background: {bg};
        border-bottom: 2px solid {fg};
        font-size: 9pt;
        font-weight: bold;
        letter-spacing: 1px;
        padding: 4px 10px;
    }}
"""
_SECTION_HINT_STYLE = "color: #666688; font-size: 9pt; background: transparent;"
_BRIGHTNESS_COLOR = "#00CCFF"
_ROLE_BTN_STYLE = (
    GHOST_BTN_STYLE
    + f"""
QPushButton:checked {{
    background-color: {PRIMARY};
    color: white;
    border-color: {PRIMARY};
}}
"""
)


class WorkAreaSettingsView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_FRAME_SELECTOR_ENABLED = True

    work_area_changed = pyqtSignal(str)
    save_area_requested = pyqtSignal(str)
    vision_state_changed = pyqtSignal(str)

    def __init__(
        self,
        work_area_definitions: list[WorkAreaDefinition] | None = None,
        parent=None,
    ):
        self._work_area_definitions = list(work_area_definitions or [])
        self._active_area_key = ""
        super().__init__("WorkAreaSettings", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_preview_panel(), stretch=3)
        root.addWidget(self._build_editor_panel(), stretch=2)
        self._connect_signals()
        self.vision_state_changed.connect(self._on_vision_state_changed)
        self._rebuild_area_choices()

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background-color: {BG_COLOR};")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        fg, bg = _STATE_COLORS["UNKNOWN"]
        self._state_label = QLabel("● UNKNOWN")
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_label.setFixedHeight(28)
        self._state_label.setStyleSheet(_STATE_LABEL_STYLE.format(fg=fg, bg=bg))
        layout.addWidget(self._state_label)

        self._preview_label = CameraView()
        self._preview_label.setMaximumHeight(720)
        layout.addWidget(self._preview_label, stretch=1)
        return panel

    def _build_editor_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(
            f"background-color: white; border-left: 1px solid {BORDER};"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Work Area Editor")
        title.setStyleSheet(LABEL_STYLE)
        layout.addWidget(title)

        hint = QLabel(
            "Select a declared work area, choose which ROI to edit, then place or drag the four corners on the preview."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(_SECTION_HINT_STYLE)
        layout.addWidget(hint)

        selector_box = QGroupBox("Selection")
        selector_box.setStyleSheet(GROUP_STYLE)
        selector_layout = QVBoxLayout(selector_box)
        selector_layout.setContentsMargins(12, 16, 12, 12)
        selector_layout.setSpacing(10)

        area_label = QLabel("Work Area")
        area_label.setStyleSheet(LABEL_STYLE)
        self._work_area_combo = QComboBox()
        self._work_area_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        selector_layout.addWidget(area_label)
        selector_layout.addWidget(self._work_area_combo)

        role_label = QLabel("ROI Role")
        role_label.setStyleSheet(LABEL_STYLE)
        selector_layout.addWidget(role_label)

        role_row = QHBoxLayout()
        role_row.setContentsMargins(0, 0, 0, 0)
        role_row.setSpacing(8)
        self._detection_btn = QPushButton("Detection ROI")
        self._brightness_btn = QPushButton("Brightness ROI")
        for button in (self._detection_btn, self._brightness_btn):
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(_ROLE_BTN_STYLE)
        role_row.addWidget(self._detection_btn)
        role_row.addWidget(self._brightness_btn)
        selector_layout.addLayout(role_row)

        layout.addWidget(selector_box)

        actions_box = QGroupBox("Actions")
        actions_box.setStyleSheet(GROUP_STYLE)
        actions_layout = QVBoxLayout(actions_box)
        actions_layout.setContentsMargins(12, 16, 12, 12)
        actions_layout.setSpacing(10)

        self._active_area_label = QLabel("No ROI selected")
        self._active_area_label.setWordWrap(True)
        self._active_area_label.setStyleSheet(_SECTION_HINT_STYLE)
        actions_layout.addWidget(self._active_area_label)

        self._save_btn = QPushButton("Save Selected ROI")
        self._save_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        actions_layout.addWidget(self._save_btn)

        layout.addWidget(actions_box)
        layout.addStretch(1)
        return panel

    def _connect_signals(self) -> None:
        self._work_area_combo.currentIndexChanged.connect(self._on_work_area_changed)
        self._detection_btn.clicked.connect(self._on_detection_clicked)
        self._brightness_btn.clicked.connect(self._on_brightness_clicked)
        self._save_btn.clicked.connect(self._on_save_clicked)

    def _rebuild_area_choices(self) -> None:
        self._work_area_combo.blockSignals(True)
        self._work_area_combo.clear()
        for definition in self._work_area_definitions:
            self._work_area_combo.addItem(definition.label, definition.id)
            if definition.supports_detection_roi:
                self.preview_label.add_area(definition.detection_area_key(), definition.color)
            if definition.supports_brightness_roi:
                self.preview_label.add_area(definition.brightness_area_key(), _BRIGHTNESS_COLOR)
        self._work_area_combo.blockSignals(False)
        self._select_default_role()

    def _select_default_role(self) -> None:
        definition = self.current_work_area_definition()
        self._detection_btn.setChecked(False)
        self._brightness_btn.setChecked(False)
        if definition is None:
            self.set_active_area_key("")
            return
        self._detection_btn.setEnabled(definition.supports_detection_roi)
        self._brightness_btn.setEnabled(definition.supports_brightness_roi)
        if definition.supports_detection_roi:
            self._detection_btn.setChecked(True)
            self.set_active_area_key(definition.detection_area_key())
            return
        if definition.supports_brightness_roi:
            self._brightness_btn.setChecked(True)
            self.set_active_area_key(definition.brightness_area_key())
            return
        self.set_active_area_key("")

    def _on_work_area_changed(self) -> None:
        area_id = self.current_work_area_id()
        self._select_default_role()
        self.work_area_changed.emit(area_id)

    def _on_detection_clicked(self) -> None:
        definition = self.current_work_area_definition()
        if definition is None:
            self.set_active_area_key("")
            return
        self._detection_btn.setChecked(True)
        self._brightness_btn.setChecked(False)
        self.set_active_area_key(definition.detection_area_key())

    def _on_brightness_clicked(self) -> None:
        definition = self.current_work_area_definition()
        if definition is None:
            self.set_active_area_key("")
            return
        self._brightness_btn.setChecked(True)
        self._detection_btn.setChecked(False)
        self.set_active_area_key(definition.brightness_area_key())

    def _on_save_clicked(self) -> None:
        if self._active_area_key:
            self.save_area_requested.emit(self._active_area_key)

    @pyqtSlot(str)
    def _on_vision_state_changed(self, state: str) -> None:
        fg, bg = _STATE_COLORS.get(state.upper(), _STATE_COLORS["UNKNOWN"])
        self._state_label.setStyleSheet(_STATE_LABEL_STYLE.format(fg=fg, bg=bg))
        self._state_label.setText(f"● {state.upper()}")

    def set_work_area_options(self, definitions: list[WorkAreaDefinition]) -> None:
        self._work_area_definitions = list(definitions)
        self._rebuild_area_choices()

    def set_current_work_area_id(self, area_id: str) -> None:
        index = self._work_area_combo.findData(str(area_id or ""))
        if index >= 0:
            self._work_area_combo.setCurrentIndex(index)

    def current_work_area_id(self) -> str:
        value = self._work_area_combo.currentData()
        return str(value or "")

    def current_work_area_definition(self) -> WorkAreaDefinition | None:
        area_id = self.current_work_area_id()
        for definition in self._work_area_definitions:
            if definition.id == area_id:
                return definition
        return None

    @property
    def work_area_definitions(self) -> list[WorkAreaDefinition]:
        return list(self._work_area_definitions)

    def set_active_area_key(self, area_key: str) -> None:
        self._active_area_key = str(area_key or "")
        self.preview_label.set_active_area(self._active_area_key or None)
        if self._active_area_key:
            self._active_area_label.setText(f"Editing: {self._active_area_key}")
        else:
            self._active_area_label.setText("No ROI selected")

    def set_vision_state(self, state: str) -> None:
        self.vision_state_changed.emit(state)

    def update_camera_view(self, image) -> None:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.preview_label.set_frame(QPixmap.fromImage(qimg))

    def set_area_corners(self, area_name: str, normalized_points: list) -> None:
        self.preview_label.set_area_corners(area_name, normalized_points)

    def get_area_corners(self, area_name: str) -> list:
        return self.preview_label.get_area_corners(area_name)

    @property
    def preview_label(self) -> CameraView:
        return self._preview_label
