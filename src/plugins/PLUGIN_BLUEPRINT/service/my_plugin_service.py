"""
Step 4 — Concrete service adapter.

Implements IMyService by delegating to platform services
(ISettingsService, IRobotService, etc.).
This is the ONLY place that imports platform internals.
The plugin never sees ISettingsService directly.
"""
from src.plugins.PLUGIN_BLUEPRINT.service.i_my_service import IMyService


class MyPluginService(IMyService):

    def __init__(self, settings_service=None):
        self._settings = settings_service

    def get_value(self) -> str:
        if self._settings is None:
            return "default"
        return self._settings.get("my_setting_key")

    def save_value(self, value: str) -> None:
        if self._settings is not None:
            self._settings.save("my_setting_key", value)
