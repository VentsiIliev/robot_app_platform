from __future__ import annotations

from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.application_factory import ApplicationFactory
from src.applications.modbus_settings.controller.modbus_settings_controller import ModbusSettingsController
from src.applications.modbus_settings.model.modbus_settings_model import ModbusSettingsModel
from src.applications.modbus_settings.service.i_modbus_settings_service import IModbusSettingsService
from src.applications.modbus_settings.view.modbus_settings_view import ModbusSettingsView


class ModbusSettingsFactory(ApplicationFactory):

    def _create_model(self, service) -> IApplicationModel:
        # not called directly — build() is overridden below
        raise NotImplementedError

    def _create_view(self) -> IApplicationView:
        return ModbusSettingsView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return ModbusSettingsController(model, view)

    def build(self, settings_service: IModbusSettingsService, action_service: IModbusActionService, messaging=None, jog_service=None):
        """Override — two services required instead of one."""
        model      = ModbusSettingsModel(settings_service, action_service)
        view       = self._create_view()
        controller = self._create_controller(model, view)
        return self._finalize_build(
            model=model,
            view=view,
            controller=controller,
            messaging=messaging,
            jog_service=jog_service,
        )
