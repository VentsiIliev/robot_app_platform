"""
Shared PPM (pixels-per-mm) online-refinement helpers.

Used by both ``handle_iterate_alignment_state`` (remaining_handlers.py) and
``_align_marker_to_center`` (tcp_offset_capture.py) so the logic lives in
exactly one place.

Algorithm summary
-----------------
At every iteration we know:
  * How far the robot actually moved   (query position before+after)
  * How much the pixel error changed   (measured in the next frame)

Because ImageToRobotMapping is a pure axis-permutation + sign-flip
(orthogonal, unit-scale), |robot_delta_mm| == |image_delta_mm|, so:

    ppm_observed = pixel_reduction / robot_delta_mm

We maintain a running EMA on ``context.ppm_working``.  The learning rate
(α) scales with the robot-move magnitude: large moves produce high-SNR
observations and are trusted more.

Noise guards
------------
* robot_delta > 0.5 mm   — reject jitter / micro-settling
* pixel_reduction > 3 px — sub-pixel ArUco noise floor
* probe_err > 8 px       — previous error must be significant (≥ ~1.8 mm)
                           to prevent near-convergence noise from dirtying
                           the estimate
* outlier band [0.33×, 3×] current estimate
"""

import logging
import math


_logger = logging.getLogger(__name__)

# ── Adaptive wait constants (same formula in both callers) ────────────────────
_MIN_SETTLE_S   = 0.10   # absolute minimum wait after any move
_MAX_ERR_REF_MM = 10.0   # errors ≥ this use the full configured wait

# ── PPM learning thresholds ───────────────────────────────────────────────────
_MIN_ROBOT_DELTA_MM  = 0.5   # robot must have moved at least this far
_MIN_PIXEL_REDUCTION = 3.0   # pixel error must have dropped at least this much
_MIN_PROBE_ERR_PX    = 8.0   # previous error must be above this (signal > noise)
_PPM_OUTLIER_LO      = 0.33  # reject if < 33 % of current estimate
_PPM_OUTLIER_HI      = 3.00  # reject if > 300 % of current estimate
_ALPHA_MIN           = 0.30  # EMA weight for small / noisy moves
_ALPHA_MAX           = 0.70  # EMA weight for large / high-SNR moves
_ALPHA_RAMP_LO_MM    = 0.5   # robot delta at which α = _ALPHA_MIN
_ALPHA_RAMP_HI_MM    = 5.0   # robot delta at which α = _ALPHA_MAX


def get_working_ppm(context) -> float:
    """Return (and lazily initialise) ``context.ppm_working``."""
    if not hasattr(context, "ppm_working") or context.ppm_working is None:
        context.ppm_working = context.calibration_vision.PPM * context.ppm_scale
    return context.ppm_working


def clear_ppm_probe(context) -> None:
    """Invalidate the probe — call when the robot teleports or rotates significantly."""
    context._ppm_probe_pos      = None
    context._ppm_probe_error_px = None


def store_ppm_probe(context, robot_pos_now: list, current_error_px: float) -> None:
    """Record position + error *before* a move so the next iteration can compute Δ."""
    context._ppm_probe_pos      = robot_pos_now
    context._ppm_probe_error_px = current_error_px


def try_refine_ppm(
    context,
    robot_pos_now: list,
    current_error_px: float,
    label: str,
) -> float:
    """
    Attempt one PPM-refinement step and return the (possibly updated) ppm_working.

    Parameters
    ----------
    context:          calibration context (holds ppm_working + probe attributes)
    robot_pos_now:    current robot position as [x, y, z, ...] list
    current_error_px: pixel error measured in this iteration (AFTER the previous move)
    label:            short string for the log line (e.g. "marker 0 iter 3")
    """
    probe_pos = getattr(context, "_ppm_probe_pos",      None)
    probe_err = getattr(context, "_ppm_probe_error_px", None)

    if probe_pos is None or probe_err is None or robot_pos_now is None:
        return context.ppm_working

    dx = robot_pos_now[0] - probe_pos[0]
    dy = robot_pos_now[1] - probe_pos[1]
    robot_delta_mm  = math.sqrt(dx * dx + dy * dy)
    pixel_reduction = probe_err - current_error_px

    if (
        robot_delta_mm  > _MIN_ROBOT_DELTA_MM
        and pixel_reduction > _MIN_PIXEL_REDUCTION
        and probe_err       > _MIN_PROBE_ERR_PX
    ):
        ppm_obs = pixel_reduction / robot_delta_mm
        if _PPM_OUTLIER_LO * context.ppm_working < ppm_obs < _PPM_OUTLIER_HI * context.ppm_working:
            ppm_prev   = context.ppm_working
            confidence = min(1.0, max(0.0, (robot_delta_mm - _ALPHA_RAMP_LO_MM) / (_ALPHA_RAMP_HI_MM - _ALPHA_RAMP_LO_MM)))
            alpha      = _ALPHA_MIN + (_ALPHA_MAX - _ALPHA_MIN) * confidence
            context.ppm_working = (1.0 - alpha) * context.ppm_working + alpha * ppm_obs
            _logger.info(
                "PPM refined — %s: robot_move=%.3f mm  Δpx=%.1f  "
                "ppm_obs=%.3f  α=%.2f  ppm_working %.3f → %.3f",
                label, robot_delta_mm, pixel_reduction,
                ppm_obs, alpha, ppm_prev, context.ppm_working,
            )

    return context.ppm_working


def adaptive_stability_wait(context, current_error_mm: float) -> float:
    """
    Return a stability-wait duration scaled to the current error magnitude.

    Small corrections near the threshold settle in milliseconds.
    The full ``context.fast_iteration_wait`` is only used for errors
    at or above ``_MAX_ERR_REF_MM`` (10 mm).
    """
    return _MIN_SETTLE_S + (context.fast_iteration_wait - _MIN_SETTLE_S) * min(
        current_error_mm / _MAX_ERR_REF_MM, 1.0
    )

