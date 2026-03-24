from __future__ import annotations

import logging
from typing import Dict, List, Optional

from src.applications.base.i_application_model import IApplicationModel
from src.shared_contracts.declarations import DispenseChannelDefinition
from src.robot_systems.glue.applications.dispense_channel_settings.service.i_dispense_channel_settings_service import (
    IDispenseChannelSettingsService,
)


class DispenseChannelSettingsModel(IApplicationModel):
    def __init__(self, service: IDispenseChannelSettingsService):
        self._service = service
        self._definitions: List[DispenseChannelDefinition] = []
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> List[DispenseChannelDefinition]:
        self._definitions = self._service.get_channel_definitions()
        return list(self._definitions)

    def get_channel_flat(self, channel_id: str) -> Optional[Dict]:
        return self._service.get_channel_flat(channel_id)

    def get_glue_type_choices(self) -> List[str]:
        return self._service.get_available_glue_types()

    def save(self, channel_id: str, flat: Dict) -> None:
        self._service.save_channel(channel_id, flat)
        self._logger.info("Channel %s saved", channel_id)

    def tare(self, channel_id: str) -> bool:
        return self._service.tare(channel_id)

    def start_pump_test(self, channel_id: str) -> bool:
        return self._service.start_pump_test(channel_id)

    def stop_pump_test(self, channel_id: str) -> bool:
        return self._service.stop_pump_test(channel_id)

    def get_channel_for_cell_id(self, cell_id: int) -> Optional[str]:
        for definition in self._definitions:
            if int(definition.weight_cell_id) == int(cell_id):
                return definition.id
        return None
