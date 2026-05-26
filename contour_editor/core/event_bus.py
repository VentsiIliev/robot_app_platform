"""
Event Bus - Central event distribution system for ContourEditor
This provides a decoupled communication mechanism between components.
All state changes are broadcast as signals, allowing widgets to react
without direct coupling.
"""
from PyQt6.QtCore import QObject, pyqtSignal
class EventBus(QObject):
    """
    Singleton event bus for application-wide event distribution.
    Usage:
        # Get the singleton instance
        bus = EventBus.get_instance()
        # Emit events
        bus.segment_visibility_changed.emit(seg_index, visible)
        # Subscribe to events
        bus.segment_visibility_changed.connect(self._on_visibility_changed)
    """
    # Segment events
    segment_added = pyqtSignal(int)  # seg_index
    segment_deleted = pyqtSignal(int)  # seg_index
    segment_visibility_changed = pyqtSignal(int, bool)  # seg_index, visible
    segment_layer_changed = pyqtSignal(int, str)  # seg_index, layer_name
    active_segment_changed = pyqtSignal(int)  # seg_index
    # Point events
    points_changed = pyqtSignal()  # General points modification
    point_added = pyqtSignal(int, int)  # seg_index, point_index
    point_deleted = pyqtSignal(int, int)  # seg_index, point_index
    point_moved = pyqtSignal(int, int)  # seg_index, point_index
    # Selection events
    selection_changed = pyqtSignal(list)  # List of selected items
    # Layer events
    layer_visibility_changed = pyqtSignal(str, bool)  # layer_name, visible
    layer_locked_changed = pyqtSignal(str, bool)  # layer_name, locked
    # Viewport events
    viewport_changed = pyqtSignal()  # Zoom or pan changed
    # Undo/Redo events
    undo_executed = pyqtSignal()
    redo_executed = pyqtSignal()
    _instance = None
    def __init__(self):
        """Private constructor - use get_instance() instead"""
        if EventBus._instance is not None:
            raise RuntimeError("EventBus is a singleton. Use EventBus.get_instance()")
        super().__init__()
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of EventBus"""
        if cls._instance is None:
            cls._instance = EventBus()
        return cls._instance
    @classmethod
    def reset_instance(cls):
        """Reset the singleton (useful for testing)"""
        cls._instance = None
