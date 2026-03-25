# `src/applications/aruco_z_probe/` — ArUco Z-Probe

Diagnostic tool for calibrating or verifying the relationship between robot Z position and the apparent pixel displacement of an ArUco marker as seen by the camera. The operator moves the robot down in even steps (sweep) and measures the marker shift at each height; optionally re-runs a subset of those heights (verification) to confirm the model.

---

## MVC Structure

```
aruco_z_probe/
├── service/
│   ├── i_aruco_z_probe_service.py              ← IArucoZProbeService (3 methods)
│   ├── aruco_z_probe_application_service.py   ← Live impl: robot + vision
│   └── stub_aruco_z_probe_service.py          ← Simulates delay + synthetic samples
├── model/
│   └── aruco_z_probe_model.py                  ← Thin delegation
├── view/
│   └── aruco_z_probe_view.py                   ← Form + progress table + chart
├── controller/
│   └── aruco_z_probe_controller.py             ← Runs sweep/verify on background thread
├── aruco_z_probe_factory.py
└── example_usage.py
```

---

## `IArucoZProbeService`

```python
ArucoZSample = Tuple[float, Optional[float], Optional[float]]
# (z_mm, dx_pixels, dy_pixels) — dx/dy are None if marker not detected at that step

class IArucoZProbeService(ABC):
    def move_to_calibration_position(self) -> bool: ...

    def run_sweep(
        self,
        marker_id:           int,
        min_z:               float,
        sample_count:        int,
        detection_attempts:  int,
        stop_event:          threading.Event,
        progress_cb:         Callable[[int, int, float, Optional[float], Optional[float]], None],
        log_cb:              Optional[Callable[[str], None]] = None,
        stabilization_delay: float = 0.3,
    ) -> Tuple[bool, str, List[ArucoZSample]]:
        """
        Starting from current Z, step down to min_z in sample_count equal steps.
        Detects the marker at each step; measures pixel displacement relative to
        the baseline detected at the starting height.
        Returns to starting Z when done.
        progress_cb(step_index, total_steps, z_mm, dx_px, dy_px).
        Returns (success, message, samples).
        """

    def run_verification(
        self,
        z_heights:           List[float],
        marker_id:           int,
        detection_attempts:  int,
        stop_event:          threading.Event,
        progress_cb:         Callable[[int, int, float, Optional[float], Optional[float]], None],
        log_cb:              Optional[Callable[[str], None]] = None,
        stabilization_delay: float = 0.3,
    ) -> Tuple[bool, str, List[ArucoZSample]]:
        """
        Re-detects baseline at current Z, then visits each height in z_heights,
        measuring actual marker shift relative to the fresh baseline.
        Returns to starting Z when done.
        Returns (success, message, samples).
        """
```

### `ArucoZSample`

`(z_mm, dx_px, dy_px)` where `dx_px` / `dy_px` are the pixel displacement of the marker centroid relative to the baseline detection. Both are `None` when the marker was not detected at that step.

---

## Sweep vs Verification

| Mode | Input | Purpose |
|------|-------|---------|
| Sweep | `min_z`, `sample_count` | Initial data collection — evenly spaced steps from current Z down to `min_z` |
| Verification | `z_heights` (list) | Confirm a previously measured or computed model — re-visits a specific set of Z heights |

---

## Controller

Runs both sweep and verification on a `QThread` (via `BackgroundWorker` or equivalent) so the UI remains responsive. Progress is delivered through `progress_cb` which is called from the worker thread; the controller must relay it to the Qt thread via a `_Bridge` with `pyqtSignal`.

The `stop_event` (`threading.Event`) is set by the view's Stop button. The service implementation polls it between steps to allow cancellation without waiting for a full step to complete.

---

## Design Notes

- **Marker detection at each step** — if the marker is not detected within `detection_attempts` tries at a given step, `dx_px` / `dy_px` are recorded as `None`. The sweep continues to the next step rather than aborting.
- **Stabilization delay** — after each robot move, the service waits `stabilization_delay` seconds before capturing, to let vibration settle.
- **Returns to start** — both `run_sweep()` and `run_verification()` move the robot back to the starting Z height when done (success or failure), so the operator is not left with the robot in a mid-sweep position.
- **`log_cb` optional** — when provided, called with human-readable move/detection status messages. The view can route these to a scrollable log area.
