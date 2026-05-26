from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget

from .segment_actions import SegmentActions
from .settings_dialog_handler import SettingsDialogHandler
from .models import ListItemData


class PointManagerCoordinator(QWidget):
    """
    Coordinates the point manager widgets and provides a unified interface.
    This orchestrator manages the single QListWidget and delegates to focused components.
    """
    point_selected_signal = pyqtSignal(dict)

    def __init__(self, contour_editor=None, parent=None):
        super().__init__()
        self.contour_editor = contour_editor
        self.parent_widget = parent

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(8, 8, 8, 8)
        self.layout().setSpacing(4)

        # Initialize EventBus and CommandHistory
        from contour_editor.core.event_bus import EventBus
        from contour_editor.services.commands import CommandHistory
        self.event_bus = EventBus.get_instance()
        self.command_history = CommandHistory.get_instance()

        # Single list widget for all items
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.itemClicked.connect(self._on_item_clicked)
        self.layout().addWidget(self.list)

        # Shared state
        self.expanded_layers = set()
        self.expanded_segments = set()

        # Create delegates
        segment_service = getattr(contour_editor, 'segment_service', None)
        self._segment_actions = SegmentActions(
            contour_editor, self.event_bus, self.command_history, self.list, segment_service
        )
        self._settings_handler = SettingsDialogHandler(
            contour_editor, self.parent_widget, self.refresh_points
        )

        # Import list builder for now (can be refactored further)
        from .list_builder import ListBuilder
        self._list_builder = ListBuilder(
            self.list, contour_editor, self._segment_actions, self._settings_handler,
            self.expanded_layers, self.expanded_segments,
            self._on_layer_expand_toggle, self._on_segment_expand_toggle
        )

        # Connect EventBus events
        self.event_bus.segment_visibility_changed.connect(lambda *_: self.refresh_points())
        self.event_bus.segment_deleted.connect(lambda *_: self.refresh_points())
        self.event_bus.segment_added.connect(lambda *_: self.refresh_points())
        self.event_bus.segment_layer_changed.connect(lambda *_: self.refresh_points())

        if self.contour_editor:
            self.contour_editor.pointsUpdated.connect(self.refresh_points)

        self._list_builder.initialize_list_structure()

    def refresh_points(self):
        """Refresh the points display in the list"""
        if not self.contour_editor:
            return

        # Save current state
        selected_item_data = None
        current_item = self.list.currentItem()
        if current_item:
            selected_item_data = current_item.data(Qt.ItemDataRole.UserRole)

        active_segment_index = getattr(self.contour_editor.manager, "active_segment_index", None)

        self._list_builder.rebuild_list()

        self._restore_selection(selected_item_data)

        if active_segment_index is not None:
            self._segment_actions.set_active_segment_ui(active_segment_index)

    def update_all_segments_settings(self, settings):
        """Apply settings to all segments (called by GlobalSettingsDialog)"""
        self._settings_handler.update_all_segments_settings(settings)

    def _on_layer_expand_toggle(self, layer_name, is_expanded):
        if is_expanded:
            self.expanded_layers.add(layer_name)
        else:
            self.expanded_layers.discard(layer_name)
        self.refresh_points()

    def _on_segment_expand_toggle(self, seg_index, is_expanded):
        if is_expanded:
            self.expanded_segments.add(seg_index)
        else:
            self.expanded_segments.discard(seg_index)
        self.refresh_points()

    def _on_item_clicked(self, item):
        """Handle point selection and highlighting"""
        if not item or not self.contour_editor:
            return

        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        if item_data.item_type == 'segment':
            self._segment_actions.set_active_segment_ui(item_data.seg_index)
        elif item_data.item_type == 'point':
            seg_index = item_data.seg_index
            point_index = item_data.point_index
            point_type = item_data.point_type

            if point_type == 'anchor':
                self.contour_editor.selected_point_info = ('anchor', seg_index, point_index)
            elif point_type == 'control':
                self.contour_editor.selected_point_info = ('control', seg_index, point_index)

            self._segment_actions.set_active_segment_ui(seg_index)
            self.point_selected_signal.emit({
                'role': point_type,
                'seg_index': seg_index,
                'point_index': point_index
            })

    def _restore_selection(self, selected_item_data):
        """Restore the selected item based on saved data"""
        if not selected_item_data:
            return

        for i in range(self.list.count()):
            item = self.list.item(i)
            item_data = item.data(Qt.ItemDataRole.UserRole)

            if self._items_match(item_data, selected_item_data):
                self.list.setCurrentItem(item)
                break

    @staticmethod
    def _items_match(item_data1, item_data2):
        """Check if two item data objects represent the same item"""
        if not item_data1 or not item_data2:
            return False
        if item_data1.item_type != item_data2.item_type:
            return False
        if item_data1.item_type == 'layer':
            return item_data1.layer_name == item_data2.layer_name
        elif item_data1.item_type == 'segment':
            return item_data1.seg_index == item_data2.seg_index
        elif item_data1.item_type == 'point':
            return (item_data1.seg_index == item_data2.seg_index and
                    item_data1.point_index == item_data2.point_index and
                    item_data1.point_type == item_data2.point_type)
        return False

    def get_current_selected_layer(self):
        """Get the currently selected layer name"""
        current_item = self.list.currentItem()
        if current_item:
            item_data = current_item.data(Qt.ItemDataRole.UserRole)
            if item_data and item_data.item_type == 'layer':
                return item_data.layer_name
        if hasattr(self.contour_editor.manager, "layer_config"):
            return self.contour_editor.manager.layer_config.default_segment_layer_name()
        return "Main"
