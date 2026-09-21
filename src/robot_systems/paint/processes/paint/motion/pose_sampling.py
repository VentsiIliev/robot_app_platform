"""Robot-pose sampling shared by paint pickup workflows."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable


class FreshPoseReadError(RuntimeError):
    """Raised when a required fresh six-axis robot pose cannot be acquired."""


def read_fresh_pose(
    robot_service: object,
    *,
    error_message: str,
) -> list[float]:
    """Read one valid six-axis pose through the required fresh-read API."""
    getter = getattr(robot_service, "get_current_position_fresh", None)
    if not callable(getter):
        raise FreshPoseReadError(f"{error_message}: get_current_position_fresh() is unavailable")
    try:
        pose = getter()
    except Exception as exc:
        raise FreshPoseReadError(error_message) from exc
    try:
        values = [float(value) for value in list(pose)[:6]]
    except (TypeError, ValueError) as exc:
        raise FreshPoseReadError(f"{error_message}: pose is not numeric") from exc
    if len(values) != 6 or not all(math.isfinite(value) for value in values):
        raise FreshPoseReadError(f"{error_message}: expected six finite axis values")
    return values


def wait_for_stable_pose(
    robot_service: object,
    *,
    logger: logging.Logger,
    read_error_message: str,
    timeout_message: str,
    timeout_s: float = 1.0,
    minimum_timeout_s: float = 0.0,
    sample_interval_s: float = 0.05,
    minimum_sample_interval_s: float = 0.0,
    required_stable_samples: int = 3,
    xyz_tolerance_mm: float = 0.5,
    angular_tolerance_deg: float = 0.2,
    stable_log_prefix: str | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> list[float] | None:
    """Return a pose after consecutive samples show that robot motion has settled."""
    deadline = monotonic() + max(float(minimum_timeout_s), float(timeout_s))
    previous = None
    stable_samples = 0
    while monotonic() < deadline:
        pose = read_fresh_pose(robot_service, error_message=read_error_message)
        if previous is not None:
            xyz_delta = math.sqrt(sum(
                (pose[index] - previous[index]) ** 2 for index in range(3)
            ))
            angular_delta = max(
                abs((pose[index] - previous[index] + 180.0) % 360.0 - 180.0)
                for index in range(3, 6)
            )
            if xyz_delta <= xyz_tolerance_mm and angular_delta <= angular_tolerance_deg:
                stable_samples += 1
                if stable_samples >= max(1, int(required_stable_samples)):
                    if stable_log_prefix:
                        logger.info(
                            "%s Robot pose stable: xyz_delta_mm=%.3f "
                            "angular_delta_deg=%.3f samples=%d pose=%s",
                            stable_log_prefix,
                            xyz_delta,
                            angular_delta,
                            stable_samples,
                            [round(value, 3) for value in pose],
                        )
                    return pose
            else:
                stable_samples = 0
            previous = pose
        else:
            previous = pose
        sleep(max(float(minimum_sample_interval_s), float(sample_interval_s)))
    logger.error(timeout_message)
    return None
