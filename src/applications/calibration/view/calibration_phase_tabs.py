from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget

from src.applications.base.app_styles import (
    APP_CARD_STYLE,
    APP_SECONDARY_BUTTON_STYLE,
    divider,
    section_hint,
    section_label,
)
from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from pl_gui.settings.settings_view.styles import BORDER, PRIMARY, SECONDARY_BG, TEXT_COLOR
from src.applications.calibration.view.compact_settings_group import CompactSettingsGroup
from src.applications.calibration.view.intrinsic_auto_capture_widget import IntrinsicAutoCaptureWidget
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField


class _BaseCalibrationTab(QWidget):
    def __init__(self, title: str, hint: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._settings_groups: list[CompactSettingsGroup] = []
        self._save_button: QPushButton | None = None
        self._settings_dialog: QDialog | None = None
        self._settings_tabs: QTabWidget | None = None
        self._settings_open_button: QPushButton | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._card = QWidget()
        self._card.setStyleSheet(APP_CARD_STYLE)
        self._card_layout = QVBoxLayout(self._card)
        self._card_layout.setContentsMargins(16, 12, 16, 16)
        self._card_layout.setSpacing(10)
        self._card_layout.addWidget(section_label(title))
        self._card_layout.addWidget(section_hint(hint))

        layout.addWidget(self._card)
        layout.addStretch(1)

    def add_widget(self, widget: QWidget) -> None:
        self._card_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._card_layout.addLayout(layout)

    def add_divider(self) -> None:
        self._card_layout.addWidget(divider())

    def add_settings_groups(self, schemas: list) -> None:
        self._settings_dialog = QDialog(self)
        self._settings_dialog.setModal(True)
        self._settings_dialog.resize(940, 560)
        self._settings_dialog.setStyleSheet("QDialog { background: white; }")
        dialog_layout = QVBoxLayout(self._settings_dialog)
        dialog_layout.setContentsMargins(24, 20, 24, 20)
        dialog_layout.setSpacing(16)
        self._settings_title = QLabel()
        self._settings_title.setFixedHeight(32)
        self._settings_title.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 15pt; font-weight: bold;")
        dialog_layout.addWidget(self._settings_title)
        self._settings_tabs = QTabWidget()
        self._settings_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self._settings_tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: white; }}"
            f"QTabBar {{ background: {SECONDARY_BG}; border-radius: 10px; }}"
            f"QTabBar::tab {{ background: transparent; color: {TEXT_COLOR}; "
            "border: none; padding: 10px 18px; min-height: 30px; }"
            f"QTabBar::tab:selected {{ background: {PRIMARY}; color: white; border-radius: 8px; }}"
        )
        for schema in schemas:
            group = CompactSettingsGroup(schema)
            self._settings_groups.append(group)
            self.add_settings_page(schema.title, group)
        dialog_layout.addWidget(self._settings_tabs)
        self._settings_open_button = MaterialButton("Settings")
        self._settings_open_button.setStyleSheet(APP_SECONDARY_BUTTON_STYLE)
        self._settings_open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_open_button.clicked.connect(self._open_settings)
        self._card_layout.addWidget(self._settings_open_button)
        self._retranslate_settings()

    def add_settings_page(self, title: str, widget: QWidget) -> int:
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        page.setFrameShape(QScrollArea.Shape.NoFrame)
        page.setStyleSheet("QScrollArea { border: none; background: white; }")
        page.setWidget(widget)
        return self._settings_tabs.addTab(page, title)

    def add_save_button(self) -> QPushButton:
        row = QHBoxLayout()
        row.addStretch()
        self._cancel_button = QPushButton()
        self._cancel_button.setMinimumSize(120, 44)
        self._cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_button.setStyleSheet(
            f"QPushButton {{ background: {SECONDARY_BG}; color: {PRIMARY}; border: none; "
            "border-radius: 8px; font-weight: bold; }"
        )
        self._cancel_button.clicked.connect(self._settings_dialog.reject)
        row.addWidget(self._cancel_button)
        self._save_button = QPushButton()
        self._save_button.setMinimumSize(120, 44)
        self._save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_button.setStyleSheet(
            f"QPushButton {{ background: {PRIMARY}; color: white; border: none; "
            "border-radius: 8px; font-weight: bold; }"
        )
        self._save_button.clicked.connect(self._settings_dialog.accept)
        row.addWidget(self._save_button)
        self._settings_dialog.layout().addLayout(row)
        self._retranslate_settings()
        return self._save_button

    def _open_settings(self) -> bool:
        previous = self.get_settings_values()
        accepted = self._settings_dialog.exec() == QDialog.DialogCode.Accepted
        if not accepted:
            self.set_settings_values(previous)
        return accepted

    def _retranslate_settings(self) -> None:
        if self._settings_dialog is None:
            return
        settings_text = QCoreApplication.translate("_BaseCalibrationTab", "settings") or "settings"
        title = f"{self._title} {settings_text}"
        self._settings_dialog.setWindowTitle(title)
        self._settings_title.setText(title)
        self._settings_open_button.setText(f"{title}  ›")
        if self._save_button is not None:
            self._save_button.setText(QCoreApplication.translate("_BaseCalibrationTab", "Save") or "Save")
            self._cancel_button.setText(QCoreApplication.translate("_BaseCalibrationTab", "Cancel") or "Cancel")

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate_settings()
        super().changeEvent(event)

    def set_settings_values(self, flat: dict) -> None:
        for group in self._settings_groups:
            group.set_values(flat)

    def get_settings_values(self) -> dict:
        values: dict = {}
        for group in self._settings_groups:
            values.update(group.get_values())
        return values


