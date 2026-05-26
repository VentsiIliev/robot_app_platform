from PyQt6.QtCore import QPointF
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .editor import ContourEditor
class ViewportAPI:
    def __init__(self, controller):
        self._ctrl = controller
    def screen_to_image(self, screen_pos: QPointF) -> QPointF:
        from ..persistence.utils.coordinate_utils import map_to_image_space
        return map_to_image_space(screen_pos, self._ctrl.translation, self._ctrl.scale_factor)
    def image_to_screen(self, image_pos: QPointF) -> QPointF:
        return image_pos * self._ctrl.scale_factor + self._ctrl.translation
    def zoom_at_point(self, point: QPointF, factor: float):
        cursor_img_pos = self.screen_to_image(point)
        self._ctrl.scale_factor *= factor
        new_cursor_screen_pos = self.image_to_screen(cursor_img_pos)
        self._ctrl.translation += point - new_cursor_screen_pos
    def zoom_centered(self, factor: float, center_screen: QPointF):
        center_img_space = self.screen_to_image(center_screen)
        self._ctrl.scale_factor *= factor
        new_center_screen_pos = self.image_to_screen(center_img_space)
        self._ctrl.translation += center_screen - new_center_screen_pos
    def reset_zoom(self, frame_width: int, frame_height: int):
        self._ctrl.scale_factor = 1.0
        img_width = self._ctrl.image.width()
        img_height = self._ctrl.image.height()
        x = (frame_width - img_width) / 2
        y = (frame_height - img_height) / 2
        self._ctrl.translation = QPointF(x, y)
    @property
    def scale(self) -> float:
        return self._ctrl.scale_factor
    @scale.setter
    def scale(self, value: float):
        self._ctrl.scale_factor = value
    @property
    def translation(self) -> QPointF:
        return self._ctrl.translation
    @translation.setter
    def translation(self, value: QPointF):
        self._ctrl.translation = value
    @property
    def is_zooming(self) -> bool:
        return self._ctrl.is_zooming
class SelectionAPI:
    def __init__(self, manager):
        self._mgr = manager
    def clear(self):
        self._mgr.clear_all_selections()
    def is_selected(self, point_info):
        return self._mgr.is_point_selected(point_info)
    def toggle(self, point_info):
        self._mgr.toggle_point_selection(point_info)
    def add(self, point_info):
        self._mgr.add_selected_point(point_info)
class SegmentAPI:
    def __init__(self, manager):
        self._mgr = manager
    def all(self):
        return self._mgr.get_segments()
    def find_drag_targets(self, pos, threshold):
        return self._mgr.find_all_drag_targets(pos, threshold)
    def remove_control_point(self, pos):
        return self._mgr.remove_control_point_at(pos)
class ModeAPI:
    def __init__(self, editor):
        self._editor = editor
    @property
    def is_pan_active(self) -> bool:
        return self._editor.pan_mode_active
    @property
    def is_ruler_active(self) -> bool:
        return getattr(self._editor, 'ruler_mode_active', False)
    @property
    def is_rectangle_select_active(self) -> bool:
        return getattr(self._editor, 'rectangle_select_mode_active', False)
    @property
    def is_multi_select_active(self) -> bool:
        return self._editor.multi_select_mode_active
    @property
    def pan(self):
        return self._editor.pan_mode
    @property
    def ruler(self):
        return self._editor.ruler_mode
    @property
    def rectangle_select(self):
        return self._editor.rectangle_select_mode
    @property
    def multi_select(self):
        return self._editor.multi_select_mode
    @property
    def drag(self):
        return self._editor.drag_mode
class OverlayAPI:
    def __init__(self, editor):
        self._editor = editor
    def hide_point_info(self):
        if hasattr(self._editor, 'point_info_overlay'):
            self._editor.point_info_overlay.hide()
    def hide_segment_click(self):
        if hasattr(self._editor, 'segment_click_overlay'):
            self._editor.segment_click_overlay.hide()
    def is_point_info_visible(self) -> bool:
        return hasattr(self._editor, 'point_info_overlay') and self._editor.point_info_overlay.isVisible()
    def is_segment_click_visible(self) -> bool:
        return hasattr(self._editor, 'segment_click_overlay') and self._editor.segment_click_overlay.isVisible()
class EditorContext:
    def __init__(self, editor: 'ContourEditor'):
        self._editor = editor
        self._viewport = None
        self._selection = None
        self._segments = None
        self._mode = None
        self._overlay = None
    @property
    def viewport(self) -> ViewportAPI:
        if self._viewport is None:
            self._viewport = ViewportAPI(self._editor.viewport_controller)
        return self._viewport
    @property
    def selection(self) -> SelectionAPI:
        if self._selection is None:
            self._selection = SelectionAPI(self._editor.selection_manager)
        return self._selection
    @property
    def segments(self) -> SegmentAPI:
        if self._segments is None:
            self._segments = SegmentAPI(self._editor.manager)
        return self._segments
    @property
    def mode(self) -> ModeAPI:
        if self._mode is None:
            self._mode = ModeAPI(self._editor)
        return self._mode
    @property
    def overlay(self) -> OverlayAPI:
        if self._overlay is None:
            self._overlay = OverlayAPI(self._editor)
        return self._overlay
    @property
    def widget(self):
        return self._editor
    def update(self):
        self._editor.update()
    def is_within_image(self, pos: QPointF) -> bool:
        return self._editor.is_within_image(pos)
