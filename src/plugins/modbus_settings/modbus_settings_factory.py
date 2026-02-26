from __future__ import annotations

from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
from src.plugins.base.i_plugin_controller import IPluginController
from src.plugins.base.i_plugin_model import IPluginModel
from src.plugins.base.i_plugin_view import IPluginView
from src.plugins.base.plugin_factory import PluginFactory
from src.plugins.modbus_settings.controller.modbus_settings_controller import ModbusSettingsController
from src.plugins.modbus_settings.model.modbus_settings_model import ModbusSettingsModel
from src.plugins.modbus_settings.service.i_modbus_settings_service import IModbusSettingsService
from src.plugins.modbus_settings.view.modbus_settings_view import ModbusSettingsView


class ModbusSettingsFactory(PluginFactory):

    def _create_model(self, service) -> IPluginModel:
        # not called directly — build() is overridden below
        raise NotImplementedError

    def _create_view(self) -> IPluginView:
        return ModbusSettingsView()

    def _create_controller(self, model: IPluginModel, view: IPluginView) -> IPluginController:
        return ModbusSettingsController(model, view)

    def build(self, settings_service: IModbusSettingsService, action_service: IModbusActionService):
        """Override — two services required instead of one."""
        model      = ModbusSettingsModel(settings_service, action_service)
        view       = self._create_view()
        controller = self._create_controller(model, view)
        controller.load()
        view._controller = controller
        self._logger.debug(
            "%s built: %s / %s / %s",
            self.__class__.__name__,
            type(model).__name__,
            type(view).__name__,
            type(controller).__name__,
        )
        return view
