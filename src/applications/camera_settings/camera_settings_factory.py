from src.applications.camera_settings.controller.camera_settings_controller import CameraSettingsController
from src.applications.camera_settings.model.camera_settings_model import CameraSettingsModel
from src.applications.camera_settings.service.i_camera_settings_service import ICameraSettingsService
from src.applications.camera_settings.view.camera_tab import camera_tab_factory
from src.engine.core.i_messaging_service import IMessagingService


class CameraSettingsFactory:

    def build(self, service: ICameraSettingsService, messaging: IMessagingService):
        from src.applications.camera_settings.mapper import CameraSettingsMapper
        view, _ = camera_tab_factory(mapper=CameraSettingsMapper)
        model      = CameraSettingsModel(service)
        controller = CameraSettingsController(model, view, messaging)
        controller.load()
        view._controller = controller
        return view