from PyQt6.QtCore import Qt, QPointF
class MouseHandler:
    def __init__(self, context):
        self.ctx = context
    def handle_press(self, event):
        editor = self.ctx.widget
        if self.ctx.overlay.is_point_info_visible():
            self.ctx.selection.clear()
            self.ctx.overlay.hide_point_info()
            self.ctx.update()
            return
        if self.ctx.overlay.is_segment_click_visible():
            self.ctx.overlay.hide_segment_click()
            return
        if self.ctx.viewport.is_zooming:
            editor.last_drag_pos = event.position()
            return
        if self.ctx.mode.is_pan_active:
            self.ctx.mode.pan.mousePress(editor, event)
            return
        if not self.ctx.is_within_image(event.position()):
            print(f"Position out of image: {event.position()}")
            return
        pos = self.ctx.viewport.screen_to_image(event.position())
        min_px_hit = 10
        hit_radius_img = min_px_hit / self.ctx.viewport.scale
        print("Mouse pressed at image coords:", pos)
        if self.ctx.mode.is_ruler_active:
            self.ctx.mode.ruler.mousePress(editor, event)
            return
        if event.button() == Qt.MouseButton.RightButton:
            if self.ctx.segments.remove_control_point(pos):
                editor.handle_right_mouse_click(editor)
                return
        elif event.button() == Qt.MouseButton.LeftButton:
            if self.ctx.mode.is_rectangle_select_active:
                self.ctx.mode.rectangle_select.mousePress(editor, event)
                return
            if editor.pickup_point_mode_active:
                editor.pickup_point = pos
                print(f"Pickup point set at: {pos}")
                self.ctx.update()
                return
            candidates = self.ctx.segments.find_drag_targets(pos, hit_radius_img)
            if candidates:
                if self.ctx.mode.is_multi_select_active:
                    self.ctx.mode.multi_select.mousePress(editor, event, candidates)
                    self.ctx.update()
                    return
                drag_target = candidates[0]
                self.ctx.mode.drag.mousePress(editor, event, drag_target)
                print(f"Dragging existing point (PointDragMode): {drag_target}")
                editor.press_hold_start_pos = event.position()
                editor.point_info_timer.start()
                return
            else:
                if self.ctx.mode.is_multi_select_active:
                    print("Multi-select mode: clicked empty space, no point added")
                    return
                result = editor._handle_add_control_point(pos)
                if result:
                    print(f"Added control point at {pos}")
                    return
            self.ctx.selection.clear()
            result = editor._handle_add_control_point(pos)
            if result:
                print(f"_handle_add_control_point return result: {result}")
                return
            editor.manager.add_point(pos)
            self.ctx.update()
            editor.pointsUpdated.emit()
    def handle_move(self, event):
        editor = self.ctx.widget
        editor.current_cursor_pos = event.position()
        if editor.point_info_timer.isActive() and editor.press_hold_start_pos is not None:
            dx = event.position().x() - editor.press_hold_start_pos.x()
            dy = event.position().y() - editor.press_hold_start_pos.y()
            distance = (dx * dx + dy * dy) ** 0.5
            if distance > 5:
                editor.point_info_timer.stop()
                editor.press_hold_start_pos = None
        if getattr(editor, 'magnifier_active', False):
            if self.ctx.mode.drag.dragging_point:
                crosshair_offset_y = -50
                crosshair_screen_pos = QPointF(
                    event.position().x(),
                    event.position().y() + crosshair_offset_y
                )
                image_pos = self.ctx.viewport.screen_to_image(crosshair_screen_pos)
                editor.magnifier.update_position(crosshair_screen_pos, image_pos)
            else:
                screen_pos = event.position()
                image_pos = self.ctx.viewport.screen_to_image(screen_pos)
                editor.magnifier.update_position(screen_pos, image_pos)
        if self.ctx.mode.is_rectangle_select_active:
            self.ctx.mode.rectangle_select.mouseMove(editor, event)
            return
        if self.ctx.mode.is_ruler_active and self.ctx.mode.ruler.dragging_ruler_point:
            self.ctx.mode.ruler.mouseMove(editor, event)
            return
        if self.ctx.mode.drag.dragging_point:
            self.ctx.mode.drag.mouseMove(editor, event)
            return
        if self.ctx.mode.is_pan_active:
            self.ctx.mode.pan.mouseMove(editor, event)
            return
    def handle_double_click(self, event):
        editor = self.ctx.widget
        pos = event.position()
        target = editor.manager.find_drag_target(pos)
        if target and target[0] == 'control':
            role, seg_index, ctrl_idx = target
            editor.manager.reset_control_point(seg_index, ctrl_idx)
            self.ctx.update()
            editor.pointsUpdated.emit()
    def handle_release(self, event):
        editor = self.ctx.widget
        if editor.point_info_timer.isActive():
            editor.point_info_timer.stop()
        editor.press_hold_start_pos = None
        if self.ctx.mode.is_rectangle_select_active:
            self.ctx.mode.rectangle_select.mouseRelease(editor, event)
            return
        if self.ctx.mode.is_ruler_active:
            self.ctx.mode.ruler.mouseRelease()
        self.ctx.mode.drag.mouseRelease()
        if self.ctx.viewport.is_zooming:
            editor.last_drag_pos = None
            self.ctx.update()
            return
        if self.ctx.mode.is_pan_active:
            editor.setCursor(Qt.CursorShape.OpenHandCursor)
            self.ctx.mode.pan.mouseRelease()
        self.ctx.update()
