import logging
from typing import Any, Callable, Dict, List, Optional

from pl_gui.shell.app_registry import build_app_registry
from pl_gui.shell.app_descriptor import AppDescriptor
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.declarations.system_specs import ApplicationSpec

_LOGGER = logging.getLogger("ApplicationLoader")


class _ApplicationManager:

    def __init__(self):
        self._descriptors: Dict[str, AppDescriptor] = {}
        self._builders: Dict[str, Callable[[], Any]] = {}
        self._applications: Dict[str, Any] = {}

    def register_lazy(self, spec: ApplicationSpec, builder: Callable[[], Any]) -> None:
        self._descriptors[spec.name] = AppDescriptor(
            name=spec.name,
            icon_str=spec.icon,
            folder_id=spec.folder_id,
        )
        self._builders[spec.name] = builder
        _LOGGER.info("Registered lazy application '%s' → folder %s", spec.name, spec.folder_id)

    def get_loaded_application_names(self) -> List[str]:
        return list(self._descriptors.keys())

    def get_descriptors(self) -> List[AppDescriptor]:
        return list(self._descriptors.values())

    def get_application(self, name: str) -> Any:
        return self._applications.get(name)

    def get_or_create_application(self, name: str) -> Any:
        application = self._applications.get(name)
        if application is not None:
            return application

        builder = self._builders.get(name)
        if builder is None:
            return None

        application = builder()
        self._applications[name] = application
        return application


class _WidgetFactory:

    def __init__(self, manager: _ApplicationManager, messaging_service: IMessagingService):
        self._manager = manager
        self._messaging_service = messaging_service

    def create_widget(self, app_name: str):
        from pl_gui.shell.base_app_widget.AppWidget import AppWidget

        try:
            application = self._manager.get_or_create_application(app_name)
        except Exception:
            _LOGGER.exception("Failed to build application '%s' lazily", app_name)
            return AppWidget(app_name=f"Failed to load ({app_name})")

        if application is None:
            _LOGGER.warning("No application found for '%s' — using fallback widget", app_name)
            return AppWidget(app_name=f"Placeholder ({app_name})")

        try:
            if hasattr(application, "register") and not getattr(application, "_lazy_registered", False):
                application.register(self._messaging_service)
                application._lazy_registered = True

            if hasattr(application, "create_widget"):
                return application.create_widget()
        except Exception:
            _LOGGER.exception("Failed to create widget for application '%s'", app_name)
            return AppWidget(app_name=f"Failed to load ({app_name})")

        _LOGGER.warning("Application '%s' has no create_widget() — using fallback", app_name)
        return AppWidget(app_name=app_name)


class ApplicationLoader:

    def __init__(self, messaging_service: IMessagingService):
        self._messaging_service = messaging_service
        self._manager = _ApplicationManager()

    def register_spec(
        self,
        spec: ApplicationSpec,
        builder: Callable[[], Any],
    ) -> "ApplicationLoader":
        try:
            self._manager.register_lazy(spec, builder)
        except Exception:
            _LOGGER.exception("Failed to register lazy application: %s", spec.name)
        return self

    def build_registry(self):
        factory = _WidgetFactory(self._manager, self._messaging_service)
        return build_app_registry(self._manager, factory)
