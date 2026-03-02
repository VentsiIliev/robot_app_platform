from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.broker_debug.controller.broker_debug_controller import BrokerDebugController
from src.applications.broker_debug.model.broker_debug_model import BrokerDebugModel
from src.applications.broker_debug.service.i_broker_debug_service import IBrokerDebugService
from src.applications.broker_debug.view.broker_debug_view import BrokerDebugView
from src.engine.core.i_messaging_service import IMessagingService


class BrokerDebugFactory(ApplicationFactory):

    def __init__(self, messaging: IMessagingService):
        self._messaging = messaging

    def _create_model(self, service: IBrokerDebugService) -> BrokerDebugModel:
        return BrokerDebugModel(service)

    def _create_view(self) -> BrokerDebugView:
        return BrokerDebugView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        assert isinstance(model, BrokerDebugModel)
        assert isinstance(view, BrokerDebugView)
        return BrokerDebugController(model, view, self._messaging)