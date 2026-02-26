from PyQt6.QtCore import pyqtSignal, QEvent
from PyQt6.QtWidgets import QVBoxLayout

from pl_gui.settings.settings_view.settings_view import SettingsView
from src.plugins.base.i_plugin_view import IPluginView
from src.robot_apps.glue.glue_settings.model.mapper import GlueSettingsMapper
from src.robot_apps.glue.glue_settings.view.glue_settings_schema import (
    SPRAY_GROUP, PUMP_GROUP, GENERATOR_GROUP, TIMING_GROUP, RAMP_GROUP,
)
from src.robot_apps.glue.glue_settings.view.glue_type_tab import GlueTypeTab


class GlueSettingsView(IPluginView):
    """View — pure Qt widget. No services, no model, no business logic."""

    save_requested        = pyqtSignal(dict)
    spray_on_changed      = pyqtSignal(bool)            # auto-save — no Save press needed
    add_type_requested    = pyqtSignal(str, str)
    update_type_requested = pyqtSignal(str, str, str)
    remove_type_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("GlueSettings", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._glue_type_tab = GlueTypeTab()
        self._settings_view = SettingsView(
            component_name="GlueSettings",
            mapper=GlueSettingsMapper.to_flat_dict,
        )
        self._settings_view.add_tab("General",        [SPRAY_GROUP, PUMP_GROUP, GENERATOR_GROUP])
        self._settings_view.add_tab("Timing",         [TIMING_GROUP, RAMP_GROUP])
        self._settings_view.add_raw_tab("Glue Types", self._glue_type_tab)
        layout.addWidget(self._settings_view)

        # ✓ Named forwarders
        self._settings_view.save_requested.connect(self._on_inner_save)
        self._settings_view.value_changed_signal.connect(self._on_inner_value_changed)
        self._glue_type_tab.add_requested.connect(self._on_inner_add_type)
        self._glue_type_tab.update_requested.connect(self._on_inner_update_type)
        self._glue_type_tab.remove_requested.connect(self._on_inner_remove_type)

    # ── Named forwarders ─────────────────────────────────────────────────

    def _on_inner_save(self, values: dict) -> None:
        self.save_requested.emit(values)

    def _on_inner_value_changed(self, key: str, value, _component: str) -> None:
        if key == "spray_on":
            self.spray_on_changed.emit(bool(value))

    def _on_inner_add_type(self, name: str, desc: str)              -> None: self.add_type_requested.emit(name, desc)
    def _on_inner_update_type(self, id_: str, name: str, desc: str) -> None: self.update_type_requested.emit(id_, name, desc)
    def _on_inner_remove_type(self, id_: str)                       -> None: self.remove_type_requested.emit(id_)

    # ── Inbound setters ──────────────────────────────────────────────────

    def load_settings(self, settings) -> None:
        self._settings_view.load(settings)

    def load_glue_types(self, types: list) -> None:
        self._glue_type_tab.load_types(types)

    def get_values(self) -> dict:
        return self._settings_view.get_values()

    # ── AppWidget hooks ───────────────────────────────────────────────────

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass
