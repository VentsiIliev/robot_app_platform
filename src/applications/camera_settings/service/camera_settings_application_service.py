import logging
from pathlib import Path
from typing import Callable
from typing import List, Optional, Tuple
from src.applications.camera_settings.camera_settings_data import CameraSettingsData
from src.applications.camera_settings.mapper import CameraSettingsMapper
from src.applications.camera_settings.service.i_camera_settings_service import (
    CameraDeviceOption,
    CameraDevicesState,
    CameraOrientation,
    ICameraSettingsService,
)
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.vision.frame_orientation import normalize_rotation
from src.engine.vision.i_vision_service import IVisionService


class CameraSettingsApplicationService(ICameraSettingsService):

    def __init__(
        self,
        settings_service: ISettingsService,
        vision_service: IVisionService,
        work_area_service=None,
        camera_devices_settings_key=None,
        camera_orientation_setter: Callable[[str, bool, bool, int], None] | None = None,
    ):
        self._settings_service = settings_service
        self._vision_service   = vision_service
        self._work_area_service = work_area_service
        self._camera_devices_settings_key = camera_devices_settings_key
        self._camera_orientation_setter = camera_orientation_setter
        self._settings_id      = CommonSettingsID.VISION_CAMERA_SETTINGS
        self._logger           = logging.getLogger(self.__class__.__name__)
        self._hardware_auto_exposure: bool | None = None

    def load_settings(self) -> CameraSettingsData:
        raw = self._settings_service.get(self._settings_id)
        settings = CameraSettingsMapper.from_json(raw.data)
        self._hardware_auto_exposure = settings.hardware_auto_exposure
        return settings

    def save_settings(self, settings: CameraSettingsData) -> None:
        from src.engine.vision.camera_settings_serializer import CameraSettings
        data = CameraSettingsMapper.to_json(settings)
        try:
            existing = self._settings_service.get(self._settings_id)
            calibration_section = dict(existing.data.get("Calibration", {}))
            if calibration_section:
                data["Calibration"] = calibration_section
        except Exception:
            pass
        raw = CameraSettings(data=data)
        self._settings_service.save(self._settings_id, raw)
        self._vision_service.update_settings(data)
        requested_auto_exposure = bool(settings.hardware_auto_exposure)
        if requested_auto_exposure != self._hardware_auto_exposure:
            self._vision_service.set_auto_exposure(requested_auto_exposure)
            self._hardware_auto_exposure = requested_auto_exposure

    def set_raw_mode(self, enabled: bool) -> None:
        self._vision_service.set_raw_mode(enabled)

    def update_settings(self, settings: dict) -> tuple[bool, str]:
        return self._vision_service.update_settings(settings)

    def save_work_area(self, area_type: str, points: List[Tuple[float, float]]) -> tuple[bool, str]:
        if self._work_area_service is None:
            return False, "No work area service available"
        return self._work_area_service.save_work_area(area_type, points)

    def get_work_area(self, area_type: str) -> tuple[bool, str, List[Tuple[float, float]]]:
        if self._work_area_service is None:
            return False, "No work area service available", []
        result = self._work_area_service.get_work_area(area_type)
        if isinstance(result, tuple) and len(result) == 3:
            return result
        return True, "ok", list(result)

    def load_camera_devices(self) -> CameraDevicesState:
        if self._camera_devices_settings_key is None:
            return CameraDevicesState(assignments={}, options=())
        config = self._settings_service.get(self._camera_devices_settings_key)
        assignments = {
            role: str(spec.device)
            for role, spec in config.cameras.items()
        }
        discovered: dict[str, CameraDeviceOption] = {}
        for path in sorted(Path("/dev/v4l/by-path").glob("*-video-index0")):
            try:
                capture_node = str(path.resolve(strict=True))
            except OSError:
                continue
            discovered[str(path)] = CameraDeviceOption(
                device=str(path),
                capture_node=capture_node,
                connected=True,
            )
        for device in assignments.values():
            if device in discovered:
                continue
            path = Path(device)
            discovered[device] = CameraDeviceOption(
                device=device,
                capture_node=str(path.resolve()) if path.exists() else "",
                connected=path.exists(),
            )
        return CameraDevicesState(
            assignments=assignments,
            options=tuple(discovered.values()),
            orientation={
                role: CameraOrientation(
                    flip_horizontal=spec.flip_horizontal,
                    flip_vertical=spec.flip_vertical,
                    rotate_degrees=spec.rotate_degrees,
                )
                for role, spec in config.cameras.items()
            },
        )

    def save_camera_devices(
        self,
        assignments: dict[str, str],
        orientation: dict[str, CameraOrientation],
    ) -> None:
        if self._camera_devices_settings_key is None:
            raise RuntimeError("Camera device settings are not configured")
        from src.engine.vision.camera_device_settings import (
            CameraDeviceSpec,
            CameraDevicesConfig,
        )

        current = self._settings_service.get(self._camera_devices_settings_key)
        cameras = dict(current.cameras)
        for role, device in assignments.items():
            existing = cameras.get(role)
            requested = orientation.get(role)
            if requested is None:
                requested = (
                    CameraOrientation()
                    if existing is None
                    else CameraOrientation(
                        flip_horizontal=existing.flip_horizontal,
                        flip_vertical=existing.flip_vertical,
                        rotate_degrees=existing.rotate_degrees,
                    )
                )
            if not isinstance(requested.flip_horizontal, bool) or not isinstance(
                requested.flip_vertical, bool
            ):
                raise ValueError("Camera flip settings must be true or false")
            rotate_degrees = normalize_rotation(requested.rotate_degrees)
            if existing is None:
                cameras[role] = CameraDeviceSpec(
                    device=device,
                    flip_horizontal=requested.flip_horizontal,
                    flip_vertical=requested.flip_vertical,
                    rotate_degrees=rotate_degrees,
                )
            else:
                cameras[role] = CameraDeviceSpec(
                    device=device,
                    width=existing.width,
                    height=existing.height,
                    required=existing.required,
                    flip_horizontal=requested.flip_horizontal,
                    flip_vertical=requested.flip_vertical,
                    rotate_degrees=rotate_degrees,
                )
        self._settings_service.save(
            self._camera_devices_settings_key,
            CameraDevicesConfig(cameras=cameras),
        )
        if self._camera_orientation_setter is not None:
            for role, spec in cameras.items():
                self._camera_orientation_setter(
                    role,
                    spec.flip_horizontal,
                    spec.flip_vertical,
                    spec.rotate_degrees,
                )
