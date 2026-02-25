from pl_gui.shell.ui.styles import QTA_ICON_COLOR
from ..menu_icon import MenuIcon


class ExpandedViewManager:
    """Handles expanded view creation and lifecycle"""

    def __init__(self, parent_widget):
        self.parent_widget = parent_widget
        self.expanded_view = None

    def show_expanded_view(self, folder_name, overlay_parent, on_close, on_app_selected, on_minimize, on_close_app):
        if self.expanded_view:
            self._cleanup()
        from ..expanded_view import ExpandedFolderView
        self.expanded_view = ExpandedFolderView(folder_name, overlay_parent)
        self.expanded_view.close_requested.connect(on_close)
        self.expanded_view.app_selected.connect(on_app_selected)
        self.expanded_view.minimize_requested.connect(on_minimize)
        self.expanded_view.close_current_app_requested.connect(on_close_app)
        return self.expanded_view

    def populate_apps(self, buttons):
        if not self.expanded_view:
            return

        cols = 4
        for i, button in enumerate(buttons):
            row, col = divmod(i, cols)
            button_copy = MenuIcon(button.icon_label, button.icon_path, button.icon_text, button.callback, qta_color=QTA_ICON_COLOR)
            button_copy.button_clicked.connect(self.expanded_view.on_app_clicked)
            self.expanded_view.add_app_icon(button_copy, row, col)

    def fade_in(self, center_pos):
        if self.expanded_view:
            self.expanded_view.fade_in(center_pos)

    def fade_out(self):
        if self.expanded_view:
            self.expanded_view.fade_out()

    def show_close_button(self):
        if self.expanded_view:
            self.expanded_view.show_close_app_button()

    def hide_close_button(self):
        if self.expanded_view:
            self.expanded_view.hide_close_app_button()

    def _cleanup(self):
        if self.expanded_view:
            try:
                self.expanded_view.close_requested.disconnect()
                self.expanded_view.app_selected.disconnect()
                self.expanded_view.minimize_requested.disconnect()
                self.expanded_view.close_current_app_requested.disconnect()
            except Exception:
                pass
            self.expanded_view.deleteLater()
            self.expanded_view = None
