from typing import List, Union

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from src.settings.settings_view.styles import (
    ACTION_BTN_STYLE, BG_COLOR, BORDER, GHOST_BTN_STYLE, LABEL_STYLE,
    PRIMARY_DARK, PRIMARY_LIGHT,
)
from src.utils_widgets.touch_spinbox import TouchSpinBox


# ── Integer editor dialog ─────────────────────────────────────────────────────

class _IntEditorDialog(QDialog):
    """Compact single-value integer editor used by IntListWidget."""

    def __init__(self, title: str, initial: int, min_val: int, max_val: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(360)
        self.setStyleSheet(f"background: {BG_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        lbl = QLabel("ID value")
        lbl.setStyleSheet(LABEL_STYLE)
        layout.addWidget(lbl)

        self._spin = TouchSpinBox(
            min_val=min_val, max_val=max_val, initial=float(initial),
            step=1, decimals=0, step_options=[1],
        )
        layout.addWidget(self._spin)

        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(GHOST_BTN_STYLE)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet(ACTION_BTN_STYLE)
        ok_btn.setMinimumWidth(100)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addWidget(btn_row)

    def get_value(self) -> int:
        return int(self._spin.value())


# ── IntListWidget ─────────────────────────────────────────────────────────────

class IntListWidget(QFrame):
    """
    Touch-friendly editor for a list of integers.

    Displays items in a QListWidget with Add / Edit / Remove buttons.
    Fits into GenericSettingGroup via widget_type="int_list".

    Signals:
        valueChanged(list)  — emits the full list of ints on every change
    """

    valueChanged = pyqtSignal(list)

    _LIST_STYLE = f"""
    QListWidget {{
        background: white;
        border: none;
        font-size: 11pt;
        color: #333333;
    }}
    QListWidget::item {{ padding: 6px 8px; }}
    QListWidget::item:selected {{
        background: {PRIMARY_LIGHT};
        color: {PRIMARY_DARK};
    }}
    """

    def __init__(self, min_val: int = 0, max_val: int = 255, parent=None):
        super().__init__(parent)
        self._min = min_val
        self._max = max_val
        self.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 2px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._list = QListWidget()
        self._list.setFixedHeight(120)
        self._list.setStyleSheet(self._LIST_STYLE)
        layout.addWidget(self._list)

        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent; border: none;")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        for label, slot, style in [
            ("Add",    self._on_add,    GHOST_BTN_STYLE),
            ("Edit",   self._on_edit,   GHOST_BTN_STYLE),
            ("Remove", self._on_remove, ACTION_BTN_STYLE),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(style)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            btn_layout.addWidget(btn)

        btn_layout.addStretch()
        layout.addWidget(btn_row)

    # ── Button handlers ───────────────────────────────────────────────────

    def _open_editor(self, title: str, initial: int, on_accept):
        dlg = _IntEditorDialog(title, initial, self._min, self._max, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            on_accept(dlg.get_value())

    def _on_add(self):
        self._open_editor("Add ID", self._min, self._append)

    def _on_edit(self):
        row = self._list.currentRow()
        if row < 0:
            return
        try:
            current = int(self._list.item(row).text())
        except ValueError:
            current = self._min
        self._open_editor("Edit ID", current, lambda v: self._update(row, v))

    def _on_remove(self):
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
            self.valueChanged.emit(self.get_ids())

    def _append(self, val: int):
        item = QListWidgetItem(str(val))
        self._list.addItem(item)
        self._list.setCurrentItem(item)
        self.valueChanged.emit(self.get_ids())

    def _update(self, row: int, val: int):
        self._list.item(row).setText(str(val))
        self.valueChanged.emit(self.get_ids())

    # ── Public API ────────────────────────────────────────────────────────

    def get_ids(self) -> List[int]:
        ids = []
        for i in range(self._list.count()):
            try:
                ids.append(int(self._list.item(i).text()))
            except ValueError:
                pass
        return ids

    def set_ids(self, value: Union[List[int], str]) -> None:
        self._list.clear()
        if isinstance(value, str):
            ids = [int(p.strip()) for p in value.split(",") if p.strip().lstrip("-").isdigit()]
        else:
            ids = [int(v) for v in value]
        for id_ in ids:
            self._list.addItem(QListWidgetItem(str(id_)))

    # Aliases so GenericSettingGroup can treat it like other widgets
    def value(self) -> List[int]:
        return self.get_ids()

    def setValue(self, val: Union[List[int], str]) -> None:
        self.set_ids(val)
