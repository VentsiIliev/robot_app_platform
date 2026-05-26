from .commands.segment_commands import (
    AddSegmentCommand,
    DeleteSegmentCommand,
    ToggleSegmentVisibilityCommand,
    ChangeSegmentLayerCommand
)


class SegmentService:
    def __init__(self, manager, command_history, event_bus):
        self.manager = manager
        self.command_history = command_history
        self.event_bus = event_bus

    def add_segment(self, layer_name=None):
        if layer_name is None and hasattr(self.manager, "layer_config"):
            layer_name = self.manager.layer_config.default_segment_layer_name()
        cmd = AddSegmentCommand(self.manager, layer_name)
        self.command_history.execute(cmd)
        return cmd.seg_index

    def delete_segment(self, seg_index):
        cmd = DeleteSegmentCommand(self.manager, seg_index)
        self.command_history.execute(cmd)

    def toggle_visibility(self, seg_index):
        cmd = ToggleSegmentVisibilityCommand(self.manager, seg_index)
        self.command_history.execute(cmd)

    def change_layer(self, seg_index, new_layer_name):
        cmd = ChangeSegmentLayerCommand(self.manager, seg_index, new_layer_name)
        self.command_history.execute(cmd)

    def add_control_point(self, seg_index, pos):
        return self.manager.add_control_point(seg_index, pos)

    def add_anchor_point(self, seg_index, pos):
        return self.manager.insert_anchor_point(seg_index, pos)

    def disconnect_line(self, pos, seg_index):
        segment_info = self.manager.find_segment_at(pos)
        if not segment_info:
            return False

        found_seg_index, line_index = segment_info

        if found_seg_index != seg_index:
            seg_index = found_seg_index

        result = self.manager.disconnect_line_segment(seg_index, line_index)
        return result

    def set_active_segment(self, seg_index):
        self.manager.set_active_segment(seg_index)
        self.event_bus.active_segment_changed.emit(seg_index)

    def set_layer_visibility(self, layer_name, visible):
        layer = self.manager._layer_for_name(layer_name) if hasattr(self.manager, "_layer_for_name") else None

        if layer is None:
            return

        layer.visible = visible

        for idx, segment in enumerate(self.manager.get_segments()):
            if hasattr(segment, 'layer') and segment.layer and segment.layer.name == layer_name:
                self.manager.set_segment_visibility(idx, visible)

        self.event_bus.points_changed.emit()

    def set_layer_locked(self, layer_name, locked):
        self.manager.set_layer_locked(layer_name, locked)
        self.event_bus.points_changed.emit()
