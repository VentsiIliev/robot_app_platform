from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QEvent, QMargins, QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
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
_DOCK_MARGIN = 8
_FIELD_MARGIN = 12
_ACTIVE_KEYBOARD_OWNER: Optional["_KeyboardMixin"] = None


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

    def closeEvent(self, event) -> None:
        self._restore_target_scroll_space()
        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        self._restore_target_scroll_space()
        super().hideEvent(event)

    def _restore_target_scroll_space(self) -> None:
        widget: Optional[QWidget] = self._target
        while widget is not None:
            notify = getattr(widget, "_on_virtual_keyboard_hidden", None)
            if callable(notify):
                notify()
                break
            widget = widget.parentWidget()

        restore = getattr(self._target, "_restore_keyboard_adjustments", None)
        if not callable(restore):
            restore = getattr(self._target, "_restore_keyboard_scroll_space", None)
        if callable(restore):
            restore()

    def dock_to_target_window(self) -> None:
        window = self._dock_window()
        if window is None:
            return

        window_top_left = window.mapToGlobal(QPoint(0, 0))
        keyboard_height = self.sizeHint().height()
        keyboard_width = max(320, window.width() - (_DOCK_MARGIN * 2))
        keyboard_x = window_top_left.x() + _DOCK_MARGIN
        keyboard_y = window_top_left.y() + window.height() - keyboard_height - _DOCK_MARGIN

        self.setFixedWidth(keyboard_width)
        self.move(QPoint(keyboard_x, keyboard_y))

    def keyboard_rect_global(self) -> QRect:
        return QRect(self.pos(), self.size())

    def _dock_window(self) -> Optional[QWidget]:
        widget: Optional[QWidget] = self._target
        while widget is not None:
            explicit_window = getattr(widget, "_virtual_keyboard_dock_window", None)
            if isinstance(explicit_window, QWidget):
                return explicit_window
            widget = widget.parentWidget()

        window = self._target.window()
        while window is not None:
            explicit_window = getattr(window, "_virtual_keyboard_dock_window", None)
            if isinstance(explicit_window, QWidget):
                return explicit_window

            parent = window.parentWidget()
            if parent is None and isinstance(window.parent(), QWidget):
                parent = window.parent()
            if parent is None:
                return window

            parent_window = parent.window()
            if parent_window is None or parent_window is window:
                return window

            window = parent_window
        return None

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
        self._keyboard_scroll_area: Optional[QAbstractScrollArea] = None
        self._keyboard_content_layout = None
        self._keyboard_content_margins: Optional[QMargins] = None
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

        self._restore_other_keyboard_owner()
        parent = self.window() if hasattr(self, "window") else None
        if self._keyboard_dialog is None:
            self._keyboard_dialog = _PopupKeyboardDialog(
                self,
                numeric_only=bool(self._numeric_keyboard),
                parent=parent,
            )

        self._keyboard_dialog.adjustSize()
        self._keyboard_dialog.dock_to_target_window()
        self._keyboard_dialog.show()
        self._keyboard_dialog.raise_()
        self._mark_active_keyboard_owner()
        self._notify_keyboard_shown()
        QTimer.singleShot(0, self._position_content_for_keyboard)

    def _notify_keyboard_shown(self) -> None:
        if self._keyboard_dialog is None:
            return

        widget: Optional[QWidget] = self
        while widget is not None:
            notify = getattr(widget, "_on_virtual_keyboard_shown", None)
            if callable(notify):
                notify(self._keyboard_dialog.keyboard_rect_global())
                break
            widget = widget.parentWidget()

    def _mark_active_keyboard_owner(self) -> None:
        global _ACTIVE_KEYBOARD_OWNER
        _ACTIVE_KEYBOARD_OWNER = self

    def _restore_other_keyboard_owner(self) -> None:
        global _ACTIVE_KEYBOARD_OWNER
        if _ACTIVE_KEYBOARD_OWNER is not None and _ACTIVE_KEYBOARD_OWNER is not self:
            _ACTIVE_KEYBOARD_OWNER._restore_keyboard_adjustments()
            if _ACTIVE_KEYBOARD_OWNER._keyboard_dialog is not None:
                _ACTIVE_KEYBOARD_OWNER._keyboard_dialog.hide()
            _ACTIVE_KEYBOARD_OWNER = None

    def _position_content_for_keyboard(self) -> None:
        self._reserve_keyboard_scroll_space()
        QTimer.singleShot(0, self._scroll_field_above_keyboard)

    def _nearest_scroll_area(self) -> Optional[QAbstractScrollArea]:
        field_window = self.window()
        explicit_scroll = getattr(field_window, "_keyboard_scroll_area", None)
        if isinstance(explicit_scroll, QAbstractScrollArea):
            return explicit_scroll

        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QAbstractScrollArea):
                return parent
            parent = parent.parentWidget()
        return None

    def _reserve_keyboard_scroll_space(self) -> None:
        self._restore_keyboard_scroll_space()
        if self._keyboard_dialog is None:
            return
        if self._has_keyboard_layout_handler():
            return

        scroll_area = self._nearest_scroll_area()
        if scroll_area is None:
            return

        dock_window = self._keyboard_dialog._dock_window()
        if dock_window is not None and self.window() is not dock_window:
            return

        viewport = scroll_area.viewport()
        viewport_bottom = viewport.mapToGlobal(QPoint(0, viewport.height())).y()
        keyboard_top = self._keyboard_dialog.keyboard_rect_global().top()
        overlap = viewport_bottom - keyboard_top
        if overlap <= 0:
            return

        content = scroll_area.widget()
        layout = content.layout() if content is not None else None
        if layout is None:
            return

        self._keyboard_content_layout = layout
        self._keyboard_content_margins = layout.contentsMargins()
        layout.setContentsMargins(
            self._keyboard_content_margins.left(),
            self._keyboard_content_margins.top(),
            self._keyboard_content_margins.right(),
            self._keyboard_content_margins.bottom() + overlap + _FIELD_MARGIN,
        )
        layout.invalidate()
        layout.activate()
        content.updateGeometry()
        self._keyboard_scroll_area = scroll_area

    def _has_keyboard_layout_handler(self) -> bool:
        widget = self.parentWidget()
        while widget is not None:
            if callable(getattr(widget, "_on_virtual_keyboard_shown", None)):
                return True
            widget = widget.parentWidget()
        return False

    def _restore_keyboard_scroll_space(self) -> None:
        self._keyboard_scroll_area = None
        if self._keyboard_content_layout is not None and self._keyboard_content_margins is not None:
            self._keyboard_content_layout.setContentsMargins(self._keyboard_content_margins)
        self._keyboard_content_layout = None
        self._keyboard_content_margins = None

    def _restore_keyboard_adjustments(self) -> None:
        global _ACTIVE_KEYBOARD_OWNER
        self._restore_keyboard_scroll_space()
        if _ACTIVE_KEYBOARD_OWNER is self:
            _ACTIVE_KEYBOARD_OWNER = None

    def _scroll_field_above_keyboard(self) -> None:
        if self._keyboard_dialog is None or not self._keyboard_dialog.isVisible():
            return

        scroll_area = self._nearest_scroll_area()
        if scroll_area is None:
            return

        if isinstance(scroll_area, QScrollArea):
            scroll_area.ensureWidgetVisible(self, _FIELD_MARGIN, _FIELD_MARGIN)
            QTimer.singleShot(
                50,
                lambda: scroll_area.ensureWidgetVisible(self, _FIELD_MARGIN, _FIELD_MARGIN),
            )

        keyboard_top = self._keyboard_dialog.keyboard_rect_global().top()
        field_bottom = self.mapToGlobal(QPoint(0, self.height())).y()
        if field_bottom >= keyboard_top:
            bar = scroll_area.verticalScrollBar()
            bar.setValue(bar.value() + field_bottom - keyboard_top + _FIELD_MARGIN)

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
