from __future__ import annotations

import cv2
from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
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
    GHOST_BTN_STYLE,
    GROUP_STYLE,
    LABEL_STYLE,
)
from pl_gui.utils.utils_widgets.camera_view import CameraView
from src.applications.camera_settings.service.i_camera_settings_service import (
    CameraDevicesState,
)


class CameraDevicesWidget(QWidget):
    refresh_requested = pyqtSignal()
    save_requested = pyqtSignal(dict, dict)
    preview_requested = pyqtSignal(str, str)
    preview_visibility_changed = pyqtSignal(bool)

    _ROLES = ("primary_vision", "auxiliary")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self._selectors: dict[str, QComboBox] = {}
        self._flip_controls: dict[str, tuple[QCheckBox, QCheckBox]] = {}
        self._build_ui()
        self.retranslateUi()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        assignment_box = QGroupBox()
        assignment_box.setStyleSheet(GROUP_STYLE)
        assignment_layout = QVBoxLayout(assignment_box)
        assignment_layout.setSpacing(12)

        for role in self._ROLES:
            row = QHBoxLayout()
            label = QLabel()
            label.setObjectName(f"{role}_label")
            label.setStyleSheet(LABEL_STYLE)
            selector = QComboBox()
            selector.setMinimumHeight(44)
            selector.setProperty("camera_role", role)
            selector.currentIndexChanged.connect(self._on_selection_changed)
            self._selectors[role] = selector
            row.addWidget(label)
            row.addWidget(selector, stretch=1)
            assignment_layout.addLayout(row)
            flip_row = QHBoxLayout()
            flip_horizontal = QCheckBox()
            flip_vertical = QCheckBox()
            flip_horizontal.setCursor(Qt.CursorShape.PointingHandCursor)
            flip_vertical.setCursor(Qt.CursorShape.PointingHandCursor)
            flip_row.addSpacing(12)
            flip_row.addWidget(flip_horizontal)
            flip_row.addWidget(flip_vertical)
            flip_row.addStretch()
            assignment_layout.addLayout(flip_row)
            self._flip_controls[role] = (flip_horizontal, flip_vertical)

        buttons = QHBoxLayout()
        self._refresh_button = QPushButton()
        self._refresh_button.setStyleSheet(GHOST_BTN_STYLE)
        self._refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_button.clicked.connect(self._on_refresh_clicked)
        self._save_button = QPushButton()
        self._save_button.setStyleSheet(ACTION_BTN_STYLE)
        self._save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_button.clicked.connect(self._on_save_clicked)
        buttons.addWidget(self._refresh_button)
        buttons.addStretch()
        buttons.addWidget(self._save_button)
        assignment_layout.addLayout(buttons)
        layout.addWidget(assignment_box)

        preview_box = QGroupBox()
        preview_box.setObjectName("preview_box")
        preview_box.setStyleSheet(GROUP_STYLE)
        preview_layout = QVBoxLayout(preview_box)
        self._preview_role = QComboBox()
        self._preview_role.setMinimumHeight(44)
        self._preview_role.currentIndexChanged.connect(self._on_preview_role_changed)
        preview_layout.addWidget(self._preview_role)
        self._preview = CameraView()
        self._preview.setMinimumHeight(320)
        preview_layout.addWidget(self._preview)
        layout.addWidget(preview_box, stretch=1)

        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._assignment_box = assignment_box
        self._preview_box = preview_box

    def set_camera_devices(self, state: CameraDevicesState) -> None:
        labels = {
            option.device: self._option_label(
                option.device,
                option.capture_node,
                option.connected,
            )
            for option in state.options
        }
        for configured in state.assignments.values():
            labels.setdefault(configured, self._option_label(configured, "", False))

        for role, selector in self._selectors.items():
            selected = state.assignments.get(role, "")
            selector.blockSignals(True)
            selector.clear()
            for device, label in labels.items():
                selector.addItem(label, device)
            index = selector.findData(selected)
            if index >= 0:
                selector.setCurrentIndex(index)
            selector.blockSignals(False)
            horizontal, vertical = state.flips.get(role, (False, False))
            self._flip_controls[role][0].setChecked(horizontal)
            self._flip_controls[role][1].setChecked(vertical)
        self._status.setText(self.tr("Camera assignments loaded."))
        self._request_preview()

    def _option_label(self, device: str, capture_node: str, connected: bool) -> str:
        status = self.tr("connected") if connected else self.tr("missing")
        node = f" → {capture_node}" if capture_node else ""
        return f"{device}{node} ({status})"

    def assignments(self) -> dict[str, str]:
        return {
            role: str(selector.currentData() or "")
            for role, selector in self._selectors.items()
        }

    def flip_settings(self) -> dict[str, tuple[bool, bool]]:
        return {
            role: (horizontal.isChecked(), vertical.isChecked())
            for role, (horizontal, vertical) in self._flip_controls.items()
        }

    def set_preview_frame(self, frame) -> None:
        if frame is None:
            self._status.setText(self.tr("No frame available from the selected camera."))
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        )
        self._preview.set_frame(QPixmap.fromImage(image))

    def set_saved(self) -> None:
        self._status.setText(
            self.tr("Camera settings saved. Flip changes are live; device changes require a restart.")
        )

    def set_error(self, message: str) -> None:
        self._status.setText(message)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.preview_visibility_changed.emit(True)

    def hideEvent(self, event) -> None:
        self.preview_visibility_changed.emit(False)
        super().hideEvent(event)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self) -> None:
        self._assignment_box.setTitle(self.tr("Camera Assignments"))
        self._preview_box.setTitle(self.tr("Live Preview"))
        self.findChild(QLabel, "primary_vision_label").setText(self.tr("Primary vision"))
        self.findChild(QLabel, "auxiliary_label").setText(self.tr("Auxiliary"))
        for horizontal, vertical in self._flip_controls.values():
            horizontal.setText(self.tr("Flip horizontally"))
            vertical.setText(self.tr("Flip vertically"))
        self._refresh_button.setText(self.tr("Refresh devices"))
        self._save_button.setText(self.tr("Save assignments"))
        current_role = self._preview_role.currentData()
        self._preview_role.blockSignals(True)
        self._preview_role.clear()
        self._preview_role.addItem(self.tr("Preview primary vision"), "primary_vision")
        self._preview_role.addItem(self.tr("Preview auxiliary"), "auxiliary")
        index = self._preview_role.findData(current_role)
        self._preview_role.setCurrentIndex(max(0, index))
        self._preview_role.blockSignals(False)

    def _on_refresh_clicked(self) -> None:
        self.refresh_requested.emit()

    def _on_save_clicked(self) -> None:
        assignments = self.assignments()
        if not all(assignments.values()):
            self.set_error(self.tr("Assign both camera roles before saving."))
            return
        if len(set(assignments.values())) != len(assignments):
            self.set_error(self.tr("Primary and auxiliary cameras must be different devices."))
            return
        self.save_requested.emit(assignments, self.flip_settings())

    def _on_selection_changed(self, _index: int) -> None:
        self._request_preview()

    def _on_preview_role_changed(self, _index: int) -> None:
        self._request_preview()

    def _request_preview(self) -> None:
        role = str(self._preview_role.currentData() or "")
        selector = self._selectors.get(role)
        device = str(selector.currentData() or "") if selector is not None else ""
        if role and device:
            self.preview_requested.emit(role, device)
