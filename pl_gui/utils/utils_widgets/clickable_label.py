"""
ClickableLabel — camera preview with multi-area overlay support.

Displays a QPixmap (camera frame) and overlays any number of named corner
areas (e.g. "working_area", "brightness_area") as draggable, filled polygons.

All coordinates are normalised to [0, 1].  The caller converts to/from the
camera resolution (e.g. 1280×720) before passing points in and after reading
them back.

Signals
-------
corner_updated(area_name, index, x_norm, y_norm)
    A corner in *area_name* was moved (click-to-place or drag).

empty_clicked(area_name, x_norm, y_norm)
    The user clicked on an empty spot while *area_name* is active (no corner hit).
    Useful for appending a new corner: add the point and call set_area_corners().
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRect
from PyQt6.QtGui import (
    QBrush, QColor, QMouseEvent, QPainter, QPen, QPixmap, QPolygonF,
)
from PyQt6.QtWidgets import QLabel, QSizePolicy


# ── tunables ──────────────────────────────────────────────────────────────────
_HIT_THRESHOLD   = 0.05   # normalised radius to detect a corner under cursor
_RADIUS_ACTIVE   = 9      # corner dot radius when area is active (editing)
_RADIUS_INACTIVE = 7      # corner dot radius when area is inactive (view-only)

# Built-in colour palette for well-known area names
_PALETTE: Dict[str, QColor] = {
    "pickup_area":     QColor( 80, 220, 100),   # green
    "spray_area":      QColor(255, 140,  50),   # orange
    "brightness_area": QColor(255, 200,  40),   # amber
}
_FALLBACK_COLOR = QColor(100, 180, 255)         # blue for unknown names


class ClickableLabel(QLabel):
    """
    Camera preview with draggable corner areas.

    Quick-start::

        label = ClickableLabel()

        # Register areas (optional — auto-registered on first set_area_corners call)
        label.add_area("working_area")             # green by default
        label.add_area("brightness_area")          # amber by default

        # Load saved corners (normalised [0,1])
        label.set_area_corners("working_area",    [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)])
        label.set_area_corners("brightness_area", [(0.3, 0.4), (0.7, 0.4), (0.7, 0.6), (0.3, 0.6)])

        # Activate one area for editing
        label.set_active_area("brightness_area")

        # React to changes
        label.corner_updated.connect(on_corner)   # (area, idx, xn, yn)
        label.empty_clicked.connect(on_click)      # (area, xn, yn)

        # Push live frames
        label.set_frame(pixmap)
    """

    corner_updated = pyqtSignal(str, int, float, float)  # area, idx, x_norm, y_norm
    empty_clicked  = pyqtSignal(str, float, float)        # area, x_norm, y_norm

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 240)
        self.setMouseTracking(True)
        # self.setStyleSheet("background: #12121F;")

        self._frame:        QPixmap | None                        = None
        self._areas:        Dict[str, List[Tuple[float, float]]] = {}
        self._colors:       Dict[str, QColor]                    = {}
        self._active_area:  Optional[str]                        = None
        self._drag:         Tuple[str, int]                      = ("", -1)
        self._coord_text:   str                                  = ""

    # ── Area management ────────────────────────────────────────────────────────

    def add_area(self, name: str, color: str | QColor | None = None) -> None:
        """Register a named area with an optional colour.  Corners start empty."""
        if name not in self._areas:
            self._areas[name] = []
        if color is not None:
            self._colors[name] = QColor(color) if isinstance(color, str) else color
        elif name not in self._colors:
            self._colors[name] = _PALETTE.get(name, _FALLBACK_COLOR)

    def set_active_area(self, name: Optional[str]) -> None:
        """
        Activate an area for editing (clicks / drags are routed to it).
        Pass *None* to enter view-only mode (no editing).
        """
        if name and name not in self._areas:
            self.add_area(name)
        self._active_area = name
        self.update()

    def set_area_corners(self, name: str, points: List[Tuple[float, float]]) -> None:
        """Set the corner positions for *name* (normalised [0, 1] coords)."""
        if name not in self._areas:
            self.add_area(name)
        self._areas[name] = list(points)
        self.update()

    def get_area_corners(self, name: str) -> List[Tuple[float, float]]:
        """Return a copy of the corner list for *name* (normalised coords)."""
        return list(self._areas.get(name, []))

    def clear_area(self, name: str) -> None:
        """Remove all corners for *name*."""
        if name in self._areas:
            self._areas[name] = []
            self.update()

    # ── Frame update ───────────────────────────────────────────────────────────

    def set_frame(self, pixmap: QPixmap) -> None:
        """Push a new camera frame.  Scaled to fit the label on paint."""
        self._frame = pixmap
        self.update()

    # ── Mouse events ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        norm = self._to_norm(event.position())
        if norm is None:
            return   # click was outside the image frame — ignore
        xn, yn = norm

        # Always show coordinates on every click
        self._update_coord_text(xn, yn)
        self.update()

        # Only dragging in the active area
        if self._active_area and self._active_area in self._areas:
            idx = _nearest(self._areas[self._active_area], xn, yn)
            if idx >= 0:
                self._drag = (self._active_area, idx)
                return

        self._drag = ("", -1)
        if self._active_area:
            pts = self._areas[self._active_area]
            if len(pts) < 4:
                idx = len(pts)
                pts.append((xn, yn))
                self.corner_updated.emit(self._active_area, idx, xn, yn)
                self.update()
            else:
                self.empty_clicked.emit(self._active_area, xn, yn)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        area, idx = self._drag
        if area and idx >= 0:
            norm = self._to_norm(event.position())
            if norm is None:
                return
            xn, yn = norm
            xn = max(0.0, min(1.0, xn))
            yn = max(0.0, min(1.0, yn))
            self._areas[area][idx] = (xn, yn)
            self._update_coord_text(xn, yn)
            self.corner_updated.emit(area, idx, xn, yn)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag = ("", -1)

    # ── Paint ──────────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background / frame
        rect = self.rect()
        if self._frame and not self._frame.isNull():
            scaled = self._frame.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            ox = (rect.width()  - scaled.width())  // 2
            oy = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(ox, oy, scaled)
        else:
            painter.fillRect(rect, QColor("#12121F"))

        # Draw inactive areas first, active area on top
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

        # Coordinate overlay at top of image rect
        if self._coord_text:
            r = self._image_rect()
            painter.setFont(self.font())
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(self._coord_text)
            th = fm.height()
            pad = 4
            bg = QColor(0, 0, 0, 140)
            painter.setBrush(QBrush(bg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(r.x() + pad, r.y() + pad, tw + pad * 2, th + pad * 2, 3, 3)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(r.x() + pad * 2, r.y() + pad + th, self._coord_text)

        painter.end()

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
            # Halo
            halo = QColor(color).darker(160)
            halo.setAlpha(180)
            painter.setBrush(QBrush(halo))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(px) - r - 2, int(py) - r - 2, (r + 2) * 2, (r + 2) * 2)
            # Dot
            painter.setBrush(QBrush(color))
            painter.drawEllipse(int(px) - r, int(py) - r, r * 2, r * 2)
            # Number
            num_color = QColor(0, 0, 0) if color.lightness() > 128 else QColor(255, 255, 255)
            painter.setPen(num_color)
            painter.drawText(int(px) - 4, int(py) + 5, str(i + 1))

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _update_coord_text(self, xn: float, yn: float) -> None:
        """Store pixel coords (based on frame size) as a readable string for the overlay."""
        if self._frame and not self._frame.isNull():
            px = int(xn * self._frame.width())
            py = int(yn * self._frame.height())
        else:
            r = self._image_rect()
            px = int(xn * r.width())
            py = int(yn * r.height())
        self._coord_text = f"x: {px}  y: {py}"

    def _image_rect(self) -> QRect:
        """Return the rect (in label pixels) occupied by the scaled frame."""
        if not self._frame or self._frame.isNull():
            return self.rect()
        lw, lh = self.width(), self.height()
        fw, fh = self._frame.width(), self._frame.height()
        scale  = min(lw / fw, lh / fh)
        sw, sh = int(fw * scale), int(fh * scale)
        return QRect((lw - sw) // 2, (lh - sh) // 2, sw, sh)

    def _to_norm(self, pos: QPointF) -> Tuple[float, float] | None:
        """
        Map a label-pixel position to normalised image coords [0, 1].
        Returns *None* if the position is outside the image frame.
        """
        r = self._image_rect()
        if not r.contains(pos.toPoint()):
            return None
        return (pos.x() - r.x()) / r.width(), (pos.y() - r.y()) / r.height()

    def _to_pixel(self, xn: float, yn: float) -> Tuple[float, float]:
        """Map normalised image coords to label-pixel coordinates."""
        r = self._image_rect()
        return r.x() + xn * r.width(), r.y() + yn * r.height()


def _nearest(pts: List[Tuple[float, float]], xn: float, yn: float) -> int:
    """Return index of the closest point within _HIT_THRESHOLD, else -1."""
    best_idx, best_d = -1, _HIT_THRESHOLD
    for i, (cx, cy) in enumerate(pts):
        d = ((cx - xn) ** 2 + (cy - yn) ** 2) ** 0.5
        if d < best_d:
            best_d, best_idx = d, i
    return best_idx
