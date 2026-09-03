from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.device_control.controller.device_control_controller import DeviceControlController
from src.applications.device_control.model.device_control_model import DeviceControlModel
from src.applications.device_control.service.i_device_control_service import IDeviceControlService
from src.applications.device_control.view.device_control_view import DeviceControlView
from src.applications.device_control.dryer.controller import DryerControlController
from src.applications.device_control.dryer.model import DryerControlModel
from src.applications.device_control.dryer.view import DryerControlPanel


class DeviceControlFactory(ApplicationFactory):

    def __init__(self, dryer_control_service=None) -> None:
        self._dryer_control_service = dryer_control_service

    def _create_model(self, service: IDeviceControlService) -> IApplicationModel:
        return DeviceControlModel(service)

    def _create_view(self) -> IApplicationView:
        return DeviceControlView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        assert isinstance(model, DeviceControlModel)
        assert isinstance(view, DeviceControlView)
        dryer_controller = None
        dryer_view = None
        if self._dryer_control_service is not None:
            dryer_model = DryerControlModel(self._dryer_control_service)
            dryer_view = DryerControlPanel()
            dryer_controller = DryerControlController(dryer_model, dryer_view)
        return DeviceControlController(
            model,
            view,
            dryer_view=dryer_view,
            dryer_controller=dryer_controller,
        )
