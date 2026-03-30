"""
CalibrationLeftPanel — mirrors HTML .left exactly:

  .left (column, dark #10101C)
    .cam-box        — aspect-ratio 4:3, flex-shrink:0
                      overlays: cam-id label, pts-pill badge, FAB capture button
    .status-bar     — 48px fixed, dark2, 5 stats
    .below-cam      — flex:1 (takes all remaining height)
        .thumb-section  — flex-shrink:0, hidden/shown on Camera tab
        .log-toggle-bar — 40px fixed, always visible
        .log-drawer     — expands to fill remaining space when open

The tab bar (.topbar) lives in CalibrationView above the content-row,
spanning the full window width.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QTextCursor, QResizeEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pl_gui.utils.utils_widgets.camera_view import CameraView
from src.shared_contracts.declarations import WorkAreaDefinition

# ── Palette ───────────────────────────────────────────────────────────────────
_DARK  = "#10101C"
_DARK2 = "#1A1A2E"
_PR    = "#905BA9"

_STATUS_KEY = "color: rgba(255,255,255,0.4); font-size: 9pt; letter-spacing: 0.3px; background: transparent;"
_STATUS_VAL = "color: rgba(255,255,255,0.9); font-size: 11pt; font-weight: 500; background: transparent;"
_STATUS_GOOD = "color: #66BB6A; font-size: 11pt; font-weight: 500; background: transparent;"
_STATUS_WARN = "color: #FFB74D; font-size: 11pt; font-weight: 500; background: transparent;"

_LOG_TOGGLE_STYLE = """
QPushButton {
    background: transparent;
    color: rgba(255,255,255,0.42);
    border: none;
    border-top: 1px solid rgba(255,255,255,0.07);
    font-size: 9pt;
    font-weight: 500;
    text-align: left;
    padding: 0 16px;
    min-height: 40px;
    max-height: 40px;
}
QPushButton:hover { color: rgba(255,255,255,0.7); }
"""

_LOG_BODY_STYLE = """
QTextEdit {
    background: transparent;
    color: rgba(255,255,255,0.6);
    border: none;
    font-family: monospace;
    font-size: 9pt;
    padding: 8px 16px 12px 16px;
}
"""

_THUMB_SECTION_STYLE = "background: transparent; border-top: 1px solid rgba(255,255,255,0.06);"

_FAB_STYLE = """
QPushButton {
    background: transparent;
    border: 3px solid rgba(144,91,169,0.85);
    border-radius: 32px;
    min-width:  64px; max-width:  64px;
    min-height: 64px; max-height: 64px;
}
QPushButton:hover { background: rgba(144,91,169,0.2); }
"""

_CAM_ID_STYLE  = "color: rgba(255,255,255,0.4); font-size: 8pt; font-family: monospace; background: transparent;"
_PTS_PILL_STYLE = (
    "color: rgba(255,255,255,0.85); font-size: 8pt;"
    "background: rgba(144,91,169,0.4);"
    "border: 1px solid rgba(144,91,169,0.6);"
    "border-radius: 14px; padding: 3px 11px;"
)


class _GridCameraView(CameraView):
    """CameraView with grid-point and substitute-region overlay painting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid_points: list[tuple[float, float]] = []
        self._grid_labels: list[str] = []
        self._point_statuses: dict[str, str] = {}
        self._substitute_polygons: dict[str, list[tuple[float, float]]] = {}

    def set_grid_points(self, points, *, point_labels=None, point_statuses=None):
        self._grid_points = [(float(x), float(y)) for x, y in points]
        self._grid_labels = [str(lbl) for lbl in (point_labels or [])]
        self._point_statuses = {str(k): str(v) for k, v in (point_statuses or {}).items()}
        self.update()

    def set_substitute_regions(self, polygons):
        self._substitute_polygons = dict(polygons)
        self.update()

    def _paint_overlay(self, painter, image_rect):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QColor, QBrush, QPainterPath, QPen, QPolygonF
        _PC = QColor("#FF7043"); _PF = QColor(255, 112, 67, 180)
        _LC = QColor("#1A1A2E")
        _OC = QColor("#2E7D32"); _OF = QColor(46, 125, 50, 190)
        _EC = QColor("#D32F2F"); _EF = QColor(211, 47, 47, 190)
        _PAL = [
            (QColor("#F9A825"), QColor(249, 168, 37, 55)),
            (QColor("#7B1FA2"), QColor(123, 31, 162, 55)),
            (QColor("#0288D1"), QColor(2, 136, 209, 55)),
        ]
        if not self._grid_points and not self._substitute_polygons:
            return
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        ordered = list(self._substitute_polygons.keys())
        ac = self.get_area_corners(self._active_area) if self._active_area else []
        ap = None
        if len(ac) >= 3:
            ap = QPainterPath()
            ap.addPolygon(QPolygonF([QPointF(*self._to_pixel(x, y)) for x, y in ac]))
            ap.closeSubpath()
        for i, (lbl, poly) in enumerate(self._substitute_polygons.items()):
            if len(poly) < 3:
                continue
            cl, cf = _PAL[i % len(_PAL)]
            painter.setPen(QPen(cl, 1.0, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(cf))
            p = QPainterPath()
            p.addPolygon(QPolygonF([QPointF(*self._to_pixel(x, y)) for x, y in poly]))
            p.closeSubpath()
            painter.drawPath(p.intersected(ap) if ap else p)
        pen = QPen(_PC, 1.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(_PF))
        for idx, (xn, yn) in enumerate(self._grid_points):
            px, py = self._to_pixel(xn, yn)
            name = self._grid_labels[idx] if idx < len(self._grid_labels) else str(idx + 1)
            st = self._point_statuses.get(name, "")
            if st in ("direct", "via_anchor", "reachable"):
                painter.setPen(QPen(_OC, 1.5)); painter.setBrush(QBrush(_OF))
            elif st == "unreachable":
                painter.setPen(QPen(_EC, 1.5)); painter.setBrush(QBrush(_EF))
            elif st == "substitute":
                ul = name[:-4]
                ci = ordered.index(ul) if ul in ordered else 0
                cl, _ = _PAL[ci % len(_PAL)]
                painter.setPen(QPen(cl, 1.5)); painter.setBrush(QBrush(cl))
            else:
                painter.setPen(pen); painter.setBrush(QBrush(_PF))
            painter.drawEllipse(int(px) - 4, int(py) - 4, 8, 8)
            painter.setPen(_LC)
            painter.drawText(int(px) + 6, int(py) - 6, name)
            painter.setPen(pen)


class _CamBox(QWidget):
    """
    Mirrors HTML .cam-box:
      - aspect-ratio 4:3, flex-shrink:0 (fixed height based on actual width)
      - dark #0A0A14 background
      - overlays: cam-id (top-left), pts-pill (top-right), FAB (bottom-center)
    """
    def __init__(self, work_area_defs: list, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #0A0A14;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Camera view fills the box
        self.preview_label = _GridCameraView(self)
        self.preview_label.setStyleSheet("background: transparent;")
        for d in work_area_defs:
            self.preview_label.add_area(d.id, d.color)
        if work_area_defs:
            self.preview_label.set_active_area(work_area_defs[0].id)

        # Overlays — absolute positioned like HTML
        self._cam_id = QLabel("CAM_01 · — · — fps", self)
        self._cam_id.setStyleSheet(_CAM_ID_STYLE)
        self._cam_id.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._pts_pill = QLabel("—", self)
        self._pts_pill.setStyleSheet(_PTS_PILL_STYLE)
        self._pts_pill.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.fab = QPushButton(self)
        self.fab.setStyleSheet(_FAB_STYLE)
        self.fab.setToolTip("Capture calibration image")
        inner = QLabel(self.fab)
        inner.setFixedSize(46, 46)
        inner.setStyleSheet(f"background: {_PR}; border-radius: 23px;")
        fab_layout = QHBoxLayout(self.fab)
        fab_layout.setContentsMargins(0, 0, 0, 0)
        fab_layout.addWidget(inner)

    def resizeEvent(self, event: QResizeEvent) -> None:
        w = self.width()
        h = self.height()
        # Camera fills entire box
        self.preview_label.setGeometry(0, 0, w, h)
        # cam-id: top-left at (14, 12)
        self._cam_id.adjustSize()
        self._cam_id.move(14, 12)
        # pts-pill: top-right at (right - width - 14, 12)
        self._pts_pill.adjustSize()
        self._pts_pill.move(w - self._pts_pill.width() - 14, 12)
        # FAB: bottom-center
        self.fab.move((w - 64) // 2, h - 64 - 14)
        super().resizeEvent(event)

    def heightForWidth(self, width: int) -> int:
        return (width * 3) // 4   # 4:3

    def hasHeightForWidth(self) -> bool:
        return True

    def sizeHint(self) -> QSize:
        w = self.width() if self.width() > 0 else 640
        return QSize(w, self.heightForWidth(w))


class CalibrationLeftPanel(QWidget):
    """
    Dark left column — matches HTML .left:
      cam-box (4:3 aspect, fixed height) → status-bar (48px) → below-cam (flex:1)
    """

    def __init__(self, work_area_definitions: list[WorkAreaDefinition] | None = None, parent=None):
        super().__init__(parent)
        self._work_area_defs = [d for d in (work_area_definitions or []) if d.supports_height_mapping]
        self._log_open = False
        self.setStyleSheet(f"background: {_DARK};")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # .cam-box — 4:3 aspect ratio, flex-shrink:0
        self._cam_box = _CamBox(self._work_area_defs)
        layout.addWidget(self._cam_box, stretch=0)

        # .status-bar — 48px fixed
        layout.addWidget(self._build_status_bar(), stretch=0)

        # .below-cam — flex:1 (takes all remaining height)
        layout.addWidget(self._build_below_cam(), stretch=1)

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet(f"background: {_DARK2}; border-top: 1px solid rgba(255,255,255,0.07);")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(0)
        stats = [
            ("RMS error",    "—",     ""),
            ("Reprojection", "—",     ""),
            ("Coverage",     "—",     ""),
            ("Frames",       "0",     ""),
            ("State",        "Ready", "good"),
        ]
        for i, (key, val, cls) in enumerate(stats):
            col = QWidget()
            col.setStyleSheet("background: transparent;" + (
                "border-right: 1px solid rgba(255,255,255,0.08);" if i < len(stats) - 1 else ""
            ))
            cl = QVBoxLayout(col)
            cl.setContentsMargins(8, 4, 8, 4)
            cl.setSpacing(2)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            k = QLabel(key)
            k.setAlignment(Qt.AlignmentFlag.AlignCenter)
            k.setStyleSheet(_STATUS_KEY)
            v = QLabel(val)
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.setStyleSheet(
                _STATUS_GOOD if cls == "good" else
                _STATUS_WARN if cls == "warn" else
                _STATUS_VAL
            )
            cl.addWidget(k)
            cl.addWidget(v)
            row.addWidget(col, stretch=1)
        return bar

    # ── Below cam (flex:1) ────────────────────────────────────────────────────

    def _build_below_cam(self) -> QWidget:
        """
        Matches HTML .below-cam:
          flex:1, column, overflow:hidden
          contains: thumb-section (shrink:0) + log-toggle-bar (shrink:0) + log-drawer (flex:1)
        """
        w = QWidget()
        w.setStyleSheet(f"background: {_DARK};")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # thumb-section — flex-shrink:0, hidden by default
        self._thumb_section = self._build_thumb_section()
        layout.addWidget(self._thumb_section, stretch=0)

        # log-toggle-bar — flex-shrink:0, always visible
        self._log_toggle_btn = QPushButton("Activity log  ▾")
        self._log_toggle_btn.setStyleSheet(_LOG_TOGGLE_STYLE)
        self._log_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._log_toggle_btn.setFixedHeight(40)
        self._log_toggle_btn.clicked.connect(self._toggle_log)
        layout.addWidget(self._log_toggle_btn, stretch=0)

        # log-drawer — flex:1, hidden until opened
        self._log_drawer = QWidget()
        self._log_drawer.setStyleSheet(f"background: {_DARK};")
        log_inner = QVBoxLayout(self._log_drawer)
        log_inner.setContentsMargins(0, 0, 0, 0)
        log_inner.setSpacing(0)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(_LOG_BODY_STYLE)
        self.log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_inner.addWidget(self.log)
        self._log_drawer.hide()
        layout.addWidget(self._log_drawer, stretch=1)

        return w

    def _build_thumb_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(_THUMB_SECTION_STYLE)
        w.hide()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(9)

        # Header row
        header = QHBoxLayout()
        title = QLabel("Captured frames")
        title.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 9pt; font-weight: 500;"
            "letter-spacing: 0.4px; background: transparent;"
        )
        self._thumb_count_label = QLabel("0 frames")
        self._thumb_count_label.setStyleSheet(
            "color: rgba(255,255,255,0.3); font-size: 9pt; background: transparent;"
        )
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._thumb_count_label)
        layout.addLayout(header)

        # Horizontal scroll area
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFixedHeight(78)
        scroll.setStyleSheet("background: transparent;")
        self._thumb_row_widget = QWidget()
        self._thumb_row_widget.setStyleSheet("background: transparent;")
        self._thumb_row = QHBoxLayout(self._thumb_row_widget)
        self._thumb_row.setContentsMargins(0, 0, 0, 2)
        self._thumb_row.setSpacing(9)
        self._thumb_row.addStretch()
        scroll.setWidget(self._thumb_row_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        return w

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def preview_label(self) -> _GridCameraView:
        return self._cam_box.preview_label

    @property
    def fab(self) -> QPushButton:
        return self._cam_box.fab

    def set_frame(self, pixmap: QPixmap) -> None:
        self._cam_box.preview_label.set_frame(pixmap)

    def append_log(self, message: str) -> None:
        self.log.append(message)
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self) -> None:
        self.log.clear()

    def set_thumbnail_strip_visible(self, visible: bool) -> None:
        self._thumb_section.setVisible(visible)

    def _toggle_log(self) -> None:
        self._log_open = not self._log_open
        self._log_drawer.setVisible(self._log_open)
        arrow = "▴" if self._log_open else "▾"
        self._log_toggle_btn.setText(f"Activity log  {arrow}")

