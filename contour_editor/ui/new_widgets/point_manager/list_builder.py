from PyQt6.QtCore import Qt, QSize, QPointF
from PyQt6.QtWidgets import QListWidgetItem

from contour_editor.ui.new_widgets.LayerButtonsWidget import LayerButtonsWidget
from contour_editor.ui.new_widgets.SegmentButtonsAndComboWidget import SegmentButtonsAndComboWidget

from .models import ListItemData
from .list_item_widgets import (
    IndentedWidget,
    ExpandableLayerWidget,
    ExpandableSegmentWidget,
    PointWidget,
)


class ListBuilder:
    """Builds and manages the hierarchical list of layers, segments, and points."""

    def __init__(self, list_widget, contour_editor, segment_actions, settings_handler,
                 expanded_layers, expanded_segments,
                 on_layer_expand_toggle, on_segment_expand_toggle):
        self.list_widget = list_widget
        self.contour_editor = contour_editor
        self.segment_actions = segment_actions
        self.settings_handler = settings_handler
        self.expanded_layers = expanded_layers
        self.expanded_segments = expanded_segments
        self._on_layer_expand_toggle = on_layer_expand_toggle
        self._on_segment_expand_toggle = on_segment_expand_toggle

        self.layers = {}
        self.layer_items = {}
        self.segment_items = {}

    def initialize_list_structure(self):
        """Initialize the list structure with layer items"""
        self.list_widget.clear()
        self.layers = {}
        self.layer_items = {}
        self.expanded_layers.clear()
        self.expanded_layers.update(self.contour_editor.manager.get_available_layer_names())

        for name in self.contour_editor.manager.get_available_layer_names():
            self._create_layer_item(name)

    def rebuild_list(self):
        """Rebuild the entire list structure"""
        self.list_widget.clear()
        self.layer_items = {}
        self.segment_items = {}

        for layer_name in self.contour_editor.manager.get_available_layer_names():
            self._create_layer_item(layer_name)

            if layer_name in self.expanded_layers:
                self._add_segments_for_layer(layer_name)

    def _create_layer_item(self, name):
        """Create a layer item with proper configuration"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 80))

        item_data = ListItemData('layer', layer_name=name)
        item.setData(Qt.ItemDataRole.UserRole, item_data)

        is_locked = self.contour_editor.manager.isLayerLocked(name) if self.contour_editor else False
        layer_buttons = LayerButtonsWidget(
            layer_name=name,
            layer_item=item,
            on_visibility_toggle=lambda visible, n=name: self.segment_actions.set_layer_visibility(n, visible),
            on_add_segment=self.segment_actions.make_add_segment(name, self.expanded_layers),
            on_lock_toggle=self.segment_actions.make_layer_lock_toggle(name),
            is_locked=is_locked
        )

        expandable_widget = ExpandableLayerWidget(
            name,
            layer_buttons,
            self._on_layer_expand_toggle
        )

        is_expanded = name in self.expanded_layers
        expandable_widget.set_expanded(is_expanded)

        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, expandable_widget)

        self.layers[name] = item_data
        self.layer_items[name] = item

    def _add_segments_for_layer(self, layer_name):
        """Add segments for a specific layer"""
        if not self.contour_editor:
            return

        segments = self.contour_editor.manager.get_segments()

        for seg_index, segment in enumerate(segments):
            layer = getattr(segment, "layer")
            if layer is None or layer.name != layer_name:
                continue

            self._add_segment_item(seg_index, segment, layer_name)

            if seg_index in self.expanded_segments:
                self._add_points_for_segment(seg_index, segment)

    def _add_segment_item(self, seg_index, segment, layer_name):
        """Add a segment item to the list"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 100))

        item_data = ListItemData('segment', layer_name=layer_name, seg_index=seg_index)
        item.setData(Qt.ItemDataRole.UserRole, item_data)

        seg_container = self._create_segment_container(item, seg_index, segment, layer_name)

        expandable_widget = ExpandableSegmentWidget(
            seg_index,
            seg_container,
            self._on_segment_expand_toggle
        )

        is_expanded = seg_index in self.expanded_segments
        expandable_widget.set_expanded(is_expanded)

        indented_widget = IndentedWidget(expandable_widget, indent_level=1)

        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, indented_widget)

        self.segment_items[seg_index] = item

    def _add_points_for_segment(self, seg_index, segment):
        """Add point items for a specific segment"""
        for i, pt in enumerate(segment.points):
            coords = f"({pt.x():.1f}, {pt.y():.1f})" if isinstance(pt, QPointF) else "Invalid"
            self._add_point_item(f"P{i}", coords, seg_index, i, 'anchor')

        for i, ctrl in enumerate(segment.controls):
            coords = f"({ctrl.x():.1f}, {ctrl.y():.1f})" if isinstance(ctrl, QPointF) else "Invalid"
            self._add_point_item(f"C{i}", coords, seg_index, i, 'control')

    def _add_point_item(self, label, coordinates, seg_index, point_index, point_type):
        """Add a point item to the list"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 55))

        item_data = ListItemData('point', seg_index=seg_index, point_index=point_index, point_type=point_type)
        item.setData(Qt.ItemDataRole.UserRole, item_data)

        point_widget = PointWidget(label, coordinates)
        indented_widget = IndentedWidget(point_widget, indent_level=2)

        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, indented_widget)

    def _create_segment_container(self, seg_item, seg_index, segment, layer_name):
        def on_visibility(btn):
            if self.segment_actions.segment_service:
                self.segment_actions.segment_service.toggle_visibility(seg_index)
            else:
                from contour_editor.services.commands import ToggleSegmentVisibilityCommand
                cmd = ToggleSegmentVisibilityCommand(
                    self.contour_editor.manager,
                    seg_index
                )
                self.segment_actions.command_history.execute(cmd)

        def on_activate():
            self.segment_actions.set_active_segment_ui(seg_index)

        def on_delete():
            self.segment_actions.delete_segment(seg_index)

        def on_settings():
            self.settings_handler.on_settings_button_clicked(seg_index)

        def on_layer_change(new_layer_name):
            self.segment_actions.assign_segment_layer(seg_index, new_layer_name)

        def on_long_press(seg_index):
            print(f"Long press detected on segment {seg_index}!")

        return SegmentButtonsAndComboWidget(
            seg_index=seg_index,
            segment=segment,
            layer_name=layer_name,
            on_visibility=on_visibility,
            on_activate=on_activate,
            on_delete=on_delete,
            on_settings=on_settings,
            on_layer_change=on_layer_change,
            on_long_press=on_long_press,
            layer_options=self.contour_editor.manager.get_available_layer_names(),
        )
