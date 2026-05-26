from PyQt6.QtCore import Qt
class GestureHandler:
    def __init__(self, context):
        self.ctx = context
        self._initial_scale = 1.0
    def handle_gesture_event(self, event):
        pinch = event.gesture(Qt.GestureType.PinchGesture)
        if not pinch:
            return
        if pinch.state() == Qt.GestureState.GestureStarted:
            self._initial_scale = self.ctx.viewport.scale
        elif pinch.state() == Qt.GestureState.GestureUpdated:
            total_scale_factor = pinch.totalScaleFactor()
            center = pinch.centerPoint()
            old_scale = self.ctx.viewport.scale
            image_point_under_fingers = (center - self.ctx.viewport.translation) / old_scale
            new_scale = self._initial_scale * total_scale_factor
            new_scale = max(0.1, min(new_scale, 20.0))
            self.ctx.viewport.scale = new_scale
            self.ctx.viewport.translation = center - image_point_under_fingers * new_scale
            self.ctx.update()
        elif pinch.state() == Qt.GestureState.GestureFinished:
            pass
