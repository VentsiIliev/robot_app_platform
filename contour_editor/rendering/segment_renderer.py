from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QColor, QBrush, QPainterPath, QTransform
from ..persistence.config import constants
from ..persistence.config.constants import LAYER_COLORS
from ..persistence.utils.point_visibility import get_visible_points
class SegmentRenderer:
    def __init__(self, context):
        self.ctx = context
    def render_all(self, painter):
        segments = self.ctx.segments.all()
        for idx, segment in enumerate(segments):
            if segment.visible:
                self._render_segment(painter, segment, idx)

    def _render_segment(self, painter, segment, seg_index):
        editor = self.ctx.widget
        points = segment.points
        controls = segment.controls
        is_active = (seg_index == editor.manager.active_segment_index)
        min_line_thickness = 2
        max_line_thickness = 6
        base_thickness = 2 if is_active else 1
        thickness = max(min_line_thickness, min(max_line_thickness, base_thickness))
        if len(points) >= 2:
            path = QPainterPath()
            path.moveTo(points[0])
            for i in range(1, len(points)):
                if i - 1 < len(controls) and controls[i - 1] is not None:
                    path.quadTo(controls[i - 1], points[i])
                else:
                    path.lineTo(points[i])
            layer_color = LAYER_COLORS.get(segment.layer.name, QColor("black"))
            pen = QPen(layer_color, thickness / self.ctx.viewport.scale)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            if not is_active:
                pen.setColor(layer_color.lighter(150))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        if is_active or editor.show_handles_only_on_selection:
            tangent_thickness = 1 / self.ctx.viewport.scale
            painter.setPen(QPen(Qt.GlobalColor.gray, tangent_thickness, Qt.PenStyle.DashLine))
            for i in range(1, len(points)):
                if i - 1 < len(controls):
                    ctrl = controls[i - 1]
                    if ctrl is not None:
                        painter.drawLine(points[i - 1], ctrl)
                        painter.drawLine(ctrl, points[i])
        self._render_handles(painter, segment, seg_index, points, controls)
    def _render_handles(self, painter, segment, seg_index, points, controls):
        editor = self.ctx.widget
        selected_points = {
            (s["role"], s["seg_index"], s["point_index"])
            for s in self.ctx.selection._mgr.selected_points_list
        }
        is_dragging = editor.drag_mode.dragging_point is not None
        if is_dragging:
            min_px = max_px = handle_px = 3
        else:
            min_px = max_px = 20
            handle_px = editor.handle_radius
            handle_px = max(min_px, min(max_px, handle_px))
        old_transform = painter.transform()
        visible_points = get_visible_points(points, self.ctx.viewport.scale)
        valid_controls = [c for c in controls if c is not None]
        visible_controls = get_visible_points(valid_controls, self.ctx.viewport.scale)
        if constants.SHOW_ANCHOR_POINTS:
            for idx, pt in enumerate(points):
                selected = ("anchor", seg_index, idx) in selected_points
                if not selected and pt not in visible_points:
                    continue
                color = editor.handle_selected_color if selected else editor.handle_color
                screen_pt = old_transform.map(pt)
                painter.setTransform(QTransform())
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(screen_pt, handle_px, handle_px)
                painter.setTransform(old_transform)
        if constants.SHOW_CONTROL_POINTS:
            for idx, ctrl in enumerate(controls):
                if ctrl is None:
                    continue
                selected = ("control", seg_index, idx) in selected_points
                if not selected and ctrl not in visible_controls:
                    continue
                color = editor.handle_selected_color if selected else QColor(255, 0, 0, 180)
                size = handle_px * (1.2 if selected else 0.8)
                size = max(min_px, min(max_px, size))
                screen_pt = old_transform.map(ctrl)
                painter.setTransform(QTransform())
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(screen_pt, size, size)
                painter.setTransform(old_transform)
