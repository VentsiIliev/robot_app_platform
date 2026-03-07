# `src/engine/vision/` — Vision Service

Camera-based alignment and detection system. Defines `IVisionService` and hosts the full `VisionSystem` implementation backed by OpenCV and the `PLVision` library.

---

## Package Structure

```
src/engine/vision/
├── i_vision_service.py                        ← IVisionService ABC (16 methods)
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
