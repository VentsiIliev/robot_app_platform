# `src/applications/camera_settings/` — Camera Settings

Configures the vision system camera: resolution, brightness, contour thresholds, and work area regions. Persists settings via `ISettingsService` and pushes live updates to the running `VisionSystem`.

This is intended to be the shared camera-settings application for any robot system that adopts the common vision contract:
- `CommonServiceID.VISION`
- `CommonSettingsID.VISION_CAMERA_SETTINGS`

---

## MVC Structure

```
camera_settings/
├── service/
│   ├── i_camera_settings_service.py          ← ICameraSettingsService (6 methods)
│   ├── stub_camera_settings_service.py        ← In-memory stub for standalone use
│   └── camera_settings_application_service.py ← Delegates to SettingsService + VisionSystem
├── model/
│   └── camera_settings_model.py               ← Load/save + pixel↔normalized conversion
├── view/
│   ├── camera_settings_view.py                ← Tab container
│   ├── camera_tab.py                          ← Main camera settings panel
│   ├── camera_controls_widget.py              ← Live preview + contour overlay
│   └── camera_settings_schema.py              ← View field definitions
├── controller/
│   └── camera_settings_controller.py
├── camera_settings_data.py                    ← CameraSettingsData dataclass (~35 fields)
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
    def save_work_area(self, area_type: str, pixel_points: List[Tuple[int, int]]) -> tuple[bool, str]: ...
    def get_work_area(self, area_type: str) -> tuple[bool, str, Optional[List]]: ...
```

`area_type` is one of `'pickup'`, `'spray'`, or `'work'`.

---

## `CameraSettingsApplicationService`

The live implementation. Constructed with `settings_service` and `vision_service`:

- `load_settings()` — reads from `SettingsService` via `CommonSettingsID.VISION_CAMERA_SETTINGS`; falls back to defaults if not found
- `save_settings()` — persists via `SettingsService`
- `update_settings(dict)` — delegates to `vision_service.updateSettings(dict)`
- `set_raw_mode(bool)` — forwards directly to `vision_service.rawMode`
- `save_work_area()` / `get_work_area()` — delegate to `vision_service`

---

## `CameraSettingsModel`

Thin delegation layer. Handles the pixel↔normalised coordinate conversion for work area points:

```python
# Save: normalised → pixel
pixel_points = [(int(x * width), int(y * height)) for x, y in normalised_points]
service.save_work_area(area_type, pixel_points)

# Load: pixel → normalised
return [(px / width, py / height) for px, py in pixel_points]
```

`area_name` (e.g. `"spray_area"`) is mapped to `area_type` (`"spray"`) by stripping `"_area"`.

---

## `CameraSettingsData`

Large frozen-like dataclass (`~35` fields) covering:

| Group | Fields |
|-------|--------|
| Resolution | `width`, `height` |
| Camera | `camera_index`, `skip_frames` |
| Brightness | `brightness`, `brightness_auto`, `brightness_region` |
| Contour detection | `contour_detection`, `threshold`, `threshold_pickup_area` |
| Calibration | `calibration_enabled`, various calibration params |
| Work area | `work_area`, `pickup_area`, `spray_area` point lists |

---

## `CameraSettingsMapper`

Converts between the flat `CameraSettingsData` dataclass and the nested JSON dict format stored on disk:

```python
CameraSettingsMapper.from_json(data: dict)   -> CameraSettingsData
CameraSettingsMapper.to_json(data: CameraSettingsData) -> dict
```

Used by `CameraSettingsSerializer` (engine layer) to persist settings.

---

## Shared Wiring Pattern

```python
service = CameraSettingsApplicationService(
    settings_service = robot_system._settings_service,
    vision_service   = robot_system.get_service(CommonServiceID.VISION),
)
return WidgetApplication(widget_factory=lambda ms: CameraSettingsFactory().build(service, ms))
```

Use this app directly in any robot system that declares the shared vision service/settings contract. `ApplicationSpec` is typically placed in the Service folder with icon `fa5s.camera`.
