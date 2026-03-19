# `VisionSystem/core/` — Core Infrastructure

Foundational building blocks used by `VisionSystem` and the feature services. No OpenCV business logic lives here — only camera I/O, messaging integration, settings I/O, data loading, and domain models.

---

## `camera/` — Camera Drivers

### `FrameGrabber`

**File:** `camera/frame_grabber.py`

Decouples frame capture from frame processing by running a dedicated daemon thread that continuously fills a `deque` buffer.

```python
class FrameGrabber:
    def __init__(
        self,
        camera,
        maxlen: int = 5,
        *,
        read_timeout_s: float = 0.25,
        restart_after_failures: int = 4,
        restart_cooldown_s: float = 1.0,
        post_restart_settle_s: float = 0.2,
    ): ...
    def start(self) -> None: ...           # starts the daemon thread
    def get_latest(self) -> np.ndarray | None: ...   # returns newest buffered frame (thread-safe)
    def stop(self) -> None: ...            # sets running=False, joins thread
```

- The buffer holds the last `maxlen` frames (default 5). Older frames are discarded automatically.
- `get_latest()` is safe to call from any thread (`threading.Lock` guards the deque).
- Each grab uses `camera.capture(timeout=read_timeout_s)` so stream failures are noticed quickly instead of blocking for a full second on every read.
- After `restart_after_failures` consecutive failed reads, `FrameGrabber` attempts stream recovery with `camera.stop_stream()` and `camera.start_stream()`.
- Restart attempts are throttled by `restart_cooldown_s` and followed by a short `post_restart_settle_s` delay so repeated FFmpeg/MJPEG parse failures do not create a tight reconnect loop.
- `VisionSystem.__init__` creates and starts `FrameGrabber`; `stop_system()` calls `stop()`.

This recovery path was added specifically for remote MJPEG streams opened through OpenCV/FFmpeg. In that setup, malformed multipart boundaries or truncated JPEG payloads can make `capture()` return `None` forever unless the stream is explicitly reopened.

### `RemoteCamera`

**File:** `camera/remote_camera.py`

Drop-in `Camera` replacement that reads from an MJPEG HTTP stream (e.g. a Raspberry Pi camera server). Implements the same `capture()` / `stopCapture()` / `stop_stream()` API as the local `Camera` class.

```python
RemoteCamera(
    url:    str,           # MJPEG stream URL, e.g. "http://192.168.222.178:5000/video_feed"
    width:  int | None,
    height: int | None,
    fps:    int | None,
)
```

To switch `VisionSystem` to a remote camera, replace `self.camera` assignment in `setup_camera()` with a `RemoteCamera` instance (see the commented `TODO` block in `VisionSystem.py`).

Notes:

- `RemoteCamera` still relies on OpenCV/FFmpeg for multipart MJPEG parsing.
- If the remote endpoint emits malformed boundaries, FFmpeg may print `mpjpeg Expected boundary '--' not found` or `mjpeg overread`.
- The primary mitigation in the current stack is `FrameGrabber` auto-restart of the stream after repeated failed reads.

---

## `external_communication/` — Broker Integration

**File:** `external_communication/system_state_management.py`

Three collaborating classes that wire `VisionSystem` to the platform message broker.

### `ServiceState` (Enum)

```python
class ServiceState(Enum):
    UNKNOWN      = 0
    INITIALIZING = 1
    IDLE         = 2
    STARTED      = 3
    PAUSED       = 4
    STOPPED      = 5
    ERROR        = 6
```

Higher numeric value = higher priority (used for comparison in multi-service state aggregation).

### `StateManager`

Tracks the current `ServiceState` of the vision service and publishes it on every change:

```python
StateManager(
    service_id:        str,            # "vision_service"
    initial_state:     ServiceState,
    message_publisher: MessagePublisher,
)
state_manager.update_state(ServiceState.IDLE)
# → publishes {"id": "vision_service", "state": "IDLE"} on VisionTopics.SERVICE_STATE
```

Thread-safe (`threading.Lock` guards state + publish).

### `MessagePublisher`

Centralises all broker `publish` calls from inside `VisionSystem`:

| Method | Topic published |
|--------|----------------|
| `publish_latest_image(image)` | `VisionTopics.LATEST_IMAGE` → `{"image": <np.ndarray>}` |
| `publish_calibration_image_captured(images)` | `VisionTopics.CALIBRATION_IMAGE_CAPTURED` |
| `publish_thresh_image(thresh)` | `VisionTopics.THRESHOLD_IMAGE` |
| `publish_state(state)` | `VisionTopics.SERVICE_STATE` |
| `publish_calibration_feedback(feedback)` | `VisionTopics.CALIBRATION_FEEDBACK` |

