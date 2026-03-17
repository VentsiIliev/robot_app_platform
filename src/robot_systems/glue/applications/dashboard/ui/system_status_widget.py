from __future__ import annotations
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy

_STATE_COLORS = {
    "idle":     ("#6B7280", "#FFFFFF"),   # gray
    "running":  ("#16A34A", "#FFFFFF"),   # green
    "paused":   ("#D97706", "#FFFFFF"),   # amber
    "stopped":  ("#6B7280", "#FFFFFF"),   # gray
    "error":    ("#DC2626", "#FFFFFF"),   # red
    "busy":     ("#D97706", "#FFFFFF"),   # amber
    "unknown":  ("#374151", "#9CA3AF"),   # dark
}

_BADGE_STYLE = (
    "QLabel {{"
    "  background: {bg};"
    "  color: {fg};"
    "  border-radius: 8px;"
    "  padding: 2px 10px;"
    "  font-size: 11px;"
    "  font-weight: 600;"
    "}}"
)

_LABEL_STYLE = (
    "QLabel { color: #9CA3AF; font-size: 11px; font-weight: 500; }"
)

_CONTAINER_STYLE = (
    "QFrame { "
    "  border: 1px solid #2D3748; "
    "  border-radius: 10px; "
    "  background: #1A202C; "
    "}"
)


class SystemStatusWidget(QFrame):
    """
    Aux-grid panel — shows currently active process and vision_service busy state.
    Updated via set_process_state() / set_system_state() from the controller.
    No broker knowledge — pure display widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_CONTAINER_STYLE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._setup_ui()

    def _setup_ui(self) -> None:
        grid = QGridLayout(self)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setSpacing(6)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        # Row 0 — process state
        self._process_label = QLabel()
        self._process_label.setStyleSheet(_LABEL_STYLE)
        self._process_badge = QLabel("idle")
        self._current_process_state = "idle"
        self._apply_badge(self._process_badge, self._current_process_state)

        # Row 1 — active process id
        self._active_label = QLabel()
        self._active_label.setStyleSheet(_LABEL_STYLE)
        self._process_id_badge = QLabel("—")
        self._process_id_badge.setStyleSheet(
            "QLabel { color: #E2E8F0; font-size: 11px; padding: 2px 10px; }"
        )

        # Row 2 — vision_service busy state
        self._system_label = QLabel()
        self._system_label.setStyleSheet(_LABEL_STYLE)
        self._system_badge = QLabel("idle")
        self._current_system_state = "idle"
        self._apply_badge(self._system_badge, self._current_system_state)

        # Row 3 — service warning
        self._warning_label = QLabel()
        self._warning_label.setStyleSheet(_LABEL_STYLE)
        self._warning_badge = QLabel("")
        self._warning_badge.setWordWrap(True)
        self._warning_badge.setStyleSheet(
            "QLabel { color: #F87171; font-size: 11px; padding: 2px 10px; }"
        )
        self._warning_badge.setVisible(False)

        self._retranslate_static_labels()
        self._refresh_badges()

        for lbl in (self._process_label, self._active_label, self._system_label, self._warning_label):
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # replace the existing addWidget block:
        grid.addWidget(self._process_label,             0, 0)
        grid.addWidget(self._process_badge,    0, 1)
        grid.addWidget(self._active_label,               1, 0)
        grid.addWidget(self._process_id_badge, 1, 1)
        grid.addWidget(self._system_label,              2, 0)
        grid.addWidget(self._system_badge,     2, 1)
        grid.addWidget(self._warning_label,             3, 0)
        grid.addWidget(self._warning_badge,    3, 1)

        for badge in (self._process_badge, self._process_id_badge, self._system_badge):
            badge.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    # ── Public API ────────────────────────────────────────────────────

    def set_process_state(self, state: str) -> None:
        self._current_process_state = state
        self._apply_badge(self._process_badge, state)
        self._process_badge.setText(self._translate_state(state))

    def set_active_process(self, process_id: str) -> None:
        self._process_id_badge.setText(process_id or "—")

    def set_system_state(self, state: str) -> None:
        self._current_system_state = state
        self._apply_badge(self._system_badge, state)
        self._system_badge.setText(self._translate_state(state))

    def set_warning(self, message: str) -> None:
        if message:
            self._warning_badge.setText(message)
            self._warning_badge.setVisible(True)
        else:
            self._warning_badge.setText("")
            self._warning_badge.setVisible(False)

    # ── Internal ──────────────────────────────────────────────────────

    @staticmethod
    def _apply_badge(label: QLabel, state: str) -> None:
        bg, fg = _STATE_COLORS.get(state.lower(), _STATE_COLORS["unknown"])
        label.setStyleSheet(_BADGE_STYLE.format(bg=bg, fg=fg))

    def _translate_state(self, state: str) -> str:
        state_map = {
            "idle": self.tr("Idle"),
            "running": self.tr("Running"),
            "paused": self.tr("Paused"),
            "stopped": self.tr("Stopped"),
            "error": self.tr("Error"),
            "busy": self.tr("Busy"),
            "unknown": self.tr("Unknown"),
        }
        return state_map.get((state or "").lower(), self.tr("Unknown"))

    def _retranslate_static_labels(self) -> None:
        self._process_label.setText(self.tr("Process"))
        self._active_label.setText(self.tr("Active"))
        self._system_label.setText(self.tr("System"))
        self._warning_label.setText(self.tr("Warning"))

    def _refresh_badges(self) -> None:
        self._process_badge.setText(self._translate_state(self._current_process_state))
        self._system_badge.setText(self._translate_state(self._current_system_state))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate_static_labels()
            self._refresh_badges()
        super().changeEvent(event)
