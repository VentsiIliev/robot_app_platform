from __future__ import annotations

from typing import Any, Dict, List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    GHOST_BTN_STYLE,
    GROUP_STYLE,
    LABEL_STYLE,
    SAVE_BUTTON_STYLE,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.robot_jog_widget import RobotJogWidget
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardLineEdit


class ChoreographySetupView(IApplicationView):
    SHOW_JOG_WIDGET = False

    new_requested = pyqtSignal(str, str)
    save_requested = pyqtSignal()
    load_requested = pyqtSignal(str)
    add_step_requested = pyqtSignal()
    delete_step_requested = pyqtSignal(int)
    capture_robot_requested = pyqtSignal(str, int)
    capture_both_requested = pyqtSignal(int)

    robot_jog_requested = pyqtSignal(str, str, str, str, float)
    robot_jog_stopped = pyqtSignal(str)
    robot_joint_jog_requested = pyqtSignal(str, str, str, str, float)

    def __init__(self, parent=None):
        super().__init__("Choreography Setup", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel(self.tr("Twin Choreography Setup"))
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        library_row = QHBoxLayout()
        library_label = QLabel(self.tr("Saved choreography"))
        library_label.setStyleSheet(LABEL_STYLE)
        library_row.addWidget(library_label)
        self.library_combo = QComboBox()
        library_row.addWidget(self.library_combo, 1)
        self.load_button = QPushButton(self.tr("Load"))
        self._style_secondary(self.load_button)
        self.load_button.clicked.connect(self._on_load_clicked)
        library_row.addWidget(self.load_button)
        root.addLayout(library_row)

        header = QHBoxLayout()
        id_label = QLabel(self.tr("ID"))
        id_label.setStyleSheet(LABEL_STYLE)
        header.addWidget(id_label)
        self.id_edit = KeyboardLineEdit()
        header.addWidget(self.id_edit)

        name_label = QLabel(self.tr("Name"))
        name_label.setStyleSheet(LABEL_STYLE)
        header.addWidget(name_label)
        self.name_edit = KeyboardLineEdit()
        header.addWidget(self.name_edit, 1)

        loop_label = QLabel(self.tr("Loops"))
        loop_label.setStyleSheet(LABEL_STYLE)
        header.addWidget(loop_label)
        self.loop_spin = QSpinBox()
        self.loop_spin.setRange(1, 100000)
        self.loop_spin.setValue(1)
        header.addWidget(self.loop_spin)

        self.new_button = QPushButton(self.tr("New"))
        self._style_secondary(self.new_button)
        self.new_button.clicked.connect(self._on_new_clicked)
        header.addWidget(self.new_button)

        self.save_button = QPushButton(self.tr("Save"))
        self.save_button.setStyleSheet(SAVE_BUTTON_STYLE)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.clicked.connect(self._on_save_clicked)
        header.addWidget(self.save_button)
        root.addLayout(header)

        jog_row = QHBoxLayout()
        self.robot1_jog, self._robot1_panel = self._build_robot_panel(
            robot_name="robot1",
            title=self.tr("Robot 1"),
            capture_text=self.tr("Capture Robot 1 into selected step"),
        )
        jog_row.addWidget(self._robot1_panel, 1)

        self.robot2_jog, self._robot2_panel = self._build_robot_panel(
            robot_name="robot2",
            title=self.tr("Robot 2"),
            capture_text=self.tr("Capture Robot 2 into selected step"),
        )
        jog_row.addWidget(self._robot2_panel, 1)
        root.addLayout(jog_row, 2)

        steps_box = QGroupBox(self.tr("Choreography Steps"))
        steps_box.setStyleSheet(GROUP_STYLE)
        steps_layout = QVBoxLayout(steps_box)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            self.tr("Step"),
            self.tr("Robot 1"),
            self.tr("Robot 2"),
            self.tr("R1 Vel"),
            self.tr("R1 Acc"),
            self.tr("R2 Vel"),
            self.tr("R2 Acc"),
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        steps_layout.addWidget(self.table)

        actions = QHBoxLayout()
        self.add_step_button = QPushButton(self.tr("Add Step"))
        self._style_secondary(self.add_step_button)
        self.add_step_button.clicked.connect(self._on_add_step_clicked)
        actions.addWidget(self.add_step_button)

        self.delete_step_button = QPushButton(self.tr("Delete Step"))
        self._style_secondary(self.delete_step_button)
        self.delete_step_button.clicked.connect(self._on_delete_step_clicked)
        actions.addWidget(self.delete_step_button)

        self.capture_both_button = QPushButton(self.tr("Capture Both"))
        self.capture_both_button.setStyleSheet(ACTION_BTN_STYLE)
        self.capture_both_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.capture_both_button.clicked.connect(self._on_capture_both_clicked)
        actions.addWidget(self.capture_both_button)
        actions.addStretch(1)
        steps_layout.addLayout(actions)
        root.addWidget(steps_box, 1)

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        root.addWidget(self.message_label)

    def _build_robot_panel(
        self,
        robot_name: str,
        title: str,
        capture_text: str,
    ) -> tuple[RobotJogWidget, QGroupBox]:
        panel = QGroupBox(title)
        panel.setStyleSheet(GROUP_STYLE)
        layout = QVBoxLayout(panel)
        widget = RobotJogWidget()
        layout.addWidget(widget)

        capture = QPushButton(capture_text)
        capture.setStyleSheet(ACTION_BTN_STYLE)
        capture.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(capture)

        if robot_name == "robot1":
            capture.clicked.connect(self._on_capture_robot1_clicked)
            widget.jog_requested.connect(self._on_robot1_jog_requested)
            widget.jog_stopped.connect(self._on_robot1_jog_stopped)
            widget.joint_jog_requested.connect(self._on_robot1_joint_jog_requested)
        else:
            capture.clicked.connect(self._on_capture_robot2_clicked)
            widget.jog_requested.connect(self._on_robot2_jog_requested)
            widget.jog_stopped.connect(self._on_robot2_jog_stopped)
            widget.joint_jog_requested.connect(self._on_robot2_joint_jog_requested)
        return widget, panel

    @staticmethod
    def _style_secondary(button: QPushButton) -> None:
        button.setStyleSheet(GHOST_BTN_STYLE)
        button.setCursor(Qt.CursorShape.PointingHandCursor)

    def selected_row(self) -> int:
        row = self.table.currentRow()
        return row if row >= 0 else 0

    def set_message(self, message: str) -> None:
        self.message_label.setText(str(message or ""))

    def set_library(self, choreographies: List[Dict[str, Any]], selected_id: str | None = None) -> None:
        self.library_combo.blockSignals(True)
        self.library_combo.clear()
        for choreography in choreographies:
            choreography_id = str(choreography.get("id", ""))
            name = str(choreography.get("name", choreography_id))
            self.library_combo.addItem(name, choreography_id)
        if selected_id:
            index = self.library_combo.findData(selected_id)
            if index >= 0:
                self.library_combo.setCurrentIndex(index)
        self.library_combo.blockSignals(False)

    def set_definition(self, choreography: Dict[str, Any], selected_row: int = 0) -> None:
        self.id_edit.setText(str(choreography.get("id", "")))
        self.name_edit.setText(str(choreography.get("name", "")))
        self.loop_spin.setValue(max(1, int(choreography.get("loop_count", 1))))

        steps = list(choreography.get("steps", []))
        self.table.setRowCount(len(steps))
        for row, step in enumerate(steps):
            robot1 = step.get("robot1", {}) or {}
            robot2 = step.get("robot2", {}) or {}
            r1_motion = step.get("robot1_motion", {}) or {}
            r2_motion = step.get("robot2_motion", {}) or {}
            self.table.setItem(row, 0, QTableWidgetItem(str(step.get("name", f"Step {row + 1}"))))
            self.table.setItem(row, 1, self._capture_status_item(robot1))
            self.table.setItem(row, 2, self._capture_status_item(robot2))
            self.table.setItem(row, 3, QTableWidgetItem(f"{float(r1_motion.get('velocity', 30.0)):.0f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{float(r1_motion.get('acceleration', 30.0)):.0f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{float(r2_motion.get('velocity', 30.0)):.0f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"{float(r2_motion.get('acceleration', 30.0)):.0f}"))

        if steps:
            self.table.selectRow(min(max(0, selected_row), len(steps) - 1))

    @staticmethod
    def _capture_status_item(robot_payload: Dict[str, Any]) -> QTableWidgetItem:
        captured = len(list(robot_payload.get("pose", []) or [])) == 6
        item = QTableWidgetItem("✓" if captured else "—")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def editor_snapshot(self) -> Dict[str, Any]:
        steps: List[Dict[str, Any]] = []
        for row in range(self.table.rowCount()):
            steps.append({
                "name": self._row_text(row, 0, f"Step {row + 1}"),
                "robot1_velocity": self._number(row, 3, 30.0),
                "robot1_acceleration": self._number(row, 4, 30.0),
                "robot2_velocity": self._number(row, 5, 30.0),
                "robot2_acceleration": self._number(row, 6, 30.0),
            })
        return {
            "name": self.name_edit.text().strip(),
            "loop_count": int(self.loop_spin.value()),
            "steps": steps,
        }

    def set_robot_state(self, robot_name: str, pose: List[float], joints: List[float]) -> None:
        widget = self.robot1_jog if robot_name == "robot1" else self.robot2_jog
        widget.set_position(list(pose or []))
        widget.set_joint_position(list(joints or []))

    def _number(self, row: int, column: int, default: float) -> float:
        item = self.table.item(row, column)
        if item is None:
            return default
        try:
            return float(item.text().strip())
        except ValueError:
            return default

    def _row_text(self, row: int, column: int, default: str) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item and item.text().strip() else default

    def _on_load_clicked(self) -> None:
        choreography_id = self.library_combo.currentData()
        if choreography_id:
            self.load_requested.emit(str(choreography_id))

    def _on_new_clicked(self) -> None:
        self.new_requested.emit(self.id_edit.text().strip(), self.name_edit.text().strip())

    def _on_save_clicked(self) -> None:
        self.save_requested.emit()

    def _on_add_step_clicked(self) -> None:
        self.add_step_requested.emit()

    def _on_delete_step_clicked(self) -> None:
        self.delete_step_requested.emit(self.selected_row())

    def _on_capture_both_clicked(self) -> None:
        self.capture_both_requested.emit(self.selected_row())

    def _on_capture_robot1_clicked(self) -> None:
        self.capture_robot_requested.emit("robot1", self.selected_row())

    def _on_capture_robot2_clicked(self) -> None:
        self.capture_robot_requested.emit("robot2", self.selected_row())

    def _on_robot1_jog_requested(self, command: str, axis: str, direction: str, step: float) -> None:
        self.robot_jog_requested.emit("robot1", command, axis, direction, step)

    def _on_robot2_jog_requested(self, command: str, axis: str, direction: str, step: float) -> None:
        self.robot_jog_requested.emit("robot2", command, axis, direction, step)

    def _on_robot1_jog_stopped(self, _key: str) -> None:
        self.robot_jog_stopped.emit("robot1")

    def _on_robot2_jog_stopped(self, _key: str) -> None:
        self.robot_jog_stopped.emit("robot2")

    def _on_robot1_joint_jog_requested(
        self, command: str, joint: str, direction: str, step: float
    ) -> None:
        self.robot_joint_jog_requested.emit("robot1", command, joint, direction, step)

    def _on_robot2_joint_jog_requested(
        self, command: str, joint: str, direction: str, step: float
    ) -> None:
        self.robot_joint_jog_requested.emit("robot2", command, joint, direction, step)

    def retranslateUi(self) -> None:
        pass

    def clean_up(self) -> None:
        pass