class SystemCalibrationTab(_BaseCalibrationTab):
    def __init__(self, sequence_btn: QWidget, stop_btn: QWidget, parent=None):
        super().__init__(
            "System Calibration",
            "Use the guided sequence for the normal workflow, or stop the active task from here.",
            parent=parent,
        )
        self.add_widget(sequence_btn)


class CameraCalibrationTab(_BaseCalibrationTab):
    auto_capture_config_saved = pyqtSignal(object)

    def __init__(
        self,
        capture_btn: QWidget,
        crosshair_btn: QWidget,
        magnifier_btn: QWidget,
        calibrate_camera_btn: QWidget,
        auto_capture_widget: IntrinsicAutoCaptureWidget | None,
        settings_schemas: list,
        parent=None,
    ):
        super().__init__(
            "Camera Calibration",
            "Capture a fresh image, use overlays while framing the board, then run camera calibration.",
            parent=parent,
        )
        self._auto_capture_widget = auto_capture_widget
        self._auto_settings_index: int | None = None
        self.add_widget(capture_btn)
        self.add_divider()
        self.add_widget(calibrate_camera_btn)
        if auto_capture_widget is not None:
            self.add_divider()
            self.add_widget(auto_capture_widget)
        self.add_settings_groups(settings_schemas)
        if auto_capture_widget is not None:
            self._auto_settings_index = self.add_settings_page(
                self._auto_capture_title(), auto_capture_widget.settings_widget(),
            )
        self.add_save_button()

    def _open_settings(self) -> bool:
        previous_config = self._auto_capture_widget.get_config() if self._auto_capture_widget else None
        accepted = super()._open_settings()
        if self._auto_capture_widget is not None:
            if accepted:
                self.auto_capture_config_saved.emit(self._auto_capture_widget.get_config())
            elif previous_config is not None:
                self._auto_capture_widget.set_config(previous_config)
        return accepted

    @staticmethod
    def _auto_capture_title() -> str:
        return QCoreApplication.translate("CameraCalibrationTab", "Auto Capture") or "Auto Capture"

    def _retranslate_settings(self) -> None:
        super()._retranslate_settings()
        if getattr(self, "_auto_settings_index", None) is not None:
            self._settings_tabs.setTabText(self._auto_settings_index, self._auto_capture_title())


class RobotCalibrationTab(_BaseCalibrationTab):
    def __init__(
        self,
        calibrate_robot_btn: QWidget,
        calibrate_tcp_btn: QWidget,
        calibrate_z_shift_btn: QWidget,
        test_btn: QWidget,
        settings_schemas: list,
        parent=None,
    ):
        super().__init__(
            "Robot Calibration",
            "Run robot calibration, then use TCP offset and test validation once calibration data exists.",
            parent=parent,
        )
        self.add_widget(calibrate_robot_btn)
        self.add_widget(calibrate_tcp_btn)
        self.add_widget(calibrate_z_shift_btn)
        self.add_divider()
        self.add_widget(test_btn)
        self.add_settings_groups(settings_schemas)
        self.add_save_button()


class ToolTcpCalibrationTab(_BaseCalibrationTab):
    def __init__(
        self,
        tool_spin: KeyboardNumberField,
        start_btn: QWidget,
        capture_btn: QWidget,
        solve_btn: QWidget,
        save_btn: QWidget,
        clear_btn: QWidget,
        result_label: QLabel,
        parent=None,
    ):
        super().__init__(
            "Tool TCP Calibration",
            "Touch the physical TCP to a fixed pivot point, capture flange poses at varied wrist orientations, then solve and save the flange-to-TCP offset.",
            parent=parent,
        )
        tool_row = QHBoxLayout()
        tool_row.setSpacing(8)
        tool_row.addWidget(QLabel("Tool ID"))
        tool_row.addWidget(tool_spin)
        self.add_layout(tool_row)
        self.add_divider()
        for button in (start_btn, capture_btn, solve_btn, save_btn, clear_btn):
            self.add_widget(button)
        self.add_divider()
        self.add_widget(result_label)


class LaserCalibrationTab(_BaseCalibrationTab):
    def __init__(
        self,
        calibrate_laser_btn: QWidget,
        detect_laser_btn: QWidget,
        settings_schemas: list,
        parent=None,
    ):
        super().__init__(
            "Laser Calibration",
            "Calibrate the laser model or run a single detection pass for validation and debugging.",
            parent=parent,
        )
        self.add_widget(calibrate_laser_btn)
        self.add_widget(detect_laser_btn)
        self.add_settings_groups(settings_schemas)
        self.add_save_button()


class HeightMappingTab(_BaseCalibrationTab):
    def __init__(
        self,
        verify_saved_model_btn: QWidget,
        settings_schemas: list,
        height_mapping_content: QWidget | None = None,
        parent=None,
    ):
        super().__init__(
            "Height Mapping",
            "Define the mapping area on the preview, generate the area grid, and verify the saved model here.",
            parent=parent,
        )
        self._height_mapping_content: QWidget | None = None
        self._height_mapping_divider: QWidget | None = None
        if height_mapping_content is not None:
            self.set_height_mapping_content(height_mapping_content)
        self.add_widget(verify_saved_model_btn)
        self.add_settings_groups(settings_schemas)
        self.add_save_button()

    def set_height_mapping_content(self, widget: QWidget) -> None:
        if self._height_mapping_content is not None:
            self._card_layout.removeWidget(self._height_mapping_content)
            self._height_mapping_content.setParent(None)
        if self._height_mapping_divider is not None:
            self._card_layout.removeWidget(self._height_mapping_divider)
            self._height_mapping_divider.setParent(None)
        self._height_mapping_content = widget
        self._height_mapping_divider = divider()
        self._card_layout.insertWidget(2, widget)
        self._card_layout.insertWidget(3, self._height_mapping_divider)
