# `src/engine/robot/height_measuring/` — Height Measuring

Generic laser-based height-measurement subsystem. Provides laser detection, Z-to-pixel calibration, per-point height measurement, surface height-correction interpolation, depth-map persistence, and the robot-system adapter contract.

---

## Files

| File | Purpose |
|------|---------|
| `settings.py` | `LaserDetectionSettings`, `LaserCalibrationSettings`, `HeightMeasuringSettings`, `HeightMeasuringModuleSettings`, `HeightMeasuringSettingsSerializer` |
| `i_height_measuring_service.py` | `IHeightMeasuringService` — measurement session + calibration interface |
| `i_height_correction_service.py` | `IHeightCorrectionService` — surface interpolation interface |
| `height_measuring_service.py` | `HeightMeasuringService` — live impl: moves robot, fires laser, measures Z |
| `height_correction_service.py` | `HeightCorrectionService` — lazy `AreaGridHeightModel` backed correction |
| `laser_detection_service.py` | `LaserDetectionService` — single-shot laser detection with exposure control |
| `laser_calibration_service.py` | `LaserCalibrationService` — sweeps Z, builds pixel↔mm polynomial model |
| `laser_detector.py` | `LaserDetector` — image processing: mask, blur, centroid extraction |
| `laser_calibration_data.py` | `LaserCalibrationData` — serialisable polynomial calibration model |
| `depth_map_data.py` | `DepthMapData` — serialisable grid of measured Z heights |
| `area_grid_height_model.py` | `AreaGridHeightModel` — bilinear/nearest interpolation over the grid |
| `piecewise_bilinear_height_model.py` | `PiecewiseBilinearHeightModel` — piecewise alternative model |
| `robot_system_height_measuring_provider.py` | `RobotSystemHeightMeasuringProvider` — abstract adapter |
| `service_builders.py` | `build_robot_system_height_measuring_services()` — standard factory |

---

## `HeightMeasuringModuleSettings`

Three nested dataclasses; persisted as a single settings file via `HeightMeasuringSettingsSerializer`:

### `LaserDetectionSettings`

| Field | Default | Notes |
|-------|---------|-------|
| `min_intensity` | `10.0` | Minimum pixel intensity to accept as laser hit |
| `gaussian_blur_kernel` | `(21, 21)` | Blur kernel size (must be odd; restored as tuple from JSON list) |
| `gaussian_blur_sigma` | `0.0` | 0 = auto-computed from kernel size |
| `default_axis` | `"y"` | Axis used for centroid projection |
| `detection_delay_ms` | `200` | Wait after turning laser on before capturing |
| `image_capture_delay_ms` | `10` | Wait before each frame capture |
| `detection_samples` | `5` | Frames averaged per detection |
| `max_detection_retries` | `5` | Attempts before giving up |

### `LaserCalibrationSettings`

| Field | Default | Notes |
|-------|---------|-------|
| `step_size_mm` | `1.0` | Z step between calibration positions |
| `num_iterations` | `50` | Total steps in the sweep |
| `calibration_velocity` | `50.0` | mm/s |
| `calibration_acceleration` | `10.0` | mm/s² |
| `movement_threshold` | `0.2` | mm — convergence tolerance |
| `movement_timeout` | `2.0` | s |
| `delay_between_move_detect_ms` | `1000` | Wait after each move before detecting |
| `calibration_max_attempts` | `5` | Retries per Z position |
| `max_polynomial_degree` | `6` | Max degree for polynomial regression |
| `calibration_initial_position` | `[0,0,0,180,0,0]` | Robot pose used as sweep start |

### `HeightMeasuringSettings`

| Field | Default | Notes |
|-------|---------|-------|
| `measurement_velocity` | `20.0` | mm/s |
| `measurement_acceleration` | `10.0` | mm/s² |
| `measurement_threshold` | `0.25` | mm — convergence tolerance |
| `measurement_timeout` | `10.0` | s |
| `delay_between_move_detect_ms` | `500` | Wait after move before measuring |

---

## `IHeightMeasuringService`

