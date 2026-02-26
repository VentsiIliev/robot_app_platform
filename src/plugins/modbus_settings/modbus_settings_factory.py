from __future__ import annotations

from src.plugins.base.i_plugin_controller import IPluginController
from src.plugins.base.i_plugin_model import IPluginModel
from src.plugins.base.i_plugin_view import IPluginView
from src.plugins.base.plugin_factory import PluginFactory
from src.plugins.modbus_settings.controller.modbus_settings_controller import ModbusSettingsController
from src.plugins.modbus_settings.model.modbus_settings_model import ModbusSettingsModel
from src.plugins.modbus_settings.service.i_modbus_settings_service import IModbusSettingsService
from src.plugins.modbus_settings.view.modbus_settings_view import ModbusSettingsView


class ModbusSettingsFactory(PluginFactory):

    def _create_model(self, service: IModbusSettingsService) -> IPluginModel:
        return ModbusSettingsModel(service)

    def _create_view(self) -> IPluginView:
        return ModbusSettingsView()

    def _create_controller(self, model: IPluginModel, view: IPluginView) -> IPluginController:
        return ModbusSettingsController(model, view)