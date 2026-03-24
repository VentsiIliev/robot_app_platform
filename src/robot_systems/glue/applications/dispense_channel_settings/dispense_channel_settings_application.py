from src.applications.base.widget_application import WidgetApplication
from src.robot_systems.glue.applications.dispense_channel_settings.dispense_channel_settings_factory import (
    DispenseChannelSettingsFactory,
)
from src.robot_systems.glue.applications.dispense_channel_settings.service.i_dispense_channel_settings_service import (
    IDispenseChannelSettingsService,
)


class DispenseChannelSettingsApplication(WidgetApplication):
    def __init__(self, service: IDispenseChannelSettingsService):
        super().__init__(
            widget_factory=lambda ms: DispenseChannelSettingsFactory().build(service, ms)
        )
