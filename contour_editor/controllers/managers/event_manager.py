from PyQt6.QtCore import QEvent

from ...input.mouse_handler import MouseHandler
from ...input.gesture_handler import GestureHandler
from ...input.zoom_handler import ZoomHandler
from ...core.editor_context import EditorContext


class EventManager:
    def __init__(self, editor):
        self.editor = editor
        
        # Event state management
        self.current_cursor_pos = None
        self.last_drag_pos = None

        # Create context and handlers
        self._context = EditorContext(editor)
        self._mouse_handler = MouseHandler(self._context)
        self._gesture_handler = GestureHandler(self._context)
        self._zoom_handler = ZoomHandler(self._context)

    def handle_mouse_press(self, event):
        self._mouse_handler.handle_press(event)

    def handle_mouse_double_click(self, event):
        self._mouse_handler.handle_double_click(event)

    def handle_mouse_move(self, event):
        self._mouse_handler.handle_move(event)

    def handle_mouse_release(self, event):
        self._mouse_handler.handle_release(event)

    def handle_wheel(self, event):
        self._zoom_handler.handle_wheel_event(event)

    def handle_general_event(self, event):
        if event.type() == QEvent.Type.Gesture:
            return self.handle_gesture_event(event)
        return False

    def handle_gesture_event(self, event):
        self._gesture_handler.handle_gesture_event(event)
        return True

    def update_cursor_position(self, pos):
        """Update the current cursor position for drag crosshair"""
        self.current_cursor_pos = pos

    def get_cursor_position(self):
        """Get the current cursor position"""
        return self.current_cursor_pos

    def update_drag_position(self, pos):
        """Update the last drag position for gesture handling"""
        self.last_drag_pos = pos

    def get_drag_position(self):
        """Get the last drag position"""
        return self.last_drag_pos

    def reset_event_state(self):
        """Reset event-related state"""
        self.current_cursor_pos = None
        self.last_drag_pos = None