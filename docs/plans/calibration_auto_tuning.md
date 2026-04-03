# Calibration Auto-Tuning Plan

## Goal

After each successful calibration run, collect per-marker performance data and automatically adjust the `AdaptiveMovementConfig` parameters (`k`, `derivative_scaling`, `max_error_ref`) so subsequent runs converge faster and more accurately.

---

## Prerequisites / Fixes Required First

### Fix 1 — `fast_iteration_wait` missing from `AdaptiveMovementConfig` (existing bug)

`robot_calibration_pipeline.py:127` reads `adaptive_movement_config.fast_iteration_wait`
but this field is **not defined** in the class constructor → `AttributeError` at runtime.

**File:** `src/engine/robot/calibration/robot_calibration/config_helpers.py`

Add `fast_iteration_wait` to `AdaptiveMovementConfig.__init__` with a sensible default:
```python
def __init__(self, min_step_mm, max_step_mm, target_error_mm, max_error_ref,
             k, derivative_scaling, fast_iteration_wait=0.5):
    ...
    self.fast_iteration_wait = fast_iteration_wait
```

### Fix 2 — Instrument context with per-marker alignment stats

`collect_run_metrics(context)` requires per-marker stats, but the context currently
tracks only a global `iteration_count`. The per-marker values are computed locally
inside `handle_iterate_alignment_state()` but never persisted.

**File:** `src/engine/robot/calibration/robot_calibration/RobotCalibrationContext.py`

Add:
```python
self.alignment_stats: dict = {}   # marker_id → {init_error_mm, final_error_mm, iterations, converged}
```

**File:** `src/engine/robot/calibration/robot_calibration/states/remaining_handlers.py`

Inside `handle_iterate_alignment_state()`, populate the stats at two points:

```python
# On first iteration for this marker — record initial error:
if context.iteration_count == 1:
    context.alignment_stats.setdefault(marker_id, {})["init_error_mm"] = current_error_mm

# On convergence or max-iterations hit — record final stats:
context.alignment_stats.setdefault(marker_id, {}).update({
    "final_error_mm": current_error_mm,
    "iterations":     context.iteration_count,
    "converged":      alignment_success,
})
```

---

## Data to Collect (per run, per marker)

| Field | Description |
|-------|-------------|
| `marker_id` | ArUco marker ID |
| `init_error_mm` | Error at start of alignment (first iteration) |
| `final_error_mm` | Error at convergence or timeout |
| `iterations` | Number of iterations taken |
| `converged` | `True` if within tolerance, `False` if hit `max_iterations` |
| `timestamp` | ISO timestamp of the run |
| `homography_error_mm` | Final reprojection error from `_finalize_calibration()` — quality tracking |

Stored as a rolling window of the last **10 runs** in:

```
src/robot_systems/paint/storage/settings/vision/data/calibration_run_history.json
```

`history_path` is derived at the call site:
```python
storage_dir = os.path.dirname(context.vision_service.camera_to_robot_matrix_path)
history_path = os.path.join(storage_dir, "calibration_run_history.json")
```

---

## Tuning Rules

Rules are applied only after a minimum of **3 runs** of history are available.

### Per-run aggregates

- `avg_iterations` = mean iterations across all converged markers
- `avg_max_init_error` = mean of the maximum `init_error_mm` seen per run
- `timeout_rate` = fraction of markers that did not converge

### Rule 1 — Slow but accurate (converges, but takes many iterations)

**Condition:** `avg_iterations > 8` and `timeout_rate < 0.05`

**Action:**
```
k                  ×= 1.08     # more aggressive steps
derivative_scaling ×= 0.92     # less braking
```

### Rule 2 — Too aggressive (timeouts / misses)

**Condition:** `timeout_rate > 0.10`

> Note: oscillation (overshoot + undershoot) manifests as timeouts, so `timeout_rate`
> is a reliable proxy — no step-level data needed.

**Action:**
```
k                  ×= 0.92
derivative_scaling ×= 1.08
```

### Rule 3 — Slide `max_error_ref` toward observed scale

```
max_error_ref = EMA(max_error_ref, 1.6 × avg_max_init_error, alpha=0.3)
```

Keeps the normalization reference in sync with real robot positioning error magnitudes.

### Bounds (applied after every update)

| Parameter | Min | Max | Tuned by rules? |
|-----------|-----|-----|-----------------|
| `k` | 0.5 | 5.0 | Yes |
| `derivative_scaling` | 0.1 | 2.0 | Yes |
| `max_error_ref` | 5.0 | 200.0 | Yes (Rule 3) |
| `min_step_mm` | — | — | Static, not tuned |
| `max_step_mm` | — | — | Static, not tuned |

Maximum change per run: **±8%**

---

## Implementation Plan

### 1. `calibration_tuner.py` (new file)

Location: `src/engine/robot/calibration/robot_calibration/calibration_tuner.py`

```python
def collect_run_metrics(context, homography_error_mm: float) -> dict:
    """Extract per-marker stats + homography error from completed context."""

def load_history(path: str) -> list[dict]:
    """Load JSON history (rolling 10 runs). Returns [] on missing or corrupt file."""

def save_history(path: str, history: list[dict]) -> None:
    """Persist updated history, trimmed to 10 entries."""

def compute_tuning_adjustments(history: list[dict]) -> dict:
    """Apply rules (requires ≥3 runs). Returns {} if no adjustment needed."""

def apply_adjustments(settings_service, key: str, adjustments: dict) -> None:
    """Read current config, apply deltas within bounds, save."""

def collect_and_tune(context, settings_service, history_path: str,
                     homography_error_mm: float) -> None:
    """Top-level entry point called at end of successful calibration run."""
```

### 2. Call site

In `robot_calibration_pipeline.py`, after `_finalize_calibration()` reports success:

```python
from src.engine.robot.calibration.robot_calibration.calibration_tuner import collect_and_tune

storage_dir  = os.path.dirname(context.vision_service.camera_to_robot_matrix_path)
history_path = os.path.join(storage_dir, "calibration_run_history.json")
collect_and_tune(context, context.settings_service, history_path, average_error_camera_center)
```

### 3. History format (JSON)

```json
[
  {
    "timestamp": "2026-04-03T10:22:00",
    "homography_error_mm": 2.295,
    "markers": [
      {"marker_id": 0, "init_error_mm": 22.4, "final_error_mm": 0.18, "iterations": 7, "converged": true},
      {"marker_id": 1, "init_error_mm": 18.1, "final_error_mm": 0.21, "iterations": 9, "converged": true}
    ]
  }
]
```

---

## What Is NOT Auto-Tuned

- `velocity` / `acceleration` — robot motion limits, safety-critical
- `recenter_max_iterations` — hard safety cap
- `rotation_step_deg` / `iterations` (TCP capture) — geometric sampling, not convergence tuning
- `settle_time_s` — hardware vibration dependent
- `min_step_mm` / `max_step_mm` — leave static; only `k` and `derivative_scaling` govern step magnitude

---

## Acceptance Criteria

- [ ] `fast_iteration_wait` AttributeError is fixed
- [ ] `context.alignment_stats` is populated before `_finalize_calibration()` is called
- [ ] After 3+ runs, parameters update by ≤8% in the correct direction
- [ ] Bounds are never violated
- [ ] History file is human-readable JSON, max 10 entries, includes `homography_error_mm`
- [ ] If history file is missing or corrupt, tuner silently skips (no crash)
- [ ] Standalone test with `StubCalibrationContext` covering all three rules