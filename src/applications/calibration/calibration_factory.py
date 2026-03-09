from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.robot_jog_service import RobotJogService
from src.applications.calibration.controller.calibration_controller import CalibrationController
from src.applications.calibration.model.calibration_model import CalibrationModel
from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.applications.calibration.view.calibration_view import CalibrationView
from src.engine.core.i_messaging_service import IMessagingService


class CalibrationFactory(ApplicationFactory):

    def __init__(self, messaging: IMessagingService,jog_service: RobotJogService):
        self._messaging = messaging
        self._jog_service = jog_service

    def _create_model(self, service: ICalibrationService) -> CalibrationModel:
        return CalibrationModel(service)

    def _create_view(self) -> CalibrationView:
        return CalibrationView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        assert isinstance(model, CalibrationModel)
        assert isinstance(view, CalibrationView)
        return CalibrationController(model, view, self._messaging,self._jog_service)
