from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.calibration_settings.controller.calibration_settings_controller import (
    CalibrationSettingsController,
)
from src.applications.calibration_settings.model.calibration_settings_model import (
    CalibrationSettingsModel,
)
from src.applications.calibration_settings.service.i_calibration_settings_service import (
    ICalibrationSettingsService,
)
from src.applications.calibration_settings.view.calibration_settings_view import (
    CalibrationSettingsView,
)


class CalibrationSettingsFactory(ApplicationFactory):
    def __init__(self, work_area_definitions=None):
        self._work_area_ids = list(dict.fromkeys(
            str(getattr(definition, "id", "")).strip()
            for definition in (work_area_definitions or [])
            if str(getattr(definition, "id", "")).strip()
        ))

    def _create_model(self, service: ICalibrationSettingsService) -> CalibrationSettingsModel:
        return CalibrationSettingsModel(service)

    def _create_view(self) -> CalibrationSettingsView:
        return CalibrationSettingsView(work_area_ids=self._work_area_ids)

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        assert isinstance(model, CalibrationSettingsModel)
        assert isinstance(view, CalibrationSettingsView)
        return CalibrationSettingsController(model, view)
