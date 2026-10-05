from src.applications.base.application_factory import ApplicationFactory
from src.applications.network_settings.controller.network_settings_controller import NetworkSettingsController
from src.applications.network_settings.model.network_settings_model import NetworkSettingsModel
from src.applications.network_settings.view.network_settings_view import NetworkSettingsView


class NetworkSettingsFactory(ApplicationFactory):
    def _create_model(self, service): return NetworkSettingsModel(service)
    def _create_view(self): return NetworkSettingsView()
    def _create_controller(self, model, view): return NetworkSettingsController(model, view)
