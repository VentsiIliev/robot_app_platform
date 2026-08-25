from __future__ import annotations

import logging
import math
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
    allow_subzero_descent: bool = False
    maximum_travel_mm: float | None = None
    minimum_z_mm: float | None = None


@dataclass(frozen=True)
class ServoRetractConfig:
    target_pose: Sequence[float] | None = None
    distance_mm: float | None = None
    motion_type: str = "servo"
    linear_mm_s: float = 25.0
    ptp_velocity_percent: float = 30.0
    ptp_acceleration_percent: float = 30.0
    poll_interval_s: float = 0.02
    timeout_s: float = 10.0
    position_tolerance_mm: float = 2.0
    maximum_distance_mm: float = 500.0
    progress_timeout_s: float = 1.5


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
    retracted: bool = False
    retract_failed: bool = False
    stop_failed: bool = False


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
        retract: ServoRetractConfig | None = None,
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
                if retract is not None:
                    return self._result(
                        started_at,
                        success=False,
                        detected=False,
                        timed_out=False,
                        start_failed=False,
                        condition_failed=False,
                        guard_triggered=False,
                        message="condition_already_active_before_motion",
                    )
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
                if retract is not None:
                    return self._result(
                        started_at,
                        success=False,
                        detected=False,
                        timed_out=False,
                        start_failed=False,
                        condition_failed=False,
                        guard_triggered=False,
                        message="condition_already_active_before_servo",
                    )
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

            travel_start_pose = None
            if cfg.maximum_travel_mm is not None or cfg.minimum_z_mm is not None:
                travel_start_pose = self._read_current_pose()
                if travel_start_pose is None:
                    return self._result(
                        started_at,
                        success=False,
                        detected=False,
                        timed_out=False,
                        start_failed=True,
                        condition_failed=False,
                        guard_triggered=True,
                        message="travel_guard_position_unreadable_before_servo",
                    )
                if cfg.minimum_z_mm is not None and travel_start_pose[2] <= float(cfg.minimum_z_mm):
                    return self._result(
                        started_at,
                        success=False,
                        detected=False,
                        timed_out=False,
                        start_failed=False,
                        condition_failed=False,
                        guard_triggered=True,
                        message="minimum_z_reached_before_servo",
                    )

            servo_kwargs = {
                "linear_mm_s": cfg.linear_mm_s if cfg.axis.value <= 3 else None,
                "angular_deg_s": cfg.angular_deg_s if cfg.axis.value > 3 else None,
                "frame": cfg.frame,
                "tool": cfg.tool,
                "user": cfg.user,
            }
            if cfg.allow_subzero_descent:
                servo_kwargs["allow_subzero_descent"] = True
            start_ret = self._robot.start_servo_jog(cfg.axis, cfg.direction, **servo_kwargs)
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
                    stop_ret = self._stop_servo()
                    started = False
                    if not self._return_code_ok(stop_ret):
                        self._stop_motion()
                        return self._result(
                            started_at,
                            success=False,
                            detected=True,
                            timed_out=False,
                            start_failed=False,
                            condition_failed=False,
                            guard_triggered=False,
                            stop_failed=True,
                            message=f"servo_stop_failed:{stop_ret}",
                        )
                    if retract is not None:
                        retract_ok, retract_message = self._retract(
                            retract,
                            cfg,
                            cancel_requested=cancel_requested,
                            stop_guard=stop_guard,
                        )
                        if not retract_ok:
                            return self._result(
                                started_at,
                                success=False,
                                detected=True,
                                timed_out=retract_message == "retract_timeout",
                                start_failed=False,
                                condition_failed=False,
                                guard_triggered=retract_message.startswith("stop_guard"),
                                retract_failed=True,
                                message=retract_message,
                            )
                    return self._result(
                        started_at,
                        success=True,
                        detected=True,
                        timed_out=False,
                        start_failed=False,
                        condition_failed=False,
                        guard_triggered=False,
                        retracted=retract is not None,
                        message="condition_detected_and_retracted" if retract is not None else "condition_detected",
                    )

                if travel_start_pose is not None:
                    current_pose = self._read_current_pose()
                    if current_pose is None:
                        return self._result(
                            started_at,
                            success=False,
                            detected=False,
                            timed_out=False,
                            start_failed=False,
                            condition_failed=False,
                            guard_triggered=True,
                            message="travel_guard_position_unreadable",
                        )
                    if cfg.minimum_z_mm is not None and current_pose[2] <= float(cfg.minimum_z_mm):
                        _logger.error(
                            "[SERVO_UNTIL_CONDITION] minimum Z reached: live_z=%.3f limit_z=%.3f",
                            current_pose[2],
                            float(cfg.minimum_z_mm),
                        )
                        return self._result(
                            started_at,
                            success=False,
                            detected=False,
                            timed_out=False,
                            start_failed=False,
                            condition_failed=False,
                            guard_triggered=True,
                            message="minimum_z_reached",
                        )
                    axis_index = int(cfg.axis.value) - 1
                    travelled = abs(current_pose[axis_index] - travel_start_pose[axis_index])
                    if cfg.maximum_travel_mm is not None and travelled >= float(cfg.maximum_travel_mm):
                        _logger.error(
                            "[SERVO_UNTIL_CONDITION] maximum travel reached: axis=%s "
                            "travelled=%.3f limit=%.3f",
                            cfg.axis,
                            travelled,
                            float(cfg.maximum_travel_mm),
                        )
                        return self._result(
                            started_at,
                            success=False,
                            detected=False,
                            timed_out=False,
                            start_failed=False,
                            condition_failed=False,
                            guard_triggered=True,
                            message="maximum_travel_reached",
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
                stop_ret = self._stop_servo()
                if not self._return_code_ok(stop_ret):
                    self._stop_motion()

    def _retract(
        self,
        retract: ServoRetractConfig,
        cfg: ServoUntilConditionConfig,
        *,
        cancel_requested: Callable[[], bool] | None,
        stop_guard: Callable[[], bool] | None,
    ) -> tuple[bool, str]:
        current_pose = self._read_current_pose()
        if current_pose is None:
            return False, "retract_position_unreadable"

        start_z = current_pose[2]
        distance_based = retract.distance_mm is not None
        if distance_based:
            distance_mm = float(retract.distance_mm)
            if not math.isfinite(distance_mm) or distance_mm <= 0.0:
                return False, "invalid_retract_distance"
            target_z = start_z + distance_mm
        else:
            target_pose = self._valid_pose(retract.target_pose)
            if target_pose is None:
                return False, "invalid_retract_pose"
            target_z = target_pose[2]
        tolerance = max(0.0, float(retract.position_tolerance_mm))
        maximum_distance = max(0.0, float(retract.maximum_distance_mm))
        requested_distance = target_z - start_z
        if not math.isfinite(float(retract.linear_mm_s)) or float(retract.linear_mm_s) <= 0.0:
            return False, "invalid_retract_linear_speed"
        if requested_distance <= tolerance:
            return False, "retract_target_not_above_contact"
        if requested_distance > maximum_distance:
            return False, "retract_maximum_distance_exceeded"

        motion_type = str(retract.motion_type or "servo").strip().lower()
        if motion_type == "ptp":
            return self._retract_ptp(
                current_pose=current_pose,
                target_z=target_z,
                tolerance=tolerance,
                retract=retract,
                cfg=cfg,
                cancel_requested=cancel_requested,
            )
        if motion_type != "servo":
            return False, "invalid_retract_motion_type"

        # The configured jog speed is an upper command value; acceleration,
        # controller scaling, and transport sampling can make a long retract
        # take materially longer than distance / commanded speed. Keep the
        # explicit timeout as a floor and derive a conservative distance-aware
        # deadline. The independent progress watchdog still stops stalled motion.
        distance_aware_timeout = requested_distance / float(retract.linear_mm_s) * 4.0 + 1.0
        effective_timeout = max(float(retract.timeout_s), distance_aware_timeout)
        _logger.info(
            "[SERVO_UNTIL_CONDITION] retract starting start_z=%.3f target_z=%.3f distance_mm=%.3f "
            "speed_mm_s=%.3f configured_timeout_s=%.3f effective_timeout_s=%.3f tolerance_mm=%.3f",
            start_z,
            target_z,
            requested_distance,
            float(retract.linear_mm_s),
            float(retract.timeout_s),
            effective_timeout,
            tolerance,
        )

        start_ret = self._robot.start_servo_jog(
            RobotAxis.Z,
            Direction.PLUS,
            linear_mm_s=float(retract.linear_mm_s),
            angular_deg_s=None,
            frame=cfg.frame,
            tool=cfg.tool,
            user=cfg.user,
        )
        if not self._return_code_ok(start_ret):
            return False, f"retract_servo_start_failed:{start_ret}"

        deadline = time.monotonic() + max(0.0, effective_timeout)
        poll_interval = max(0.005, float(retract.poll_interval_s))
        next_progress_log_at = time.monotonic()
        best_z = start_z
        last_forward_progress_at = time.monotonic()
        progress_timeout = max(0.5, float(retract.progress_timeout_s))
        failure = ""
        while not failure:
            if cancel_requested is not None and cancel_requested():
                failure = "cancelled_during_retract"
                break
            if stop_guard is not None:
                try:
                    if bool(stop_guard()):
                        failure = "stop_guard_triggered_during_retract"
                        break
                except Exception:
                    _logger.exception("[SERVO_UNTIL_CONDITION] retract stop guard read failed")
                    failure = "stop_guard_unreadable_during_retract"
                    break
            current_pose = self._read_current_pose()
            if current_pose is None:
                failure = "retract_position_unreadable"
                break
            travelled = current_pose[2] - start_z
            now = time.monotonic()
            if current_pose[2] > best_z + 0.5:
                best_z = current_pose[2]
                last_forward_progress_at = now
            if now >= next_progress_log_at:
                _logger.info(
                    "[SERVO_UNTIL_CONDITION] retract progress live_z=%.3f target_z=%.3f travelled_mm=%.3f",
                    current_pose[2],
                    target_z,
                    travelled,
                )
                next_progress_log_at = now + 0.5
            if travelled > maximum_distance + tolerance:
                failure = "retract_maximum_distance_exceeded"
                break
            reached_target = (
                travelled >= requested_distance
                if distance_based
                else current_pose[2] >= target_z - tolerance
            )
            if reached_target:
                break
            if now - last_forward_progress_at >= progress_timeout:
                failure = "retract_progress_stalled"
                break
            if time.monotonic() >= deadline:
                failure = "retract_timeout"
                break
            time.sleep(poll_interval)

        stop_ret = self._stop_servo()
        if not self._return_code_ok(stop_ret):
            self._stop_motion()
            return False, f"retract_servo_stop_failed:{stop_ret}"
        if failure:
            return False, failure
        final_pose = self._read_current_pose()
        if final_pose is None:
            return False, "retract_final_position_unreadable"
        final_travelled = final_pose[2] - start_z
        if distance_based:
            if final_travelled < requested_distance:
                _logger.error(
                    "[SERVO_UNTIL_CONDITION] retract final clearance insufficient "
                    "travelled_mm=%.3f required_mm=%.3f",
                    final_travelled,
                    requested_distance,
                )
                return False, "retract_final_clearance_insufficient"
            if final_travelled > maximum_distance:
                _logger.error(
                    "[SERVO_UNTIL_CONDITION] retract final clearance exceeded "
                    "travelled_mm=%.3f maximum_mm=%.3f",
                    final_travelled,
                    maximum_distance,
                )
                return False, "retract_maximum_distance_exceeded"
            _logger.info(
                "[SERVO_UNTIL_CONDITION] retract clearance completed "
                "travelled_mm=%.3f required_mm=%.3f maximum_mm=%.3f",
                final_travelled,
                requested_distance,
                maximum_distance,
            )
            return True, ""
        if abs(final_pose[2] - target_z) > tolerance:
            _logger.error(
                "[SERVO_UNTIL_CONDITION] retract final mismatch final_z=%.3f target_z=%.3f tolerance_mm=%.3f",
                final_pose[2],
                target_z,
                tolerance,
            )
            return False, "retract_final_position_mismatch"
        _logger.info(
            "[SERVO_UNTIL_CONDITION] retract completed final_z=%.3f target_z=%.3f",
            final_pose[2],
            target_z,
        )
        return True, ""

    def _retract_ptp(
        self,
        *,
        current_pose: list[float],
        target_z: float,
        tolerance: float,
        retract: ServoRetractConfig,
        cfg: ServoUntilConditionConfig,
        cancel_requested: Callable[[], bool] | None,
    ) -> tuple[bool, str]:
        if cancel_requested is not None and cancel_requested():
            return False, "cancelled_before_retract"
        velocity = float(retract.ptp_velocity_percent)
        acceleration = float(retract.ptp_acceleration_percent)
        if not math.isfinite(velocity) or velocity <= 0.0:
            return False, "invalid_retract_ptp_velocity"
        if not math.isfinite(acceleration) or acceleration <= 0.0:
            return False, "invalid_retract_ptp_acceleration"

        target_pose = list(current_pose)
        target_pose[2] = target_z
        _logger.info(
            "[SERVO_UNTIL_CONDITION] PTP retract starting start_z=%.3f target_z=%.3f vel=%.3f acc=%.3f",
            current_pose[2],
            target_z,
            velocity,
            acceleration,
        )
        try:
            ret = self._robot.move_ptp(
                target_pose,
                tool=cfg.tool,
                user=cfg.user,
                velocity=velocity,
                acceleration=acceleration,
                wait_to_reach=True,
            )
        except TypeError:
            ret = self._robot.move_ptp(
                target_pose,
                tool=cfg.tool,
                user=cfg.user,
                vel=velocity,
                acc=acceleration,
                blocking=True,
            )
        except Exception:
            _logger.exception("[SERVO_UNTIL_CONDITION] PTP retract failed")
            self._stop_motion()
            return False, "retract_ptp_failed"
        if not self._return_code_ok(ret):
            self._stop_motion()
            return False, f"retract_ptp_failed:{ret}"
        if cancel_requested is not None and cancel_requested():
            self._stop_motion()
            return False, "cancelled_during_retract"

        final_pose = self._read_current_pose()
        if final_pose is None:
            return False, "retract_final_position_unreadable"
        if abs(final_pose[2] - target_z) > tolerance:
            _logger.error(
                "[SERVO_UNTIL_CONDITION] PTP retract final mismatch final_z=%.3f target_z=%.3f tolerance_mm=%.3f",
                final_pose[2],
                target_z,
                tolerance,
            )
            return False, "retract_final_position_mismatch"
        _logger.info(
            "[SERVO_UNTIL_CONDITION] PTP retract completed final_z=%.3f target_z=%.3f",
            final_pose[2],
            target_z,
        )
        return True, ""

    def _stop_servo(self):
        try:
            return self._robot.stop_servo_jog()
        except Exception:
            _logger.exception("[SERVO_UNTIL_CONDITION] stop_servo_jog failed")
            return -1

    def _stop_motion(self) -> None:
        try:
            self._robot.stop_motion()
        except Exception:
            _logger.exception("[SERVO_UNTIL_CONDITION] stop_motion failed")

    def _read_current_pose(self) -> list[float] | None:
        try:
            getter = getattr(self._robot, "get_current_position_fresh", None)
            if not callable(getter):
                getter = self._robot.get_current_position
            return self._valid_pose(getter())
        except Exception:
            _logger.exception("[SERVO_UNTIL_CONDITION] current position read failed")
            return None

    @staticmethod
    def _valid_pose(pose: Sequence[float] | None) -> list[float] | None:
        if pose is None or len(pose) < 6:
            return None
        try:
            values = [float(value) for value in pose[:6]]
        except (TypeError, ValueError):
            return None
        return values if all(math.isfinite(value) for value in values) else None

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
        if cfg.maximum_travel_mm is not None:
            try:
                maximum_travel = float(cfg.maximum_travel_mm)
            except (TypeError, ValueError):
                return False, "invalid_maximum_travel"
            if not math.isfinite(maximum_travel) or maximum_travel <= 0.0:
                return False, "invalid_maximum_travel"
        if cfg.minimum_z_mm is not None:
            try:
                minimum_z = float(cfg.minimum_z_mm)
            except (TypeError, ValueError):
                return False, "invalid_minimum_z"
            if not math.isfinite(minimum_z):
                return False, "invalid_minimum_z"
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
        retracted: bool = False,
        retract_failed: bool = False,
        stop_failed: bool = False,
    ) -> ServoUntilConditionResult:
        return ServoUntilConditionResult(
            success=bool(success),
            detected=bool(detected),
            timed_out=bool(timed_out),
            start_failed=bool(start_failed),
            condition_failed=bool(condition_failed),
            guard_triggered=bool(guard_triggered),
            retracted=bool(retracted),
            retract_failed=bool(retract_failed),
            stop_failed=bool(stop_failed),
            elapsed_s=max(0.0, time.monotonic() - started_at),
            message=str(message),
        )
