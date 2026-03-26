# `src/applications/camera_settings/` — Camera Settings

Configures the vision system camera: resolution, brightness, contour thresholds, preprocessing, and ArUco options. Persists camera settings via `ISettingsService` and pushes live camera-setting updates to the running `VisionSystem`.

Work-area ROI editing has been moved into the shared [Work Area Settings](/home/ilv/Desktop/robot_app_platform/docs/applications/work_area_settings/README.md) application.
Calibration-related settings have been moved into the shared [Calibration Settings](/home/ilv/Desktop/robot_app_platform/docs/applications/calibration_settings/README.md) application.

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
```

---

## `CameraSettingsApplicationService`

The live implementation. Constructed with `settings_service` and `vision_service`:

- `load_settings()` — reads from `SettingsService` via `CommonSettingsID.VISION_CAMERA_SETTINGS`; falls back to defaults if not found
- `save_settings()` — persists via `SettingsService`
- `update_settings(dict)` — delegates to `vision_service.updateSettings(dict)`
- `set_raw_mode(bool)` — forwards directly to `vision_service.rawMode`

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
