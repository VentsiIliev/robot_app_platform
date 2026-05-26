from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen

from ..core.editor_context import EditorContext
from .segment_renderer import SegmentRenderer
from .renderer import (
    draw_ruler, draw_rectangle_selection, draw_pickup_point,
    draw_selection_status, draw_drag_crosshair,
    draw_highlighted_line_segment
)


class EditorRenderer:
    def __init__(self, editor):
        self.editor = editor
        self._context = EditorContext(editor)
        self._segment_renderer = SegmentRenderer(self._context)

    def render(self, painter, event):
        if not painter.isActive():
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.editor.rect(), Qt.GlobalColor.white)
        
        painter.translate(self.editor.translation)
        painter.scale(self.editor.scale_factor, self.editor.scale_factor)
        painter.drawImage(0, 0, self.editor.image)
        self._draw_verification_contours(painter)

        draw_ruler(self.editor, painter)
        self._segment_renderer.render_all(painter)
        draw_rectangle_selection(self.editor, painter)
        draw_pickup_point(self.editor, painter)
        draw_selection_status(self.editor, painter)

        if self.editor.highlighted_line_segment:
            draw_highlighted_line_segment(self.editor, painter)

        painter.resetTransform()

        if (hasattr(self.editor.mode_manager, 'drag_mode') and
            self.editor.mode_manager.drag_mode.is_actually_dragging and 
            self.editor.current_cursor_pos is not None):
            draw_drag_crosshair(self.editor, painter, self.editor.current_cursor_pos)

    def _draw_verification_contours(self, painter):
        contours = getattr(self.editor, "verification_contours", None) or []
        if not contours:
            return

        pen = QPen(QColor(0, 180, 255, 220))
        pen.setWidthF(2.0)
        pen.setCosmetic(True)

        painter.save()
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for contour in contours:
            if contour is None or len(contour) < 2:
                continue
            points = [(float(point[0]), float(point[1])) for point in contour]
            path = QPainterPath(QPointF(points[0][0], points[0][1]))
            for x, y in points[1:]:
                path.lineTo(x, y)
            if len(points) > 2:
                first_x, first_y = points[0]
                last_x, last_y = points[-1]
                if abs(first_x - last_x) > 1e-6 or abs(first_y - last_y) > 1e-6:
                    path.closeSubpath()
            painter.drawPath(path)

        painter.restore()
