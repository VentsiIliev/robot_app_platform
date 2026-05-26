from .base_command import Command
from ...core.event_bus import EventBus


class ToggleSegmentVisibilityCommand(Command):
    def __init__(self, manager, seg_index):
        super().__init__()
        self.manager = manager
        self.seg_index = seg_index
        self.old_visible = None
        self.new_visible = None

    def execute(self):
        if 0 <= self.seg_index < len(self.manager.segments):
            segment = self.manager.segments[self.seg_index]
            self.old_visible = segment.visible
            self.new_visible = not self.old_visible
            segment.visible = self.new_visible
            EventBus.get_instance().segment_visibility_changed.emit(
                self.seg_index, self.new_visible
            )
        self._executed = True

    def undo(self):
        if 0 <= self.seg_index < len(self.manager.segments):
            segment = self.manager.segments[self.seg_index]
            segment.visible = self.old_visible
            EventBus.get_instance().segment_visibility_changed.emit(
                self.seg_index, self.old_visible
            )

    def get_description(self):
        return f"Toggle visibility of segment {self.seg_index}"


class DeleteSegmentCommand(Command):
    def __init__(self, manager, seg_index):
        super().__init__()
        self.manager = manager
        self.seg_index = seg_index
        self.deleted_segment = None

    def execute(self):
        if 0 <= self.seg_index < len(self.manager.segments):
            self.deleted_segment = self.manager.segments[self.seg_index]
            self.manager.delete_segment(self.seg_index)
            EventBus.get_instance().segment_deleted.emit(self.seg_index)
        self._executed = True

    def undo(self):
        if self.deleted_segment:
            self.manager.segments.insert(self.seg_index, self.deleted_segment)
            EventBus.get_instance().segment_added.emit(self.seg_index)

    def get_description(self):
        return f"Delete segment {self.seg_index}"


class AddSegmentCommand(Command):
    def __init__(self, manager, layer_name=None):
        super().__init__()
        self.manager = manager
        self.layer_name = (
            layer_name
            or (
                manager.layer_config.default_segment_layer_name()
                if hasattr(manager, "layer_config")
                else "Contour"
            )
        )
        self.seg_index = None
        self.created_segment = None

    def execute(self):
        self.created_segment, success = self.manager.start_new_segment(self.layer_name)
        if success:
            self.seg_index = len(self.manager.segments) - 1
            EventBus.get_instance().segment_added.emit(self.seg_index)
        self._executed = True

    def undo(self):
        if self.seg_index is not None and self.seg_index < len(self.manager.segments):
            del self.manager.segments[self.seg_index]
            EventBus.get_instance().segment_deleted.emit(self.seg_index)

    def get_description(self):
        return f"Add segment to {self.layer_name}"


class ChangeSegmentLayerCommand(Command):
    def __init__(self, manager, seg_index, new_layer_name):
        super().__init__()
        self.manager = manager
        self.seg_index = seg_index
        self.new_layer_name = new_layer_name
        self.old_layer_name = None

    def execute(self):
        if 0 <= self.seg_index < len(self.manager.segments):
            segment = self.manager.segments[self.seg_index]
            self.old_layer_name = segment.layer.name if segment.layer else None
            self.manager.assign_segment_layer(self.seg_index, self.new_layer_name)
            EventBus.get_instance().segment_layer_changed.emit(
                self.seg_index, self.new_layer_name
            )
        self._executed = True

    def undo(self):
        if self.old_layer_name and 0 <= self.seg_index < len(self.manager.segments):
            self.manager.assign_segment_layer(self.seg_index, self.old_layer_name)
            EventBus.get_instance().segment_layer_changed.emit(
                self.seg_index, self.old_layer_name
            )

    def get_description(self):
        return f"Change segment {self.seg_index} layer to {self.new_layer_name}"
