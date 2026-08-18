from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
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
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.styled_message_box import show_critical, show_info
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardLineEdit
from src.robot_systems.paint.applications.paint_motion_recipe.domain.recipe import (
    MotionRecipe,
    MotionRecipeStep,
)


def _t(text: str) -> str:
    translated = QCoreApplication.translate("PaintMotionRecipe", text)
    return translated or text


class PaintMotionRecipeView(IApplicationView):
    add_group_step_requested = pyqtSignal(str, str, str)
    capture_pose_step_requested = pyqtSignal(str)
    remove_step_requested = pyqtSignal(int)
    move_step_requested = pyqtSignal(int, int)
    step_enabled_changed = pyqtSignal(int, bool)
    save_requested = pyqtSignal()
    reload_requested = pyqtSignal()
    test_step_requested = pyqtSignal(int)

    _ACTIONS = (
        ("move_group", "Move Group"),
        ("capture", "Capture"),
        ("vacuum_on", "Vacuum ON"),
        ("vacuum_off", "Vacuum OFF"),
        ("unwind", "Unwind"),
        ("cleanup", "Cleanup"),
        ("wait", "Wait"),
    )

    def __init__(self, parent=None) -> None:
        self._groups: list[str] = []
        self._recipe = MotionRecipe.default()
        self._updating = False
        super().__init__("PaintMotionRecipe", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Paint Motion Recipe")
        title.setStyleSheet(LABEL_STYLE)
        root.addWidget(title)

        form = QWidget()
        form.setStyleSheet(GROUP_STYLE)
        form_layout = QGridLayout(form)
        form_layout.setContentsMargins(12, 18, 12, 12)
        form_layout.setHorizontalSpacing(8)
        form_layout.setVerticalSpacing(8)

        self._label_input = KeyboardLineEdit()
        self._label_input.setPlaceholderText("Step label")
        self._action_combo = QComboBox()
        for value, label in self._ACTIONS:
            self._action_combo.addItem(label, value)
        self._group_combo = QComboBox()

        form_layout.addWidget(QLabel("Label"), 0, 0)
        form_layout.addWidget(self._label_input, 0, 1)
        form_layout.addWidget(QLabel("Action"), 0, 2)
        form_layout.addWidget(self._action_combo, 0, 3)
        form_layout.addWidget(QLabel("Group"), 0, 4)
        form_layout.addWidget(self._group_combo, 0, 5)

        self._add_group_btn = self._button("Add Step", primary=True)
        self._capture_pose_btn = self._button("Capture Pose Step", primary=False)
        self._add_group_btn.clicked.connect(self._on_add_group_step)
        self._capture_pose_btn.clicked.connect(self._on_capture_pose_step)
        form_layout.addWidget(self._add_group_btn, 0, 6)
        form_layout.addWidget(self._capture_pose_btn, 0, 7)
        root.addWidget(form)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["On", "Label", "Action", "Group", "Pose", "Note"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        root.addWidget(self._table, 1)

        controls = QHBoxLayout()
        for text, handler in (
            ("Up", lambda: self._emit_move(-1)),
            ("Down", lambda: self._emit_move(1)),
            ("Remove", self._emit_remove),
            ("Test Selected", self._emit_test),
            ("Reload", self.reload_requested.emit),
        ):
            btn = self._button(text, primary=False)
            btn.clicked.connect(handler)
            controls.addWidget(btn)
        controls.addStretch()
        self._save_btn = self._button("Save Recipe", primary=True)
        self._save_btn.clicked.connect(self.save_requested.emit)
        controls.addWidget(self._save_btn)
        root.addLayout(controls)

        self._status = QLabel("Ready")
        self._status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._status)

    def set_groups(self, groups: list[str]) -> None:
        self._groups = list(groups)
        self._group_combo.clear()
        self._group_combo.addItems(self._groups)

    def set_recipe(self, recipe: MotionRecipe) -> None:
        self._recipe = recipe
        self._updating = True
        try:
            self._table.setRowCount(len(recipe.steps))
            for row, step in enumerate(recipe.steps):
                self._set_step_row(row, step)
        finally:
            self._updating = False

    def set_status(self, message: str) -> None:
        self._status.setText(str(message or "Ready"))

    def show_info(self, title: str, message: str) -> None:
        show_info(self, _t(title), _t(message))

    def show_error(self, title: str, message: str) -> None:
        show_critical(self, _t(title), _t(message))

    def _set_step_row(self, row: int, step: MotionRecipeStep) -> None:
        enabled = QCheckBox()
        enabled.setChecked(step.enabled)
        enabled.stateChanged.connect(
            lambda state, r=row: self._on_enabled_changed(r, state == Qt.CheckState.Checked.value)
        )
        self._table.setCellWidget(row, 0, enabled)
        self._table.setItem(row, 1, self._item(step.label))
        self._table.setItem(row, 2, self._item(step.action))
        self._table.setItem(row, 3, self._item(step.group_id))
        self._table.setItem(row, 4, self._item(self._pose_summary(step.pose)))
        self._table.setItem(row, 5, self._item(step.note))

    def _on_enabled_changed(self, row: int, enabled: bool) -> None:
        if not self._updating:
            self.step_enabled_changed.emit(row, enabled)

    def _on_add_group_step(self) -> None:
        label = self._label_input.text().strip()
        action = str(self._action_combo.currentData() or "")
        group = self._group_combo.currentText().strip()
        self.add_group_step_requested.emit(label, action, group)

    def _on_capture_pose_step(self) -> None:
        label = self._label_input.text().strip() or "Captured safety waypoint"
        self.capture_pose_step_requested.emit(label)

    def _selected_row(self) -> int:
        rows = self._table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _emit_remove(self) -> None:
        self.remove_step_requested.emit(self._selected_row())

    def _emit_move(self, delta: int) -> None:
        self.move_step_requested.emit(self._selected_row(), delta)

    def _emit_test(self) -> None:
        self.test_step_requested.emit(self._selected_row())

    @staticmethod
    def _item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text or ""))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    @staticmethod
    def _pose_summary(pose) -> str:
        if pose is None:
            return ""
        return ", ".join(f"{float(value):.1f}" for value in pose[:6])

    @staticmethod
    def _button(text: str, *, primary: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(ACTION_BTN_STYLE if primary else GHOST_BTN_STYLE)
        return btn
