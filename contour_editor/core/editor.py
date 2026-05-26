from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QFrame


from ..persistence.config import constants
from ..controllers.SegmentActionController import SegmentActionController
from ..controllers.viewport_controller import ViewportController
from ..controllers.managers.selection_manager import SelectionManager
from ..controllers.managers.tool_manager import ToolManager
from ..controllers.managers.mode_manager import ModeManager
from ..controllers.managers.overlay_manager import OverlayManager
from ..controllers.managers.settings_manager import SettingsManager
from ..controllers.managers.data_export_manager import DataExportManager
from ..controllers.managers.event_manager import EventManager
from ..controllers.managers.layer_manager import LayerManager
from ..rendering.editor_renderer import EditorRenderer
from ..models.segment import Segment, Layer
from ..persistence.data.segment_provider import SegmentManagerProvider
from ..core.event_bus import EventBus
from ..services.commands.command_history import CommandHistory
from ..services.segment_service import SegmentService


class ContourEditor(QFrame):
    pointsUpdated = pyqtSignal()
    update_camera_feed_requested = pyqtSignal()
    glue_type_names_list_requested = pyqtSignal()
    fetch_glue_types_requested = pyqtSignal()  # Signal to request glue types from controller
    glue_types_received = pyqtSignal(list)  # Signal to receive glue types (list of names)

    def __init__(self, visionSystem, image_path=None, contours=None, parent=None, data=None):
        super().__init__()

        # Subscribe to EventBus for automatic canvas repainting
        self._event_bus = EventBus.get_instance()
        self._connect_event_bus()

        # Initialize glue type names (will be fetched via controller when needed)
        self.glue_type_names = []

        # Initialize all managers first to avoid AttributeError during Qt events
        self.settings_manager = SettingsManager(self,self.glue_type_names)
        self.event_manager = EventManager(self)  # Initialize early for event handling
        self.renderer = EditorRenderer(self)
        self.mode_manager = ModeManager(self)
        self.overlay_manager = OverlayManager(self)
        self.data_export_manager = DataExportManager(self)
        self.layer_manager = LayerManager(self)

        # external manager is optional and can be injected externally (e.g., by workpiece_editor)
        # This keeps the core editor domain-agnostic
        self.workpiece_manager = None

        self.parent = parent
        self.setWindowTitle("Editable Bezier Curves")
        self.setGeometry(100, 100, 640, 360)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.setAutoFillBackground(False)
        self.visionSystem = visionSystem
        self.selection_manager = SelectionManager()
        self.manager = SegmentManagerProvider.get_instance().create_manager()

        self._command_history = CommandHistory.get_instance()
        self.segment_service = SegmentService(self.manager, self._command_history, self._event_bus)
        self.segment_action_controller = SegmentActionController(self.manager, self.segment_service)

        self.setup_timers()
        # Viewport controller - owns zoom, translation, and image state
        self.viewport_controller = ViewportController(self)

        # Tool manager - owns tool state and tool mode objects
        self.tool_manager = ToolManager(self)

        # Initialize viewport with image
        self.viewport_controller.load_image(image_path)


        self.grabGesture(Qt.GestureType.PinchGesture)

        self.contours = None
        self.verification_contours = []
        # Pickup point functionality (TODO: Move to ModeManager)
        self.pickup_point_mode_active = False
        self.pickup_point = None

        # --- Handle rendering parameters (moved to SettingsManager) ---
        self.handle_radius = self.settings_manager.handle_radius
        self.handle_color = self.settings_manager.handle_color
        self.handle_selected_color = self.settings_manager.handle_selected_color
        self.show_handles_only_on_selection = True
        self.min_point_display_scale = self.settings_manager.min_point_display_scale
        self.cluster_distance_px = self.settings_manager.cluster_distance_px


        # Highlighted line segment for measurement display (TODO: Move to RenderingManager)
        self.highlighted_line_segment = None  # (seg_index, line_index) or None

        # Initialize data if workpiece_manager is available (injected by workpiece_editor)
        # Generic contour_editor doesn't have workpiece_manager
        if self.workpiece_manager:
            if data is None:
                if contours is not None:
                    self.workpiece_manager.init_contour(contours)
            else:
                self.workpiece_manager.set_current_workpiece(data)
                print(f"Set data in ContourEditor: {data}")
                self.workpiece_manager.load_workpiece(data)

    def _connect_event_bus(self):
        """Subscribe to EventBus events that require canvas repaint"""
        self._event_bus.segment_visibility_changed.connect(lambda *_: self.update())
        self._event_bus.segment_deleted.connect(lambda *_: self.update())
        self._event_bus.segment_added.connect(lambda *_: self.update())
        self._event_bus.segment_layer_changed.connect(lambda *_: self.update())
        self._event_bus.points_changed.connect(self.update)
        self._event_bus.undo_executed.connect(self.update)
        self._event_bus.redo_executed.connect(self.update)

    # Property accessors for backward compatibility
    @property
    def scale_factor(self):
        return self.viewport_controller.scale_factor

    @scale_factor.setter
    def scale_factor(self, value):
        self.viewport_controller.scale_factor = value

    @property
    def translation(self):
        return self.viewport_controller.translation

    @translation.setter
    def translation(self, value):
        self.viewport_controller.translation = value

    @property
    def image(self):
        return self.viewport_controller.image

    @image.setter
    def image(self, value):
        self.viewport_controller.image = value

    # Tool-related property accessors for backward compatibility
    @property
    def ruler_mode_active(self):
        return self.tool_manager.ruler_mode_active

    @ruler_mode_active.setter
    def ruler_mode_active(self, value):
        self.tool_manager.ruler_mode_active = value

    @property
    def magnifier_active(self):
        return self.tool_manager.magnifier_active

    @magnifier_active.setter
    def magnifier_active(self, value):
        self.tool_manager.magnifier_active = value

    @property
    def rectangle_select_mode_active(self):
        return self.tool_manager.rectangle_select_mode_active

    @rectangle_select_mode_active.setter
    def rectangle_select_mode_active(self, value):
        self.tool_manager.rectangle_select_mode_active = value

    @property
    def ruler_mode(self):
        return self.tool_manager.ruler_mode

    @property
    def rectangle_select_mode(self):
        return self.tool_manager.rectangle_select_mode

    @property
    def magnifier(self):
        return self.tool_manager.magnifier
    
    # Mode-related property accessors for backward compatibility
    @property
    def current_mode(self):
        return self.mode_manager.current_mode
    
    @current_mode.setter
    def current_mode(self, value):
        self.mode_manager.current_mode = value
    
    @property
    def pan_mode_active(self):
        return self.mode_manager.pan_mode_active
    
    @pan_mode_active.setter
    def pan_mode_active(self, value):
        self.mode_manager.pan_mode_active = value
    
    @property
    def pickup_point_mode_active(self):
        return self.mode_manager.pickup_point_mode_active
    
    @pickup_point_mode_active.setter
    def pickup_point_mode_active(self, value):
        self.mode_manager.pickup_point_mode_active = value
    
    @property
    def multi_select_mode_active(self):
        return self.mode_manager.multi_select_mode_active
    
    @multi_select_mode_active.setter
    def multi_select_mode_active(self, value):
        self.mode_manager.multi_select_mode_active = value
    
    @property
    def pan_mode(self):
        return self.mode_manager.pan_mode
    
    @property
    def drag_mode(self):
        return self.mode_manager.drag_mode
    
    @property
    def multi_select_mode(self):
        return self.mode_manager.multi_select_mode
    
    # Overlay-related property accessors for backward compatibility
    @property
    def segment_click_overlay(self):
        return self.overlay_manager.segment_click_overlay
    
    @property
    def point_info_overlay(self):
        return self.overlay_manager.point_info_overlay
    
    @property
    def pending_segment_click_pos(self):
        return self.overlay_manager.pending_segment_click_pos
    
    @pending_segment_click_pos.setter
    def pending_segment_click_pos(self, value):
        self.overlay_manager.pending_segment_click_pos = value
    
    @property
    def pending_segment_click_index(self):
        return self.overlay_manager.pending_segment_click_index
    
    @pending_segment_click_index.setter
    def pending_segment_click_index(self, value):
        self.overlay_manager.pending_segment_click_index = value
    
    @property
    def press_hold_start_pos(self):
        return self.overlay_manager.press_hold_start_pos
    
    @press_hold_start_pos.setter
    def press_hold_start_pos(self, value):
        self.overlay_manager.press_hold_start_pos = value
    
    @property
    def point_info_timer(self):
        return self.overlay_manager.point_info_timer
    
    # Event-related property accessors for backward compatibility
    @property
    def current_cursor_pos(self):
        return self.event_manager.current_cursor_pos
    
    @current_cursor_pos.setter
    def current_cursor_pos(self, value):
        self.event_manager.current_cursor_pos = value
    
    @property
    def last_drag_pos(self):
        return self.event_manager.last_drag_pos
    
    @last_drag_pos.setter
    def last_drag_pos(self, value):
        self.event_manager.last_drag_pos = value
    
    # Data-related property accessors (optional, only if workpiece_manager is injected)
    @property
    def workpiece(self):
        """Get current workpiece if workpiece_manager is available"""
        return self.workpiece_manager.current_workpiece if self.workpiece_manager else None

    @workpiece.setter
    def workpiece(self, value):
        """Set current workpiece if workpiece_manager is available"""
        if self.workpiece_manager:
            self.workpiece_manager.current_workpiece = value

    @property
    def contours(self):
        """Get contours if workpiece_manager is available"""
        return self.workpiece_manager.contours if self.workpiece_manager else None

    @contours.setter
    def contours(self, value):
        """Set contours if workpiece_manager is available"""
        if self.workpiece_manager:
            self.workpiece_manager.contours = value

    """ TOOLS """

    def show_tools_menu(self):
        self.tool_manager.show_tools_menu()

    def setup_timers(self):
        # Drag update throttling (used by PointDragMode)
        self.drag_timer = QTimer(self)
        self.drag_timer.setInterval(constants.DRAG_UPDATE_INTERVAL_MS)  # Limit updates to ~60 FPS
        self.drag_timer.timeout.connect(self.perform_drag_update)

        # Camera feed update timer
        self.camera_feed_update_timer = QTimer(self)
        self.camera_feed_update_timer.setInterval(constants.CAMERA_FEED_UPDATE_INTERVAL_MS)
        self.camera_feed_update_timer.timeout.connect(self.update_camera_feed_requested.emit)
        self.camera_feed_update_timer.start()

    """ OVERLAYS """

    def remove_selected_points(self):
        self.overlay_manager.remove_selected_points()

    def _should_draw_all_points(self):
        """Decide whether to draw all points based on current zoom level."""
        return self.mode_manager._should_draw_all_points()

    def set_cursor_mode(self, mode):
        self.mode_manager.set_cursor_mode(mode)

    def toggle_multi_select_mode(self):
        """Toggle multi-selection mode on/off"""
        return self.mode_manager.toggle_multi_select_mode()

    """ WORKPIECE/CONTOURS INITIALIZATION METHODS """

    def load_workpiece(self, workpiece):
        """Load a workpiece - delegates to external manager"""
        return self.workpiece_manager.load_workpiece(workpiece)

    def initContour(self, contours_by_layer, close_contour=True):
        """Initialize contours - delegates to external manager"""
        return self.workpiece_manager.init_contour(contours_by_layer, close_contour)

    """ IMAGE HANDLING METHODS - Delegated to ViewportController """

    def load_image(self, path):
        return self.viewport_controller.load_image(path)

    def set_image(self, image):
        self.viewport_controller.set_image(image)

    def set_verification_contours(self, contours):
        self.verification_contours = list(contours or [])
        self.update()

    def clear_verification_contours(self):
        self.verification_contours = []
        self.update()

    def update_image(self, image_input):
        self.viewport_controller.update_image(image_input)

    """ SEGMENT MANAGEMENT METHODS """

    def delete_segment(self, seg_index):
        """Delete a segment - delegates to external manager"""
        self.segment_action_controller.delete_segment(seg_index)
        self.update()
        self.pointsUpdated.emit()

    def _handle_add_control_point(self, pos):
        """Smart segment click handling - shows overlay only if no control point exists"""
        return self.overlay_manager.handle_add_control_point(pos)

    def set_layer_visibility(self, layer_name, visible):
        """Set layer visibility - delegates to LayerManager"""
        self.layer_manager.set_layer_visibility(layer_name, visible)

    def is_point_selected(self, role, seg_index, point_index):
        """Check if a specific point is selected"""
        return self.selection_manager.is_point_selected(role, seg_index, point_index)

    def _show_point_info_on_hold(self):
        """Callback when press-and-hold timer fires - show point info overlay"""
        self.overlay_manager._show_point_info_on_hold()

    def open_settings_dialog(self):
        """Open the constants settings dialog (Ctrl+S)"""
        self.settings_manager.open_settings_dialog()

    def _reload_constants(self):
        """Reload constants that are cached as instance variables"""
        self.settings_manager.reload_constants()

    """ MOUSE EVENTS"""

    def mousePressEvent(self, event):
        self.event_manager.handle_mouse_press(event)

    def mouseDoubleClickEvent(self, event):
        self.event_manager.handle_mouse_double_click(event)

    def mouseMoveEvent(self, event):
        self.event_manager.handle_mouse_move(event)

    def mouseReleaseEvent(self, event):
        self.event_manager.handle_mouse_release(event)

    def wheelEvent(self, event):
        self.event_manager.handle_wheel(event)
        event.accept()  # Accept the event so Qt knows we handled it

    """ GESTURE EVENTS"""

    def event(self, event):
        # Safety check in case event_manager is not yet initialized
        if hasattr(self, 'event_manager'):
            handled = self.event_manager.handle_general_event(event)
            if handled:
                return True
        return super().event(event)

    def handle_gesture_event(self, event):
        return self.event_manager.handle_gesture_event(event)

    """ KEYBOARD EVENTS"""

    def perform_drag_update(self):
        """Throttled update callback for drag operations"""
        if self.mode_manager.drag_mode.pending_drag_update:
            self.update()
            self.mode_manager.drag_mode.pending_drag_update = False
        else:
            self.drag_timer.stop()

    def addNewSegment(self, layer_name=None):
        """Add new segment - delegates to external manager"""
        new_segment = self.segment_action_controller.add_new_segment(layer_name)
        self.update()
        self.pointsUpdated.emit()
        return  new_segment

    def paintEvent(self, event):
        painter = QPainter(self)
        self.renderer.render(painter, event)
        painter.end()


    def get_selected_points_count(self):
        """Get the number of currently selected points"""
        return len(self.selection_manager.selected_points_list)

    def save_robot_path_dict_to_txt(self, filename="robot_path_dict.txt", samples_per_segment=5):
        """Save robot path as dictionary - delegates to DataExportManager"""
        return self.data_export_manager.save_robot_path_dict_to_txt(filename, samples_per_segment)

    def save_robot_path_to_txt(self, filename="robot_path.txt", samples_per_segment=5):
        """Save robot path to text file - delegates to DataExportManager"""
        return self.data_export_manager.save_robot_path_to_txt(filename, samples_per_segment)

    def plot_robot_path(self, filename="robot_path.txt"):
        """Plot robot path - delegates to DataExportManager"""
        return self.data_export_manager.plot_robot_path(filename)

    def is_within_image(self, pos: QPointF) -> bool:
        return self.viewport_controller.is_within_image(pos)

    def set_layer_locked(self, layer_name, locked):
        """Set layer lock state - delegates to LayerManager"""
        self.layer_manager.set_layer_locked(layer_name, locked)

    def show_global_settings(self):
        self.settings_manager.show_global_settings()

    def reset_editor(self):
        """Reset editor - clear all segments and data"""
        # Clear all segments (domain-agnostic)
        self.manager.clear_all_segments()

        # Clear workpiece-specific data if workpiece_manager is available
        if self.workpiece_manager:
            self.workpiece_manager.clear_workpiece()

        # Clear selection and update UI
        self.selection_manager.clear_all_selections()
        self.update()
        self.pointsUpdated.emit()
