from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.calibration.controller.calibration_controller import CalibrationController
from src.applications.calibration.model.calibration_model import CalibrationModel
from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.applications.calibration_v2.view.calibration_view import CalibrationView
from src.shared_contracts.declarations import WorkAreaDefinition


class CalibrationFactory(ApplicationFactory):
    def __init__(self, work_area_definitions: list[WorkAreaDefinition] | None = None):
        self._messaging = None
        self._work_area_definitions = list(work_area_definitions or [])

    def _create_model(self, service: ICalibrationService) -> CalibrationModel:
        return CalibrationModel(service)

    def _create_view(self) -> CalibrationView:
        return CalibrationView(work_area_definitions=self._work_area_definitions)

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        assert isinstance(model, CalibrationModel)
        assert isinstance(view, CalibrationView)
        return CalibrationController(model, view, self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)
