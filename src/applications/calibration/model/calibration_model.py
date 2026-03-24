from src.applications.base.i_application_model import IApplicationModel
from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.shared_contracts.declarations import WorkAreaDefinition


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

    def measure_marker_heights(self) -> tuple[bool, str]:
        return self._service.measure_marker_heights()

    def get_work_area_definitions(self) -> list[WorkAreaDefinition]:
        return self._service.get_work_area_definitions()

    def get_active_work_area_id(self) -> str:
        return self._service.get_active_work_area_id()

    def set_active_work_area_id(self, area_id: str) -> None:
        self._service.set_active_work_area_id(area_id)

    def save_height_mapping_area(self, area_key: str, corners_norm) -> tuple[bool, str]:
        return self._service.save_height_mapping_area(area_key, corners_norm)

    def get_height_mapping_area(self, area_key: str) -> list[tuple[float, float]]:
        return self._service.get_height_mapping_area(area_key)

    def generate_area_grid(
        self,
        corners_norm,
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]:
        return self._service.generate_area_grid(corners_norm, rows, cols)

    def measure_area_grid(
        self,
        area_id: str,
        corners_norm,
        rows: int,
        cols: int,
    ) -> tuple[bool, str]:
        return self._service.measure_area_grid(area_id, corners_norm, rows, cols)

    def verify_area_grid(
        self,
        corners_norm,
        rows: int,
        cols: int,
        progress_callback=None,
    ) -> tuple[bool, str, dict]:
        return self._service.verify_area_grid(
            corners_norm,
            rows,
            cols,
            progress_callback=progress_callback,
        )

    def stop_marker_height_measurement(self) -> None:
        self._service.stop_marker_height_measurement()

    def can_measure_marker_heights(self) -> bool:
        return self._service.can_measure_marker_heights()

    def verify_height_model(self, area_id: str = "") -> tuple[bool, str]:
        return self._service.verify_height_model(area_id)

    def get_height_calibration_data(self, area_id: str = ""):
        return self._service.get_height_calibration_data(area_id)

    def has_saved_height_model(self, area_id: str = "") -> bool:
        return self._service.has_saved_height_model(area_id)

    def restore_pending_safety_walls(self) -> bool:
        return self._service.restore_pending_safety_walls()
