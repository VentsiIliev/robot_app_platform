from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer
from src.engine.vision.frame_orientation import normalize_rotation


CameraDevice = int | str


@dataclass(frozen=True)
class CameraDeviceSpec:
    device: CameraDevice
    width: int = 1280
    height: int = 720
    required: bool = False
    flip_horizontal: bool = False
    flip_vertical: bool = False
    rotate_degrees: int = 0


@dataclass
class CameraDevicesConfig:
    cameras: dict[str, CameraDeviceSpec] = field(default_factory=dict)

    def get(self, role: str) -> CameraDeviceSpec | None:
        return self.cameras.get(role)


class CameraDevicesConfigSerializer(ISettingsSerializer[CameraDevicesConfig]):
    @property
    def settings_type(self) -> str:
        return "camera_devices"

    def get_default(self) -> CameraDevicesConfig:
        return CameraDevicesConfig(
            cameras={
                "primary_vision": CameraDeviceSpec(device=0, required=True),
            }
        )

    def to_dict(self, settings: CameraDevicesConfig) -> dict[str, Any]:
        return {
            "cameras": {
                role: {
                    "device": spec.device,
                    "width": spec.width,
                    "height": spec.height,
                    "required": spec.required,
                    "flip_horizontal": spec.flip_horizontal,
                    "flip_vertical": spec.flip_vertical,
                    "rotate_degrees": spec.rotate_degrees,
                }
                for role, spec in settings.cameras.items()
            }
        }

    def from_dict(self, data: dict[str, Any]) -> CameraDevicesConfig:
        raw_cameras = data.get("cameras", {})
        if not isinstance(raw_cameras, dict):
            raise ValueError("'cameras' must be an object keyed by camera role")

        cameras: dict[str, CameraDeviceSpec] = {}
        for raw_role, raw_spec in raw_cameras.items():
            role = str(raw_role).strip()
            if not role:
                raise ValueError("Camera role names must not be empty")
            if not isinstance(raw_spec, dict):
                raise ValueError(f"Camera role '{role}' must contain an object")

            device = raw_spec.get("device")
            if isinstance(device, bool) or not isinstance(device, (int, str)):
                raise ValueError(
                    f"Camera role '{role}' device must be an integer index or device path"
                )
            if isinstance(device, int) and device < 0:
                raise ValueError(f"Camera role '{role}' device index must be non-negative")
            if isinstance(device, str):
                device = device.strip()
                if not device:
                    raise ValueError(f"Camera role '{role}' device path must not be empty")

            width = int(raw_spec.get("width", 1280))
            height = int(raw_spec.get("height", 720))
            if width <= 0 or height <= 0:
                raise ValueError(f"Camera role '{role}' dimensions must be positive")

            for flag in ("flip_horizontal", "flip_vertical"):
                if not isinstance(raw_spec.get(flag, False), bool):
                    raise ValueError(f"Camera role '{role}' {flag} must be true or false")

            # Raises a role-less message on purpose: the allowed set is global.
            rotate_degrees = normalize_rotation(raw_spec.get("rotate_degrees", 0))

            cameras[role] = CameraDeviceSpec(
                device=device,
                width=width,
                height=height,
                required=bool(raw_spec.get("required", False)),
                flip_horizontal=raw_spec.get("flip_horizontal", False),
                flip_vertical=raw_spec.get("flip_vertical", False),
                rotate_degrees=rotate_degrees,
            )
        return CameraDevicesConfig(cameras=cameras)
