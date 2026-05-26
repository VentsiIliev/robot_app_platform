from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.applications.base.i_application_view import IApplicationView
from pl_gui.dashboard.DashboardWidget import DashboardWidget
from pl_gui.settings.settings_view.styles import BG_COLOR, GROUP_STYLE, LABEL_STYLE


class PaintDashboardView(IApplicationView):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    test_pickup_requested = pyqtSignal()
    go_to_calibration_requested = pyqtSignal()
    move_to_calibration_ptp_requested = pyqtSignal()
    move_to_home_zeros_requested = pyqtSignal()
    pickup_to_paint_position_requested = pyqtSignal()
    test_pre_paint_marker_requested = pyqtSignal()
    paint_marker_settings_requested = pyqtSignal()

    action_requested = pyqtSignal(str)

    def __init__(self, config, action_buttons: list, cards: list, parent=None):
        self._config = config
        self._action_buttons = action_buttons
        self._cards_input = cards
        super().__init__("PaintDashboard", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._dashboard = DashboardWidget(
            config=self._config,
            action_buttons=self._action_buttons,
            cards=self._cards_input,
        )
        layout.addWidget(self._dashboard)

        self._state_label = QLabel("State: idle")
        self._mode_label = QLabel("Mode: Paint Mode")
        self._job_label = QLabel("Job: No active job")

        self._notes = QTextEdit()
        self._notes.setReadOnly(True)
        self._notes.setPlaceholderText("Dashboard notes")

        self._status_widget = QWidget()
        status_layout = QVBoxLayout(self._status_widget)
        status_layout.setContentsMargins(8, 8, 8, 8)
        status_layout.setSpacing(8)
        status_layout.addWidget(self._state_label)
        status_layout.addWidget(self._mode_label)
        status_layout.addWidget(self._job_label)
        status_layout.addWidget(self._notes, 1)
        self._inject_aux_widget(self._status_widget)

        self._dashboard.start_requested.connect(self.start_requested)
        self._dashboard.stop_requested.connect(self.stop_requested)
        self._dashboard.pause_requested.connect(self.pause_requested)
        self._dashboard.action_requested.connect(self._on_inner_action)

        self._marker_settings_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self._marker_settings_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._marker_settings_shortcut.activated.connect(self.paint_marker_settings_requested.emit)

    def _inject_aux_widget(self, widget) -> None:
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            preview_container = top_section.itemAt(0).widget()
            aux_grid = preview_container.layout().itemAt(1).widget()
            aux_layout = aux_grid.layout()
            rows = self._config.preview_aux_rows
            cols = self._config.preview_aux_cols
            aux_layout.addWidget(widget, 0, 0, rows, cols)
        except Exception:
            widget.setParent(self._dashboard)

    def _on_inner_action(self, action_id: str) -> None:
        if action_id == "reset_errors":
            self.reset_requested.emit()
            return
        if action_id == "test_pickup":
            self.test_pickup_requested.emit()
            return
        if action_id == "go_to_calibration":
            self.go_to_calibration_requested.emit()
            return
        if action_id == "move_to_calibration_ptp":
            self.move_to_calibration_ptp_requested.emit()
            return
        if action_id == "move_to_home_zeros":
            self.move_to_home_zeros_requested.emit()
            return
        if action_id == "pickup_to_paint_position":
            self.pickup_to_paint_position_requested.emit()
            return
        if action_id == "test_pre_paint_marker":
            self.test_pre_paint_marker_requested.emit()
            return
        self.action_requested.emit(action_id)

    def set_trajectory_image(self, image) -> None:
        self._dashboard.set_trajectory_image(image)

    def set_state(self, state: str) -> None:
        self._state_label.setText(f"State: {state}")

    def set_mode(self, mode: str) -> None:
        self._mode_label.setText(f"Mode: {mode}")

    def set_active_job(self, label: str) -> None:
        self._job_label.setText(f"Job: {label}")

    def set_notes(self, lines: list[str]) -> None:
        self._notes.setPlainText("\n".join(lines))

    def open_paint_marker_settings_dialog(self, settings: dict) -> dict | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Pre-Painting Marker Settings")
        dialog.setModal(True)
        dialog.setStyleSheet(f"background-color: {BG_COLOR};")

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form_widget = QWidget(dialog)
        form_widget.setStyleSheet(GROUP_STYLE)
        form = QFormLayout(form_widget)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(10)

        enabled = QCheckBox()
        enabled.setChecked(bool(settings.get("enabled", True)))

        marker_id = QSpinBox()
        marker_id.setRange(0, 999999)
        marker_id.setValue(int(settings.get("marker_id", 1)))

        dictionary = QLineEdit(str(settings.get("dictionary", "DICT_4X4_1000")))
        pre_paint_group = QLineEdit(str(settings.get("pre_paint_group_id", "PRE_PAINTING")))

        offset_x = self._offset_spin(float(settings.get("offset_x_mm", 0.0)))
        offset_y = self._offset_spin(float(settings.get("offset_y_mm", 0.0)))
        offset_z = self._offset_spin(float(settings.get("offset_z_mm", 0.0)))

        form.addRow(self._field_label("Enabled"), enabled)
        form.addRow(self._field_label("Marker ID"), marker_id)
        form.addRow(self._field_label("Dictionary"), dictionary)
        form.addRow(self._field_label("Pre-paint group"), pre_paint_group)
        form.addRow(self._field_label("X offset (mm)"), offset_x)
        form.addRow(self._field_label("Y offset (mm)"), offset_y)
        form.addRow(self._field_label("Z offset (mm)"), offset_z)
        layout.addWidget(form_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return {
            "enabled": bool(enabled.isChecked()),
            "marker_id": int(marker_id.value()),
            "dictionary": dictionary.text().strip() or "DICT_4X4_1000",
            "pre_paint_group_id": pre_paint_group.text().strip() or "PRE_PAINTING",
            "offset_x_mm": float(offset_x.value()),
            "offset_y_mm": float(offset_y.value()),
            "offset_z_mm": float(offset_z.value()),
        }

    def show_message(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    @staticmethod
    def _offset_spin(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-10000.0, 10000.0)
        spin.setDecimals(3)
        spin.setSingleStep(0.1)
        spin.setSuffix(" mm")
        spin.setValue(float(value))
        return spin

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(LABEL_STYLE)
        return label

    def set_start_enabled(self, enabled: bool) -> None:
        self._dashboard.set_start_enabled(enabled)

    def set_stop_enabled(self, enabled: bool) -> None:
        self._dashboard.set_stop_enabled(enabled)

    def set_pause_enabled(self, enabled: bool) -> None:
        self._dashboard.set_pause_enabled(enabled)

    def set_pause_label(self, text: str) -> None:
        self._dashboard.set_pause_text(text)

    def apply_dashboard_state(self, state) -> None:
        self.set_state(state.process_state)
        self.set_mode(state.mode_label)
        self.set_active_job(state.active_job_label)
        self.set_notes(state.status_lines)
        self.set_start_enabled(state.can_start)
        self.set_stop_enabled(state.can_stop)
        self.set_pause_enabled(state.can_pause)
        self.set_pause_label(state.pause_label)

    def clean_up(self) -> None:
        pass
