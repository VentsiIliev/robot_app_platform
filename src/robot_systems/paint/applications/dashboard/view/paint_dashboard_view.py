from __future__ import annotations

from collections import deque
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.applications.base.i_application_view import IApplicationView
from pl_gui.dashboard.DashboardWidget import DashboardWidget
from pl_gui.settings.settings_view.styles import BG_COLOR, BORDER, PRIMARY, TEXT_COLOR


_MAX_MESSAGE_ROWS = 50
_MESSAGE_SCROLL_MIN_HEIGHT = 60
_MESSAGE_PANEL_STYLE = f"""
QFrame {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
"""
_MESSAGE_TITLE_STYLE = f"""
QLabel {{
    color: {TEXT_COLOR};
    font-size: 11pt;
    font-weight: bold;
    background: transparent;
    border: none;
}}
"""
_MESSAGE_EMPTY_STYLE = """
QLabel {
    color: #777777;
    font-size: 10pt;
    background: transparent;
    border: none;
}
"""
_MESSAGE_ROW_STYLE = """
QLabel {
    color: #202124;
    font-size: 10pt;
    background: transparent;
    border: none;
    padding: 2px 0;
}
"""
_MESSAGE_WARNING_STYLE = """
QLabel {
    color: #8A4B00;
    font-size: 10pt;
    font-weight: bold;
    background: transparent;
    border: none;
    padding: 2px 0;
}
"""
_MESSAGE_INFO_STYLE = f"""
QLabel {{
    color: {PRIMARY};
    font-size: 10pt;
    font-weight: bold;
    background: transparent;
    border: none;
    padding: 2px 0;
}}
"""


