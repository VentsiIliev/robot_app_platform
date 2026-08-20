from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

from src.engine.robot.enums.axis import Direction, RobotAxis

_logger = logging.getLogger(__name__)


class PickupCondition(Protocol):
    def is_active(self) -> bool:
        ...


@dataclass(frozen=True)
class ServoUntilConditionConfig:
    axis: RobotAxis = RobotAxis.Z
    direction: Direction = Direction.MINUS
    linear_mm_s: float = 25.0
    angular_deg_s: float | None = None
    frame: str | int = "user"
    tool: int = 0
    user: int = 0
    poll_interval_s: float = 0.02
    timeout_s: float = 10.0
    approach_velocity: float = 10.0
    approach_acceleration: float = 10.0
    preflight_condition_read_attempts: int = 2
    condition_read_failure_limit: int = 3


@dataclass(frozen=True)
class ServoUntilConditionResult:
    success: bool
    detected: bool
    timed_out: bool
    start_failed: bool
    elapsed_s: float
    message: str
    condition_failed: bool = False
    guard_triggered: bool = False


class ServoUntilConditionProcedure:
    """
    Generic servo-until-condition primitive.

    This is intentionally robot-system agnostic. The condition can be a vacuum
    sensor, force threshold, distance sensor, dummy test trigger, or any object
    exposing is_active().
    """

    def __init__(
        self,
        robot,
        condition: PickupCondition | Callable[[], bool],
    ) -> None:
        self._robot = robot
        self._condition = condition

    def run(
        self,
        *,
        approach_pose: Sequence[float] | None = None,
        config: ServoUntilConditionConfig | None = None,
        cancel_requested: Callable[[], bool] | None = None,
        stop_guard: Callable[[], bool] | None = None,
    ) -> ServoUntilConditionResult:
        cfg = config or ServoUntilConditionConfig()
        started = False
        started_at = time.monotonic()

        try:
            valid, message = self._validate_config(cfg)
            if not valid:
                return self._result(
                    started_at,
                    success=False,
                    detected=False,
                    timed_out=False,
                    start_failed=False,
                    condition_failed=False,
                    guard_triggered=False,
                    message=message,
                )

            preflight = self._preflight_condition(cfg)
            if preflight is None:
                return self._result(
                    started_at,
                    success=False,
                    detected=False,
                    timed_out=False,
                    start_failed=False,
                    condition_failed=True,
                    guard_triggered=False,
                    message="condition_unreadable_before_motion",
                )
            if preflight:
                return self._result(
                    started_at,
                    success=True,
                    detected=True,
                    timed_out=False,
                    start_failed=False,
                    condition_failed=False,
                    guard_triggered=False,
                    message="condition_already_active",
                )

            if approach_pose is not None:
                if not self._move_to_approach(approach_pose, cfg):
                    return self._result(
                        started_at,
                        success=False,
                        detected=False,
                        timed_out=False,
                        start_failed=True,
                        condition_failed=False,
                        guard_triggered=False,
                        message="approach_failed",
                    )

            active, read_ok = self._read_condition()
            if not read_ok:
                return self._result(
                    started_at,
                    success=False,
                    detected=False,
                    timed_out=False,
                    start_failed=False,
                    condition_failed=True,
                    guard_triggered=False,
                    message="condition_unreadable_after_approach",
                )
            if active:
                return self._result(
                    started_at,
                    success=True,
                    detected=True,
                    timed_out=False,
                    start_failed=False,
                    condition_failed=False,
                    guard_triggered=False,
                    message="condition_already_active",
                )

            start_ret = self._robot.start_servo_jog(
                cfg.axis,
                cfg.direction,
                linear_mm_s=cfg.linear_mm_s if cfg.axis.value <= 3 else None,
                angular_deg_s=cfg.angular_deg_s if cfg.axis.value > 3 else None,
                frame=cfg.frame,
                tool=cfg.tool,
                user=cfg.user,
            )
            if not self._return_code_ok(start_ret):
                return self._result(
                    started_at,
                    success=False,
                    detected=False,
                    timed_out=False,
                    start_failed=True,
                    condition_failed=False,
                    guard_triggered=False,
                    message=f"servo_start_failed:{start_ret}",
                )

            started = True
            self._notify_condition_servo_started()
            deadline = started_at + max(0.0, float(cfg.timeout_s))
            poll_interval_s = max(0.005, float(cfg.poll_interval_s))
            read_failure_count = 0
            read_failure_limit = max(1, int(cfg.condition_read_failure_limit))

            while True:
                if cancel_requested is not None and cancel_requested():
                    return self._result(
                        started_at,
                        success=False,
                        detected=False,
                        timed_out=False,
                        start_failed=False,
                        condition_failed=False,
                        guard_triggered=False,
                        message="cancelled",
                    )

                active, read_ok = self._read_condition()
                if not read_ok:
                    read_failure_count += 1
                    _logger.warning(
                        "[SERVO_UNTIL_CONDITION] condition read failed while servo active (%d/%d)",
                        read_failure_count,
                        read_failure_limit,
                    )
                    if read_failure_count >= read_failure_limit:
                        return self._result(
                            started_at,
                            success=False,
                            detected=False,
                            timed_out=False,
                            start_failed=False,
                            condition_failed=True,
                            guard_triggered=False,
                            message="condition_unreadable_during_servo",
                        )
                else:
                    read_failure_count = 0

                if active:
                    return self._result(
                        started_at,
                        success=True,
                        detected=True,
                        timed_out=False,
                        start_failed=False,
                        condition_failed=False,
                        guard_triggered=False,
                        message="condition_detected",
                    )

                if stop_guard is not None:
                    try:
                        guard_active = bool(stop_guard())
                    except Exception:
                        _logger.exception("[SERVO_UNTIL_CONDITION] stop guard read failed")
                        return self._result(
                            started_at,
                            success=False,
                            detected=False,
                            timed_out=False,
                            start_failed=False,
                            condition_failed=False,
                            guard_triggered=True,
                            message="stop_guard_unreadable",
                        )
                    if guard_active:
                        return self._result(
                            started_at,
                            success=False,
                            detected=False,
                            timed_out=False,
                            start_failed=False,
                            condition_failed=False,
                            guard_triggered=True,
                            message="stop_guard_triggered",
                        )

                if time.monotonic() >= deadline:
                    return self._result(
                        started_at,
                        success=False,
                        detected=False,
                        timed_out=True,
                        start_failed=False,
                        condition_failed=False,
                        guard_triggered=False,
                        message="timeout",
                    )

                time.sleep(poll_interval_s)
        finally:
            if started:
                try:
                    self._robot.stop_servo_jog()
                except Exception:
                    _logger.exception("[SERVO_UNTIL_CONDITION] stop_servo_jog failed")

    def _move_to_approach(
        self,
        approach_pose: Sequence[float],
        cfg: ServoUntilConditionConfig,
    ) -> bool:
        try:
            ret = self._robot.move_ptp(
                list(approach_pose),
                tool=cfg.tool,
                user=cfg.user,
                vel=cfg.approach_velocity,
                acc=cfg.approach_acceleration,
                blocking=True,
            )
        except TypeError:
            ret = self._robot.move_ptp(
                list(approach_pose),
                tool=cfg.tool,
                user=cfg.user,
                velocity=cfg.approach_velocity,
                acceleration=cfg.approach_acceleration,
                wait_to_reach=True,
            )
        except Exception:
            _logger.exception("[SERVO_UNTIL_CONDITION] approach move failed")
            return False
        return self._return_code_ok(ret)

    def _preflight_condition(self, cfg: ServoUntilConditionConfig) -> bool | None:
        attempts = max(1, int(cfg.preflight_condition_read_attempts))
        poll_interval_s = max(0.005, float(cfg.poll_interval_s))
        for attempt in range(1, attempts + 1):
            active, read_ok = self._read_condition()
            if read_ok:
                return active
            _logger.warning(
                "[SERVO_UNTIL_CONDITION] condition preflight read failed (%d/%d)",
                attempt,
                attempts,
            )
            if attempt < attempts:
                time.sleep(poll_interval_s)
        return None

    def _read_condition(self) -> tuple[bool, bool]:
        try:
            if callable(self._condition):
                return bool(self._condition()), True
            return bool(self._condition.is_active()), True
        except Exception:
            _logger.exception("[SERVO_UNTIL_CONDITION] condition read failed")
            return False, False

    def _notify_condition_servo_started(self) -> None:
        callback = getattr(self._condition, "on_servo_start", None)
        if callback is None or not callable(callback):
            return
        try:
            callback()
        except Exception:
            _logger.exception("[SERVO_UNTIL_CONDITION] condition on_servo_start failed")

    @staticmethod
    def _validate_config(cfg: ServoUntilConditionConfig) -> tuple[bool, str]:
        try:
            axis = cfg.axis
            axis_value = int(axis.value if hasattr(axis, "value") else axis)
        except (TypeError, ValueError):
            return False, "invalid_axis"
        if axis_value <= 3:
            try:
                speed = float(cfg.linear_mm_s)
            except (TypeError, ValueError):
                return False, "invalid_linear_speed"
            if speed <= 0.0:
                return False, "invalid_linear_speed"
        else:
            try:
                speed = float(cfg.angular_deg_s)
            except (TypeError, ValueError):
                return False, "invalid_angular_speed"
            if speed <= 0.0:
                return False, "invalid_angular_speed"
        return True, ""

    @staticmethod
    def _return_code_ok(ret) -> bool:
        if isinstance(ret, bool):
            return ret
        try:
            return int(ret) == 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _result(
        started_at: float,
        *,
        success: bool,
        detected: bool,
        timed_out: bool,
        start_failed: bool,
        condition_failed: bool,
        guard_triggered: bool,
        message: str,
    ) -> ServoUntilConditionResult:
        return ServoUntilConditionResult(
            success=bool(success),
            detected=bool(detected),
            timed_out=bool(timed_out),
            start_failed=bool(start_failed),
            condition_failed=bool(condition_failed),
            guard_triggered=bool(guard_triggered),
            elapsed_s=max(0.0, time.monotonic() - started_at),
            message=str(message),
        )
