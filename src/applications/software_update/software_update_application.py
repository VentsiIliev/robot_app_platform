from src.applications.base.widget_application import WidgetApplication
from .software_update_factory import SoftwareUpdateFactory


class SoftwareUpdateApplication(WidgetApplication):
    def __init__(self, service):
        factory = SoftwareUpdateFactory()
        super().__init__(widget_factory=lambda _messaging: factory.build(service))
