from PyQt6.QtGui import QIcon
from ....persistence.providers.icon_provider import IconProvider


class SegmentActions:
    """Command-based actions for segments: delete, add, visibility, layer, active state."""

    def __init__(self, contour_editor, event_bus, command_history, list_widget, segment_service=None):
        self.contour_editor = contour_editor
        self.event_bus = event_bus
        self.command_history = command_history
        self.list_widget = list_widget
        self.segment_service = segment_service

    def delete_segment(self, seg_index):
        """Delete a segment using Command Pattern"""
        if self.segment_service:
            self.segment_service.delete_segment(seg_index)
        elif self.contour_editor:
            from contour_editor.services.commands import DeleteSegmentCommand

            cmd = DeleteSegmentCommand(
                self.contour_editor.manager,
                seg_index
            )
            self.command_history.execute(cmd)

    def assign_segment_layer(self, seg_index, layer_name):
        """Assign a segment to a different layer using Command Pattern"""
        if self.segment_service:
            self.segment_service.change_layer(seg_index, layer_name)
        elif self.contour_editor:
            from contour_editor.services.commands import ChangeSegmentLayerCommand

            cmd = ChangeSegmentLayerCommand(
                self.contour_editor.manager,
                seg_index,
                layer_name
            )
            self.command_history.execute(cmd)

    def set_layer_visibility(self, layer_name, visible):
        """Set the visibility of a layer"""
        print(f"[ContourEditor] Set {layer_name} visibility to {visible}")
        if self.segment_service:
            self.segment_service.set_layer_visibility(layer_name, visible)
        elif self.contour_editor:
            self.contour_editor.set_layer_visibility(layer_name, visible)

    def make_add_segment(self, layer_name, expanded_layers):
        """Create an add segment callback for a layer"""

        def add_segment():
            if self.segment_service:
                self.segment_service.add_segment(layer_name)
            else:
                from contour_editor.services.commands import AddSegmentCommand

                cmd = AddSegmentCommand(
                    self.contour_editor.manager,
                    layer_name
                )
                self.command_history.execute(cmd)

            expanded_layers.add(layer_name)

        return add_segment

    def make_layer_lock_toggle(self, layer_name):
        """Create a lock toggle callback for a layer"""

        def toggle_lock(locked):
            if self.segment_service:
                self.segment_service.set_layer_locked(layer_name, locked)
            elif self.contour_editor:
                self.contour_editor.set_layer_locked(layer_name, locked)
                self.contour_editor.update()
            print(f"[ContourEditor] Set {layer_name} locked = {locked}")

        return toggle_lock

    def set_active_segment_ui(self, seg_index):
        """Update UI to reflect the active segment"""
        if self.segment_service:
            self.segment_service.set_active_segment(seg_index)
        else:
            self.contour_editor.manager.set_active_segment(seg_index)
            self.event_bus.active_segment_changed.emit(seg_index)

        # Update all segment active buttons
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item_data = item.data(256)  # Qt.ItemDataRole.UserRole

            if item_data and item_data.item_type == 'segment':
                is_active = item_data.seg_index == seg_index

                # Get the item widget (IndentedWidget)
                indented_widget = self.list_widget.itemWidget(item)
                if indented_widget:
                    # Navigate: IndentedWidget -> ExpandableSegmentWidget -> SegmentButtonsAndComboWidget
                    expandable_segment = indented_widget.layout().itemAt(0).widget()
                    if expandable_segment and hasattr(expandable_segment, 'layout'):
                        # Get the SegmentButtonsAndComboWidget (second item in layout, after expand button)
                        segment_buttons_widget = expandable_segment.layout().itemAt(1).widget()
                        if segment_buttons_widget:
                            # Find the active button specifically
                            active_btn = getattr(segment_buttons_widget, 'active_btn', None)
                            if active_btn:
                                print(
                                    f"Updating active button for segment {item_data.seg_index}, is_active: {is_active}")
                                active_btn.setIcon(QIcon(ACTIVE_ICON if is_active else INACTIVE_ICON))
                            index_label = getattr(segment_buttons_widget, 'index_label', None)

                            if index_label:
                                if is_active:
                                    index_label.setText(f"S{item_data.seg_index}")
                                    index_label.setStyleSheet("""
                                        QPushButton {
                                            background-color: #7E6DAD;
                                            color: white;
                                            border-radius: 15px;
                                            font-weight: bold;
                                            text-align: center;
                                            padding: 0px;
                                            min-width: 50px;
                                            min-height: 50px;
                                            max-width: 50px;
                                            max-height: 50px;
                                        }
                                    """)
                                else:
                                    index_label.setText(f"S{item_data.seg_index}")
                                    index_label.setStyleSheet("""
                                        QPushButton {
                                            background-color: #f0f0f0;
                                            color: #666;
                                            border-radius: 15px;
                                            font-weight: normal;
                                            text-align: center;
                                            padding: 0px;
                                            border: 1px solid #ddd;
                                            min-width: 50px;
                                            min-height: 50px;
                                            max-width: 50px;
                                            max-height: 50px;
                                        }
                                    """)
        self.list_widget.viewport().update()
        if self.contour_editor:
            self.contour_editor.update()
