from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from ...persistence.config import constants
from ...persistence.config.constants_manager import ConstantsManager
from ...ui.new_widgets.ConstantsSettingsDialog import ConstantsSettingsDialog
from ...ui.new_widgets.GlobalSettingsDialog import GlobalSettingsDialog


class SettingsManager:
    def __init__(self, editor,glue_type_names):
        self.editor = editor
        self.glue_type_names = glue_type_names
        self.point_manager_widget = None  # Will be set later by parent

        # Load and apply initial settings
        self.load_initial_settings()
        
        # Setup settings-related UI
        self.setup_settings_shortcuts()
        
        # Initialize cached constants
        self.setup_cached_constants()
    
    def set_point_manager_widget(self, widget):
        """Set the point manager widget reference (called by parent ContourEditor)"""
        self.point_manager_widget = widget

    def load_initial_settings(self):
        """Load user settings from JSON and apply to constants"""
        settings = ConstantsManager.load_settings()
        ConstantsManager.apply_settings(settings)
    
    def setup_settings_shortcuts(self):
        """Setup keyboard shortcuts for settings"""
        # Settings dialog shortcut (Ctrl+S)
        self.settings_shortcut = QShortcut(QKeySequence("Ctrl+S"), self.editor)
        self.settings_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.settings_shortcut.activated.connect(self.open_settings_dialog)
        self.settings_shortcut.setEnabled(True)

        # Global settings shortcut (Ctrl+G)
        self.global_settings_shortcut = QShortcut(QKeySequence("Ctrl+G"), self.editor)
        self.global_settings_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.global_settings_shortcut.activated.connect(self.show_global_settings)
        self.global_settings_shortcut.setEnabled(True)

    def setup_cached_constants(self):
        """Initialize cached constants from the constants module"""
        self.handle_radius = constants.POINT_HANDLE_RADIUS
        self.handle_color = constants.POINT_HANDLE_COLOR
        self.handle_selected_color = constants.POINT_HANDLE_SELECTED_COLOR
        self.min_point_display_scale = constants.POINT_MIN_DISPLAY_SCALE
        self.cluster_distance_px = constants.CLUSTER_DISTANCE_PX
    
    def open_settings_dialog(self):
        """Open the constants settings dialog (Ctrl+S)"""

        dialog = ConstantsSettingsDialog(self.editor)
        result = dialog.show()

        if result == dialog.DialogCode.Accepted:
            print("Settings dialog closed with OK")
            # Note: Settings are already applied and reloaded by the dialog's apply_changes method
    
    def reload_constants(self):
        """Reload constants that are cached as instance variables"""
        # Reload the constants module to get updated values

        # Update cached instance variables
        self.handle_radius = constants.POINT_HANDLE_RADIUS
        self.handle_color = constants.POINT_HANDLE_COLOR
        self.handle_selected_color = constants.POINT_HANDLE_SELECTED_COLOR
        self.min_point_display_scale = constants.POINT_MIN_DISPLAY_SCALE
        self.cluster_distance_px = constants.CLUSTER_DISTANCE_PX

        # Update editor's cached values
        self.editor.handle_radius = self.handle_radius
        self.editor.handle_color = self.handle_color
        self.editor.handle_selected_color = self.handle_selected_color
        self.editor.min_point_display_scale = self.min_point_display_scale
        self.editor.cluster_distance_px = self.cluster_distance_px

        # Update timer intervals
        if hasattr(self.editor, 'drag_timer'):
            self.editor.drag_timer.setInterval(constants.DRAG_UPDATE_INTERVAL_MS)
        if hasattr(self.editor.overlay_manager, 'point_info_timer'):
            self.editor.overlay_manager.point_info_timer.setInterval(constants.POINT_INFO_HOLD_DURATION_MS)

        print("Reloaded cached constants in editor")

        # Trigger a repaint to show the changes
        self.editor.update()
    
    def show_global_settings(self):
        """Show the global settings dialog (Ctrl+G)"""
        from ...persistence.data.settings_provider_registry import SettingsProviderRegistry

        # Check settings provider is configured
        registry = SettingsProviderRegistry.get_instance()
        if not registry.has_provider():
            provider = None
        else:
            provider = registry.get_provider()
        if not provider:
            QMessageBox.information(
                self.editor,
                "Settings Not Available",
                "Global settings are not available in standalone mode.\n\n"
                "This feature requires connection to the application controller.\n"
                "Please configure a SettingsProvider before creating the editor.\n\n"
                "See API_USAGE.md for configuration examples.",
                QMessageBox.StandardButton.Ok
            )
            return

        # Get material types directly from the provider (authoritative source)
        try:
            material_types = provider.get_available_material_types()
            if material_types:
                self.glue_type_names = material_types
        except Exception as e:
            print(f"[SettingsManager] Warning: Could not fetch material types from provider: {e}")
            # Fallback: try signal-based fetch
            try:
                self._fetch_glue_types()
            except Exception as e2:
                print(f"[SettingsManager] Warning: Could not fetch glue types via signal: {e2}")

        if not self.glue_type_names:
            QMessageBox.information(
                self.editor,
                "Settings Not Available",
                "Global settings are not available: no material types could be loaded.\n\n"
                "Please ensure the settings provider is properly configured.",
                QMessageBox.StandardButton.Ok
            )
            return

        if not self.point_manager_widget:
            QMessageBox.information(
                self.editor,
                "Settings Not Available",
                "Global settings are not available: point manager widget is not initialized.",
                QMessageBox.StandardButton.Ok
            )
            return

        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        dialog = GlobalSettingsDialog(self.point_manager_widget, self.glue_type_names, parent=self.editor)
        dialog.setMinimumWidth(screen_width)
        dialog.setMinimumHeight(int(screen_height / 2))
        dialog.setMaximumHeight(int(screen_height / 2))
        dialog.adjustSize()
        dialog.show()

    def _fetch_glue_types(self):
        """Request glue types via signal - controller will handle the fetch and respond"""
        print("[SettingsManager] Requesting glue types via signal...")

        # Emit signal to request glue types from parent controller
        if hasattr(self.editor, 'fetch_glue_types_requested'):
            self.editor.fetch_glue_types_requested.emit()
            # Update local list from editor (will be populated by signal response)
            self.glue_type_names = self.editor.glue_type_names
            print(f"[SettingsManager] Current glue types count: {len(self.glue_type_names)}")
        else:
            raise RuntimeError("[SettingsManager] Editor does not have fetch_glue_types_requested signal")
