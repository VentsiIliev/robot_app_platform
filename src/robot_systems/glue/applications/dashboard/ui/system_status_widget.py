from __future__ import annotations
from PyQt6.QtCore import Qt
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
    Aux-grid panel — shows currently active process and system busy state.
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
        proc_label = QLabel("Process")
        proc_label.setStyleSheet(_LABEL_STYLE)
        self._process_badge = QLabel("idle")
        self._apply_badge(self._process_badge, "idle")

        # Row 1 — active process id
        id_label = QLabel("Active")
        id_label.setStyleSheet(_LABEL_STYLE)
        self._process_id_badge = QLabel("—")
        self._process_id_badge.setStyleSheet(
            "QLabel { color: #E2E8F0; font-size: 11px; padding: 2px 10px; }"
        )

        # Row 2 — system busy state
        sys_label = QLabel("System")
        sys_label.setStyleSheet(_LABEL_STYLE)
        self._system_badge = QLabel("idle")
        self._apply_badge(self._system_badge, "idle")

        # Row 3 — service warning
        warn_label = QLabel("Warning")
        warn_label.setStyleSheet(_LABEL_STYLE)
        self._warning_badge = QLabel("")
        self._warning_badge.setWordWrap(True)
        self._warning_badge.setStyleSheet(
            "QLabel { color: #F87171; font-size: 11px; padding: 2px 10px; }"
        )
        self._warning_badge.setVisible(False)

        for lbl in (proc_label, id_label, sys_label, warn_label):
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # replace the existing addWidget block:
        grid.addWidget(proc_label,             0, 0)
        grid.addWidget(self._process_badge,    0, 1)
        grid.addWidget(id_label,               1, 0)
        grid.addWidget(self._process_id_badge, 1, 1)
        grid.addWidget(sys_label,              2, 0)
        grid.addWidget(self._system_badge,     2, 1)
        grid.addWidget(warn_label,             3, 0)
        grid.addWidget(self._warning_badge,    3, 1)


        for lbl in (proc_label, id_label, sys_label):
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        for badge in (self._process_badge, self._process_id_badge, self._system_badge):
            badge.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        grid.addWidget(proc_label,             0, 0)
        grid.addWidget(self._process_badge,    0, 1)
        grid.addWidget(id_label,               1, 0)
        grid.addWidget(self._process_id_badge, 1, 1)
        grid.addWidget(sys_label,              2, 0)
        grid.addWidget(self._system_badge,     2, 1)

    # ── Public API ────────────────────────────────────────────────────

    def set_process_state(self, state: str) -> None:
        self._apply_badge(self._process_badge, state)
        self._process_badge.setText(state.upper())

    def set_active_process(self, process_id: str) -> None:
        self._process_id_badge.setText(process_id or "—")

    def set_system_state(self, state: str) -> None:
        self._apply_badge(self._system_badge, state)
        self._system_badge.setText(state.upper())

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