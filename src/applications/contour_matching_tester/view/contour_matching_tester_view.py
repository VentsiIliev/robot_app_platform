from typing import Optional

import cv2
import numpy as np
from PyQt6.QtCore import pyqtSignal, Qt, QEvent
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QFrame,
    QListWidget, QPushButton, QWidget, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, BG_COLOR, BORDER, LABEL_STYLE, TEXT_COLOR,
    PRIMARY, PRIMARY_LIGHT,
)
from pl_gui.utils.utils_widgets.camera_view import CameraView
from pl_gui.utils.utils_widgets.table_helpers import make_table
from src.applications.base.app_styles import (
    compact_button_style,
    emphasis_text_style,
    list_style,
    muted_text_style,
    panel_style,
    table_style,
)
from src.applications.base.i_application_view import IApplicationView

_LIST_STYLE = list_style()
_TABLE_STYLE = table_style()

_CAPTURE_BTN_STYLE = compact_button_style(variant="secondary")
_CAPTURE_ACTIVE_BTN_STYLE = compact_button_style(variant="primary")

_STATUS_LIVE_STYLE     = emphasis_text_style(color="#2E7D32")
_STATUS_CAPTURED_STYLE = emphasis_text_style(color="#905BA9")

_SUMMARY_OK_STYLE   = emphasis_text_style(color="#2E7D32", size_pt=11.0)
_SUMMARY_WARN_STYLE = emphasis_text_style(color="#C62828", size_pt=11.0)
_SUMMARY_IDLE_STYLE = muted_text_style(color="#888", size_pt=10.0)

_THUMB_IDLE_STYLE   = muted_text_style(color="#aaa")
_THUMB_NAME_STYLE   = emphasis_text_style(color=TEXT_COLOR)

_COLOR_HIGH = QColor("#E8F5E9")
_COLOR_MED  = QColor("#FFF9C4")
_COLOR_LOW  = QColor("#FFEBEE")

_COLS = ["#", "Workpiece", "Orientation", "Confidence", "Result"]
_THUMB_SIZE = 140


