# `VisionSystem/features/` — Vision Features

Self-contained subsystems providing optional or specialised vision capabilities. Unlike `services/` (which are always active during `run()`), features are invoked on demand or wired explicitly.

---

## `contour_matching/` — Workpiece Contour Matching

**Entry point:** `contour_matcher.py` → `find_matching_workpieces()`

Matches a list of live camera contours against a library of saved workpiece contours, then computes the precise rotation and translation needed to align each match.

```python
find_matching_workpieces(
    workpieces:    list,          # objects with get_main_contour(), get_spray_pattern_contours(), get_spray_pattern_fills()
    new_contours:  list[np.ndarray],
    debug:         bool = False,
) -> tuple[dict, list, list]
    # returns (final_matches, unmatched_contours, matched_contours)
```

### Pipeline

```
1. Matching
   ├── GeometricMatchingStrategy  (default) — shape similarity + centroid/rotation comparison
   └── MLMatchingStrategy         (optional) — loads a trained model from saved_models/
       Selects by ContourMatchingSettings.get_use_comparison_model()

2. Alignment  (for each matched pair)
   ├── prepare_data_for_alignment()  — attaches Contour objects to MatchInfo
   └── _alignContours()
       ├── rotate + translate contour to match template
       ├── mask_refinement           (optional — crops spray pattern to corrected region)
       └── update_workpiece_data()   — writes final spray path back to workpiece object
```

### Key Types

| Type | File | Role |
|------|------|------|
| `MatchInfo` | `matching/match_info.py` | One matched pair: workpiece + contour + centroid/rotation diff |
| `BestMatchResult` | `matching/best_match_result.py` | Result from a matching strategy: `is_match`, `workpiece`, `confidence` |
| `MatchingStrategy` | `matching/strategies/matching_strategy_interface.py` | ABC: `find_best_match(workpieces, contour) → BestMatchResult` |
| `GeometricMatchingStrategy` | `matching/strategies/` | Shape-hash + Hu moments comparison |
| `MLMatchingStrategy` | `matching/strategies/ml_matching_strategy.py` | ML model inference |
| `ContourMatchingSettings` | `settings/ContourMatchingSettings.py` | Similarity threshold, debug flags, model toggle |
| `ContourAligner` | `alignment/contour_aligner.py` | Rotation + translation computation |

### Debug Output

When `debug=True` or individual `ContourMatchingSettings` debug flags are set, `plot_generator.py` saves debug plots to `features/contour_matching/debug/output/`.

---

## `calibration/` — Camera Calibration (Internal)

**Entry point:** `calibration/cameraCalibration/CameraCalibrationService.py`

Implements chessboard-based lens distortion calibration using OpenCV `calibrateCamera`. Called by `services/CalibrationService` — not used directly.

```python
CameraCalibrationService(
    chessboardWidth:   int,
    chessboardHeight:  int,
    squareSizeMM:      float,
    skipFrames:        int,
    storagePath:       str,
    message_publisher: MessagePublisher | None = None,
    messaging_service: IMessagingService | None = None,
)

result = svc.run(raw_image)
# result.success, result.camera_matrix, result.distortion_coefficients, result.perspective_matrix
```

Saves calibration data (`.npz`) to `storagePath`. Also includes `stereo_calibration/` for dual-camera setups (standalone, not integrated into the main pipeline).

---

## `laser_detection/` — Structured-Light Height Measurement

Measures workpiece height using a line laser. Uses a median-of-frames approach to separate laser-on vs laser-off images, then detects the laser line position.

```python
LaserDetectionService(
    detector:        LaserDetector,
    laser:           Laser,           # hardware laser control
    vision_service:  VisionSystem,
    config:          LaserDetectionConfig | None = None,
)

mask, bright, closest = service.detect()
# closest: pixel position of the laser line closest point
```

### `LaserDetectionConfig`

| Field | Default | Role |
|-------|---------|------|
| `default_axis` | `'x'` | Laser line direction |
| `detection_delay_ms` | `100` | Wait after laser toggle before capture |
| `image_capture_delay_ms` | `50` | Inter-frame delay |
| `detection_samples` | `5` | Number of frames for median |
| `max_detection_retries` | `3` | Attempts before returning `None` |

Also contains `laser_calibration_service.py` for calibrating the pixel-to-mm scale, and `height_measuring.py` for computing Z from a pixel offset.

---

## `brightness_control/` — Brightness Manager

**File:** `brightness_control/brightness_manager.py`

Higher-level brightness control that can manage brightness across multiple camera regions or modes. Wraps `BrightnessController` from `plvision/PID/`. The `services/BrightnessService` is the simpler single-region variant used in the main loop.

---

## `hand_eye/` — Hand-Eye Calibration

**Files:** `hand_eye/collect_robot_poses.py`, `ttest_eye_in_hand.py`

Utilities for collecting matched robot pose / camera pose pairs to solve the hand-eye calibration problem (`cv2.calibrateHandEye`). Standalone scripts — not integrated into the platform startup.

---

## `camera_pose_solver/` — Camera Pose Estimation

**File:** `camera_pose_solver/pose_solver.py`

Estimates camera pose (rotation + translation) relative to a known marker pattern using `cv2.solvePnP`. Used in research/development workflows.

---

## `heightMeasuring/` — Height Abstraction

Placeholder package for height measurement abstractions. The active implementation is in `laser_detection/`.

---

## `qr_scanner/` — QR Code Scanner

**File:** `qr_scanner/QRcodeScanner.py`

Wraps `cv2.QRCodeDetector` or `pyzbar` (whichever is available) to decode QR codes from a frame. Used by `services/QrDetectionService`.