### `SubscriptionManager`

Registers `VisionSystem` as a subscriber to control topics at startup:

| Topic subscribed | Handler |
|-----------------|---------|
| `VisionTopics.THRESHOLD_REGION` | `vision_system.on_threshold_update(msg)` |
| `VisionTopics.AUTO_BRIGHTNESS` | `brightness_service.on_brightness_toggle(mode)` |

`subscribe_all()` is called from `VisionSystem.setup_external_communication()` when a messaging service is provided.

---

## `service/` — Internal Service (Data Facade)

**File:** `service/internal_service.py` → `Service`

Unifies settings loading and calibration data loading behind one object. `VisionSystem` holds `self.service: Service` and never touches `DataManager` or `SettingsManager` directly.

```python
Service(
    data_storage_path:  str,
    settings_file_path: str | None = None,  # defaults to user config path
)
```

| Responsibility | Delegates to |
|---------------|-------------|
| `loadSettings()` | `SettingsManager` → returns `CameraSettings` |
| `updateSettings(...)` | `SettingsManager.updateSettings(...)` |
| `loadPerspectiveMatrix()` | `DataManager` |
| `loadCameraCalibrationData()` | `DataManager` |
| `loadCameraToRobotMatrix()` | `DataManager` |
| `loadWorkAreaPoints()` | `DataManager` |
| `saveWorkAreaPoints(data)` | `DataManager` |
| `cameraData`, `cameraToRobotMatrix`, `perspectiveMatrix` | `DataManager` properties |
| `sprayAreaPoints`, `pickupAreaPoints`, `workAreaPoints` | `DataManager` properties |
| `isCalibrated` | `cameraData is not None and cameraToRobotMatrix is not None` |

---

## `settings/` — Camera Settings

### `CameraSettingKey` (Enum)

**File:** `settings/CameraSettingKey.py`

Enum of all setting keys used by `CameraSettings`. Grouped by concern:

| Group | Keys |
|-------|------|
| Core camera | `INDEX`, `WIDTH`, `HEIGHT`, `SKIP_FRAMES`, `CAPTURE_POS_OFFSET` |
| Contour detection | `THRESHOLD`, `THRESHOLD_PICKUP_AREA`, `EPSILON`, `MIN_CONTOUR_AREA`, `MAX_CONTOUR_AREA`, `CONTOUR_DETECTION`, `DRAW_CONTOURS` |
| Preprocessing | `GAUSSIAN_BLUR`, `BLUR_KERNEL_SIZE`, `THRESHOLD_TYPE`, `DILATE_*`, `ERODE_*` |
| Calibration | `CHESSBOARD_WIDTH`, `CHESSBOARD_HEIGHT`, `SQUARE_SIZE_MM`, `CALIBRATION_SKIP_FRAMES` |
| Auto-brightness (PID) | `BRIGHTNESS_AUTO`, `BRIGHTNESS_KP`, `BRIGHTNESS_KI`, `BRIGHTNESS_KD`, `TARGET_BRIGHTNESS`, `BRIGHTNESS_AREA_P1..P4` |
| ArUco | `ARUCO_ENABLED`, `ARUCO_DICTIONARY`, `ARUCO_FLIP_IMAGE` |

### `CameraSettings`

**File:** `settings/CameraSettings.py`

Provides typed getter/setter methods for every key in `CameraSettingKey`. Backed by a plain `dict`. Used by all services — they hold a `CameraSettings` reference and call `get_threshold()`, `get_camera_width()`, etc.

### `SettingsManager`

**File:** `settings/settings_manager.py`

Loads and saves the camera settings JSON file. `updateSettings()` validates incoming `dict` values, applies them to the `CameraSettings` object, and persists.

---

## `models/` — Domain Models

### `Contour`

**File:** `models/contour.py`

Wraps a raw numpy contour array with convenience accessors:

```python
class Contour:
    def get(self) -> np.ndarray: ...
    def centroid(self) -> tuple[float, float]: ...
    def area(self) -> float: ...
    def orientation(self) -> float: ...   # angle in degrees
```

Used by the contour matching feature to keep contour data and metadata together.

---

## `data_loading.py` — DataManager

Loads and caches all persistent binary data from `storage_path`:

| Data | File | Property |
|------|------|----------|
| Camera calibration | `camera_calibration.npz` | `cameraData`, `get_camera_matrix()`, `get_distortion_coefficients()` |
| Perspective matrix | `perspective_matrix.npz` | `perspectiveMatrix` |
| Camera-to-robot matrix | `camera_to_robot_matrix.npz` | `cameraToRobotMatrix` |
| Work area points | `work_area_points.json` | `sprayAreaPoints`, `pickupAreaPoints`, `workAreaPoints` |
