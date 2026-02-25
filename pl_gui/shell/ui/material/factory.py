from .folder_widget import FolderWidget
from .managers.expanded_view_manager import ExpandedViewManager
from .managers.floating_icon_manager import FloatingIconManager
from .managers.overlay_manager import OverlayManager


class MaterialUIFactory:
    """Factory that creates Material Design 3 UI components (the existing implementation)."""

    def create_folder_widget(self, ID, folder_name):
        return FolderWidget(ID, folder_name)

    def create_expanded_view_manager(self, folder_widget):
        return ExpandedViewManager(folder_widget)

    def create_floating_icon_manager(self, folder_widget):
        return FloatingIconManager(folder_widget)

    def create_overlay_manager(self, folder_widget, overlay_parent, overlay_callback):
        return OverlayManager(folder_widget, overlay_parent, overlay_callback)
