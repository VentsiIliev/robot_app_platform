from src.plugins.base.widget_plugin import WidgetPlugin
from src.engine.core.i_messaging_service import IMessagingService
from src.plugins.glue_cell_settings.glue_cell_settings_factory import GlueCellSettingsFactory
from src.plugins.glue_cell_settings.service.i_glue_cell_settings_service import IGlueCellSettingsService


class GlueCellSettingsPlugin(WidgetPlugin):

    def __init__(self, service: IGlueCellSettingsService):
        super().__init__(
            widget_factory=lambda ms: GlueCellSettingsFactory().build(service, ms)
        )