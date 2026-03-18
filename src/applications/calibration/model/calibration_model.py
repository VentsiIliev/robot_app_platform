from src.applications.base.i_application_model import IApplicationModel
from src.applications.calibration.service.i_calibration_service import ICalibrationService


class CalibrationModel(IApplicationModel):

    def __init__(self, service: ICalibrationService):
        self._service = service

    def load(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        pass

    def capture_calibration_image(self) -> tuple[bool, str]:
        return self._service.capture_calibration_image()

    def calibrate_camera(self) -> tuple[bool, str]:
        return self._service.calibrate_camera()

    def calibrate_robot(self) -> tuple[bool, str]:
        return self._service.calibrate_robot()

    def calibrate_camera_and_robot(self) -> tuple[bool, str]:
        return self._service.calibrate_camera_and_robot()

    def calibrate_camera_tcp_offset(self) -> tuple[bool, str]:
        return self._service.calibrate_camera_tcp_offset()

    def stop_calibration(self) -> None:
        self._service.stop_calibration()

    def is_calibrated(self) -> bool:
        return self._service.is_calibrated()

    def test_calibration(self) -> tuple[bool, str]:
        return self._service.test_calibration()

    def stop_test_calibration(self) -> None:
        self._service.stop_test_calibration()

    def get_height_calibration_data(self):
        return self._service.get_height_calibration_data()
