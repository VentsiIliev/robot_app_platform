from typing import Optional

import numpy as np
from PyQt6.QtCore import pyqtSignal, Qt, QEvent
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel,
    QListWidget, QPushButton, QTextEdit, QWidget, QSizePolicy,
)

from src.applications.base.i_application_view import IApplicationView

_DARK_BG   = "#1e1e1e"
_PANEL_BG  = "#2a2a2a"
_ACCENT    = "#0078d4"
_TEXT      = "#e0e0e0"
_MUTED     = "#888888"
_BTN_STYLE = (
    "QPushButton {"
    f"  background:{_ACCENT}; color:#fff; border:none;"
    "  border-radius:4px; padding:8px 16px; font-size:13px;"
    "}"
    "QPushButton:hover  { background:#1a8fe8; }"
    "QPushButton:pressed { background:#005fa3; }"
    "QPushButton:disabled { background:#444; color:#777; }"
)
_LIST_STYLE = (
    f"QListWidget {{ background:{_PANEL_BG}; color:{_TEXT}; border:1px solid #444;"
    f"  border-radius:4px; font-size:12px; }}"
    f"QListWidget::item:selected {{ background:{_ACCENT}; }}"
)
_TEXT_STYLE = (
    f"QTextEdit {{ background:{_PANEL_BG}; color:{_TEXT}; border:1px solid #444;"
    f"  border-radius:4px; font-size:12px; font-family:monospace; }}"
)


class ContourMatchingTesterView(IApplicationView):

    load_workpieces_requested = pyqtSignal()
    match_requested           = pyqtSignal()

    def __init__(self, parent=None):
        self._current_frame: Optional[np.ndarray] = None
        super().__init__("ContourMatchingTester", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background:{_DARK_BG}; color:{_TEXT};")

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        root.addWidget(self._build_camera_panel(), stretch=3)
        root.addWidget(self._build_control_panel(), stretch=1)

    # ── Panel builders ────────────────────────────────────────────────────

    def _build_camera_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background:{_PANEL_BG}; border-radius:6px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("Camera Feed")
        header.setStyleSheet(f"color:{_MUTED}; font-size:11px; font-weight:bold;")
        layout.addWidget(header)

        self._feed_label = QLabel("No camera feed")
        self._feed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._feed_label.setStyleSheet(f"color:{_MUTED}; background:#111; border-radius:4px;")
        self._feed_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._feed_label.setMinimumSize(320, 240)
        layout.addWidget(self._feed_label)

        return panel

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background:{_PANEL_BG}; border-radius:6px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # — Workpieces section —
        wp_header = QLabel("Workpieces")
        wp_header.setStyleSheet(f"color:{_MUTED}; font-size:11px; font-weight:bold;")
        layout.addWidget(wp_header)

        self._load_btn = QPushButton("Load Workpieces")
        self._load_btn.setStyleSheet(_BTN_STYLE)
        self._load_btn.clicked.connect(self._on_load_clicked)
        layout.addWidget(self._load_btn)

        self._workpiece_list = QListWidget()
        self._workpiece_list.setStyleSheet(_LIST_STYLE)
        self._workpiece_list.setMaximumHeight(180)
        layout.addWidget(self._workpiece_list)

        # — Matching section —
        match_header = QLabel("Matching")
        match_header.setStyleSheet(f"color:{_MUTED}; font-size:11px; font-weight:bold;")
        layout.addWidget(match_header)

        self._match_btn = QPushButton("Match")
        self._match_btn.setStyleSheet(_BTN_STYLE)
        self._match_btn.clicked.connect(self._on_match_clicked)
        layout.addWidget(self._match_btn)

        results_label = QLabel("Results")
        results_label.setStyleSheet(f"color:{_MUTED}; font-size:11px; font-weight:bold;")
        layout.addWidget(results_label)

        self._results_text = QTextEdit()
        self._results_text.setReadOnly(True)
        self._results_text.setStyleSheet(_TEXT_STYLE)
        self._results_text.setPlaceholderText("Run matching to see results…")
        layout.addWidget(self._results_text, stretch=1)

        return panel

    # ── Inbound setters ───────────────────────────────────────────────────

    def set_camera_frame(self, frame: Optional[np.ndarray]) -> None:
        self._current_frame = frame
        if frame is None:
            self._feed_label.setText("No camera feed")
            return
        rgb = frame[:, :, ::-1].copy()
        h, w, ch = rgb.shape
        qimg = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            self._feed_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self._feed_label.setPixmap(pixmap)

    def set_workpieces(self, workpieces: list) -> None:
        self._workpiece_list.clear()
        for wp in workpieces:
            self._workpiece_list.addItem(getattr(wp, "name", str(wp)))
        self._results_text.clear()

    def set_match_results(self, results: dict, no_match_count: int) -> None:
        wps          = results.get("workpieces", [])
        orientations = results.get("orientations", [])
        confidences  = results.get("mlConfidences", [])

        lines = [
            f"Matched: {len(wps)}   Unmatched: {no_match_count}",
            "─" * 34,
        ]
        for i, (wp, orient) in enumerate(zip(wps, orientations)):
            name = getattr(wp, "name", f"WP {i}")
            conf = confidences[i] if i < len(confidences) else 0.0
            lines.append(f"[{i}]  {name}")
            lines.append(f"     orient = {orient:.1f}°   conf = {conf:.1f}%")

        if not wps:
            lines.append("No matches found.")

        self._results_text.setPlainText("\n".join(lines))

    def set_matching_busy(self, busy: bool) -> None:
        self._match_btn.setEnabled(not busy)
        self._match_btn.setText("Matching…" if busy else "Match")

    # ── Inner forwarders — named methods only, no lambdas ─────────────────

    def _on_load_clicked(self) -> None:
        self.load_workpieces_requested.emit()

    def _on_match_clicked(self) -> None:
        self.match_requested.emit()

    # ── AppWidget hooks ───────────────────────────────────────────────────

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass

