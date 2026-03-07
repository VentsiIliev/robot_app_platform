# `VisionSystem/services/` — Vision Services

Thin, single-responsibility service objects that encapsulate individual image processing operations. `VisionSystem` instantiates all five at construction time and calls them from `run()`.

All services receive a `CameraSettings` reference at construction and read configuration from it — no direct coupling to `VisionSystem`.

---

## `ContourDetectionService`

**File:** `contour_detection_service.py`

Runs the full contour detection pipeline on a single frame.

```python
ContourDetectionService(camera_settings: CameraSettings, message_publisher=None)

detect(
    image:              np.ndarray,
    threshold:          int,
    is_calibrated:      bool,
    correct_image_fn:   Callable[[np.ndarray], np.ndarray],
    spray_area_points:  Optional[np.ndarray],
    sort:               bool = False,
) -> Tuple[Optional[List], Optional[np.ndarray], None]
    # returns (contours, corrected_image, None)
```

### Pipeline

```
1. correct_image_fn(image)       if is_calibrated, else stamp "not calibrated" overlay
2. _find_contours(corrected, threshold)
   a. Grayscale conversion
   b. Optional Gaussian blur   (GAUSSIAN_BLUR, BLUR_KERNEL_SIZE)
   c. cv2.threshold             (THRESHOLD_TYPE)
   d. Optional dilate           (DILATE_ENABLED, DILATE_KERNEL_SIZE, DILATE_ITERATIONS)
   e. Optional erode            (ERODE_ENABLED, ERODE_KERNEL_SIZE, ERODE_ITERATIONS)
   f. cv2.findContours
3. _approx_contours             (cv2.approxPolyDP, EPSILON)
4. _filter_by_area              (MIN_CONTOUR_AREA, MAX_CONTOUR_AREA)
5. Filter to spray_area_points  (pointPolygonTest for each point in each contour)
6. Optional sort by proximity   (nearest-neighbour from origin)
7. Optional draw overlay        (DRAW_CONTOURS)
8. publish_latest_image(corrected)
```

`sort=False` by default; pass `sort=True` when ordering matters for robot path planning.

---

## `CalibrationService`

**File:** `calibration_service.py`

Manages calibration image capture and chessboard-based camera calibration. Acts as a stateful buffer — images accumulate across multiple `capture_image()` calls until `calibrate()` is invoked.

```python
CalibrationService(
    camera_settings:   CameraSettings,
    storage_path:      str,
    message_publisher: MessagePublisher | None = None,
    messaging_service: IMessagingService | None = None,
)
```

| Method | Description |
|--------|-------------|
| `capture_image(raw_image)` | Appends `raw_image` to internal list; publishes via `message_publisher`; returns `(bool, str)` |
| `calibrate(raw_image)` | Runs `CameraCalibrationService.run()` on all captured images + current raw frame; returns `CalibrationOutcome` |

### `CalibrationOutcome`

```python
@dataclass
class CalibrationOutcome:
    success:                 bool
    message:                 str
    camera_matrix:           Optional[np.ndarray]
    distortion_coefficients: Optional[np.ndarray]
    perspective_matrix:      Optional[np.ndarray]
```

On success, `VisionSystem.calibrateCamera()` copies these values into its own state and calls `service.loadCameraCalibrationData()` to reload from disk.

The internal `CameraCalibrationService` is in `features/calibration/cameraCalibration/`.

---

## `ArucoDetectionService`

**File:** `aruco_detection_service.py`

Detects ArUco markers in an image using settings from `CameraSettings`.

```python
ArucoDetectionService(camera_settings: CameraSettings)

detect(
    corrected_image: Optional[np.ndarray],
    flip:  Optional[bool] = None,   # overrides ARUCO_FLIP_IMAGE if provided
    image: Optional[np.ndarray] = None,  # preferred over corrected_image if given
) -> Tuple[corners, ids, target_image]
    # returns (None, None, None) on failure
```

- Reads `ARUCO_DICTIONARY` from settings to select the ArUco dictionary (defaults to `DICT_4X4_1000`)
- Temporarily disables `DRAW_CONTOURS` during detection to avoid interfering with the contour pipeline
- Uses `ArucoDetector` from `plvision/PLVision/arucoModule.py`

---

## `BrightnessService`

**File:** `brightness_service.py`

PID-based automatic brightness adjustment. Runs every frame when `BRIGHTNESS_AUTO` is enabled.

```python
BrightnessService(camera_settings: CameraSettings)
```

| Method | Description |
|--------|-------------|
| `adjust(image)` | Applies PID correction to `image`; returns adjusted `np.ndarray` |
| `on_brightness_toggle(mode: str)` | Broker callback — `"start"` enables auto, `"stop"` disables |

### Adjustment Logic

```
1. adjustBrightness(image, self._adjustment)    ← apply current offset
2. calculateBrightness(adjusted, area_points)   ← measure mean brightness in area
3. error = target - current
4. correction = error * gain  (0.6 for |error|>10, 0.4 for |error|>2, 1.0 otherwise)
5. self._adjustment += correction  (clamped to [-255, 255])
6. return adjustBrightness(image, self._adjustment)
```

Area points are read from `BRIGHTNESS_AREA_P1..P4`; falls back to a hardcoded default region if not configured.

---

## `QrDetectionService`

**File:** `qr_detection_service.py`

Scans a raw frame for QR codes. No settings dependency.

```python
QrDetectionService()

detect(raw_image: Optional[np.ndarray]) -> Optional[str]
    # returns decoded text or None
```

Uses `QRcodeScanner` from `features/qr_scanner/`.

---

## Service Instantiation in `VisionSystem`

```python
# VisionSystem.__init__
self._brightness_service = BrightnessService(self.camera_settings)
self._aruco_service      = ArucoDetectionService(self.camera_settings)
self._qr_service         = QrDetectionService()

# after setup_external_communication():
self._contour_service    = ContourDetectionService(
    camera_settings   = self.camera_settings,
    message_publisher = self.message_publisher,  # may be None
)
self._calibration_service = CalibrationService(
    camera_settings   = self.camera_settings,
    storage_path      = self.storage_path,
    message_publisher = self.message_publisher,
    messaging_service = self.messaging_service,
)
```

`message_publisher` is `None` when no `messaging_service` is provided (standalone use).
