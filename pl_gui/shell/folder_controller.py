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

        self.state = FolderState()
        self._veto_pending = False          # ← NEW

        self.floating_icon_manager = ui_factory.create_floating_icon_manager(folder_widget)
        self.overlay_manager = ui_factory.create_overlay_manager(
            folder_widget, overlay_parent=self.main_window, overlay_callback=self.handle_outside_click
        )
        self.expanded_view_manager = ui_factory.create_expanded_view_manager(folder_widget)

        self.folder_widget.clicked.connect(self.handle_folder_click)

    def set_main_window(self, main_window):
        self.main_window = main_window

    def handle_folder_click(self):
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
        if self.state.current_app_name:
            self.minimize_to_floating_icon()
        else:
            self.close_folder()

    def minimize_to_floating_icon(self):
        self.overlay_manager.hide_overlay()
        self.expanded_view_manager.fade_out()
        self.overlay_manager.set_style(f"background-color: {OVERLAY_FAINT};")
        self.floating_icon_manager.show_floating_icon(
            self.folder_widget.folder_name,
            self.restore_from_floating_icon
        )

    def restore_from_floating_icon(self):
        if self.state.current_app_name and self.main_window:
            app_widget = getattr(self.main_window, 'running_widgets', {}).get(self.state.current_app_name)
            if app_widget and hasattr(app_widget, 'can_close') and not app_widget.can_close():
                return  # warning shown by can_close(), floating icon stays visible

        self.overlay_manager.show_overlay()
        self.overlay_manager.set_style(f"background-color: {OVERLAY_LIGHT};")
        if self.main_window:
            center = self.main_window.rect().center()
            self.expanded_view_manager.fade_in(center)        # ← start expand first
            if self.state.current_app_name:
                self.expanded_view_manager.show_close_button()
        self.floating_icon_manager.hide_floating_icon()       # ← MOVED: hide AFTER fade_in starts

    def close_folder(self):
        # ── veto gate: absorb the close_requested fired after a vetoed handle_close_app ──
        if self._veto_pending:                                 # ← NEW
            self._veto_pending = False
            self.expanded_view_manager.show_close_button()    # restore the hidden close btn
            return

        if not self.state.current_app_name:
            self.state.app_running = False
        self.expanded_view_manager.fade_out()
        self.overlay_manager.hide_overlay()
        self.floating_icon_manager.hide_floating_icon()
        self.state.is_open = False
        self.state.current_app_name = None
        self.folder_closed.emit()

    def handle_app_selected(self, app_name):
        # Veto check: block navigating to a new app if the current one can't be closed
        if self.state.current_app_name and self.main_window:
            app_widget = getattr(self.main_window, 'running_widgets', {}).get(self.state.current_app_name)
            if app_widget and hasattr(app_widget, 'can_close') and not app_widget.can_close():
                return

        self.state.app_running = True
        self.state.current_app_name = app_name
        self.app_selected.emit(app_name)
        self.expanded_view_manager.show_close_button()
        self.overlay_manager.set_style(f"background-color: {OVERLAY_SUBTLE};")
        self.overlay_manager.hide_overlay()
        QTimer.singleShot(300, self.minimize_to_floating_icon)

    def handle_close_app(self):
        # ── veto check BEFORE any state mutation ──
        if self.main_window:                                   # ← NEW
            app_widget = getattr(self.main_window, 'running_widgets', {}).get(self.state.current_app_name)
            if app_widget and hasattr(app_widget, 'can_close') and not app_widget.can_close():
                self._veto_pending = True   # block the close_requested that fires next
                return

        self.state.app_running = False
        self.state.current_app_name = None
        self.expanded_view_manager.hide_close_button()
        self.close_current_app_signal.emit()
        self.close_folder()

    def set_disabled(self, disabled):
        self.state.is_grayed_out = disabled
        self.folder_widget.set_grayed_out(disabled)
        self.folder_widget.setVisible(not disabled)
