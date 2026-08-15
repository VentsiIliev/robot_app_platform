from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class TwinDashboardView(QWidget):
    choreography_selected = pyqtSignal(str)
    plan_requested = pyqtSignal()
    start_requested = pyqtSignal(int)
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        title = QLabel("Twin Robot Choreography")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        root.addWidget(title)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Choreography"))
        self.choreography_combo = QComboBox()
        self.choreography_combo.currentIndexChanged.connect(self._on_selection_changed)
        selector_row.addWidget(self.choreography_combo, 1)
        root.addLayout(selector_row)

        status_card = QFrame()
        status_card.setFrameShape(QFrame.Shape.StyledPanel)
        status_layout = QVBoxLayout(status_card)
        self.robot1_status = QLabel("Robot 1 trajectory: NOT PLANNED")
        self.robot2_status = QLabel("Robot 2 trajectory: NOT PLANNED")
        self.sync_status = QLabel("Synchronization: NOT READY")
        status_layout.addWidget(self.robot1_status)
        status_layout.addWidget(self.robot2_status)
        status_layout.addWidget(self.sync_status)
        root.addWidget(status_card)

        controls = QHBoxLayout()
        self.plan_button = QPushButton("PLAN BOTH")
        self.plan_button.clicked.connect(self.plan_requested.emit)
        controls.addWidget(self.plan_button)

        controls.addWidget(QLabel("Loops"))
        self.loop_count = QSpinBox()
        self.loop_count.setRange(1, 100000)
        self.loop_count.setValue(1)
        controls.addWidget(self.loop_count)

        self.start_button = QPushButton("START")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(
            lambda: self.start_requested.emit(int(self.loop_count.value()))
        )
        controls.addWidget(self.start_button)

        self.stop_button = QPushButton("STOP")
        self.stop_button.clicked.connect(self.stop_requested.emit)
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
            self.choreography_combo.addItem(choreography.name, choreography.choreography_id)
        if current:
            index = self.choreography_combo.findData(current)
            if index >= 0:
                self.choreography_combo.setCurrentIndex(index)
        self.choreography_combo.blockSignals(False)
        if self.choreography_combo.count():
            self._on_selection_changed(self.choreography_combo.currentIndex())

    def set_plan_status(self, robot1_ready: bool, robot2_ready: bool, message: str = "") -> None:
        self.robot1_status.setText(
            f"Robot 1 trajectory: {'READY' if robot1_ready else 'NOT READY'}"
        )
        self.robot2_status.setText(
            f"Robot 2 trajectory: {'READY' if robot2_ready else 'NOT READY'}"
        )
        ready = bool(robot1_ready and robot2_ready)
        self.sync_status.setText(f"Synchronization: {'READY' if ready else 'NOT READY'}")
        self.start_button.setEnabled(ready)
        self.message_label.setText(message)

    def set_message(self, message: str) -> None:
        self.message_label.setText(str(message or ""))

    def _on_selection_changed(self, index: int) -> None:
        choreography_id = self.choreography_combo.itemData(index) if index >= 0 else None
        self.start_button.setEnabled(False)
        self.set_plan_status(False, False)
        if choreography_id:
            self.choreography_selected.emit(str(choreography_id))
