from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def _fmt_pose(values) -> str:
    if not values:
        return "-"
    try:
        return ", ".join(f"{float(v):.3f}" for v in list(values)[:6])
    except Exception:
        return "-"


class WorkObjectCalibrationTab(QWidget):
    capture_requested = pyqtSignal(str)
    solve_requested = pyqtSignal(int, str)
    save_requested = pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._point_labels: dict[str, QLabel] = {}
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        setup_group = QGroupBox("WorkObject")
        setup_layout = QFormLayout(setup_group)
        setup_layout.setContentsMargins(12, 12, 12, 12)
        setup_layout.setSpacing(10)

        self._user_id = QSpinBox()
        self._user_id.setRange(0, 99)
        self._user_id.setValue(1)
        setup_layout.addRow("User ID", self._user_id)

        self._name = QLineEdit()
        self._name.setText("WOBJ_1")
        setup_layout.addRow("Name", self._name)
        root.addWidget(setup_group)

        points_group = QGroupBox("3 Point Frame")
        points_layout = QGridLayout(points_group)
        points_layout.setContentsMargins(12, 12, 12, 12)
        points_layout.setHorizontalSpacing(10)
        points_layout.setVerticalSpacing(8)

        for row, key, label in (
            (0, "center", "Center"),
            (1, "x", "X Direction"),
            (2, "y", "Y Direction"),
        ):
            btn = QPushButton(f"Capture {label}")
            btn.clicked.connect(lambda _checked=False, k=key: self.capture_requested.emit(k))
            value = QLabel("-")
            value.setWordWrap(True)
            self._point_labels[key] = value
            points_layout.addWidget(btn, row, 0)
            points_layout.addWidget(value, row, 1)
        root.addWidget(points_group)

        action_row = QHBoxLayout()
        solve_btn = QPushButton("Solve Orientation")
        solve_btn.clicked.connect(self._emit_solve)
        save_btn = QPushButton("Save and Activate")
        save_btn.clicked.connect(self._emit_save)
        action_row.addWidget(solve_btn)
        action_row.addWidget(save_btn)
        root.addLayout(action_row)

        self._result = QLabel("No WorkObject solved")
        self._result.setWordWrap(True)
        root.addWidget(self._result)
        root.addStretch()

    def _emit_solve(self) -> None:
        self.solve_requested.emit(self.user_id(), self.name())

    def _emit_save(self) -> None:
        self.save_requested.emit(self.user_id(), self.name())

    def user_id(self) -> int:
        return int(self._user_id.value())

    def name(self) -> str:
        return self._name.text().strip() or f"WOBJ_{self.user_id()}"

    def set_capture_result(self, point: str, pose) -> None:
        label = self._point_labels.get(str(point).lower())
        if label is not None:
            label.setText(_fmt_pose(pose))

    def set_result(self, ok: bool, message: str, payload: dict | None = None) -> None:
        text = message
        transform = (payload or {}).get("transform")
        if transform:
            text = f"{message}\nTransform: [{_fmt_pose(transform)}]"
        self._result.setText(text)
        self._result.setStyleSheet("color: #1B5E20;" if ok else "color: #B00020;")
