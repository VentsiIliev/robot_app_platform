from pl_gui.shell.ui.styles import OVERLAY_LIGHT
from ..overlay import FolderOverlay


class OverlayManager:
    """Handles overlay creation and styling"""

    def __init__(self, parent_widget, overlay_parent, overlay_callback):
        self.parent_widget = parent_widget
        self.overlay_parent = overlay_parent
        self.overlay = FolderOverlay(overlay_parent)
        self.overlay.mouse_pressed_outside.connect(overlay_callback)

    def show_overlay(self):
        """Create and show overlay"""
        try:
            self.overlay.resize(self.overlay_parent.size())
            self.overlay.setStyleSheet(f"background-color: {OVERLAY_LIGHT};")
            self.overlay.fade_in()
        except Exception:
            import traceback
            traceback.print_exc()
            return None
        return self.overlay

    def set_style(self, style):
        if self.overlay:
            self.overlay.setStyleSheet(style)

    def hide_overlay(self):
        if self.overlay:
            self.overlay.fade_out()
