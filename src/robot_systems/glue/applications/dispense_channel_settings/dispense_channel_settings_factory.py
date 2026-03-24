from __future__ import annotations

import logging

from src.applications.base.application_factory import finalize_application_build
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.glue.applications.dispense_channel_settings.controller.dispense_channel_settings_controller import (
    DispenseChannelSettingsController,
)
from src.robot_systems.glue.applications.dispense_channel_settings.model.dispense_channel_settings_model import (
    DispenseChannelSettingsModel,
)
from src.robot_systems.glue.applications.dispense_channel_settings.service.i_dispense_channel_settings_service import (
    IDispenseChannelSettingsService,
)
from src.robot_systems.glue.applications.dispense_channel_settings.view.dispense_channel_settings_view import (
    DispenseChannelSettingsView,
)


class DispenseChannelSettingsFactory:
    _logger = logging.getLogger("DispenseChannelSettingsFactory")

    def build(self, service: IDispenseChannelSettingsService, messaging: IMessagingService, jog_service=None):
        channel_definitions = service.get_channel_definitions()
        glue_types = service.get_available_glue_types()
        model = DispenseChannelSettingsModel(service)
        view = DispenseChannelSettingsView(channel_definitions, glue_types)
        controller = DispenseChannelSettingsController(model, view, messaging)
        return finalize_application_build(
            logger=self._logger,
            factory_name=self.__class__.__name__,
            model=model,
            view=view,
            controller=controller,
            messaging=messaging,
            jog_service=jog_service,
        )
