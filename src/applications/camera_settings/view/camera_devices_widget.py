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
    QSizePolicy,
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
    SECONDARY_BG,
    TERTIARY_TEXT,
    TEXT_COLOR,
)
from pl_gui.utils.utils_widgets.camera_view import CameraView
from pl_gui.utils.utils_widgets.SwitchButton import QToggle
from src.applications.camera_settings.service.i_camera_settings_service import (
    CameraDevicesState,
    CameraOrientation,
)


class CameraDevicesWidget(QWidget):
    refresh_requested = pyqtSignal()
    save_requested = pyqtSignal(dict, dict)
    preview_requested = pyqtSignal(str, str)
    preview_visibility_changed = pyqtSignal(bool)

    _ROLES = ("primary_vision", "auxiliary")

    def __init__(self, parent=None, *, device_control_mode: bool = False) -> None:
        super().__init__(parent)
        self._device_control_mode = device_control_mode
        self._device_state: CameraDevicesState | None = None
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self._selectors: dict[str, QComboBox] = {}
        self._orientation_controls: dict[str, tuple[QCheckBox, QCheckBox, QComboBox]] = {}
        self._rotation_values: dict[str, QLabel] = {}
        self._rotation_labels: dict[str, QLabel] = {}
        self._rotation_buttons: dict[str, tuple[QPushButton, QPushButton]] = {}
        self._role_panels: dict[str, QWidget] = {}
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
            role_panel = QWidget()
            if self._device_control_mode:
                role_panel.setStyleSheet("background: transparent;")
                role_panel.setSizePolicy(
                    QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
                )
            role_panel_layout = QVBoxLayout(role_panel)
            role_panel_layout.setContentsMargins(0, 0, 0, 0)
            role_panel_layout.setSpacing(12)
            row = QHBoxLayout()
            label = QLabel()
            label.setObjectName(f"{role}_label")
            label.setStyleSheet(LABEL_STYLE)
            selector = QComboBox()
            selector.setMinimumHeight(44)
            if self._device_control_mode:
                selector.setStyleSheet(self._device_combo_style())
            selector.setProperty("camera_role", role)
            selector.currentIndexChanged.connect(self._on_selection_changed)
            self._selectors[role] = selector
            row.addWidget(label)
            row.addWidget(selector, stretch=1)
            role_panel_layout.addLayout(row)
            orientation_row = QVBoxLayout() if self._device_control_mode else QHBoxLayout()
            flip_horizontal = QToggle() if self._device_control_mode else QCheckBox()
            flip_vertical = QToggle() if self._device_control_mode else QCheckBox()
            rotation = QComboBox(role_panel)
            rotation.setMinimumHeight(44)
            if self._device_control_mode:
                rotation.hide()
            rotation.setProperty("camera_role", role)
            flip_horizontal.setCursor(Qt.CursorShape.PointingHandCursor)
            flip_vertical.setCursor(Qt.CursorShape.PointingHandCursor)
            rotation.setCursor(Qt.CursorShape.PointingHandCursor)
            if self._device_control_mode:
                for toggle in (flip_horizontal, flip_vertical):
                    toggle.setFixedHeight(44)
                    orientation_row.addWidget(toggle)
                rotation_row = QHBoxLayout()
                rotation_label = QLabel()
                rotation_label.setStyleSheet(LABEL_STYLE)
                rotation_value = QLabel("0°")
                rotation_value.setMinimumWidth(42)
                rotation_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
                rotation_value.setStyleSheet(
                    f"color: {PRIMARY}; background: {SECONDARY_BG};"
                    " border-radius: 10px; padding: 8px; font-weight: bold;"
                )
                counterclockwise = QPushButton()
                clockwise = QPushButton()
                for button, step in ((counterclockwise, -90), (clockwise, 90)):
                    button.setProperty("camera_role", role)
                    button.setProperty("rotation_step", step)
                    button.setStyleSheet(GHOST_BTN_STYLE)
                    button.setCursor(Qt.CursorShape.PointingHandCursor)
                    button.clicked.connect(self._on_rotate_clicked)
                    button.setMinimumHeight(44)
                rotation_row.addWidget(rotation_label, 1)
                rotation_row.addWidget(counterclockwise)
                rotation_row.addWidget(rotation_value)
                rotation_row.addWidget(clockwise)
                orientation_row.addLayout(rotation_row)
                self._rotation_labels[role] = rotation_label
                self._rotation_values[role] = rotation_value
                self._rotation_buttons[role] = (counterclockwise, clockwise)
            else:
                orientation_row.addSpacing(12)
                orientation_row.addWidget(flip_horizontal)
                orientation_row.addWidget(flip_vertical)
                orientation_row.addSpacing(12)
                orientation_row.addWidget(rotation)
                orientation_row.addStretch()
            role_panel_layout.addLayout(orientation_row)
            assignment_layout.addWidget(role_panel, 0, Qt.AlignmentFlag.AlignTop)
            self._role_panels[role] = role_panel
            self._orientation_controls[role] = (flip_horizontal, flip_vertical, rotation)
            rotation.currentIndexChanged.connect(self._on_rotation_changed)

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
        if self._device_control_mode:
            assignment_layout.addStretch(1)
        assignment_layout.addLayout(buttons)
        self._assignment_buttons = buttons
        self._recalibration_hint = QLabel()
        self._recalibration_hint.setWordWrap(True)
        self._recalibration_hint.setVisible(False)
        assignment_layout.addWidget(self._recalibration_hint)
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
        self._status.setVisible(False)
        layout.addWidget(self._status)

        self._assignment_box = assignment_box
        self._preview_box = preview_box
        if self._device_control_mode:
            self._apply_device_control_layout(layout)

    def _apply_device_control_layout(self, layout: QVBoxLayout) -> None:
        layout.removeWidget(self._assignment_box)
        layout.removeWidget(self._preview_box)
        layout.removeWidget(self._status)
        heading = QLabel()
        heading.setStyleSheet("font-size: 18pt; font-weight: bold; background: transparent;")
        hint = QLabel()
        hint.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        layout.addWidget(heading)
        layout.addWidget(hint)
        self._device_heading = heading
        self._device_hint = hint
        toolbar = QHBoxLayout()
        self._device_role = QComboBox()
        self._device_role.setMinimumHeight(48)
        self._device_role.setStyleSheet(self._device_combo_style())
        self._device_role.currentIndexChanged.connect(self._on_device_role_changed)
        toolbar.addWidget(self._device_role, 1)
        self._connected_badge = QLabel()
        self._connected_badge.hide()
        self._connected_badge.setStyleSheet(
            f"color: {PRIMARY}; background: {SECONDARY_BG}; border-radius: 14px; padding: 8px 12px;"
        )
        toolbar.addWidget(self._connected_badge)
        toolbar.addStretch(1)
        self._assignment_buttons.removeWidget(self._refresh_button)
        toolbar.addWidget(self._refresh_button)
        layout.addLayout(toolbar)
        cards = QHBoxLayout()
        cards.setSpacing(16)
        card_style = f"""
            QGroupBox {{ background: white; border: 1px solid {BORDER};
                border-radius: 18px; margin-top: 12px; padding-top: 8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 18px;
                padding: 0 5px; background: white; font-weight: bold; }}
        """
        for box in (self._assignment_box, self._preview_box):
            box.setStyleSheet(card_style)
        cards.addWidget(self._assignment_box, 1)
        cards.addWidget(self._preview_box, 1)
        layout.addLayout(cards, 1)
        self._preview_role.hide()
        self._preview.set_toolbar_visible(False)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self._zoom_out = QPushButton("−")
        self._zoom_in = QPushButton("+")
        self._zoom_reset = QPushButton("⊙")
        self._zoom_value = QLabel("100%")
        self._zoom_value.setStyleSheet("background: transparent;")
        zoom_style = f"""
            QPushButton {{ background: {SECONDARY_BG}; color: {PRIMARY}; border: none;
                border-radius: 12px; min-width: 40px; min-height: 40px;
                font-size: 13pt; font-weight: bold; }}
        """
        for button in (self._zoom_out, self._zoom_in, self._zoom_reset):
            button.setStyleSheet(zoom_style)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        for widget in (self._zoom_out, self._zoom_value, self._zoom_in, self._zoom_reset):
            footer.addWidget(widget)
        footer.addStretch(1)
        self._preview_box.layout().addLayout(footer)
        self._zoom_out.clicked.connect(self._preview.zoom_out)
        self._zoom_in.clicked.connect(self._preview.zoom_in)
        self._zoom_reset.clicked.connect(self._preview.reset_zoom)
        self._preview.zoom_changed.connect(self._on_zoom_changed)
        self._status.setStyleSheet(
            f"color: {TERTIARY_TEXT}; background: {SECONDARY_BG};"
            " border-radius: 12px; padding: 10px 14px;"
        )
        layout.addWidget(self._status)

    @staticmethod
    def _device_combo_style() -> str:
        return f"""
            QComboBox {{ background: white; color: {TEXT_COLOR}; border: 1px solid {BORDER};
                border-radius: 10px; padding: 8px 14px; font-size: 11pt; }}
            QComboBox:hover {{ border-color: {PRIMARY}; }}
        """

    def _on_zoom_changed(self, percent: int) -> None:
        self._zoom_value.setText(f"{percent}%")

    def _on_device_role_changed(self) -> None:
        role = self._device_role.currentData()
        for key, panel in self._role_panels.items():
            panel.setVisible(key == role)
        index = self._preview_role.findData(role)
        if index >= 0:
            self._preview_role.setCurrentIndex(index)
        role_label = self.tr("Primary vision") if role == "primary_vision" else self.tr("Auxiliary")
        self._assignment_box.setTitle(self.tr("{role} settings").format(role=role_label))
        self._preview_box.setTitle(self.tr("Live preview — {role}").format(role=role_label))
        self._update_connected_badge()

    def _update_connected_badge(self) -> None:
        if not self._device_control_mode or self._device_state is None:
            return
        role = self._device_role.currentData()
        selector = self._selectors.get(role)
        selected = str(selector.currentData() or "") if selector is not None else ""
        connected = any(
            option.device == selected and option.connected
            for option in self._device_state.options
        )
        self._connected_badge.setText(
            self.tr("Connected") if connected else self.tr("Not connected")
        )
        self._connected_badge.show()

    def set_camera_devices(self, state: CameraDevicesState) -> None:
        self._device_state = state
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
            horizontal, vertical, rotation = self._orientation_controls[role]
            orientation = state.orientation.get(role, CameraOrientation())
            if self._device_control_mode:
                horizontal.sync_visual_state(orientation.flip_horizontal)
                vertical.sync_visual_state(orientation.flip_vertical)
            else:
                horizontal.setChecked(orientation.flip_horizontal)
                vertical.setChecked(orientation.flip_vertical)
            index = rotation.findData(orientation.rotate_degrees)
            rotation.setCurrentIndex(index if index >= 0 else 0)
        self._update_recalibration_hint()
        self._update_connected_badge()
        self._status.setText(self.tr("Camera assignments loaded."))
        self._status.setVisible(True)
        self._request_preview()

    def _update_recalibration_hint(self) -> None:
        """Warn that a transposing rotation invalidates the stored calibration."""
        self._recalibration_hint.setVisible(
            any(
                CameraOrientation(
                    rotate_degrees=int(rotation.currentData() or 0)
                ).transposes_frame
                for _, _, rotation in self._orientation_controls.values()
            )
        )

    def _option_label(self, device: str, capture_node: str, connected: bool) -> str:
        status = self.tr("connected") if connected else self.tr("missing")
        node = f" → {capture_node}" if capture_node else ""
        return f"{device}{node} ({status})"

    def assignments(self) -> dict[str, str]:
        return {
            role: str(selector.currentData() or "")
            for role, selector in self._selectors.items()
        }

    def orientation_settings(self) -> dict[str, CameraOrientation]:
        return {
            role: CameraOrientation(
                flip_horizontal=horizontal.isChecked(),
                flip_vertical=vertical.isChecked(),
                rotate_degrees=int(rotation.currentData() or 0),
            )
            for role, (horizontal, vertical, rotation) in self._orientation_controls.items()
        }

    def set_preview_frame(self, frame) -> None:
        if frame is None:
            self._status.setText(self.tr("No frame available from the selected camera."))
            self._status.setVisible(True)
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
            self.tr("Camera settings saved. Flip and rotation changes are live; device changes require a restart.")
        )
        self._status.setVisible(True)

    def set_error(self, message: str) -> None:
        self._status.setText(message)
        self._status.setVisible(True)

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
        for horizontal, vertical, rotation in self._orientation_controls.values():
            horizontal.setText(self.tr("Flip horizontally"))
            vertical.setText(self.tr("Flip vertically"))
            current = rotation.currentData()
            rotation.blockSignals(True)
            rotation.clear()
            rotation.addItem(self.tr("No rotation"), 0)
            rotation.addItem(self.tr("Rotate 90° clockwise"), 90)
            rotation.addItem(self.tr("Rotate 180°"), 180)
            rotation.addItem(self.tr("Rotate 270° clockwise"), 270)
            index = rotation.findData(current)
            rotation.setCurrentIndex(max(0, index))
            rotation.blockSignals(False)
        if self._device_control_mode:
            for role, label in self._rotation_labels.items():
                label.setText(self.tr("Rotation"))
                counterclockwise, clockwise = self._rotation_buttons[role]
                counterclockwise.setText(self.tr("↶ 90°"))
                clockwise.setText(self.tr("90° ↷"))
                self._rotation_values[role].setText(
                    f"{int(self._orientation_controls[role][2].currentData() or 0)}°"
                )
        self._recalibration_hint.setText(
            self.tr(
                "Rotating a camera by 90 or 270 degrees transposes the image and "
                "invalidates the stored camera calibration. Re-run calibration before painting."
            )
        )
        self._update_recalibration_hint()
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
        if self._device_control_mode:
            self._device_heading.setText(self.tr("Cameras"))
            self._device_hint.setText(self.tr("Pick a camera to set it up and see its live image."))
            current = self._device_role.currentData()
            self._device_role.blockSignals(True)
            self._device_role.clear()
            self._device_role.addItem(self.tr("Primary vision"), "primary_vision")
            self._device_role.addItem(self.tr("Auxiliary"), "auxiliary")
            index = self._device_role.findData(current)
            self._device_role.setCurrentIndex(max(0, index))
            self._device_role.blockSignals(False)
            self._on_device_role_changed()

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
        self.save_requested.emit(assignments, self.orientation_settings())

    def _on_rotation_changed(self, _index: int) -> None:
        rotation = self.sender()
        if self._device_control_mode and isinstance(rotation, QComboBox):
            role = str(rotation.property("camera_role"))
            self._rotation_values[role].setText(f"{int(rotation.currentData() or 0)}°")
        self._update_recalibration_hint()

    def _on_rotate_clicked(self) -> None:
        button = self.sender()
        if not isinstance(button, QPushButton):
            return
        role = str(button.property("camera_role"))
        rotation = self._orientation_controls[role][2]
        current = int(rotation.currentData() or 0)
        target = (current + int(button.property("rotation_step"))) % 360
        index = rotation.findData(target)
        if index >= 0:
            rotation.setCurrentIndex(index)

    def _on_selection_changed(self, _index: int) -> None:
        self._update_connected_badge()
        self._request_preview()

    def _on_preview_role_changed(self, _index: int) -> None:
        self._request_preview()

    def _request_preview(self) -> None:
        role = str(self._preview_role.currentData() or "")
        selector = self._selectors.get(role)
        device = str(selector.currentData() or "") if selector is not None else ""
        if role and device:
            self.preview_requested.emit(role, device)
