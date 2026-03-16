"""
CameraView — zoomable, pannable camera preview with multi-area overlay support.

Combines the area-editing API of ``ClickableLabel`` with the zoom/pan
capabilities of ``_ZoomableImageWidget`` into a single reusable ``QWidget``
that lives in ``pl_gui/`` and is free of numpy / cv2.

All area coordinates are normalised to [0, 1].  Frame delivery (BGR→RGB→
QImage→QPixmap conversion) stays in application controllers — this widget only
accepts a ``QPixmap``.

Signals
-------
corner_updated(area_name, index, x_norm, y_norm)
    A corner in *area_name* was moved (click-to-place or drag).

empty_clicked(area_name, x_norm, y_norm)
    The user clicked on an empty spot while *area_name* is active and all four
    corners are already placed.  Useful for custom append logic.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QMouseEvent, QPainter, QPen, QPixmap, QPolygonF,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)


# ── tunables ──────────────────────────────────────────────────────────────────
_HIT_THRESHOLD   = 0.05    # normalised radius to detect a corner under cursor
_RADIUS_ACTIVE   = 9       # corner dot radius when area is active (editing)
_RADIUS_INACTIVE = 7       # corner dot radius when area is inactive

_ZOOM_STEP = 1.30
_ZOOM_MIN  = 0.05
_ZOOM_MAX  = 12.0
_PAN_MARGIN = 40           # minimum px of image visible on any edge

_BG_COLOR        = QColor("#F8F9FA")   # light background — matches app BG_COLOR
_TOOLBAR_STYLE   = "background: white; border-bottom: 1px solid #E0E0E0;"
_TOOLBAR_HEIGHT  = 48                  # tall enough for touch-friendly buttons

# Built-in colour palette for well-known area names
_PALETTE: Dict[str, QColor] = {
    "pickup_area":     QColor( 80, 200,  90),
    "spray_area":      QColor(255, 140,  50),
    "brightness_area": QColor(255, 180,  20),
}
_FALLBACK_COLOR = QColor(100, 140, 255)

# Zoom buttons: ghost style using PRIMARY (#905BA9), touch-friendly 44 px squares
_ZOOM_BTN_STYLE = (
    "QPushButton {"
    "  background: white; color: #905BA9;"
    "  border: 2px solid #905BA9; border-radius: 8px;"
    "  font-size: 13pt; font-weight: bold;"
    "  min-width: 44px; max-width: 44px;"
    "  min-height: 40px; max-height: 40px;"
    "}"
    "QPushButton:hover   { background: rgba(144,91,169,0.10); }"
    "QPushButton:pressed { background: rgba(144,91,169,0.22); }"
)
_PCT_LABEL_STYLE = (
    "font-size: 9pt; font-weight: bold; color: #905BA9;"
    " background: transparent; min-width: 46px;"
)
_ZOOM_LABEL_STYLE = (
    "font-size: 9pt; font-weight: bold; color: #666;"
    " background: transparent;"
)


class CameraView(QWidget):
    """
    Camera preview widget with zoom/pan and draggable corner-area overlays.

    Drop-in replacement for ``ClickableLabel`` — exposes the same area-management
    API and signals while adding zoom/pan and a subclass paint hook.

    Quick-start::

        view = CameraView()

        view.add_area("working_area")
        view.set_area_corners("working_area", [(0.1, 0.1), (0.9, 0.1),
                                               (0.9, 0.9), (0.1, 0.9)])
        view.set_active_area("working_area")
        view.corner_updated.connect(on_corner)  # (area, idx, xn, yn)
        view.empty_clicked.connect(on_click)    # (area, xn, yn)

        # Push live frames from a controller
        view.set_frame(pixmap)
    """

    corner_updated = pyqtSignal(str, int, float, float)  # area, idx, x_norm, y_norm
    empty_clicked  = pyqtSignal(str, float, float)        # area, x_norm, y_norm

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 240)
        self.setMouseTracking(True)

        # ── state ──────────────────────────────────────────────────────────────
        self._frame:       QPixmap | None                        = None
        self._zoom:        float                                 = 1.0
        self._pan:         QPointF                              = QPointF(0.0, 0.0)

        self._areas:       Dict[str, List[Tuple[float, float]]] = {}
        self._colors:      Dict[str, QColor]                    = {}
        self._active_area: Optional[str]                        = None
        self._drag_corner: Tuple[str, int]                      = ("", -1)

        self._pan_active:  bool                                 = False
        self._pan_last:    QPointF                              = QPointF()
        self._coord_text:  str                                  = ""

        # ── toolbar ────────────────────────────────────────────────────────────
        self._toolbar = QWidget(self)
        self._toolbar.setFixedHeight(_TOOLBAR_HEIGHT)
        self._toolbar.setStyleSheet(_TOOLBAR_STYLE)

        bar = QHBoxLayout(self._toolbar)
        bar.setContentsMargins(6, 2, 6, 2)
        bar.setSpacing(4)

        zoom_label = QLabel("Zoom:")
        zoom_label.setStyleSheet(_ZOOM_LABEL_STYLE)

        self._out_btn   = QPushButton("−")
        self._in_btn    = QPushButton("+")
        self._reset_btn = QPushButton("⊙")
        for btn in (self._out_btn, self._in_btn, self._reset_btn):
            btn.setStyleSheet(_ZOOM_BTN_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._pct_label = QLabel("100%")
        self._pct_label.setStyleSheet(_PCT_LABEL_STYLE)

        bar.addWidget(zoom_label)
        bar.addWidget(self._out_btn)
        bar.addWidget(self._in_btn)
        bar.addWidget(self._reset_btn)
        bar.addSpacing(4)
        bar.addWidget(self._pct_label)
        bar.addStretch()

        self._out_btn.clicked.connect(self._zoom_out_center)
        self._in_btn.clicked.connect(self._zoom_in_center)
        self._reset_btn.clicked.connect(self.reset_zoom)

        # position toolbar at top
        self._toolbar.setGeometry(0, 0, self.width(), _TOOLBAR_HEIGHT)

    # ── resize / geometry ──────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        self._toolbar.setGeometry(0, 0, self.width(), self._toolbar.height())
        self._clamp_pan()
        super().resizeEvent(event)

    # ── public API — frame ─────────────────────────────────────────────────────

    def set_frame(self, pixmap: QPixmap) -> None:
        """Push a new camera frame (QPixmap).  Zoom/pan state is preserved."""
        self._frame = pixmap
        self._clamp_pan()
        self.update()

    # ── public API — zoom ──────────────────────────────────────────────────────

    def zoom_in(self) -> None:
        self._apply_zoom(self._zoom * _ZOOM_STEP, self._available_rect().center())

    def zoom_out(self) -> None:
        self._apply_zoom(self._zoom / _ZOOM_STEP, self._available_rect().center())

    def reset_zoom(self) -> None:
        self._zoom = 1.0
        self._pan  = QPointF(0.0, 0.0)
        self._clamp_pan()
        self._update_pct_label()
        self.update()

    # ── public API — areas (identical to ClickableLabel) ───────────────────────

    def add_area(self, name: str, color: str | QColor | None = None) -> None:
        """Register a named area with an optional colour.  Corners start empty."""
        if name not in self._areas:
            self._areas[name] = []
        if color is not None:
            self._colors[name] = QColor(color) if isinstance(color, str) else color
        elif name not in self._colors:
            self._colors[name] = _PALETTE.get(name, _FALLBACK_COLOR)

    def set_active_area(self, name: Optional[str]) -> None:
        """Activate an area for editing.  Pass *None* for view-only mode."""
        if name and name not in self._areas:
            self.add_area(name)
        self._active_area = name
        self.update()

    def set_area_corners(self, name: str, points: List[Tuple[float, float]]) -> None:
        """Set corner positions for *name* (normalised [0, 1] coords)."""
        if name not in self._areas:
            self.add_area(name)
        self._areas[name] = list(points)
        self.update()

    def get_area_corners(self, name: str) -> List[Tuple[float, float]]:
        """Return a copy of the corner list for *name*."""
        return list(self._areas.get(name, []))

    def clear_area(self, name: str) -> None:
        """Remove all corners for *name*."""
        if name in self._areas:
            self._areas[name] = []
            self.update()

    # ── subclass hook ─────────────────────────────────────────────────────────

    def _paint_overlay(self, painter: QPainter, image_rect: QRectF) -> None:
        """
        Override in subclasses to draw Qt-native overlays on top of the frame.

        *image_rect* is the destination rectangle of the current frame in widget
        coordinates (already zoom/pan–adjusted).  Default implementation is a
        no-op.
        """

    # ── mouse ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()

        if event.button() == Qt.MouseButton.RightButton:
            self._start_pan(pos)
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        norm = self._to_norm(pos)

        if self._active_area and norm is not None:
            xn, yn = norm
            self._update_coord_text(xn, yn)
            area_pts = self._areas[self._active_area]
            idx = _nearest(area_pts, xn, yn)
            if idx >= 0:
                self._drag_corner = (self._active_area, idx)
                self.update()
                return
            # no corner hit
            self._drag_corner = ("", -1)
            if len(area_pts) < 4:
                idx = len(area_pts)
                area_pts.append((xn, yn))
                self.corner_updated.emit(self._active_area, idx, xn, yn)
                self.update()
            else:
                self.empty_clicked.emit(self._active_area, xn, yn)
            return

        # no active area → pan
        self._start_pan(pos)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()

        # corner drag
        area, idx = self._drag_corner
        if area and idx >= 0:
            norm = self._to_norm(pos)
            if norm is not None:
                xn = max(0.0, min(1.0, norm[0]))
                yn = max(0.0, min(1.0, norm[1]))
                self._areas[area][idx] = (xn, yn)
                self._update_coord_text(xn, yn)
                self.corner_updated.emit(area, idx, xn, yn)
                self.update()
            return

        # pan
        if self._pan_active:
            delta = pos - self._pan_last
            self._pan_last = pos
            self._pan = QPointF(self._pan.x() + delta.x(), self._pan.y() + delta.y())
            self._clamp_pan()
            self.update()
            return

        # cursor shape when hovering over a corner
        if self._active_area:
            norm = self._to_norm(pos)
            if norm is not None:
                idx = _nearest(self._areas[self._active_area], *norm)
                if idx >= 0:
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                    return
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_corner = ("", -1)
        if self._pan_active:
            self._pan_active = False
            cursor = (Qt.CursorShape.CrossCursor if self._active_area
                      else Qt.CursorShape.OpenHandCursor)
            self.setCursor(cursor)

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = _ZOOM_STEP if event.angleDelta().y() > 0 else 1.0 / _ZOOM_STEP
        self._apply_zoom(self._zoom * factor, event.position())

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. background
        painter.fillRect(self.rect(), _BG_COLOR)

        # 2. frame
        ir = self._image_rect()
        if self._frame and not self._frame.isNull():
            painter.drawPixmap(ir.toRect(), self._frame)
        # else dark background already drawn

        # 3. area polygons
        order = [n for n in self._areas if n != self._active_area]
        if self._active_area and self._active_area in self._areas:
            order.append(self._active_area)
        for name in order:
            pts = self._areas[name]
            if not pts:
                continue
            color  = self._colors.get(name, _FALLBACK_COLOR)
            active = (name == self._active_area)
            self._draw_area(painter, pts, color, active)

        # 4. coordinate overlay
        if self._coord_text:
            fm  = painter.fontMetrics()
            tw  = fm.horizontalAdvance(self._coord_text)
            th  = fm.height()
            pad = 4
            bg  = QColor(0, 0, 0, 140)
            painter.setBrush(QBrush(bg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                int(ir.x() + pad), int(ir.y() + pad),
                tw + pad * 2, th + pad * 2, 3, 3,
            )
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(int(ir.x() + pad * 2), int(ir.y() + pad + th), self._coord_text)

        # 5. subclass hook
        self._paint_overlay(painter, ir)

        painter.end()

    # ── internal helpers ──────────────────────────────────────────────────────

    def _available_rect(self) -> QRectF:
        th = self._toolbar.height()
        return QRectF(0, th, self.width(), self.height() - th)

    def _image_rect(self) -> QRectF:
        avail  = self._available_rect()
        if not self._frame or self._frame.isNull():
            return avail

        fw, fh = self._frame.width(), self._frame.height()
        if fw == 0 or fh == 0:
            return avail

        fit_scale = min(avail.width() / fw, avail.height() / fh)
        dw = fw * fit_scale * self._zoom
        dh = fh * fit_scale * self._zoom

        cx = avail.center().x() + self._pan.x()
        cy = avail.center().y() + self._pan.y()
        return QRectF(cx - dw / 2, cy - dh / 2, dw, dh)

    def _to_norm(self, pos: QPointF) -> Tuple[float, float] | None:
        r = self._image_rect()
        if not r.contains(pos):
            return None
        return (pos.x() - r.x()) / r.width(), (pos.y() - r.y()) / r.height()

    def _to_pixel(self, xn: float, yn: float) -> Tuple[float, float]:
        r = self._image_rect()
        return r.x() + xn * r.width(), r.y() + yn * r.height()

    def _apply_zoom(self, new_zoom: float, cursor_pos: QPointF) -> None:
        """Zoom toward *cursor_pos* (widget coords) so the image point stays fixed."""
        old_rect = self._image_rect()

        # Normalised position of cursor in image space (before zoom)
        if old_rect.width() > 0 and old_rect.height() > 0:
            nxn = (cursor_pos.x() - old_rect.x()) / old_rect.width()
            nyn = (cursor_pos.y() - old_rect.y()) / old_rect.height()
        else:
            nxn, nyn = 0.5, 0.5

        self._zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, new_zoom))

        # new image rect with old pan
        new_rect = self._image_rect()

        # pixel position of the same normalised point in new rect
        new_px = QPointF(new_rect.x() + nxn * new_rect.width(),
                         new_rect.y() + nyn * new_rect.height())
        drift = new_px - cursor_pos
        self._pan = QPointF(self._pan.x() - drift.x(), self._pan.y() - drift.y())

        self._clamp_pan()
        self._update_pct_label()
        self.update()

    def _zoom_in_center(self) -> None:
        self._apply_zoom(self._zoom * _ZOOM_STEP, self._available_rect().center())

    def _zoom_out_center(self) -> None:
        self._apply_zoom(self._zoom / _ZOOM_STEP, self._available_rect().center())

    def _clamp_pan(self) -> None:
        """Keep at least _PAN_MARGIN px of the image visible on every edge."""
        avail = self._available_rect()
        ir    = self._image_rect()

        m = _PAN_MARGIN

        # right edge of image must be at least m px into widget from left
        max_pan_x = avail.width()  / 2 + ir.width()  / 2 - m
        # left edge of image must be at most (avail.width - m) from left → pan_x >= ...
        min_pan_x = -(avail.width()  / 2 + ir.width()  / 2 - m)

        max_pan_y = avail.height() / 2 + ir.height() / 2 - m
        min_pan_y = -(avail.height() / 2 + ir.height() / 2 - m)

        px = max(min_pan_x, min(max_pan_x, self._pan.x()))
        py = max(min_pan_y, min(max_pan_y, self._pan.y()))
        self._pan = QPointF(px, py)

    def _start_pan(self, pos: QPointF) -> None:
        self._pan_active = True
        self._pan_last   = pos
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _update_pct_label(self) -> None:
        self._pct_label.setText(f"{self._zoom * 100:.0f}%")

    def _update_coord_text(self, xn: float, yn: float) -> None:
        if self._frame and not self._frame.isNull():
            px = int(xn * self._frame.width())
            py = int(yn * self._frame.height())
        else:
            r  = self._image_rect()
            px = int(xn * r.width())
            py = int(yn * r.height())
        self._coord_text = f"x: {px}  y: {py}"

    def _draw_area(
        self,
        painter: QPainter,
        pts: List[Tuple[float, float]],
        color: QColor,
        active: bool,
    ) -> None:
        pixel_pts = [self._to_pixel(x, y) for x, y in pts]

        # Semi-transparent fill
        if len(pixel_pts) >= 3:
            fill = QColor(color)
            fill.setAlpha(55 if active else 25)
            painter.setBrush(QBrush(fill))
            painter.setPen(Qt.PenStyle.NoPen)
            poly = QPolygonF([QPointF(px, py) for px, py in pixel_pts])
            painter.drawPolygon(poly)

        # Border lines
        if len(pixel_pts) >= 2:
            border = QColor(color)
            border.setAlpha(230 if active else 130)
            pen = QPen(
                border,
                2.0 if active else 1.2,
                Qt.PenStyle.SolidLine if active else Qt.PenStyle.DashLine,
            )
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(len(pixel_pts)):
                p1 = pixel_pts[i]
                p2 = pixel_pts[(i + 1) % len(pixel_pts)]
                painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

        # Corner dots + index numbers
        r = _RADIUS_ACTIVE if active else _RADIUS_INACTIVE
        for i, (px, py) in enumerate(pixel_pts):
            halo = QColor(color).darker(160)
            halo.setAlpha(180)
            painter.setBrush(QBrush(halo))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(px) - r - 2, int(py) - r - 2, (r + 2) * 2, (r + 2) * 2)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(int(px) - r, int(py) - r, r * 2, r * 2)
            num_color = QColor(0, 0, 0) if color.lightness() > 128 else QColor(255, 255, 255)
            painter.setPen(num_color)
            painter.drawText(int(px) - 4, int(py) + 5, str(i + 1))


# ── module-level helper ───────────────────────────────────────────────────────

def _nearest(pts: List[Tuple[float, float]], xn: float, yn: float) -> int:
    """Return index of the closest point within _HIT_THRESHOLD, else -1."""
    best_idx, best_d = -1, _HIT_THRESHOLD
    for i, (cx, cy) in enumerate(pts):
        d = ((cx - xn) ** 2 + (cy - yn) ** 2) ** 0.5
        if d < best_d:
            best_d, best_idx = d, i
    return best_idx
