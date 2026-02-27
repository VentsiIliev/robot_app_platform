import logging
from typing import Any, Dict, List, Optional

from pl_gui.shell.app_registry import build_app_registry
from src.engine.core.i_messaging_service import IMessagingService

_LOGGER = logging.getLogger("ApplicationLoader")


class _ApplicationManager:

    def __init__(self):
        self._applications: Dict[str, Any] = {}

    def register(self, name: str, application: Any, folder_id: int, icon: str = "fa5s.cog") -> None:
        application._json_metadata = {"folder_id": folder_id, "icon_str": icon}
        self._applications[name] = application
        _LOGGER.info("Registered application '%s' → folder %s", name, folder_id)

    def get_loaded_application_names(self) -> List[str]:
        return list(self._applications.keys())

    def get_application(self, name: str) -> Any:
        return self._applications.get(name)


class _WidgetFactory:

    def __init__(self, manager: _ApplicationManager):
        self._manager = manager

    def create_widget(self, app_name: str):
        from pl_gui.shell.base_app_widget.AppWidget import AppWidget

        application = self._manager.get_application(app_name)
        if application is None:
            _LOGGER.warning("No application found for '%s' — using fallback widget", app_name)
            return AppWidget(app_name=f"Placeholder ({app_name})")

        if hasattr(application, "create_widget"):
            return application.create_widget()

        _LOGGER.warning("Application '%s' has no create_widget() — using fallback", app_name)
        return AppWidget(app_name=app_name)


class ApplicationLoader:

    def __init__(self, messaging_service: IMessagingService):
        self._messaging_service  = messaging_service
        self._manager = _ApplicationManager()

    def load(
        self,
        application: Any,
        folder_id: int,
        icon: str = "fa5s.cog",
        name: Optional[str] = None,          # ← explicit name; falls back to class name
    ) -> 'ApplicationLoader':
        name = name or type(application).__name__
        try:
            if hasattr(application, "register"):
                application.register(self._messaging_service)
            self._manager.register(name, application, folder_id, icon)
        except Exception:
            _LOGGER.exception("Failed to load application: %s", name)
        return self

    def build_registry(self):
        factory = _WidgetFactory(self._manager)
        return build_app_registry(self._manager, factory)
