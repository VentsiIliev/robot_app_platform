import logging
from typing import Any, Dict, List, Optional

from pl_gui.shell.app_registry import build_app_registry
from src.engine.core.i_messaging_service import IMessagingService

_LOGGER = logging.getLogger("PluginLoader")


class _PluginManager:

    def __init__(self):
        self._plugins: Dict[str, Any] = {}

    def register(self, name: str, plugin: Any, folder_id: int, icon: str = "fa5s.cog") -> None:
        plugin._json_metadata = {"folder_id": folder_id, "icon_str": icon}
        self._plugins[name] = plugin
        _LOGGER.info("Registered plugin '%s' → folder %s", name, folder_id)

    def get_loaded_plugin_names(self) -> List[str]:
        return list(self._plugins.keys())

    def get_plugin(self, name: str) -> Any:
        return self._plugins.get(name)


class _WidgetFactory:

    def __init__(self, manager: _PluginManager):
        self._manager = manager

    def create_widget(self, app_name: str):
        from pl_gui.shell.base_app_widget.AppWidget import AppWidget

        plugin = self._manager.get_plugin(app_name)
        if plugin is None:
            _LOGGER.warning("No plugin found for '%s' — using fallback widget", app_name)
            return AppWidget(app_name=f"Placeholder ({app_name})")

        if hasattr(plugin, "create_widget"):
            return plugin.create_widget()

        _LOGGER.warning("Plugin '%s' has no create_widget() — using fallback", app_name)
        return AppWidget(app_name=app_name)


class PluginLoader:

    def __init__(self, messaging_service: IMessagingService):
        self._messaging_service  = messaging_service
        self._manager = _PluginManager()

    def load(
        self,
        plugin: Any,
        folder_id: int,
        icon: str = "fa5s.cog",
        name: Optional[str] = None,          # ← explicit name; falls back to class name
    ) -> 'PluginLoader':
        name = name or type(plugin).__name__
        try:
            if hasattr(plugin, "register"):
                plugin.register(self._messaging_service)
            self._manager.register(name, plugin, folder_id, icon)
        except Exception:
            _LOGGER.exception("Failed to load plugin: %s", name)
        return self

    def build_registry(self):
        factory = _WidgetFactory(self._manager)
        return build_app_registry(self._manager, factory)