```python
class IHeightMeasuringService(ABC):
    def begin_measurement_session(self) -> None: ...
    def end_measurement_session(self) -> None: ...
    def measure_at(self, x: float, y: float, *, already_at_xy: bool = False) -> Optional[float]: ...
    def is_calibrated(self) -> bool: ...
    def get_calibration_data(self) -> Optional[LaserCalibrationData]: ...
    def reload_calibration(self) -> None: ...
    def save_height_map(
        self,
        samples: List[List[float]],
        area_id: str = "",
        marker_ids: Optional[List[int]] = None,
        point_labels: Optional[List[str]] = None,
        grid_rows: int = 0,
        grid_cols: int = 0,
        planned_points: Optional[List[List[float]]] = None,
        planned_point_labels: Optional[List[str]] = None,
        unavailable_point_labels: Optional[List[str]] = None,
    ) -> None: ...
    def get_depth_map_data(self, area_id: str = "") -> Optional[DepthMapData]: ...
```

- `begin_measurement_session()` / `end_measurement_session()` — bracket a sequence of `measure_at()` calls; the service may activate the laser once at session start rather than per-measurement.
- `measure_at(x, y)` — moves the robot to (x, y) unless `already_at_xy=True`, fires the laser, returns the measured Z offset in mm (or `None` on detection failure).
- `save_height_map()` — persists a completed grid of measurements as a `DepthMapData` for the given `area_id`.
- `get_depth_map_data()` — loads persisted depth map for interpolation.

---

## `IHeightCorrectionService`

```python
class IHeightCorrectionService(ABC):
    def predict_z(self, x: float, y: float) -> float | None: ...
    def reload(self) -> None: ...
```

Surface interpolation interface. Returns the estimated Z offset at a given robot XY position, or `None` when no model is loaded or the point cannot be covered. Used by `TargetFrame.get_z_correction()`.

### `HeightCorrectionService`

Live implementation backed by `AreaGridHeightModel`:

- Model is loaded lazily on the first `predict_z()` call via `IHeightMeasuringService.get_depth_map_data()`.
- `reload()` clears the cached model so the next call rebuilds from storage.
- Logs a DEBUG line for each corrected point.

---

## `build_robot_system_height_measuring_services()`

```python
def build_robot_system_height_measuring_services(robot_system) -> tuple[
    HeightMeasuringService,
    LaserCalibrationService,
    LaserDetectionService,
]:
```

Standard factory called by `SystemBuilder`. Requires the robot system to have:
- `get_height_measuring_provider()` returning a `RobotSystemHeightMeasuringProvider`
- `CommonSettingsID.HEIGHT_MEASURING_SETTINGS` and `ROBOT_CONFIG` settings
- `CommonSettingsID.HEIGHT_MEASURING_CALIBRATION` and `DEPTH_MAP_DATA` repositories
- `_robot` (live `IRobotService`) and `_vision` (live vision service) attributes

Returns `(measuring_svc, calibration_svc, detection_svc)`.

---

## `RobotSystemHeightMeasuringProvider`

```python
class RobotSystemHeightMeasuringProvider(ABC):
    def build_laser_control(self) -> ILaserControl: ...
```

Single-method adapter that robot systems implement to supply the hardware-specific `ILaserControl` instance. Keeps the generic service builder decoupled from robot-system imports.

---

## Service Composition

```
build_robot_system_height_measuring_services()
  ├── LaserDetector(detection_settings)
  ├── LaserDetectionService(detector, laser=provider.build_laser_control(), vision, config)
  ├── LaserCalibrationService(detection_svc, robot, calibration_repo, config)
  └── HeightMeasuringService(detection_svc, robot, calibration_repo, config, depth_map_repo)
```

---

## Design Notes

- **`gaussian_blur_kernel` is a tuple** — JSON round-trips it as a list; the serializer restores it to `tuple` on `from_dict()`.
- **Session bracketing** — callers must call `begin_measurement_session()` before a batch of `measure_at()` calls and `end_measurement_session()` after. The service may leave the laser on between measurements for performance.
- **`already_at_xy=True`** — skip the robot move when the robot is already positioned; avoids redundant motion when the caller manages positioning externally.
- **Lazy model loading** — `HeightCorrectionService` builds the interpolation model on first use and caches it. Call `reload()` after a new height map is saved.
