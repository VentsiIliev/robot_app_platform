# Standalone paint shaft alignment

This package is an isolated proving ground for shaft alignment before the
feature is composed into `PaintRobotSystem`.

The first milestone detects one configured ArUco marker and reports its ID,
four corners, pixel center, pixel area, and image-plane orientation. Orientation
is clockwise in degrees from the image's horizontal axis. It deliberately does not claim a
full robot pose: the current `IVisionService` marker API does not provide a
capture timestamp or a synchronized robot pose. Marker center XY is mapped to
paint calibration/base robot millimetres using the existing
`HomographyResidualTransformer`. Tool/TCP offsets are intentionally not applied.

The runtime factory reads the real paint-system `settings_specs`, camera JSON,
work-area definitions, and vision data paths. It does not copy camera or ArUco
dictionary settings into this package.

Edit development values in `config.py`, then run `__main__.py` directly from
the IDE. No command-line arguments are required:

```bash
./.venv/bin/python scripts/paint_shaft_alignment/__main__.py
```

Available configuration fields include:

- `marker_id` selects the shaft marker;
- `active_work_area` selects a real paint work area;
- `raw_mode` uses raw-mode vision behavior;
- `minimum_area_px2` rejects very small detections;
- `headless` disables the OpenCV window;
- `debug_draw_detected_markers` outlines every visible marker and prints its ID;
- `debug_draw_detection_region` draws that ROI in the viewer;
- `debug_draw_robot_coordinates` shows mapped paint calibration/base XY in mm;
- `draw_initial_detection_region` pauses detection on the first frame so the base
  ROI can be drawn with the mouse (Enter accepts the configured centered ROI);
- `orientation_strategy` switches between `compare`, `solve_pnp`, and `corner_edge`;
- `orientation_primary_strategy` chooses which comparison result feeds stabilization;
- `marker_size_mm` is the measured black marker square size (currently 10 mm);
- `base_region_width_px` and `base_region_height_px` define the temporary base ROI;
- `tracking_region_padding_px` controls the margin around a tracked marker;
- `tracking_region_minimum_width_px` and `tracking_region_minimum_height_px`
  prevent an excessively tight tracking crop;
- `tracking_recovery_expansion_px` expands the ROI after every valid miss;
- `marker_misses_before_region_fallback` controls when tracking returns to the base ROI;
- `detections_before_tracking` controls how many accepted detections are needed before tracking;
- `acquisition_misses_before_reset` allows short detection gaps while acquiring;
- `tracking_position_filter_alpha` filters center measurements used for prediction;
- `tracking_prediction_gain` limits how aggressively velocity moves the next ROI;
- `tracking_maximum_center_jump_px` rejects implausible position jumps;
- `tracking_maximum_area_ratio_change` rejects implausible marker-size changes;
- `stability_required_samples` controls the rolling robust sample window;
- `stability_maximum_center_spread_px` limits pixel-position variation;
- `stability_maximum_orientation_spread_deg` limits circular angle variation;
- `stability_misses_before_reset` clears stale samples after marker loss;
- `q` or Escape closes the OpenCV viewer.
- At startup, drag with the left mouse button to set the initial base detection
  region. Drag again later to replace it; `r`
  restores the configured centered region. The adaptive tracker continues to
  operate inside/around the selected base region and falls back to it after loss.

Next milestones should add a timestamped capture contract, stable multi-frame
sampling, marker pose estimation, and robot-pose synchronization as separate
components rather than adding those responsibilities to `ShaftMarkerDetector`.
The temporary centered region is selected when the runner composes the
detector. The separate `MarkerRegionTracker` shrinks the search to the detected
marker, predicts its next center, progressively expands during recovery, and
returns to the base region after consecutive valid misses. A future paint-shaft
work-area adapter can replace the centered base provider without changing the
detector or tracker.

`MarkerSampleStabilizer` is separate from tracking. The tracker follows raw
detections immediately, while robot XY is reported only from a stable median
center. Orientation uses a circular mean so the ±180° boundary is handled
correctly.

In `compare` mode both algorithms receive the same four detected corners. The
overlay shows edge angle, PnP angle, and their shortest signed angular delta.
PnP diagnostics also show RX, RY, total tilt, camera-frame Z, reprojection RMS,
candidate count, and the selected positive-Z IPPE candidate.