class PaintDashboardView(IApplicationView):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    action_requested = pyqtSignal(str)

    def __init__(self, config, action_buttons: list, cards: list, parent=None):
        self._config = config
        self._action_buttons = action_buttons
        self._cards_input = cards
        self._cards_by_id = self._index_cards_by_id(cards)
        self._last_card_states = {}
        self._last_state_signature = None
        self._messages = deque(maxlen=_MAX_MESSAGE_ROWS)
        self._message_rows: list[QLabel] = []
        self._message_empty_label: QLabel | None = None
        self._message_panel: QFrame | None = None
        self._message_scroll: QScrollArea | None = None
        super().__init__("PaintDashboard", parent)

    @staticmethod
    def _index_cards_by_id(cards: list) -> dict[int, object]:
        indexed = {}
        for item in cards or []:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            widget, card_id = item[0], item[1]
            indexed[card_id] = widget
        return indexed

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._dashboard = DashboardWidget(
            config=self._config,
            action_buttons=self._action_buttons,
            cards=self._cards_input,
        )
        layout.addWidget(self._dashboard)
        self._dashboard.setStyleSheet(f"background-color: {BG_COLOR};")
        self._align_preview_and_card_columns()
        self._install_message_panel()
        self._move_reset_below_cards()
        self._expand_process_controls()

        self._dashboard.start_requested.connect(self.start_requested)
        self._dashboard.stop_requested.connect(self.stop_requested)
        self._dashboard.pause_requested.connect(self.pause_requested)
        self._dashboard.action_requested.connect(self._on_inner_action)

    def _align_preview_and_card_columns(self) -> None:
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            preview_container = top_section.itemAt(0).widget()
            preview_container.setStyleSheet(f"background-color: {BG_COLOR};")
            aux_grid = preview_container.layout().itemAt(1).widget()
            aux_grid.setStyleSheet(f"background-color: {BG_COLOR};")
            side_panel = top_section.itemAt(1).widget()
            if side_panel is not None:
                side_panel.setStyleSheet(f"background-color: {BG_COLOR};")
                side_panel.setFixedHeight(self._config.trajectory_height + 8)
                top_section.setAlignment(side_panel, Qt.AlignmentFlag.AlignTop)
        except Exception:
            pass

    def _install_message_panel(self) -> None:
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            preview_container = top_section.itemAt(0).widget()
            aux_grid = preview_container.layout().itemAt(1).widget()
            layout = aux_grid.layout()
            if layout is None:
                return
            self._clear_layout(layout)
            panel = self._build_message_panel()
            rows = max(1, layout.rowCount())
            cols = max(1, layout.columnCount())
            layout.addWidget(panel, 0, 0, rows, cols)
            for row in range(rows):
                layout.setRowStretch(row, 1)
            for col in range(cols):
                layout.setColumnStretch(col, 1)
            aux_grid.show()
            self._message_panel = panel
            self._render_messages()
        except Exception:
            pass

    def _build_message_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(_MESSAGE_PANEL_STYLE)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        title = QLabel("Messages")
        title.setStyleSheet(_MESSAGE_TITLE_STYLE)
        layout.addWidget(title)

        self._message_scroll = QScrollArea()
        self._message_scroll.setWidgetResizable(True)
        self._message_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._message_scroll.setMinimumHeight(_MESSAGE_SCROLL_MIN_HEIGHT)
        self._message_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        rows_container = QWidget()
        rows_container.setStyleSheet("background: transparent; border: none;")
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(0)

        self._message_empty_label = QLabel("No process messages")
        self._message_empty_label.setStyleSheet(_MESSAGE_EMPTY_STYLE)
        rows_layout.addWidget(self._message_empty_label)

        self._message_rows = []
        for _index in range(_MAX_MESSAGE_ROWS):
            row = QLabel("")
            row.setWordWrap(True)
            row.setStyleSheet(_MESSAGE_ROW_STYLE)
            row.hide()
            rows_layout.addWidget(row)
            self._message_rows.append(row)

        rows_layout.addStretch(1)
        self._message_scroll.setWidget(rows_container)
        layout.addWidget(self._message_scroll, 1)
        return panel

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _move_reset_below_cards(self) -> None:
        try:
            reset_button = self._dashboard._action_buttons.get("reset_errors")
            if reset_button is None:
                return
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            side_panel = top_section.itemAt(1).widget()
            side_layout = side_panel.layout()
            side_layout.addWidget(reset_button, 3, 0)
        except Exception:
            pass

    def _expand_process_controls(self) -> None:
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            bottom_container = main_layout.itemAt(1).widget()
            bottom_layout = bottom_container.layout()
            action_area = bottom_layout.itemAt(0).widget()
            controls = bottom_layout.itemAt(1).widget()
            action_area.hide()
            bottom_layout.setStretchFactor(action_area, 0)
            bottom_layout.setStretchFactor(controls, 1)
        except Exception:
            pass

    def _on_inner_action(self, action_id: str) -> None:
        if action_id == "reset_errors":
            self.reset_requested.emit()
            return
        self.action_requested.emit(action_id)

    def set_trajectory_image(self, image) -> None:
        self._dashboard.set_trajectory_image(image)

    def set_state(self, state: str) -> None:
        _ = state

    def set_mode(self, mode: str) -> None:
        _ = mode

    def set_active_job(self, label: str) -> None:
        _ = label

    def set_notes(self, lines: list[str]) -> None:
        _ = lines

    def set_start_enabled(self, enabled: bool) -> None:
        self._dashboard.set_start_enabled(enabled)

    def set_stop_enabled(self, enabled: bool) -> None:
        self._dashboard.set_stop_enabled(enabled)

    def set_pause_enabled(self, enabled: bool) -> None:
        self._dashboard.set_pause_enabled(enabled)

    def set_pause_label(self, text: str) -> None:
        self._dashboard.set_pause_text(text)

    def set_action_enabled(self, action_id: str, enabled: bool) -> None:
        self._dashboard.set_action_button_enabled(action_id, enabled)

    def show_info(self, title: str, message: str) -> None:
        self._enqueue_message("info", title, message)

    def show_warning(self, title: str, message: str) -> None:
        self._enqueue_message("warning", title, message)

    def _enqueue_message(self, level: str, title: str, message: str) -> None:
        clean_title = str(title or "").strip()
        clean_message = str(message or "").strip()
        if not clean_title and not clean_message:
            return
        self._messages.append(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": str(level or "info").strip().lower(),
                "title": clean_title,
                "message": clean_message,
            }
        )
        self._render_messages()

    def _render_messages(self) -> None:
        if self._message_empty_label is None or not self._message_rows:
            return

        messages = list(self._messages)
        self._message_empty_label.setVisible(not messages)
        for index, row in enumerate(self._message_rows):
            if index >= len(messages):
                row.clear()
                row.hide()
                continue
            item = messages[index]
            row.setText(self._format_message(item))
            row.setStyleSheet(
                _MESSAGE_WARNING_STYLE
                if item["level"] == "warning"
                else _MESSAGE_INFO_STYLE
                if item["level"] == "info"
                else _MESSAGE_ROW_STYLE
            )
            row.show()

        QTimer.singleShot(0, self._scroll_messages_to_bottom)

    def _scroll_messages_to_bottom(self) -> None:
        if self._message_scroll is None:
            return
        bar = self._message_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    @staticmethod
    def _format_message(item: dict) -> str:
        title = str(item.get("title") or "").strip()
        message = str(item.get("message") or "").strip()
        if title and message:
            body = f"{title}: {message}"
        else:
            body = title or message
        return f"{item.get('time', '')}  {body}".strip()

    def show_debug_plot(self, title: str, image_path: str, message: str = "") -> None:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.show_warning(title, f"Could not load plot image:\n{image_path}")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(1200, 800)

        layout = QVBoxLayout(dialog)
        if message:
            message_label = QLabel(message)
            message_label.setWordWrap(True)
            layout.addWidget(message_label)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setPixmap(pixmap)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(image_label)
        layout.addWidget(scroll, 1)

        dialog.exec()

    def apply_dashboard_state(self, state) -> None:
        signature = self._state_signature(state)
        if self._last_state_signature == signature:
            return
        self._last_state_signature = signature
        self.set_state(state.process_state)
        self.set_mode(state.mode_label)
        self.set_active_job(state.active_job_label)
        self.set_notes(state.status_lines)
        self._apply_card_states(getattr(state, "card_states", {}))
        self.set_start_enabled(state.can_start)
        self.set_stop_enabled(state.can_stop)
        self.set_pause_enabled(state.can_pause)
        self.set_pause_label(state.pause_label)

    @staticmethod
    def _state_signature(state) -> tuple:
        card_states = getattr(state, "card_states", {}) or {}
        return (
            getattr(state, "process_state", None),
            getattr(state, "mode_label", None),
            getattr(state, "active_job_label", None),
            tuple(getattr(state, "status_lines", []) or []),
            tuple(
                sorted(
                    (
                        card_id,
                        getattr(card_state, "title", ""),
                        getattr(card_state, "value", ""),
                        getattr(card_state, "note", ""),
                    )
                    for card_id, card_state in card_states.items()
                )
            ),
            getattr(state, "can_start", None),
            getattr(state, "can_stop", None),
            getattr(state, "can_pause", None),
            getattr(state, "pause_label", None),
        )

    def _apply_card_states(self, card_states: dict) -> None:
        for card_id, card_state in (card_states or {}).items():
            if self._last_card_states.get(card_id) == card_state:
                continue
            card = self._cards_by_id.get(card_id)
            set_content = getattr(card, "set_content", None)
            if not callable(set_content):
                continue
            set_content(
                getattr(card_state, "title", ""),
                getattr(card_state, "value", ""),
                getattr(card_state, "note", ""),
            )
            self._last_card_states[card_id] = card_state

    def clean_up(self) -> None:
        pass
