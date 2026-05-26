from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QMessageBox

from contour_editor.ui.new_widgets.SegmentSettingsWidget import SegmentSettingsWidget, get_default_settings, get_combo_field_key


class SettingsDialogHandler:
    """Handles segment settings dialogs and global settings updates."""

    def __init__(self, contour_editor, parent_widget, refresh_callback):
        self.contour_editor = contour_editor
        self.parent_widget = parent_widget
        self._refresh_callback = refresh_callback

    def on_settings_button_clicked(self, seg_index):
        """Handle settings button click for a segment"""
        segment = self.contour_editor.manager.get_segments()[seg_index]
        layer = getattr(segment, "layer", None)
        layer_name = layer.name if layer else "Unknown"
        print(f"Settings button clicked for segment {seg_index} (Layer: {layer_name})")
        self._show_settings_dialog(seg_index, segment)

    def _show_settings_dialog(self, seg_index, segment):
        from contour_editor.persistence.data.settings_provider_registry import SettingsProviderRegistry

        default_settings = get_default_settings()
        combo_key = get_combo_field_key()
        inputKeys = [k for k in default_settings.keys() if k != combo_key]

        # Get material/glue types from settings provider registry
        glue_type_names = []

        # Try to get from settings provider registry first
        provider = SettingsProviderRegistry.get_instance().get_provider()
        if provider:
            try:
                glue_type_names = provider.get_available_material_types()
                print(f"[SettingsDialogHandler] Loaded {len(glue_type_names)} material types from provider")
            except Exception as e:
                print(f"[SettingsDialogHandler] Warning: Could not get material types from provider: {e}")

        # Fall back to contour editor's settings manager if available
        if not glue_type_names and self.contour_editor and hasattr(self.contour_editor, 'settings_manager'):
            try:
                self.contour_editor.settings_manager._fetch_glue_types()
                glue_type_names = self.contour_editor.glue_type_names or []
            except Exception as e:
                print(f"[SettingsDialogHandler] Warning: Could not fetch glue types: {e}")

        if not glue_type_names:
            QMessageBox.information(
                self.parent_widget,
                "Settings Not Available",
                "Segment settings are not available in standalone mode.\n\n"
                "This feature requires connection to the application controller.\n"
                "Please configure a SettingsProvider before creating the editor.\n\n"
                "See API_USAGE.md for configuration examples.",
                QMessageBox.StandardButton.Ok
            )
            return

        comboEnums = [[combo_key, glue_type_names]] if combo_key else []

        # Create the settings widget
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        dialog = QDialog(parent=self.parent_widget)
        dialog.setWindowTitle(f"Segment {seg_index} Settings")
        dialog.setMinimumWidth(screen_width)
        dialog.setMinimumHeight(int(screen_height / 2))
        dialog.setMaximumHeight(int(screen_height / 2))

        print("Parent for settings dialog:", self.parent_widget)
        all_keys = inputKeys + ([combo_key] if combo_key else [])
        widget = SegmentSettingsWidget(all_keys, comboEnums, segment=segment,
                                       parent=self.parent_widget)
        widget.save_requested.connect(lambda: dialog.accept())
        layout = QVBoxLayout(dialog)
        layout.addWidget(widget)
        dialog.setLayout(layout)
        dialog.adjustSize()

        dialog.show()

    def update_all_segments_settings(self, settings):
        """Apply the given settings to all segments in the contour editor"""
        from contour_editor.services.settings_service import SettingsService

        service = SettingsService.get_instance()
        service.apply_to_all_segments(self.contour_editor.manager, settings)

        self._refresh_callback()
        self.contour_editor.update()
