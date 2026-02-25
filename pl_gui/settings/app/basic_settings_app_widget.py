from PyQt6.QtCore import pyqtSignal

from settings.settings_menu.build_showcase import build_settings_menu_showcase
from shell.base_app_widget.AppWidget import AppWidget


class BasicSettingsAppWidget(AppWidget):
    tab_changing = pyqtSignal(str, str)  # old_tab_id, new_tab_id
    tab_changed = pyqtSignal(str, str)   # old_tab_id, new_tab_id
    def __init__(self, parent=None):
        super().__init__("Settings", parent)  # AppWidget calls setup_ui() automatically

    # ------------------------------------------------------------------ #
    #  UI setup                                                            #
    # ------------------------------------------------------------------ #
    def setup_ui(self):
        from PyQt6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # self._settings_view = SettingsNavigationWidget()
        self._settings_view = build_settings_menu_showcase()
        layout.addWidget(self._settings_view)

        # Re-emit dashboard signals as this widget's own public signals
        self._settings_view.tab_changing.connect(self.tab_changing.emit)
        self._settings_view.tab_changed.connect(self.tab_changed.emit)