class ContourMatchingTesterView(IApplicationView):

    SHOW_JOG_WIDGET = True
    JOG_FRAME_SELECTOR_ENABLED = True

    load_workpieces_requested = pyqtSignal()
    match_requested           = pyqtSignal()
    capture_requested         = pyqtSignal()
    workpiece_selected        = pyqtSignal(int)   # row index

    def __init__(self, parent=None):
        self._current_frame: Optional[np.ndarray] = None
        super().__init__("ContourMatchingTester", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        root.addWidget(self._build_camera_panel(), stretch=3)
        root.addWidget(self._build_control_panel(), stretch=1)

    # ── Panel builders ────────────────────────────────────────────────────────

    def _build_camera_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(panel_style())
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header = QLabel("Camera Feed")
        header.setStyleSheet(LABEL_STYLE)
        header_row.addWidget(header)
        header_row.addStretch()

        self._status_label = QLabel("● LIVE")
        self._status_label.setStyleSheet(_STATUS_LIVE_STYLE)
        header_row.addWidget(self._status_label)

        self._capture_btn = QPushButton("Capture")
        self._capture_btn.setStyleSheet(_CAPTURE_BTN_STYLE)
        self._capture_btn.clicked.connect(self._on_capture_clicked)
        header_row.addWidget(self._capture_btn)

        layout.addLayout(header_row)

        self._feed_label = CameraView()
        self._feed_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._feed_label.setMinimumSize(320, 240)
        layout.addWidget(self._feed_label)

        return panel

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(panel_style())
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Workpieces ──
        wp_header = QLabel("Workpieces")
        wp_header.setStyleSheet(LABEL_STYLE)
        layout.addWidget(wp_header)

        self._load_btn = QPushButton("Load Workpieces")
        self._load_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._load_btn.clicked.connect(self._on_load_clicked)
        layout.addWidget(self._load_btn)

        self._workpiece_list = QListWidget()
        self._workpiece_list.setStyleSheet(_LIST_STYLE)
        self._workpiece_list.setMaximumHeight(120)
        self._workpiece_list.currentRowChanged.connect(self._on_workpiece_row_changed)
        layout.addWidget(self._workpiece_list)

        # ── Thumbnail preview ──
        thumb_frame = QFrame()
        thumb_frame.setStyleSheet(f"QFrame {{ {panel_style()} }}")
        thumb_layout = QVBoxLayout(thumb_frame)
        thumb_layout.setContentsMargins(6, 6, 6, 6)
        thumb_layout.setSpacing(4)

        self._thumb_name_label = QLabel("Click a workpiece to preview")
        self._thumb_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_name_label.setStyleSheet(_THUMB_IDLE_STYLE)
        thumb_layout.addWidget(self._thumb_name_label)

        self._thumb_img_label = QLabel()
        self._thumb_img_label.setFixedSize(_THUMB_SIZE, _THUMB_SIZE)
        self._thumb_img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_img_label.setStyleSheet(
            f"background: {BG_COLOR}; border: none;"
        )
        thumb_layout.addWidget(self._thumb_img_label, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(thumb_frame)

        # ── Matching ──
        match_header = QLabel("Matching")
        match_header.setStyleSheet(LABEL_STYLE)
        layout.addWidget(match_header)

        self._match_btn = QPushButton("Match")
        self._match_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._match_btn.clicked.connect(self._on_match_clicked)
        layout.addWidget(self._match_btn)

        # ── Results ──
        results_header = QLabel("Results")
        results_header.setStyleSheet(LABEL_STYLE)
        layout.addWidget(results_header)

        self._summary_label = QLabel("Run matching to see results")
        self._summary_label.setStyleSheet(_SUMMARY_IDLE_STYLE)
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        self._results_table = make_table(_COLS)
        self._results_table.setStyleSheet(_TABLE_STYLE)
        hdr = self._results_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._results_table, stretch=1)

        return panel

    # ── Inbound setters ───────────────────────────────────────────────────────

    def update_camera_view(self, image: np.ndarray) -> None:
        if self._feed_label is None:
            return
        rgb  = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._feed_label.set_frame(QPixmap.fromImage(qimg))

    def set_capture_state(self, captured: bool) -> None:
        if captured:
            self._status_label.setText("⏸ CAPTURED")
            self._status_label.setStyleSheet(_STATUS_CAPTURED_STYLE)
            self._capture_btn.setText("Resume")
            self._capture_btn.setStyleSheet(_CAPTURE_ACTIVE_BTN_STYLE)
        else:
            self._status_label.setText("● LIVE")
            self._status_label.setStyleSheet(_STATUS_LIVE_STYLE)
            self._capture_btn.setText("Capture")
            self._capture_btn.setStyleSheet(_CAPTURE_BTN_STYLE)

    def set_workpieces(self, workpieces: list) -> None:
        self._workpiece_list.clear()
        for wp in workpieces:
            self._workpiece_list.addItem(getattr(wp, "name", str(wp)))
        self._results_table.setRowCount(0)
        self._summary_label.setText("Run matching to see results")
        self._summary_label.setStyleSheet(_SUMMARY_IDLE_STYLE)
        self._clear_thumbnail()

    def show_thumbnail(self, name: str, thumbnail_bytes: Optional[bytes]) -> None:
        self._thumb_name_label.setText(name or "Unknown")
        self._thumb_name_label.setStyleSheet(_THUMB_NAME_STYLE)
        if thumbnail_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(thumbnail_bytes)
            scaled = pixmap.scaled(
                _THUMB_SIZE, _THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._thumb_img_label.setPixmap(scaled)
            self._thumb_img_label.setText("")
        else:
            self._thumb_img_label.setPixmap(QPixmap())
            self._thumb_img_label.setText("No preview")
            self._thumb_img_label.setStyleSheet(f"color: #aaa; background: {BG_COLOR}; border: none;")

    def set_match_results(self, results: dict, no_match_count: int) -> None:
        wps          = results.get("workpieces", [])
        orientations = results.get("orientations", [])
        confidences  = results.get("mlConfidences", [])
        ml_results   = results.get("mlResults", [])
        matched      = len(wps)

        if matched == 0 and no_match_count == 0:
            self._summary_label.setText("No contours detected")
            self._summary_label.setStyleSheet(_SUMMARY_IDLE_STYLE)
        elif no_match_count == 0:
            self._summary_label.setText(f"✓  All {matched} contour(s) matched")
            self._summary_label.setStyleSheet(_SUMMARY_OK_STYLE)
        else:
            self._summary_label.setText(f"✓ {matched} matched     ✗ {no_match_count} unmatched")
            style = _SUMMARY_OK_STYLE if matched >= no_match_count else _SUMMARY_WARN_STYLE
            self._summary_label.setStyleSheet(style)

        self._results_table.clearSpans()
        self._results_table.setRowCount(matched)

        for i, (wp, orient) in enumerate(zip(wps, orientations)):
            name   = getattr(wp, "name", f"WP {i}")
            conf   = confidences[i] if i < len(confidences) else 0.0
            result = ml_results[i]  if i < len(ml_results)  else ""
            color  = _COLOR_HIGH if conf >= 80 else (_COLOR_MED if conf >= 50 else _COLOR_LOW)

            for col, text, align in (
                (0, f"#{i}",          Qt.AlignmentFlag.AlignCenter),
                (1, name,             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                (2, f"{orient:.1f}°", Qt.AlignmentFlag.AlignCenter),
                (3, f"{conf:.1f}%",   Qt.AlignmentFlag.AlignCenter),
                (4, result or "—",    Qt.AlignmentFlag.AlignCenter),
            ):
                item = QTableWidgetItem(text)
                item.setTextAlignment(align)
                item.setBackground(color)
                self._results_table.setItem(i, col, item)

        if matched == 0:
            self._results_table.setRowCount(1)
            item = QTableWidgetItem("No matches found")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QColor("#888888"))
            self._results_table.setItem(0, 0, item)
            self._results_table.setSpan(0, 0, 1, len(_COLS))

    def set_matching_busy(self, busy: bool) -> None:
        self._match_btn.setEnabled(not busy)
        self._match_btn.setText("Matching…" if busy else "Match")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _clear_thumbnail(self) -> None:
        self._thumb_name_label.setText("Click a workpiece to preview")
        self._thumb_name_label.setStyleSheet(_THUMB_IDLE_STYLE)
        self._thumb_img_label.setPixmap(QPixmap())
        self._thumb_img_label.setText("")
        self._thumb_img_label.setStyleSheet(f"background: {BG_COLOR}; border: none;")

    # ── Outbound forwarders ───────────────────────────────────────────────────

    def _on_load_clicked(self) -> None:
        self.load_workpieces_requested.emit()

    def _on_match_clicked(self) -> None:
        self.match_requested.emit()

    def _on_capture_clicked(self) -> None:
        self.capture_requested.emit()

    def _on_workpiece_row_changed(self, row: int) -> None:
        if row >= 0:
            self.workpiece_selected.emit(row)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass
