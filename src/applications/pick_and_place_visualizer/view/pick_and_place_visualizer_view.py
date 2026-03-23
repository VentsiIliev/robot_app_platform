from typing import List, Optional

import cv2
import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QWidget, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QSplitter, QFrame,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, BG_COLOR, BORDER, LABEL_STYLE, TEXT_COLOR, PRIMARY,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.pick_and_place_visualizer.service.i_pick_and_place_visualizer_service import (
    SimResult, MatchedItem,
)
from src.applications.pick_and_place_visualizer.view.plane_canvas import PlaneCanvas

_TABLE_STYLE = """
QTableWidget {
    background: white; border: 1px solid #E0E0E0;
    border-radius: 4px; gridline-color: #F0F0F0; font-size: 9pt;
}
QHeaderView::section {
    background: #EDE7F6; color: #1A1A2E; font-weight: bold;
    font-size: 9pt; padding: 5px 4px; border: none;
    border-bottom: 1px solid #D0C8E0;
}
QTableWidget::item { padding: 4px; }
QTableWidget::item:selected { background: rgba(144,91,169,0.15); }
"""

_LOG_STYLE = """
QPlainTextEdit {
    background: #1E1E1E; color: #D4D4D4;
    font-family: monospace; font-size: 9pt;
    border: 1px solid #333; border-radius: 4px;
}
"""

_STATE_RUNNING = "color: #2E7D32; font-size: 9pt; font-weight: bold; background: transparent;"
_STATE_STOPPED = "color: #888;    font-size: 9pt; font-weight: bold; background: transparent;"
_STATE_ERROR   = "color: #C62828; font-size: 9pt; font-weight: bold; background: transparent;"

_MATCH_COLS = ["WP Name", "ID", "Gripper", "Orientation"]
_SMALL_TOGGLE_STYLE = """
QPushButton {
    background: white;
    color: #1A1A2E;
    border: 1px solid #CFCFCF;
    border-radius: 4px;
    font-size: 9pt;
    padding: 4px 10px;
}
QPushButton:checked {
    background: #E6F4EA;
    border-color: #2E7D32;
    color: #1E4620;
}
QPushButton:hover {
    background: #F6F6F6;
}
"""


class PickAndPlaceVisualizerView(IApplicationView):

    SHOW_JOG_WIDGET = True
    JOG_FRAME_SELECTOR_ENABLED = True

    simulation_toggled = pyqtSignal(bool)
    step_mode_toggled = pyqtSignal(bool)
    start_process_requested = pyqtSignal()
    stop_process_requested  = pyqtSignal()
    pause_process_requested = pyqtSignal()
    reset_process_requested = pyqtSignal()
    step_process_requested  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("PickAndPlaceVisualizer", parent)
        self._crosshair_enabled = False

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Top toolbar ──
        root.addLayout(self._build_toolbar())

        # ── Main splitter: left camera | right plane ──
        top_split = QSplitter(Qt.Orientation.Horizontal)
        top_split.addWidget(self._build_camera_panel())
        top_split.addWidget(self._build_plane_panel())
        top_split.setStretchFactor(0, 3)
        top_split.setStretchFactor(1, 2)
        top_split.setSizes([600, 400])

        # ── Bottom splitter: table | logs ──
        bot_split = QSplitter(Qt.Orientation.Horizontal)
        bot_split.addWidget(self._build_match_panel())
        bot_split.addWidget(self._build_log_panel())
        bot_split.setStretchFactor(0, 1)
        bot_split.setStretchFactor(1, 1)

        vert = QSplitter(Qt.Orientation.Vertical)
        vert.addWidget(top_split)
        vert.addWidget(bot_split)
        vert.setStretchFactor(0, 3)
        vert.setStretchFactor(1, 2)
        vert.setSizes([420, 280])
        root.addWidget(vert)

    # ── Builders ──────────────────────────────────────────────────────

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        lbl = QLabel("Pick & Place Visualizer")
        lbl.setStyleSheet(
            f"font-size: 13pt; font-weight: bold; color: {TEXT_COLOR}; background: transparent;"
        )
        row.addWidget(lbl)
        row.addStretch()

        self._state_label = QLabel("● IDLE")
        self._state_label.setStyleSheet(_STATE_STOPPED)
        row.addWidget(self._state_label)

        # ── separator ──
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {BORDER};")
        row.addWidget(sep)

        # ── Live process controls ──
        self._start_btn = QPushButton("▶ Start")
        self._start_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._start_btn.clicked.connect(self._on_start_clicked)
        row.addWidget(self._start_btn)

        self._pause_btn = QPushButton("⏸ Pause")
        self._pause_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._on_pause_clicked)
        row.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("■ Stop")
        self._stop_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        row.addWidget(self._stop_btn)

        self._reset_btn = QPushButton("↺ Reset")
        self._reset_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._reset_btn.setEnabled(False)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        row.addWidget(self._reset_btn)

        # ── separator ──
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet(f"color: {BORDER};")
        row.addWidget(sep2)

        # ── Simulation mode toggle ──
        self._sim_toggle_btn = QPushButton("Simulation: OFF")
        self._sim_toggle_btn.setCheckable(True)
        self._sim_toggle_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._sim_toggle_btn.toggled.connect(self._on_sim_toggled)
        row.addWidget(self._sim_toggle_btn)

        self._step_mode_btn = QPushButton("Step Mode: OFF")
        self._step_mode_btn.setCheckable(True)
        self._step_mode_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._step_mode_btn.toggled.connect(self._on_step_mode_toggled)
        row.addWidget(self._step_mode_btn)

        self._step_btn = QPushButton("Step")
        self._step_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._step_btn.setEnabled(False)
        self._step_btn.clicked.connect(self._on_step_clicked)
        row.addWidget(self._step_btn)

        return row

    def _build_camera_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border: 1px solid {BORDER}; border-radius: 6px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        hdr_row = QHBoxLayout()
        hdr = QLabel("Camera Feed")
        hdr.setStyleSheet(LABEL_STYLE)
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        self._crosshair_btn = QPushButton("Crosshair")
        self._crosshair_btn.setCheckable(True)
        self._crosshair_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._crosshair_btn.setStyleSheet(_SMALL_TOGGLE_STYLE)
        self._crosshair_btn.toggled.connect(self._on_crosshair_toggled)
        hdr_row.addWidget(self._crosshair_btn)
        layout.addLayout(hdr_row)

        self._feed_label = QLabel("No feed")
        self._feed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._feed_label.setStyleSheet(
            f"color: #888; background: #F0F0F0; border: 1px solid {BORDER}; border-radius: 4px;"
        )
        self._feed_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._feed_label.setMinimumSize(320, 220)
        layout.addWidget(self._feed_label)
        return panel

    def _build_plane_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border: 1px solid {BORDER}; border-radius: 6px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        hdr = QLabel("Plane View")
        hdr.setStyleSheet(LABEL_STYLE)
        layout.addWidget(hdr)

        self._plane_canvas = PlaneCanvas()
        self._plane_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._plane_canvas)
        return panel

    def _build_match_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border: 1px solid {BORDER}; border-radius: 6px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        hdr_row = QHBoxLayout()
        hdr = QLabel("Matched Workpieces")
        hdr.setStyleSheet(LABEL_STYLE)
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet("color: #888; font-size: 9pt; background: transparent;")
        hdr_row.addWidget(self._summary_label)
        layout.addLayout(hdr_row)

        self._step_status_label = QLabel("Current step: -")
        self._step_status_label.setStyleSheet("color: #666; font-size: 9pt; background: transparent;")
        layout.addWidget(self._step_status_label)

        self._match_table = QTableWidget(0, len(_MATCH_COLS))
        self._match_table.setHorizontalHeaderLabels(_MATCH_COLS)
        self._match_table.setStyleSheet(_TABLE_STYLE)
        self._match_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._match_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._match_table.verticalHeader().setVisible(False)
        hdr_h = self._match_table.horizontalHeader()
        hdr_h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr_h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr_h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr_h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._match_table)
        return panel

    def _build_log_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border: 1px solid {BORDER}; border-radius: 6px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        hdr_row = QHBoxLayout()
        hdr = QLabel("Log")
        hdr.setStyleSheet(LABEL_STYLE)
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(24)
        clear_btn.setStyleSheet(
            f"QPushButton {{ background: white; color: {PRIMARY}; border: 1px solid {PRIMARY};"
            f" border-radius: 3px; font-size: 9pt; padding: 0 8px; }}"
            f"QPushButton:hover {{ background: #EDE7F6; }}"
        )
        clear_btn.clicked.connect(self._on_clear_log)
        hdr_row.addWidget(clear_btn)
        layout.addLayout(hdr_row)

        self._log_text = QPlainTextEdit()
        self._log_text.setStyleSheet(_LOG_STYLE)
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumBlockCount(500)
        layout.addWidget(self._log_text)
        return panel

    # ── Inbound setters ───────────────────────────────────────────────

    def update_camera_frame(self, frame: np.ndarray) -> None:
        display_frame = frame.copy()
        if self._crosshair_enabled:
            height, width = display_frame.shape[:2]
            cx = width // 2
            cy = height // 2
            cv2.line(display_frame, (0, cy), (width - 1, cy), (0, 255, 0), 1)
            cv2.line(display_frame, (cx, 0), (cx, height - 1), (0, 255, 0), 1)

        rgb  = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        px   = QPixmap.fromImage(qimg).scaled(
            self._feed_label.width(), self._feed_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._feed_label.setPixmap(px)

    def set_matched_items(self, items: List[MatchedItem]) -> None:
        self._populate_table(items)
        n = len(items)
        self._summary_label.setText(f"✓ {n} matched" if n else "No matches")
        self._summary_label.setStyleSheet(
            ("color: #2E7D32;" if n else "color: #888;") + " font-size: 9pt; background: transparent;"
        )

    def set_simulation_result(self, result: SimResult) -> None:
        self._populate_table(result.matched)
        self._plane_canvas.set_placed(result.placements)

        if result.error:
            self._summary_label.setText(f"✗  {result.error}")
            self._summary_label.setStyleSheet("color: #C62828; font-size: 9pt; background: transparent;")
        elif result.matched:
            n = len(result.matched)
            u = result.unmatched_count
            self._summary_label.setText(
                f"✓ {n} matched" + (f"  ✗ {u} unmatched" if u else "")
            )
            self._summary_label.setStyleSheet(
                "color: #2E7D32; font-size: 9pt; background: transparent;"
            )
        else:
            self._summary_label.setText("No matches")
            self._summary_label.setStyleSheet("color: #888; font-size: 9pt; background: transparent;")

    def set_plane_bounds(self, x_min, x_max, y_min, y_max, spacing) -> None:
        self._plane_canvas.set_bounds(x_min, x_max, y_min, y_max, spacing)

    def set_process_state(self, state: str) -> None:
        styles = {
            "running": (_STATE_RUNNING, "● RUNNING"),
            "paused": (_STATE_STOPPED, "⏸ PAUSED"),
            "error": (_STATE_ERROR, "✗ ERROR"),
            "stopped": (_STATE_STOPPED, "■ STOPPED"),
            "idle": (_STATE_STOPPED, "● IDLE"),
        }
        style, text = styles.get(state.lower(), (_STATE_STOPPED, f"● {state.upper()}"))
        self._state_label.setStyleSheet(style)
        self._state_label.setText(text)

        running = state.lower() == "running"
        paused = state.lower() == "paused"
        error = state.lower() == "error"
        idle_or_stopped = state.lower() in ("idle", "stopped")

        self._start_btn.setEnabled(idle_or_stopped or paused or error)
        self._pause_btn.setEnabled(running)
        self._stop_btn.setEnabled(running or paused)
        self._reset_btn.setEnabled(error)
        self._step_btn.setEnabled(self._step_mode_btn.isChecked() and running)

    def set_step_mode(self, enabled: bool) -> None:
        self._step_mode_btn.blockSignals(True)
        self._step_mode_btn.setChecked(enabled)
        self._step_mode_btn.setText("Step Mode: ON" if enabled else "Step Mode: OFF")
        self._step_mode_btn.blockSignals(False)
        self._step_btn.setEnabled(enabled and self._state_label.text() == "● RUNNING")

    def set_step_status(
        self,
        checkpoint: Optional[str],
        waiting: bool,
        step_budget: int,
        current_workpiece: Optional[str] = None,
    ) -> None:
        checkpoint_text = checkpoint or "-"
        waiting_text = "waiting" if waiting else "ready"
        workpiece_text = f" | workpiece: {current_workpiece}" if current_workpiece else ""
        self._step_status_label.setText(
            f"Current step: {checkpoint_text} | {waiting_text} | queued: {step_budget}{workpiece_text}"
        )

    def _on_start_clicked(self):  self.start_process_requested.emit()
    def _on_pause_clicked(self):  self.pause_process_requested.emit()
    def _on_stop_clicked(self):   self.stop_process_requested.emit()
    def _on_reset_clicked(self):  self.reset_process_requested.emit()
    def _on_step_clicked(self):   self.step_process_requested.emit()

    def add_placed_item(self, item) -> None:
        self._plane_canvas.add_item(item)

    def reset_plane(self) -> None:
        self._plane_canvas.clear()

    def append_log(self, text: str) -> None:
        self._log_text.appendPlainText(text)

    def set_busy(self, busy: bool) -> None:
        pass  # no longer used

    # ── Private ───────────────────────────────────────────────────────

    def _populate_table(self, items: List[MatchedItem]) -> None:
        self._match_table.clearSpans()
        self._match_table.setRowCount(len(items))
        colors = ["#E3F2FD", "#E8F5E9", "#FFF9C4", "#FCE4EC", "#F3E5F5"]
        for i, item in enumerate(items):
            color = QColor(colors[i % len(colors)])
            for col, text in enumerate([
                item.workpiece_name,
                item.workpiece_id,
                f"G{item.gripper_id}",
                f"{item.orientation:.1f}°",
            ]):
                cell = QTableWidgetItem(text)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setBackground(color)
                self._match_table.setItem(i, col, cell)

        if not items:
            self._match_table.setRowCount(1)
            cell = QTableWidgetItem("No matches")
            cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setForeground(QColor("#888"))
            self._match_table.setItem(0, 0, cell)
            self._match_table.setSpan(0, 0, 1, len(_MATCH_COLS))

    def _on_sim_toggled(self, checked: bool) -> None:
        self._sim_toggle_btn.setText("Simulation: ON" if checked else "Simulation: OFF")
        self.simulation_toggled.emit(checked)

    def _on_step_mode_toggled(self, checked: bool) -> None:
        self._step_mode_btn.setText("Step Mode: ON" if checked else "Step Mode: OFF")
        self._step_btn.setEnabled(checked and self._state_label.text() == "● RUNNING")
        self.step_mode_toggled.emit(checked)

    def _on_clear_log(self) -> None:
        self._log_text.clear()

    def _on_crosshair_toggled(self, checked: bool) -> None:
        self._crosshair_enabled = checked

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass
