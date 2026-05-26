class SegmentActionController:
    def __init__(self, bezier_manager, segment_service=None):
        self.bezier_manager = bezier_manager
        self.segment_service = segment_service

    def add_new_segment(self, layer_name=None):
        """Add a new segment"""
        print("New segment started.")
        if layer_name is None and hasattr(self.bezier_manager, "layer_config"):
            layer_name = self.bezier_manager.layer_config.default_segment_layer_name()
        new_segment, success = self.bezier_manager.start_new_segment(layer_name)

        if success:
            print(f"Current segments: {len(self.bezier_manager.get_segments())}")
            print(f"Active segment index: {self.bezier_manager.active_segment_index}")
        else:
            print(f"Failed to create new segment (layer may be locked)")

        return new_segment

    def on_disconnect_line_requested(self,pending_segment_click_pos,pending_segment_click_index):
        """Called when user clicks 'Disconnect Line' in the overlay"""
        if pending_segment_click_index is None or pending_segment_click_pos is None:
            return

        if self.segment_service:
            return self.segment_service.disconnect_line(pending_segment_click_pos, pending_segment_click_index)

        seg_index = pending_segment_click_index
        pos = pending_segment_click_pos

        segment_info = self.bezier_manager.find_segment_at(pos)
        if not segment_info:
            print("No segment line found at click position")
            return

        found_seg_index, line_index = segment_info

        if found_seg_index != seg_index:
            print(f"Warning: Found segment {found_seg_index} but expected {seg_index}")
            seg_index = found_seg_index

        result = self.bezier_manager.disconnect_line_segment(seg_index, line_index)
        return result

    def on_add_control_point_requested(self,pending_segment_click_pos,pending_segment_click_index):
        """Called when user clicks 'Add Control Point' in the overlay"""
        if pending_segment_click_pos is None or pending_segment_click_index is None:
            return

        if self.segment_service:
            return self.segment_service.add_control_point(pending_segment_click_index, pending_segment_click_pos)

        pos = pending_segment_click_pos
        seg_index = pending_segment_click_index

        segment = self.bezier_manager.get_segments()[seg_index]
        segment_info = self.bezier_manager.find_segment_at(pos)

        result = False
        if segment_info:
            _, line_index = segment_info

            result = self.bezier_manager.add_control_point(seg_index, pos)

        return result

    def on_delete_segment_requested(self,pending_segment_click_index):
        """Called when user clicks 'Delete Segment' in the overlay"""
        if pending_segment_click_index is None:
            return

        seg_index = pending_segment_click_index

        self.bezier_manager.delete_segment(seg_index)

    def on_add_anchor_point_requested(self,pending_segment_click_pos,pending_segment_click_index):
        """Called when user clicks 'Add Anchor Point' in the overlay"""
        if pending_segment_click_pos is None or pending_segment_click_index is None:
            return

        if self.segment_service:
            return self.segment_service.add_anchor_point(pending_segment_click_index, pending_segment_click_pos)

        pos = pending_segment_click_pos
        seg_index = pending_segment_click_index

        result = self.bezier_manager.insert_anchor_point(seg_index, pos)
        return result

    def delete_segment(self, seg_index):
        """Delete a segment"""
        self.bezier_manager.delete_segment(seg_index)
