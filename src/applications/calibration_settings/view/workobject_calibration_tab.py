from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from pl_gui.settings.settings_view.styles import BORDER, PRIMARY, SECONDARY_BG, TEXT_COLOR
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardLineEdit
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField


def _fmt_pose(values) -> str:
    if not values:
        return "-"
    try:
        return ", ".join(f"{float(v):.3f}" for v in list(values)[:6])
    except Exception:
        return "-"


_PRIMARY_STYLE = f"""
QPushButton {{ background: {PRIMARY}; color: white; border: none;
    border-radius: 8px; min-height: 42px; padding: 0 16px; font-weight: bold; }}
QPushButton:disabled {{ background: {SECONDARY_BG}; color: {PRIMARY}; }}
"""
_SECONDARY_STYLE = f"""
QPushButton {{ background: {SECONDARY_BG}; color: {PRIMARY}; border: none;
    border-radius: 8px; min-height: 42px; padding: 0 16px; font-weight: bold; }}
"""


class WorkObjectCalibrationTab(QWidget):
    capture_requested = pyqtSignal(str)
    solve_requested = pyqtSignal(int, str)
    save_requested = pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._point_labels: dict[str, QLabel] = {}
        self._step_widgets: list[tuple[QLabel, QLabel, QPushButton, str, str]] = []
        self._captured_points: set[str] = set()
        self._result_is_default = True
        self._build()

    @staticmethod
    def _t(source: str) -> str:
        return QCoreApplication.translate("WorkObjectCalibrationTab", source) or source

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        card = QWidget()
        card.setStyleSheet(f"QWidget {{ background: white; border: 1px solid {BORDER}; border-radius: 10px; }}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._title_label = QLabel()
        self._title_label.setStyleSheet(f"color: {TEXT_COLOR}; border: none; font-size: 15pt; font-weight: bold;")
        layout.addWidget(self._title_label)
        self._hint_label = QLabel()
        self._hint_label.setWordWrap(True)
        self._hint_label.setStyleSheet(f"color: {PRIMARY}; border: none; font-size: 9pt;")
        layout.addWidget(self._hint_label)

        setup = QWidget()
        setup.setStyleSheet(f"background: white; border: 1px solid {BORDER}; border-radius: 8px;")
        setup_layout = QVBoxLayout(setup)
        setup_layout.setContentsMargins(12, 8, 12, 8)
        setup_layout.setSpacing(6)
        self._setup_label = QLabel()
        self._setup_label.setStyleSheet(f"color: {TEXT_COLOR}; border: none; font-weight: bold;")
        setup_layout.addWidget(self._setup_label)
        self._user_id = KeyboardNumberField()
        self._user_id.setRange(0, 99)
        self._user_id.setValue(1)
        self._name = KeyboardLineEdit()
        self._name.setText("WOBJ_1")
        for label_text, editor in (("User ID", self._user_id), ("Name", self._name)):
            label = QLabel()
            label.setStyleSheet(f"color: {PRIMARY}; border: none; font-size: 9pt;")
            setup_layout.addWidget(label)
            setup_layout.addWidget(editor)
            if label_text == "Name":
                self._name_label = label
            else:
                self._user_label = label
        layout.addWidget(setup)

        self._add_step(layout, 1, "center", "Center", self._capture_center)
        self._add_step(layout, 2, "x", "X direction", self._capture_x)
        self._add_step(layout, 3, "y", "Y direction", self._capture_y)

        self._solve_btn = QPushButton()
        self._solve_btn.setStyleSheet(_PRIMARY_STYLE)
        self._solve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._solve_btn.setEnabled(False)
        self._solve_btn.clicked.connect(self._emit_solve)
        layout.addWidget(self._solve_btn)
        self._save_btn = QPushButton()
        self._save_btn.setStyleSheet(_PRIMARY_STYLE)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._emit_save)
        layout.addWidget(self._save_btn)

        self._result = QLabel()
        self._result.setWordWrap(True)
        self._result.setStyleSheet(
            f"color: {PRIMARY}; background: {SECONDARY_BG}; border: none; "
            "border-radius: 8px; padding: 10px;"
        )
        layout.addWidget(self._result)
        root.addWidget(card)
        root.addStretch()
        self._retranslate()

    def _add_step(self, layout: QVBoxLayout, number: int, key: str, name: str, callback) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        badge = QLabel(str(number))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(28, 28)
        badge.setStyleSheet(
            f"color: {PRIMARY}; background: {SECONDARY_BG}; border: none; "
            "border-radius: 14px; font-weight: bold;"
        )
        row.addWidget(badge)
        text = QVBoxLayout()
        text.setSpacing(0)
        name_label = QLabel()
        name_label.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
        text.addWidget(name_label)
        value = QLabel()
        value.setWordWrap(True)
        value.setStyleSheet(f"color: {PRIMARY}; border: none; font-size: 9pt;")
        self._point_labels[key] = value
        text.addWidget(value)
        row.addLayout(text, stretch=1)
        button = QPushButton()
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(_SECONDARY_STYLE)
        button.clicked.connect(callback)
        row.addWidget(button)
        layout.addLayout(row)
        self._step_widgets.append((name_label, value, button, name, key))

    def _retranslate(self) -> None:
        self._title_label.setText(self._t("WorkObject"))
        self._hint_label.setText(self._t("Capture three points to define the work object frame."))
        self._setup_label.setText(self._t("Work object"))
        self._user_label.setText(self._t("User ID"))
        self._name_label.setText(self._t("Name"))
        for name_label, value_label, button, source, key in self._step_widgets:
            name_label.setText(self._t(source))
            if key not in self._captured_points:
                value_label.setText(self._t("Not captured"))
            button.setText(self._t("Capture"))
        self._solve_btn.setText(self._t("Solve orientation"))
        self._save_btn.setText(self._t("Save and activate"))
        if self._result_is_default:
            self._result.setText(self._t("No WorkObject solved"))

    def _capture_center(self) -> None:
        self.capture_requested.emit("center")

    def _capture_x(self) -> None:
        self.capture_requested.emit("x")

    def _capture_y(self) -> None:
        self.capture_requested.emit("y")

    def _emit_solve(self) -> None:
        self.solve_requested.emit(self.user_id(), self.name())

    def _emit_save(self) -> None:
        self.save_requested.emit(self.user_id(), self.name())

    def user_id(self) -> int:
        return int(self._user_id.value())

    def name(self) -> str:
        return self._name.text().strip() or f"WOBJ_{self.user_id()}"

    def set_capture_result(self, point: str, pose) -> None:
        key = str(point).lower()
        label = self._point_labels.get(key)
        if label is not None:
            label.setText(_fmt_pose(pose))
            if pose:
                self._captured_points.add(key)
            else:
                self._captured_points.discard(key)
            self._solve_btn.setEnabled(len(self._captured_points) == 3)
            self._save_btn.setEnabled(False)

    def set_result(self, ok: bool, message: str, payload: dict | None = None) -> None:
        self._result_is_default = False
        result_text = message
        transform = (payload or {}).get("transform")
        if transform:
            result_text = f"{message}\nTransform: [{_fmt_pose(transform)}]"
        self._result.setText(result_text)
        self._save_btn.setEnabled(bool(ok and transform))
