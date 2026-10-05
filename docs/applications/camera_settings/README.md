# `src/applications/camera_settings/` — Camera Settings

Configures the vision system camera: resolution, brightness, contour thresholds, preprocessing, and ArUco options. Persists camera settings via `ISettingsService` and pushes live camera-setting updates to the running `VisionSystem`.

Work-area ROI editing has been moved into the shared [Work Area Settings](/home/ilv/Desktop/robot_app_platform/docs/applications/work_area_settings/README.md) application.
Calibration-related settings have been moved into the shared [Calibration Settings](/home/ilv/Desktop/robot_app_platform/docs/applications/calibration_settings/README.md) application.

`CameraDevicesWidget(device_control_mode=True)` is the compact camera panel in
the paint system's Devices screen. It shows one role's assignment and orientation
controls beside its live preview, with a role selector, connection badge, and
zoom buttons. The normal Camera Settings presentation continues to use the
same widget without this mode. Camera assignment, orientation, preview, and
save signals still follow the shared camera controller and service.
The Devices presentation uses the shared `QToggle` switches for horizontal and
vertical flips and 90° counterclockwise/clockwise buttons for rotation. Rotation
wraps through 0°, 90°, 180°, and 270° and retains the same saved orientation
contract and recalibration warning.

This is intended to be the shared camera-settings application for any robot system that adopts the common vision contract:
- `CommonServiceID.VISION`
- `CommonSettingsID.VISION_CAMERA_SETTINGS`

---

## MVC Structure

```
camera_settings/
├── service/
│   ├── i_camera_settings_service.py          ← ICameraSettingsService (4 methods)
│   ├── stub_camera_settings_service.py        ← In-memory stub for standalone use
│   └── camera_settings_application_service.py ← Delegates to SettingsService + VisionSystem
├── model/
│   └── camera_settings_model.py               ← Load/save + raw-mode delegation
├── view/
│   ├── camera_settings_view.py                ← Tab container
│   ├── camera_tab.py                          ← Main camera settings panel
│   ├── camera_controls_widget.py              ← Live preview + contour overlay
│   └── camera_settings_schema.py              ← View field definitions
├── controller/
│   └── camera_settings_controller.py
├── camera_settings_data.py                    ← CameraSettingsData dataclass
├── mapper.py                                  ← CameraSettingsMapper.from_json() / to_json()
└── camera_settings_factory.py
```

---

## `ICameraSettingsService`

```python
class ICameraSettingsService(ABC):
    def load_settings(self) -> CameraSettingsData: ...
    def save_settings(self, settings: CameraSettingsData) -> None: ...
    def set_raw_mode(self, enabled: bool) -> None: ...
    def update_settings(self, settings: dict) -> tuple[bool, str]: ...
    def save_work_area(self, area_type, points) -> tuple[bool, str]: ...
    def get_work_area(self, area_type) -> tuple[bool, str, List[Tuple[float, float]]]: ...
    def load_camera_devices(self) -> CameraDevicesState: ...
    def save_camera_devices(self, state: CameraDevicesState) -> tuple[bool, str]: ...
```

---

## Per-camera orientation (`rotate_degrees`, flips)

Each camera device role (primary, auxiliary) carries its own orientation in the
`hardware/cameras.json` device file, edited from the Devices app:

| Field | Values | Notes |
|-------|--------|-------|
| `rotate_degrees` | `0`, `90`, `180`, `270` | Only multiples of 90 are accepted. Stored input is normalized into that set, so `360` → `0` and `-90` → `270` |
| `flip_horizontal` | bool | Applied after rotation |
| `flip_vertical` | bool | Applied after rotation |

The app-layer value object is a frozen `CameraOrientation` dataclass
(`i_camera_settings_service.py`); `CameraDevicesState` exposes it per role via
`orientation`, and `transposes_frame` reports whether the role swaps width/height.

Transform order is **rotate first, then flip**, implemented once in
`src/engine/vision/frame_orientation.py` (`VALID_ROTATION_DEGREES`,
`normalize_rotation`, `is_transposing`, `apply_orientation`).

Saving is applied live to every role through
`IVisionService.set_camera_orientation`, which reaches both capture paths:
- primary — `FrameGrabber`
- auxiliary — `CameraStreamPublisher`

Invalid values are rejected with
`"Camera rotation must be one of 0, 90, 180 or 270"`; `bool` is not accepted as an integer.

> **Calibration caveat:** `rotate_degrees` of `90` or `270` transposes the frame, so
> `VisionService.get_camera_width` / `get_camera_height` return swapped values. The stored
> camera intrinsics (`cameraMatrix`, `cameraDist`) and the undistort maps are **not**
> transformed to match, and work-area normalization still uses raw sensor dimensions.
> Re-run calibration after applying a transposing rotation. The Devices view shows a
> hint when any role uses `90` or `270`.

---

## `CameraSettingsApplicationService`

The live implementation. Constructed with `settings_service`, `vision_service`, an optional
`work_area_service`, an optional `camera_devices_settings_key`, and an optional
`camera_orientation_setter` callback:

- `load_settings()` — reads from `SettingsService` via `CommonSettingsID.VISION_CAMERA_SETTINGS`; falls back to defaults if not found
- `save_settings()` — persists via `SettingsService`
- `update_settings(dict)` — delegates to `vision_service.updateSettings(dict)`
- `set_raw_mode(bool)` — forwards directly to `vision_service.rawMode`
- `save_camera_devices()` — validates and normalizes every role, persists the device file, then pushes each role live through `camera_orientation_setter`

---

## `CameraSettingsModel`

Thin delegation layer for camera settings only.

The tabbed settings panels use the shared collapsible settings-view pattern:
- every schema group is collapsible
- groups are collapsed by default on load
- the brightness-control group follows the same behavior

---

## `CameraSettingsData`

Camera-only dataclass covering:

| Group | Fields |
|-------|--------|
| Resolution | `width`, `height` |
| Camera | `camera_index`, `skip_frames` |
| Brightness | `brightness`, `brightness_auto`, `brightness_region` |
| Contour detection | `contour_detection`, `threshold`, `threshold_pickup_area` |
| ArUco | `aruco_enabled`, `aruco_dictionary`, `aruco_flip_image` |
## `CameraSettingsMapper`

Converts between the flat `CameraSettingsData` dataclass and the nested JSON dict format stored on disk:

```python
CameraSettingsMapper.from_json(data: dict)   -> CameraSettingsData
CameraSettingsMapper.to_json(data: CameraSettingsData) -> dict
```

Used by `CameraSettingsSerializer` (engine layer) to persist camera-only settings.

`CameraSettingsApplicationService.save_settings()` preserves any existing `Calibration` section in the stored vision JSON so the current calibration runtime data is not lost.

---

## Shared Wiring Pattern

```python
service = CameraSettingsApplicationService(
    settings_service=robot_system._settings_service,
    vision_service=robot_system.get_service(CommonServiceID.VISION),
)
return WidgetApplication(widget_factory=lambda ms: CameraSettingsFactory().build(service, ms))
```

Use this app directly in any robot system that declares the shared vision contract. `ApplicationSpec` is typically placed in the Service folder with icon `fa5s.camera`.
