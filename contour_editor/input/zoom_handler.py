from PyQt6.QtCore import QPointF
class ZoomHandler:
    def __init__(self, context):
        self.ctx = context
    def zoom_in(self):
        center_screen = QPointF(
            self.ctx.widget.width() / 2,
            self.ctx.widget.height() / 2
        )
        self.ctx.viewport.zoom_centered(1.25, center_screen)
    def zoom_out(self):
        center_screen = QPointF(
            self.ctx.widget.width() / 2,
            self.ctx.widget.height() / 2
        )
        self.ctx.viewport.zoom_centered(0.8, center_screen)
    def reset_zoom(self):
        self.ctx.viewport.reset_zoom(
            self.ctx.widget.width(),
            self.ctx.widget.height()
        )
    def handle_wheel_event(self, event):
        angle = event.angleDelta().y()
        if angle == 0:  # No vertical scroll
            return
        factor = 1.25 if angle > 0 else 0.8
        cursor_pos = event.position()
        self.ctx.viewport.zoom_at_point(cursor_pos, factor)
        self.ctx.widget.update()  # Trigger repaint
