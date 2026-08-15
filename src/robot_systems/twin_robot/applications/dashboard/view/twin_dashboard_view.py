from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    GHOST_BTN_STYLE,
    GROUP_STYLE,
    LABEL_STYLE,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardSpinBox


class TwinDashboardView(IApplicationView):
    SHOW_JOG_WIDGET = False

    choreography_selected = pyqtSignal(str)
    plan_requested = pyqtSignal()
    start_requested = pyqtSignal(int)
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Twin Dashboard", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        title = QLabel(self.tr("Twin Robot Choreography"))
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        root.addWidget(title)

        selector_row = QHBoxLayout()
        selector_label = QLabel(self.tr("Choreography"))
        selector_label.setStyleSheet(LABEL_STYLE)
        selector_row.addWidget(selector_label)
        self.choreography_combo = QComboBox()
        self.choreography_combo.currentIndexChanged.connect(self._on_selection_changed)
        selector_row.addWidget(self.choreography_combo, 1)
        root.addLayout(selector_row)

        status_box = QGroupBox(self.tr("Preparation"))
        status_box.setStyleSheet(GROUP_STYLE)
        status_layout = QVBoxLayout(status_box)
        self.robot1_status = QLabel(self.tr("Robot 1 trajectory: NOT PLANNED"))
        self.robot2_status = QLabel(self.tr("Robot 2 trajectory: NOT PLANNED"))
        self.sync_status = QLabel(self.tr("Synchronization: NOT READY"))
        status_layout.addWidget(self.robot1_status)
        status_layout.addWidget(self.robot2_status)
        status_layout.addWidget(self.sync_status)
        root.addWidget(status_box)

        controls = QHBoxLayout()
        self.plan_button = QPushButton(self.tr("PLAN BOTH"))
        self.plan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plan_button.setStyleSheet(ACTION_BTN_STYLE)
        self.plan_button.clicked.connect(self._on_plan_clicked)
        controls.addWidget(self.plan_button)

        loop_label = QLabel(self.tr("Loops"))
        loop_label.setStyleSheet(LABEL_STYLE)
        controls.addWidget(loop_label)
        self.loop_count = KeyboardSpinBox()
        self.loop_count.setRange(1, 100000)
        self.loop_count.setValue(1)
        controls.addWidget(self.loop_count)

        self.start_button = QPushButton(self.tr("START"))
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.setStyleSheet(ACTION_BTN_STYLE)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._on_start_clicked)
        controls.addWidget(self.start_button)

        self.stop_button = QPushButton(self.tr("STOP"))
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setStyleSheet(GHOST_BTN_STYLE)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        controls.addWidget(self.stop_button)
        root.addLayout(controls)

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        root.addWidget(self.message_label)
        root.addStretch(1)

    def set_choreographies(self, items) -> None:
        current = self.choreography_combo.currentData()
        self.choreography_combo.blockSignals(True)
        self.choreography_combo.clear()
        for choreography in items:
            choreography_id = str(choreography.get("id", ""))
            name = str(choreography.get("name", choreography_id))
            self.choreography_combo.addItem(name, choreography_id)
        if current:
            index = self.choreography_combo.findData(current)
            if index >= 0:
                self.choreography_combo.setCurrentIndex(index)
        self.choreography_combo.blockSignals(False)

    def select_first_choreography(self) -> None:
        if self.choreography_combo.count() > 0:
            self.choreography_combo.setCurrentIndex(0)
            self._on_selection_changed(0)

    def set_loop_count(self, value: int) -> None:
        self.loop_count.setValue(max(1, int(value)))

    def set_busy(self, busy: bool, message: str = "") -> None:
        self.plan_button.setEnabled(not busy)
        self.choreography_combo.setEnabled(not busy)
        if busy:
            self.start_button.setEnabled(False)
        if message:
            self.message_label.setText(message)

    def set_plan_status(self, robot1_ready: bool, robot2_ready: bool, message: str = "") -> None:
        self.robot1_status.setText(
            self.tr("Robot 1 trajectory: READY") if robot1_ready
            else self.tr("Robot 1 trajectory: NOT READY")
        )
        self.robot2_status.setText(
            self.tr("Robot 2 trajectory: READY") if robot2_ready
            else self.tr("Robot 2 trajectory: NOT READY")
        )
        ready = bool(robot1_ready and robot2_ready)
        self.sync_status.setText(
            self.tr("Synchronization: READY") if ready
            else self.tr("Synchronization: NOT READY")
        )
        self.start_button.setEnabled(ready)
        self.plan_button.setEnabled(True)
        self.choreography_combo.setEnabled(True)
        self.message_label.setText(message)

    def set_message(self, message: str) -> None:
        self.message_label.setText(str(message or ""))

    def _on_selection_changed(self, index: int) -> None:
        choreography_id = self.choreography_combo.itemData(index) if index >= 0 else None
        self.set_plan_status(False, False)
        if choreography_id:
            self.choreography_selected.emit(str(choreography_id))

    def _on_plan_clicked(self) -> None:
        self.plan_requested.emit()

    def _on_start_clicked(self) -> None:
        self.start_requested.emit(int(self.loop_count.value()))

    def _on_stop_clicked(self) -> None:
        self.stop_requested.emit()

    def retranslateUi(self) -> None:
        pass

    def clean_up(self) -> None:
        pass
