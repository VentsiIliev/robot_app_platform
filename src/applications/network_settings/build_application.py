"""Reusable shell wiring for every robot system."""

from src.applications.base.widget_application import WidgetApplication
from .network_settings_factory import NetworkSettingsFactory
from .service.network_settings_service import NetworkSettingsService


def build_network_settings_application(_robot_system):
    service = NetworkSettingsService()
    factory = NetworkSettingsFactory()
    return WidgetApplication(widget_factory=lambda _messaging: factory.build(service))
