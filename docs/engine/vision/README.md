# `src/engine/vision/` — Vision Service

Camera-based alignment and detection system. Defines `IVisionService` and hosts the full `VisionSystem` implementation backed by OpenCV and the `PLVision` library.

---

## Package Structure

```
src/engine/vision/
├── i_vision_service.py                        ← IVisionService ABC (16 methods)
├── homography_transformer.py                  ← HomographyTransformer (ICoordinateTransformer impl)
├── camera_settings_serializer.py              ← CameraSettingsSerializer (engine ↔ settings layer)
└── implementation/
    ├── VisionSystem/
    │   ├── VisionSystem.py                    ← Main entry point — camera loop + feature dispatch
    │   ├── camera_initialization.py           ← CameraInitializer (auto-detect + retry)
    │   ├── core/
    │   │   ├── camera/
    │   │   │   ├── frame_grabber.py           ← FrameGrabber — threaded deque buffer
    │   │   │   └── remote_camera.py           ← RemoteCamera — MJPEG HTTP stream adapter
    │   │   ├── external_communication/
    │   │   │   └── system_state_management.py ← StateManager, MessagePublisher, SubscriptionManager, ServiceState
    │   │   ├── service/
    │   │   │   └── internal_service.py        ← Service — settings + data loading facade
    │   │   ├── settings/
    │   │   │   ├── CameraSettingKey.py        ← CameraSettingKey enum (~40 keys)
    │   │   │   ├── CameraSettings.py          ← CameraSettings accessors
    │   │   │   ├── settings_manager.py        ← Load/save JSON settings file
    │   │   │   └── BaseSettings.py
    │   │   ├── models/
    │   │   │   └── contour.py                 ← Contour wrapper (centroid, area, orientation)
    │   │   └── data_loading.py                ← DataManager (matrices, work area points)
    │   ├── services/                          ← Thin service objects used by VisionSystem.run()
    │   │   ├── contour_detection_service.py   ← Threshold → blur → contour → filter → spray area
    │   │   ├── calibration_service.py         ← Image capture + chessboard calibration
    │   │   ├── aruco_detection_service.py     ← ArUco marker detection
    │   │   ├── brightness_service.py          ← PID-based auto-brightness adjustment
    │   │   └── qr_detection_service.py        ← QR code scan
    │   └── features/                          ← Self-contained subsystems (not all active by default)
    │       ├── contour_matching/              ← Workpiece-to-camera contour matching + alignment
    │       ├── calibration/                   ← CameraCalibrationService (chessboard solver)
    │       ├── laser_detection/               ← Structured-light height measurement
    │       ├── brightness_control/            ← BrightnessManager (PID brightness controller)
    │       ├── hand_eye/                      ← Hand-eye calibration data collection
    │       ├── camera_pose_solver/            ← Camera pose estimation
    │       ├── heightMeasuring/               ← Height measurement abstraction
    │       └── qr_scanner/                   ← QRcodeScanner
    └── plvision/
        └── PLVision/                         ← Internal vision library (OpenCV utilities)
            ├── ImageProcessing.py            ← undistort, blur, threshold helpers
            ├── Contouring.py                 ← findContours, centroid, area, approx
            ├── Aruco.py / arucoModule.py     ← ArucoDictionary, ArucoDetector
            ├── Calibration.py               ← Chessboard pattern solver
            └── PID/
                ├── PIDController.py          ← Generic PID
                └── BrightnessController.py   ← adjustBrightness, calculateBrightness
```

→ Subdocs: [core/](core/README.md) · [services/](services/README.md) · [features/](features/README.md) · [plvision/](plvision/README.md)

---

## `IVisionService`

**File:** `i_vision_service.py`

The public contract consumed by robot system processes and applications:

```python
class IVisionService(ABC):
    # Lifecycle
    def start(self)  -> None: ...
    def stop(self)   -> None: ...

    # Camera control
    def set_raw_mode(self, enabled: bool) -> None: ...
    def set_draw_contours(self, enabled: bool) -> None: ...
    def get_latest_frame(self) -> np.ndarray: ...
    def get_camera_width(self)  -> int: ...
    def get_camera_height(self) -> int: ...

    # Calibration settings
    def get_chessboard_width(self)  -> int: ...
    def get_chessboard_height(self) -> int: ...
    def get_square_size_mm(self)    -> float: ...
    @property
    def camera_to_robot_matrix_path(self) -> str: ...

    # Camera calibration
    def capture_calibration_image(self)             -> tuple[bool, str]: ...
    def calibrate_camera(self)                      -> tuple[bool, str]: ...

    # Settings
    def update_settings(self, settings: dict)       -> tuple[bool, str]: ...

    # Work area
    def save_work_area(self, area_type, pixel_points) -> tuple[bool, str]: ...
    def get_work_area(self, area_type)               -> tuple[bool, str, any]: ...

    # Contour / matching
    def get_latest_contours(self) -> list: ...
    def run_matching(self, workpieces, contours) -> Tuple[dict, int, List, List]: ...

    # ArUco
    def detect_aruco_markers(self, image) -> tuple: ...
```

---

## `HomographyTransformer`

**File:** `homography_transformer.py`

Concrete `ICoordinateTransformer` that loads a 3×3 homography matrix from a `.npy` file and applies projective math to convert camera pixel coordinates to robot-frame millimetres.

```python
class HomographyTransformer(ICoordinateTransformer):
    def __init__(self, matrix_path: str,
                 tcp_x_offset: float = <not provided>,
                 tcp_y_offset: float = <not provided>): ...
    def is_available(self) -> bool: ...
    def reload(self) -> bool: ...
    def transform(self, x: float, y: float) -> Tuple[float, float]: ...
    def transform_to_tcp(self, x: float, y: float) -> Tuple[float, float]: ...
    def inverse_transform(self, x: float, y: float) -> Tuple[float, float]: ...
```

- Matrix is loaded once at construction via `np.load(matrix_path)`.
- If the file is missing or unreadable, `is_available()` returns `False`; `transform()` raises `RuntimeError`.
- `reload()` re-reads the file from disk — call this after a calibration run writes a fresh matrix so that the running service picks up the new values without restarting.
- `tcp_x_offset` / `tcp_y_offset` are **optional** but must both be provided together. If either is omitted, calling `transform_to_tcp()` raises `RuntimeError` — there is no silent default.
- `transform_to_tcp(x, y)` = `transform(x, y)` + `(tcp_x_offset, tcp_y_offset)`. Use this when you need the result relative to the tool tip rather than the camera optical center.
- `inverse_transform(x, y)` applies the inverse homography and maps robot/output coordinates back into image space. This is used by the production dashboard to project the live TCP onto the static captured glue-progress image.
- Created by the wiring layer (`application_wiring.py`) using `vision_service.camera_to_robot_matrix_path` and `robot_config.tcp_x_offset` / `robot_config.tcp_y_offset`; injected as `ICoordinateTransformer` into services that need it.

---

## `CameraSettingsSerializer`

**File:** `camera_settings_serializer.py`

`ISettingsSerializer` implementation that bridges the engine settings layer and `VisionSystem.CameraSettings`:

```python
class CameraSettingsSerializer(ISettingsSerializer[CameraSettings]):
    def get_default(self) -> CameraSettings:
        # constructs default VisionSystem CameraSettings and wraps in engine CameraSettings
    def to_dict(self, settings) -> dict: ...
    def from_dict(self, data)   -> CameraSettings: ...
```

Used in `GlueRobotSystem.settings_specs` under key `SettingsID.VISION_CAMERA_SETTINGS`. The file is stored at `storage/settings/GlueSystem/vision/camera_settings.json`.

---

## `VisionSystem` — Main Entry Point

**File:** `implementation/VisionSystem/VisionSystem.py`

See [VisionSystem.py](../../../src/engine/vision/implementation/VisionSystem/VisionSystem.py) for full API. Key points:

- Constructed once by `build_vision_service()` in `service_builders.py`
- Runs a background `FrameGrabber` thread from construction
- `start_system()` starts the main `_loop` daemon thread; `stop_system()` joins it
- `run()` is the per-tick processing method (called by `_loop`):
  1. Grab latest frame from `FrameGrabber`
  2. Auto-brightness if enabled
  3. If `rawMode` → publish raw frame and return
  4. If `contour_detection` → `ContourDetectionService.detect()` → cache in `_latest_contours`
  5. If calibrated → `correctImage()` (undistort + perspective warp)
