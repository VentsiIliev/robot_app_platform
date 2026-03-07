# `implementation/plvision/PLVision/` — PLVision Library

An internal OpenCV utility library. All `VisionSystem` services and features use `PLVision` functions rather than calling OpenCV directly — this centralises low-level image operations and makes them independently testable.

> **Treat as a stable internal library.** Do not import from application code. Always go through `VisionSystem` or the service objects.

---

## Package Contents

| Module | Key Exports | Role |
|--------|------------|------|
| `ImageProcessing.py` | `undistortImage`, `blurImage`, `threshImage`, `toGrayscale` | Low-level frame transforms |
| `Contouring.py` | `findContours`, `calculateCentroid`, `calculateArea`, `approxContour` | Contour extraction + geometry |
| `Aruco.py` / `arucoModule.py` | `ArucoDictionary`, `ArucoDetector` | ArUco marker detection |
| `Calibration.py` | Chessboard pattern solver helpers | Used by `CameraCalibrationService` |
| `PID/PIDController.py` | `PIDController` | Generic PID with Kp/Ki/Kd |
| `PID/BrightnessController.py` | `BrightnessController` | `adjustBrightness()`, `calculateBrightness()` |
| `JsonHandler.py` | `loadJson`, `saveJson` | JSON file I/O helpers |
| `arucoModule.py` | `ArucoDictionary` (enum), `ArucoDetector` | ArUco with dict selection |

---

## `ImageProcessing.py`

```python
undistortImage(
    image, camera_matrix, dist_coefficients,
    width, height,
    crop=False,
    optimal_camera_matrix=None,
    roi=None,
) -> np.ndarray
# Used in VisionSystem.correctImage()

blurImage(image, kernelSize, sigmaX) -> np.ndarray
threshImage(image, thresholdValue, maxValue, thresholdType) -> np.ndarray
toGrayscale(image) -> np.ndarray
```

`undistortImage` is the most performance-sensitive call in the pipeline — it runs every frame when the camera is calibrated. `optimal_camera_matrix` is pre-computed once and cached in `VisionSystem` to avoid recalculating it on every tick.

---

## `Contouring.py`

```python
findContours(image) -> list[np.ndarray]
calculateCentroid(contour) -> tuple[float, float]
calculateArea(contour) -> float
approxContour(contour, epsilon_factor) -> np.ndarray
```

`ContourDetectionService._sort_by_proximity()` calls `Contouring.calculateCentroid()` to compute nearest-neighbour ordering.

---

## `arucoModule.py`

```python
class ArucoDictionary(Enum):
    DICT_4X4_50   = cv2.aruco.DICT_4X4_50
    DICT_4X4_100  = ...
    DICT_4X4_1000 = ...   # default
    DICT_5X5_50   = ...
    # ... more

class ArucoDetector:
    def __init__(self, arucoDict: ArucoDictionary): ...
    def detectAll(self, image: np.ndarray) -> tuple[corners, ids]: ...
```

`ArucoDetectionService` reads `CameraSettingKey.ARUCO_DICTIONARY` to select the dictionary at runtime.

---

## `PID/BrightnessController.py`

```python
class BrightnessController:
    def __init__(self, Kp, Ki, Kd, setPoint): ...
    def adjustBrightness(self, image: np.ndarray, adjustment: float) -> np.ndarray: ...
    def calculateBrightness(self, image: np.ndarray, area_points: np.ndarray) -> float: ...
    @property
    def target(self) -> float: ...
```

`BrightnessService.adjust()` calls both methods on every frame. `calculateBrightness` computes the mean pixel value inside the polygon defined by `area_points`.

---

## Tests

`plvision/tests/PLVision/` contains unit tests for the library functions:

| Test file | Covers |
|-----------|--------|
| `test_Calibration.py` | Chessboard detection helpers |
| `test_Camera.py` | Camera capture mock |
| `test_Contouring.py` | Centroid, area, approx |
| `test_ImageProcessing.py` | undistort, blur, threshold |
| `test_JsonHandler.py` | load/save round-trip |

Run with: `python -m unittest tests/plvision/...`
