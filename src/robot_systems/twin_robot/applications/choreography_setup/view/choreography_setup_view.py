from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.applications.base.robot_jog_widget import RobotJogWidget


class ChoreographySetupView(QWidget):
    new_requested = pyqtSignal(str, str)
    save_requested = pyqtSignal()
    load_requested = pyqtSignal(str)
    add_step_requested = pyqtSignal()
    delete_step_requested = pyqtSignal(int)
    capture_robot_requested = pyqtSignal(str, int)
    capture_both_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Twin Choreography Setup")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        header = QHBoxLayout()
        header.addWidget(QLabel("ID"))
        self.id_edit = QLineEdit()
        header.addWidget(self.id_edit)
        header.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit()
        header.addWidget(self.name_edit, 1)
        header.addWidget(QLabel("Loops"))
        self.loop_spin = QSpinBox()
        self.loop_spin.setRange(1, 100000)
        header.addWidget(self.loop_spin)
        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(
            lambda: self.new_requested.emit(self.id_edit.text().strip(), self.name_edit.text().strip())
        )
        header.addWidget(self.new_button)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_requested.emit)
        header.addWidget(self.save_button)
        root.addLayout(header)

        jog_row = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("Robot 1"))
        self.robot1_jog = RobotJogWidget()
        left.addWidget(self.robot1_jog)
        self.capture_r1_button = QPushButton("Capture Robot 1 into selected step")
        self.capture_r1_button.clicked.connect(
            lambda: self.capture_robot_requested.emit("robot1", self.selected_row())
        )
        left.addWidget(self.capture_r1_button)
        jog_row.addLayout(left, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Robot 2"))
        self.robot2_jog = RobotJogWidget()
        right.addWidget(self.robot2_jog)
        self.capture_r2_button = QPushButton("Capture Robot 2 into selected step")
        self.capture_r2_button.clicked.connect(
            lambda: self.capture_robot_requested.emit("robot2", self.selected_row())
        )
        right.addWidget(self.capture_r2_button)
        jog_row.addLayout(right, 1)
        root.addLayout(jog_row, 2)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Step",
            "Robot 1",
            "Robot 2",
            "R1 Vel",
            "R1 Acc",
            "R2 Vel",
            "R2 Acc",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        root.addWidget(self.table, 1)

        row = QHBoxLayout()
        add_btn = QPushButton("Add Step")
        add_btn.clicked.connect(self.add_step_requested.emit)
        row.addWidget(add_btn)
        delete_btn = QPushButton("Delete Step")
        delete_btn.clicked.connect(lambda: self.delete_step_requested.emit(self.selected_row()))
        row.addWidget(delete_btn)
        capture_both_btn = QPushButton("Capture Both")
        capture_both_btn.clicked.connect(lambda: self.capture_both_requested.emit(self.selected_row()))
        row.addWidget(capture_both_btn)
        row.addStretch(1)
        root.addLayout(row)

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        root.addWidget(self.message_label)

    def selected_row(self) -> int:
        row = self.table.currentRow()
        return row if row >= 0 else 0

    def set_message(self, message: str) -> None:
        self.message_label.setText(str(message or ""))

    def set_definition(self, choreography) -> None:
        self.id_edit.setText(choreography.choreography_id)
        self.name_edit.setText(choreography.name)
        self.loop_spin.setValue(max(1, int(choreography.loop_count)))
        self.table.setRowCount(len(choreography.steps))
        for row, step in enumerate(choreography.steps):
            self.table.setItem(row, 0, QTableWidgetItem(step.name))
            self.table.setItem(row, 1, QTableWidgetItem("✓" if step.robot1.captured else "—"))
            self.table.setItem(row, 2, QTableWidgetItem("✓" if step.robot2.captured else "—"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{step.robot1_motion.velocity:.0f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{step.robot1_motion.acceleration:.0f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{step.robot2_motion.velocity:.0f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"{step.robot2_motion.acceleration:.0f}"))
        if choreography.steps:
            self.table.selectRow(0)
