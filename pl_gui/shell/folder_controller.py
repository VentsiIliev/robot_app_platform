from dataclasses import dataclass
from typing import Optional
from PyQt6.QtCore import pyqtSignal, QTimer, QObject
from pl_gui.shell.ui.styles import OVERLAY_BG, OVERLAY_LIGHT, OVERLAY_SUBTLE, OVERLAY_FAINT


@dataclass
class FolderState:
    """Simple folder state data"""
    is_open: bool = False
    is_grayed_out: bool = False
    app_running: bool = False
    current_app_name: Optional[str] = None


class FolderController(QObject):
    """Handles all folder business logic and orchestration"""

    folder_opened = pyqtSignal()
    folder_closed = pyqtSignal()
    app_selected = pyqtSignal(str)
    close_current_app_signal = pyqtSignal()

    def __init__(self, folder_widget, main_window=None, ui_factory=None, parent=None):
        super().__init__(parent)
        self.folder_widget = folder_widget
        self.main_window = main_window

        # Business state
        self.state = FolderState()

        # Managers for complex operations - created via injected factory
        self.floating_icon_manager = ui_factory.create_floating_icon_manager(folder_widget)
        self.overlay_manager = ui_factory.create_overlay_manager(
            folder_widget, overlay_parent=self.main_window, overlay_callback=self.handle_outside_click
        )
        self.expanded_view_manager = ui_factory.create_expanded_view_manager(folder_widget)

        # Connect to UI events
        self.folder_widget.clicked.connect(self.handle_folder_click)

    def set_main_window(self, main_window):
        """Set main window reference"""
        self.main_window = main_window

    def handle_folder_click(self):
        """Handle folder click - business logic"""
        if self.state.is_grayed_out or self.state.app_running:
            return

        self.state.is_open = not self.state.is_open
        if self.state.is_open:
            try:
                self.open_folder()
            except Exception:
                import traceback
                traceback.print_exc()
                self.state.is_open = False
        else:
            self.close_folder()

    def open_folder(self):
        """Business logic for opening folder"""
        if not self.main_window:
            self.state.is_open = False
            return

        overlay = self.overlay_manager.show_overlay()
        if not overlay:
            self.state.is_open = False
            return

        expanded_view = self.expanded_view_manager.show_expanded_view(
            self.folder_widget.folder_name,
            overlay,
            self.close_folder,
            self.handle_app_selected,
            self.minimize_to_floating_icon,
            self.handle_close_app
        )
        self.expanded_view_manager.populate_apps(self.folder_widget.buttons)

        screen_center = self.main_window.rect().center()
        self.expanded_view_manager.fade_in(screen_center)

        self.folder_opened.emit()

    def handle_outside_click(self):
        """Handle clicking outside folder"""
        if self.state.current_app_name:
            self.minimize_to_floating_icon()
        else:
            self.close_folder()

    def minimize_to_floating_icon(self):
        """Business logic for minimizing to floating icon"""
        self.overlay_manager.hide_overlay()
        self.expanded_view_manager.fade_out()
        self.overlay_manager.set_style(f"background-color: {OVERLAY_FAINT};")
        self.floating_icon_manager.show_floating_icon(
            self.folder_widget.folder_name,
            self.restore_from_floating_icon
        )

    def restore_from_floating_icon(self):
        """Business logic for restoring from floating icon"""
        self.overlay_manager.show_overlay()
        self.floating_icon_manager.hide_floating_icon()
        self.overlay_manager.set_style(f"background-color: {OVERLAY_LIGHT};")

        if self.main_window:
            center = self.main_window.rect().center()
            self.expanded_view_manager.fade_in(center)

            if self.state.current_app_name:
                self.expanded_view_manager.show_close_button()

    def close_folder(self):
        """Business logic for closing folder"""
        if not self.state.current_app_name:
            self.state.app_running = False

        self.expanded_view_manager.fade_out()
        self.overlay_manager.hide_overlay()
        self.floating_icon_manager.hide_floating_icon()

        self.state.is_open = False
        self.state.current_app_name = None

        self.folder_closed.emit()

    def handle_app_selected(self, app_name):
        """Business logic for app selection"""
        self.state.app_running = True
        self.state.current_app_name = app_name

        self.app_selected.emit(app_name)

        self.expanded_view_manager.show_close_button()
        self.overlay_manager.set_style(f"background-color: {OVERLAY_SUBTLE};")
        self.overlay_manager.hide_overlay()
        QTimer.singleShot(300, self.minimize_to_floating_icon)

    def handle_close_app(self):
        """Business logic for closing app"""
        self.state.app_running = False
        self.state.current_app_name = None
        self.expanded_view_manager.hide_close_button()
        self.close_current_app_signal.emit()
        self.close_folder()

    def set_disabled(self, disabled):
        """Update business and UI state"""
        self.state.is_grayed_out = disabled
        self.folder_widget.set_grayed_out(disabled)
        self.folder_widget.setVisible(not disabled)
