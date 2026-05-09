from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEvent, QPoint, QRect, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.applications.base.config.virtual_keyboard_config import (
    ENABLE_CUSTOM_VIRTUAL_KEYBOARD,
)


_KEYBOARD_BG = "#FFFFFF"
_KEYBOARD_PANEL = "#F7F3FA"
_KEYBOARD_BORDER = "#905BA9"
_KEYBOARD_TEXT = "#3A2C4A"
_KEYBOARD_KEY = "#F7F3FA"
_KEYBOARD_KEY_HOVER = "#EFE7F5"
_KEYBOARD_ACTION = "#905BA9"
_KEYBOARD_ACTION_HOVER = "#7E4C96"


class _PopupKeyboardDialog(QDialog):
    def __init__(
        self,
        target: QWidget,
        *,
        numeric_only: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._target = target
        self._numeric_only = bool(numeric_only)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setModal(False)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {_KEYBOARD_BG};
                border: 2px solid {_KEYBOARD_BORDER};
                border-radius: 12px;
            }}
            QPushButton {{
                background-color: {_KEYBOARD_KEY};
                color: {_KEYBOARD_TEXT};
                border: 1px solid #D3D3D3;
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 14px;
                font-weight: 600;
                min-height: 42px;
            }}
            QPushButton:hover {{
                background-color: {_KEYBOARD_KEY_HOVER};
                border: 1px solid {_KEYBOARD_BORDER};
            }}
            QPushButton#actionKey {{
                background-color: {_KEYBOARD_ACTION};
                color: white;
                border: 1px solid {_KEYBOARD_ACTION};
            }}
            QPushButton#actionKey:hover {{
                background-color: {_KEYBOARD_ACTION_HOVER};
                border: 1px solid {_KEYBOARD_ACTION_HOVER};
            }}
            QWidget#keyboardPanel {{
                background-color: {_KEYBOARD_PANEL};
                border-radius: 10px;
            }}
            """
        )
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        panel = QWidget(self)
        panel.setObjectName("keyboardPanel")
        root.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        if self._numeric_only:
            for row in (("7", "8", "9"), ("4", "5", "6"), ("1", "2", "3"), ("-", "0", ".")):
                layout.addLayout(self._row(row))
        else:
            for row in (
                ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0"),
                ("Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"),
                ("A", "S", "D", "F", "G", "H", "J", "K", "L"),
                ("Z", "X", "C", "V", "B", "N", "M"),
            ):
                layout.addLayout(self._row(row))
            layout.addLayout(self._row(("Space",), stretch=True))

        nav = QHBoxLayout()
        nav.setSpacing(8)
        nav.addWidget(self._button("←", self._move_cursor_left, action=True))
        nav.addWidget(self._button("→", self._move_cursor_right, action=True))
        layout.addLayout(nav)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self._button("Backspace", self._backspace, action=True))
        actions.addWidget(self._button("Clear", self._clear, action=True))
        actions.addWidget(self._button("Close", self.close, action=True))
        layout.addLayout(actions)

    def _row(self, labels: tuple[str, ...], *, stretch: bool = False) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for label in labels:
            if label == "Space":
                btn = self._button(label, lambda _checked=False, value=" ": self._append(value))
                btn.setMinimumWidth(220)
            else:
                btn = self._button(label, lambda _checked=False, value=label: self._append(value))
            if stretch:
                row.addStretch(1)
            row.addWidget(btn)
            if stretch:
                row.addStretch(1)
        return row

    def _button(self, label: str, callback, *, action: bool = False) -> QPushButton:
        btn = QPushButton(label, self)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if action:
            btn.setObjectName("actionKey")
        btn.clicked.connect(callback)
        return btn

    def _target_line_edit(self) -> Optional[QLineEdit]:
        if isinstance(self._target, QLineEdit):
            return self._target
        if isinstance(self._target, QAbstractSpinBox):
            return self._target.lineEdit()
        return None

    def _append(self, value: str) -> None:
        line_edit = self._target_line_edit()
        if line_edit is not None:
            line_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            line_edit.insert(value)

    def _backspace(self) -> None:
        line_edit = self._target_line_edit()
        if line_edit is not None:
            line_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            line_edit.backspace()

    def _clear(self) -> None:
        line_edit = self._target_line_edit()
        if line_edit is not None:
            line_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            line_edit.clear()

    def _move_cursor_left(self) -> None:
        line_edit = self._target_line_edit()
        if line_edit is not None:
            line_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            line_edit.setCursorPosition(max(0, line_edit.cursorPosition() - 1))

    def _move_cursor_right(self) -> None:
        line_edit = self._target_line_edit()
        if line_edit is not None:
            line_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            line_edit.setCursorPosition(min(len(line_edit.text()), line_edit.cursorPosition() + 1))


class _KeyboardMixin:
    _numeric_keyboard = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._keyboard_dialog: Optional[_PopupKeyboardDialog] = None
        self._install_trigger_hooks()

    def _keyboard_enabled(self) -> bool:
        return bool(ENABLE_CUSTOM_VIRTUAL_KEYBOARD)

    def _install_trigger_hooks(self) -> None:
        if isinstance(self, QAbstractSpinBox):
            line_edit = self.lineEdit()
            if line_edit is not None:
                line_edit.installEventFilter(self)

    def _show_keyboard(self) -> None:
        if not self._keyboard_enabled():
            return

        parent = self.window() if hasattr(self, "window") else None
        if self._keyboard_dialog is None:
            self._keyboard_dialog = _PopupKeyboardDialog(
                self,
                numeric_only=bool(self._numeric_keyboard),
                parent=parent,
            )

        self._keyboard_dialog.adjustSize()
        self._keyboard_dialog.move(self._keyboard_position())
        self._keyboard_dialog.show()
        self._keyboard_dialog.raise_()

    def _keyboard_position(self) -> QPoint:
        if self._keyboard_dialog is None:
            return self.mapToGlobal(QPoint(0, self.height() + 6))

        margin = 6
        keyboard_size = self._keyboard_dialog.sizeHint()
        field_top_left = self.mapToGlobal(QPoint(0, 0))
        field_bottom_left = self.mapToGlobal(QPoint(0, self.height()))
        desired_x = field_top_left.x()
        desired_y = field_bottom_left.y() + margin

        screen = self.screen() or (self.window().windowHandle().screen() if self.window().windowHandle() else None)
        available: QRect | None = screen.availableGeometry() if screen is not None else None
        if available is None:
            return QPoint(desired_x, desired_y)

        below_bottom = desired_y + keyboard_size.height()
        above_y = field_top_left.y() - keyboard_size.height() - margin
        if below_bottom > available.bottom() and above_y >= available.top():
            desired_y = above_y

        min_x = available.left() + margin
        max_x = available.right() - keyboard_size.width() - margin
        min_y = available.top() + margin
        max_y = available.bottom() - keyboard_size.height() - margin

        clamped_x = max(min_x, min(desired_x, max_x))
        clamped_y = max(min_y, min(desired_y, max_y))
        return QPoint(clamped_x, clamped_y)

    def _handle_keyboard_mouse_press(self, event: QMouseEvent) -> None:
        self._show_keyboard()
        super().mousePressEvent(event)

    def focusInEvent(self, event) -> None:
        self._show_keyboard()
        super().focusInEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if (
            isinstance(self, QAbstractSpinBox)
            and watched is self.lineEdit()
            and event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.FocusIn)
        ):
            self._show_keyboard()
        return super().eventFilter(watched, event)


class KeyboardLineEdit(_KeyboardMixin, QLineEdit):
    _numeric_keyboard = False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._handle_keyboard_mouse_press(event)


class KeyboardSpinBox(_KeyboardMixin, QSpinBox):
    _numeric_keyboard = True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._handle_keyboard_mouse_press(event)


class KeyboardDoubleSpinBox(_KeyboardMixin, QDoubleSpinBox):
    _numeric_keyboard = True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._handle_keyboard_mouse_press(event)
