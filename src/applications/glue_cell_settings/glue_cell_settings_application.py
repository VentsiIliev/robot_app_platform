from src.applications.base.widget_application import WidgetApplication
from src.engine.core.i_messaging_service import IMessagingService
from src.applications.glue_cell_settings.glue_cell_settings_factory import GlueCellSettingsFactory
from src.applications.glue_cell_settings.service.i_glue_cell_settings_service import IGlueCellSettingsService


class GlueCellSettingsApplication(WidgetApplication):

    def __init__(self, service: IGlueCellSettingsService):
        super().__init__(
            widget_factory=lambda ms: GlueCellSettingsFactory().build(service, ms)
        )