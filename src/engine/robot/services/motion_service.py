import math
import logging
import time
from threading import Event, Thread
from typing import Callable, List, Optional

from ..interfaces.i_motion_service import IMotionService
from ..interfaces.i_robot import IRobot
from ..interfaces.i_safety_checker import ISafetyChecker
from ..enums.axis import RobotAxis, Direction
from ..motion_sequence import MotionSequenceSegment
from ..safety.motion_corridor import MotionCorridor, MotionCorridorRegistry
from src.shared_contracts.events.robot_events import RobotTopics


class MotionService(IMotionService):
    _WAIT_THRESHOLD_MM = 2
    _WAIT_THRESHOLD_DEG = 1.0
    _WAIT_DELAY_S = 0.1
    _WAIT_TIMEOUT_S = 10.0
    _STOP_RETRY_DELAY_S = 0.05
    _STOP_ATTEMPTS = 3
    _JOG_TARGET_REUSE_POS_MM = 5.0
    _JOG_TARGET_REUSE_ANG_DEG = 2.0
    _SERVO_FLOOR_POLL_S = 0.02

    def __init__(
            self,
            robot: IRobot,
            safety_checker: ISafetyChecker,
            jog_velocity: float = 10.0,
            jog_acceleration: float = 10.0,
            messaging_service=None,
    ):
        self._robot = robot
        self._safety = safety_checker
        self._jog_vel = jog_velocity
        self._jog_acc = jog_acceleration
        self._last_jog_target: List[float] = []
        self._logger = logging.getLogger(self.__class__.__name__)
        self._cached_position: List[float] = []
        self._motion_corridors = MotionCorridorRegistry()
        self._servo_floor_stop = Event()
        self._servo_floor_thread: Thread | None = None
        if messaging_service:
            messaging_service.subscribe(RobotTopics.POSITION, self._on_position)

    def _on_position(self, position: List[float]) -> None:
        self._cached_position = position
        if self._last_jog_target and self._positions_close(position, self._last_jog_target):
            self._last_jog_target = list(position)

    def set_motion_passage_closed(self, passage_id: str, closed: bool) -> bool:
        """Forward planning-scene passage state changes to the robot driver."""
        setter = getattr(self._robot, "set_motion_passage_closed", None)
        if not callable(setter):
            self._logger.error("Motion passage control is unavailable passage_id=%s", passage_id)
            return False
        try:
            return bool(setter(str(passage_id), bool(closed)))
        except Exception:
            self._logger.exception(
                "Failed to set motion passage state passage_id=%s closed=%s",
                passage_id,
                closed,
            )
            return False

    def move_ptp(
            self,
            position,
            tool,
            user,
            velocity,
            acceleration,
            wait_to_reach=False,
            wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        self._last_jog_target = []
        started = time.perf_counter()
        safety_started = time.perf_counter()
        violations = self._motion_violations(position)
        self._logger.info(
            "[TIMING] move_ptp_safety_check elapsed_s=%.3f violations=%d",
            time.perf_counter() - safety_started,
            len(violations),
        )
        if violations:
            self._logger.warning("move_ptp blocked by safety limits: %s", ", ".join(violations))
            return False
        try:
            self._logger.debug("move_ptp → pos=%s tool=%s user=%s vel=%s acc=%s", position, tool, user, velocity,
                               acceleration)
            driver_started = time.perf_counter()

            ret = self._robot.move_ptp(
                position,
                tool,
                user,
                velocity,
                acceleration,
                blocking=wait_to_reach
            )

            driver_elapsed = time.perf_counter() - driver_started
            success = ret >= 0
            wait_elapsed = 0.0
            if wait_to_reach and success:
                wait_started = time.perf_counter()
                success = self._wait_for_position(position, cancelled=wait_cancelled)
                wait_elapsed = time.perf_counter() - wait_started
            self._logger.info(
                "[TIMING] move_ptp_total success=%s driver_elapsed_s=%.3f wait_elapsed_s=%.3f total_elapsed_s=%.3f pos=%s vel=%s acc=%s",
                success,
                driver_elapsed,
                wait_elapsed,
                time.perf_counter() - started,
                [round(float(v), 3) for v in position[:6]] if position and len(position) >= 6 else position,
                velocity,
                acceleration,
            )
            self._logger.debug("move_ptp ← success=%s", success)
            return success
        except Exception:
            self._logger.exception("move_ptp failed")
            return False

    def move_linear(
            self,
            position,
            tool,
            user,
            velocity,
            acceleration,
            blendR=0.0,
            wait_to_reach=False,
            wait_cancelled: Callable[[], bool] | None = None,
            allow_subzero_step_recovery: bool = False,
            allow_collision_recovery: bool = False,
            bypass_safety_limits: bool = False,
    ) -> bool:
        self._last_jog_target = []
        violations = self._motion_violations(position)
        if bypass_safety_limits and violations:
            self._logger.warning(
                "move_linear platform safety limits BYPASSED by Jog Recovery: %s",
                ", ".join(violations),
            )
            violations = []
        if allow_subzero_step_recovery:
            current = self._fresh_position()
            if not self._is_bounded_subzero_retract(current, position):
                self._logger.warning(
                    "move_linear recovery rejected: requires a pure upward move from sub-zero Z"
                )
                return False
            violations = [
                violation for violation in violations
                if "sub-zero" not in violation.lower()
                and not (
                    violation.lstrip().startswith("Z=")
                    and "not in [0," in violation
                )
            ]
        if violations:
            self._logger.warning("move_linear blocked by safety limits: %s", ", ".join(violations))
            return False
        try:
            self._logger.debug("move_linear → pos=%s tool=%s user=%s vel=%s acc=%s blendR=%s", position, tool, user,
                               velocity, acceleration, blendR)
            driver_kwargs = {"blocking": wait_to_reach}
            if allow_subzero_step_recovery or allow_collision_recovery:
                driver_kwargs["allow_collision_recovery"] = True
            ret = self._robot.move_linear(
                position, tool, user, velocity, acceleration, blendR, **driver_kwargs
            )
            success = ret >= 0
            if wait_to_reach and success:
                success = self._wait_for_position(position, cancelled=wait_cancelled)
            self._logger.debug("move_linear ← success=%s", success)
            return success
        except Exception:
            self._logger.exception("move_linear failed")
            return False

    def move_sequence(
            self,
            segments: List[MotionSequenceSegment],
            tool: int,
            user: int,
            wait_to_reach=False,
            wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        self._last_jog_target = []
        started = time.perf_counter()
        if not segments:
            self._logger.warning("move_sequence rejected: empty sequence")
            return False

        safety_started = time.perf_counter()
        for index, segment in enumerate(segments):
            violations = self._motion_violations(segment.position)
            if violations:
                self._logger.warning(
                    "move_sequence blocked by safety limits at segment %d: %s",
                    index,
                    ", ".join(violations),
                )
                return False
        self._logger.info(
            "[TIMING] move_sequence_safety_check elapsed_s=%.3f segments=%d",
            time.perf_counter() - safety_started,
            len(segments),
        )

        try:
            if not self._robot.set_active_tool(tool):
                self._logger.warning("move_sequence rejected: failed to set active tool=%s", tool)
                return False
            driver_started = time.perf_counter()
            ret = self._robot.execute_motion_sequence(
                segments,
                tool=tool,
                user=user,
                blocking=wait_to_reach,
            )
            driver_elapsed = time.perf_counter() - driver_started
            success = ret >= 0
            wait_elapsed = 0.0
            if wait_to_reach and success:
                wait_started = time.perf_counter()
                success = self._wait_for_position(segments[-1].position, cancelled=wait_cancelled)
                wait_elapsed = time.perf_counter() - wait_started
            self._logger.info(
                "[TIMING] move_sequence_total success=%s driver_elapsed_s=%.3f wait_elapsed_s=%.3f total_elapsed_s=%.3f segments=%d",
                success,
                driver_elapsed,
                wait_elapsed,
                time.perf_counter() - started,
                len(segments),
            )
            return bool(success)
        except Exception:
            self._logger.exception("move_sequence failed")
            return False

    def move_custom_sequence(
            self,
            segments: List[MotionSequenceSegment],
            tool: int,
            user: int,
            wait_to_reach=False,
            wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        self._last_jog_target = []
        started = time.perf_counter()
        if not segments:
            self._logger.warning("move_custom_sequence rejected: empty sequence")
            return False

        safety_started = time.perf_counter()
        for index, segment in enumerate(segments):
            violations = self._motion_violations(segment.position)
            if violations:
                self._logger.warning(
                    "move_custom_sequence blocked by safety limits at segment %d: %s",
                    index,
                    ", ".join(violations),
                )
                return False
        self._logger.info(
            "[TIMING] move_custom_sequence_safety_check elapsed_s=%.3f segments=%d",
            time.perf_counter() - safety_started,
            len(segments),
        )

        try:
            if not self._robot.set_active_tool(tool):
                self._logger.warning("move_custom_sequence rejected: failed to set active tool=%s", tool)
                return False
            driver_started = time.perf_counter()
            ret = self._robot.execute_custom_motion_sequence(
                segments,
                tool=tool,
                user=user,
                blocking=wait_to_reach,
            )
            driver_elapsed = time.perf_counter() - driver_started
            success = ret >= 0
            wait_elapsed = 0.0
            if wait_to_reach and success:
                wait_started = time.perf_counter()
                success = self._wait_for_position(segments[-1].position, cancelled=wait_cancelled)
                wait_elapsed = time.perf_counter() - wait_started
            self._logger.info(
                "[TIMING] move_custom_sequence_total success=%s driver_elapsed_s=%.3f wait_elapsed_s=%.3f total_elapsed_s=%.3f segments=%d",
                success,
                driver_elapsed,
                wait_elapsed,
                time.perf_counter() - started,
                len(segments),
            )
            return bool(success)
        except Exception:
            self._logger.exception("move_custom_sequence failed")
            return False

    def start_jog(
            self,
            axis: RobotAxis,
            direction: Direction,
            step: float,
            velocity: float | None = None,
            acceleration: float | None = None,
    ) -> int:
        jog_velocity = self._jog_vel if velocity is None else float(velocity)
        jog_acceleration = self._jog_acc if acceleration is None else float(acceleration)
        self._logger.debug(
            "start_jog → axis=%s direction=%s step=%s vel=%s acc=%s",
            axis,
            direction,
            step,
            jog_velocity,
            jog_acceleration,
        )
        try:
            current = self._robot.get_current_position()
            self._logger.info(f"Current -> {current}")
            base_position = self._select_jog_base_position(current)
            self._logger.info(f"Jog base -> {base_position}")
            if base_position and len(base_position) >= 3:
                target = list(base_position)

                idx = axis.value - 1  # X=0, Y=1, Z=2, RX=3, RY=4, RZ=5
                if idx < len(target):
                    if idx < 3 and len(target) >= 6:
                        dx, dy, dz = self._tool_frame_delta(target, idx, direction.value, step)
                        target[0] += dx
                        target[1] += dy
                        target[2] += dz
                    else:
                        target[idx] += direction.value * step
                self._logger.info(f"Target -> {target}")
                violations = self._motion_violations(target)
                # Recovery from an accidental sub-zero opening collision must
                # remain possible with the physical step jog controls.  Keep
                # this exception deliberately narrow: only Cartesian X/Y/Z,
                # positive/negative 1 mm steps, and only while the measured
                # pose is already below the platform floor.  Remove only the
                # synthetic sub-zero floor/corridor messages; all workspace,
                # collision, drive, and joint-limit checks remain enforced.
                if (
                    axis in (RobotAxis.X, RobotAxis.Y, RobotAxis.Z)
                    and abs(float(step)) <= 1.0
                    and base_position
                    and len(base_position) >= 3
                    and float(base_position[2]) < 0.0
                ):
                    violations = [
                        violation for violation in violations
                        if "sub-zero" not in violation.lower()
                        and "not in [0, 800]" not in violation.lower()
                    ]
                if violations:
                    self._logger.warning(
                        "start_jog blocked by safety limits: axis=%s dir=%s step=%s → %s",
                        axis, direction, step, ", ".join(violations),
                    )
                    return -1
            else:
                target = []

            ret = self._robot.start_jog(axis, direction, step, jog_velocity, jog_acceleration)
            if ret == 0 and target:
                self._last_jog_target = list(target)
            self._logger.debug("start_jog ← ret=%s", ret)
            return ret
        except Exception:
            self._logger.exception("start_jog failed")
            return -1

    def start_servo_jog(
            self,
            axis: RobotAxis,
            direction: Direction,
            linear_mm_s: float | None = None,
            angular_deg_s: float | None = None,
            *,
            frame: str | int = "user",
            tool: int = 0,
            user: int = 0,
            allow_subzero_descent: bool = False,
            allow_subzero_retract_settle: bool = False,
            disable_collision_checking: bool = False,
    ) -> int:
        self._last_jog_target = []
        try:
            starter = getattr(self._robot, "start_servo_jog", None)
            if not callable(starter):
                return -1
            current_getter = getattr(self._robot, "get_current_position_fresh", None)
            if not callable(current_getter):
                current_getter = self._robot.get_current_position
            current = list(current_getter() or self._cached_position or [])
            subzero_recovery = (
                axis == RobotAxis.Z
                and direction == Direction.PLUS
                and len(current) >= 3
                and float(current[2]) < 0.0
            )
            bounded_retract_settle = (
                axis == RobotAxis.Z
                and direction == Direction.PLUS
                and len(current) >= 3
                and allow_subzero_retract_settle
            )
            recovery = subzero_recovery or bounded_retract_settle
            result = int(starter(
                axis,
                direction,
                linear_mm_s=linear_mm_s,
                angular_deg_s=angular_deg_s,
                frame=frame,
                tool=tool,
                user=user,
                disable_collision_checking=disable_collision_checking,
            ))
            if result == 0:
                if allow_subzero_descent:
                    self._servo_floor_stop.set()
                    self._logger.info(
                        "Servo Z-floor bypassed for bounded sub-zero descent procedure"
                    )
                else:
                    self._start_servo_floor_supervisor(
                        allow_subzero_recovery=recovery,
                        initial_z=float(current[2]) if recovery else None,
                        allow_initial_reverse_settle=bounded_retract_settle,
                    )
            return result
        except Exception:
            self._logger.exception("start_servo_jog failed")
            return -1

    def start_joint_jog(
            self,
            joint: str,
            direction: Direction,
            step: float,
            velocity: float | None = None,
            acceleration: float | None = None,
    ) -> int:
        self._last_jog_target = []
        jog_velocity = self._jog_vel if velocity is None else float(velocity)
        jog_acceleration = self._jog_acc if acceleration is None else float(acceleration)
        try:
            starter = getattr(self._robot, "start_joint_jog", None)
            if not callable(starter):
                return -1
            return int(starter(joint, direction, step, jog_velocity, jog_acceleration))
        except Exception:
            self._logger.exception("start_joint_jog failed")
            return -1

    def stop_servo_jog(self, *, restore_collision_checking: bool = True, timing_trace_id: str | None = None) -> int:
        self._last_jog_target = []
        self._servo_floor_stop.set()
        try:
            stopper = getattr(self._robot, "stop_servo_jog", None)
            if not callable(stopper):
                return -1
            kwargs = {"restore_collision_checking": restore_collision_checking}
            if timing_trace_id is not None:
                kwargs["timing_trace_id"] = timing_trace_id
            return int(stopper(**kwargs))
        except Exception:
            self._logger.exception("stop_servo_jog failed")
            return -1

    def servo_jog_to_z(self, **kwargs) -> dict | None:
        self._last_jog_target = []
        self._servo_floor_stop.set()
        mover = getattr(self._robot, "servo_jog_to_z", None)
        if not callable(mover):
            return None
        try:
            return mover(**kwargs)
        except Exception:
            self._logger.exception("servo_jog_to_z failed")
            return {"success": False, "error": "platform_servo_jog_to_z_failed"}

    def start_conditional_servo(self, request: dict) -> dict | None:
        method = getattr(self._robot, "start_conditional_servo", None)
        return method(request) if callable(method) else None

    def publish_conditional_servo_sensor(self, **event) -> bool:
        method = getattr(self._robot, "publish_conditional_servo_sensor", None)
        return bool(callable(method) and method(**event))

    def get_conditional_servo_status(self) -> dict | None:
        method = getattr(self._robot, "get_conditional_servo_status", None)
        return method() if callable(method) else None

    def cancel_conditional_servo(self) -> dict | None:
        method = getattr(self._robot, "cancel_conditional_servo", None)
        return method() if callable(method) else None

    def move_fast_linear(self, **kwargs) -> dict | None:
        self._last_jog_target = []
        self._servo_floor_stop.set()
        driver_kwargs = dict(kwargs)
        position = driver_kwargs.get("position")
        allow_subzero_retract = bool(driver_kwargs.pop("allow_subzero_retract", False))
        subzero_recovery = False
        safety_current = None
        if allow_subzero_retract:
            current = self._fresh_position()
            try:
                current_values = [float(value) for value in current[:6]]
                vertical_target = list(current_values)
                vertical_target[2] = float(position[2])
            except (IndexError, TypeError, ValueError):
                current_values = []
                vertical_target = []
            valid_upward_retract = (
                len(current_values) == 6
                and len(vertical_target) == 6
                and all(math.isfinite(value) for value in (*current_values, *vertical_target))
                and vertical_target[2] > current_values[2]
            )
            subzero_recovery = bool(valid_upward_retract and current_values[2] < 0.0)
            safety_current = current_values
            if not valid_upward_retract or (
                subzero_recovery
                and not self._is_bounded_subzero_retract(current_values, vertical_target)
            ):
                return {
                    "result": -1, "success": False, "accepted": False,
                    "final": True, "queued": False,
                    "error": "invalid_subzero_retract",
                }
            # Servo stop settling can change the live pose between the procedure's
            # target construction and this safety gate. Anchor every non-Z component
            # to this same fresh sample so the authorized escape remains pure +Z.
            position = vertical_target
            driver_kwargs["position"] = vertical_target
        violations = self._motion_violations(position, current_position=safety_current)
        if subzero_recovery:
            violations = [
                violation for violation in violations
                if "sub-zero" not in violation.lower()
                and not (
                    violation.lstrip().startswith("Z=")
                    and "not in [0," in violation
                )
            ]
        if violations:
            self._logger.warning(
                "move_fast_linear blocked by safety limits: %s",
                ", ".join(violations),
            )
            return {
                "result": -1, "success": False, "accepted": False,
                "final": True, "queued": False,
                "error": "platform_safety_violation",
                "detail": ", ".join(violations),
            }
        mover = getattr(self._robot, "move_fast_linear", None)
        if not callable(mover):
            return None
        try:
            outcome = mover(**driver_kwargs)
            if isinstance(outcome, dict):
                outcome = dict(outcome)
                outcome["commanded_position"] = [float(value) for value in position[:6]]
            return outcome
        except Exception:
            self._logger.exception("move_fast_linear failed")
            return {"success": False, "error": "platform_fast_linear_failed"}

    def stop_motion(self) -> bool:
        self._logger.debug("stop_motion →")
        self._last_jog_target = []
        self._servo_floor_stop.set()
        for attempt in range(1, self._STOP_ATTEMPTS + 1):
            try:
                success = self._robot.stop_motion() == 0
                if success:
                    self._logger.debug("stop_motion ← success=True attempts=%s", attempt)
                    return True
            except Exception:
                self._logger.exception("stop_motion failed")
                return False
            if attempt < self._STOP_ATTEMPTS:
                time.sleep(self._STOP_RETRY_DELAY_S)
        self._logger.debug("stop_motion ← success=False attempts=%s", self._STOP_ATTEMPTS)
        return False

    def controlled_stop(self, expected_task_id) -> dict:
        method = getattr(self._robot, "controlled_stop", None)
        if not callable(method):
            return {"success": False, "error": "controlled_stop_unsupported"}
        return method(expected_task_id)

    def get_current_position(self) -> List[float]:
        return self._robot.get_current_position()

    def get_execution_status(self):
        get_status = getattr(self._robot, "get_execution_status", None)
        if callable(get_status):
            return get_status()
        return None

    def register_motion_corridor(self, corridor: MotionCorridor) -> None:
        self._motion_corridors.register(corridor)

    def move_linear_in_corridor(
            self,
            corridor_id: str,
            position: List[float],
            tool: int,
            user: int,
            velocity: float,
            acceleration: float,
            blendR: float = 0.0,
            wait_to_reach: bool = False,
    ) -> bool:
        corridor = self._motion_corridors.get(corridor_id)
        if corridor is None:
            self._logger.error("Corridor LIN rejected: unknown corridor_id=%s", corridor_id)
            return False
        target = list(position or [])
        current_getter = getattr(self._robot, "get_current_position_fresh", None)
        if not callable(current_getter):
            current_getter = self._robot.get_current_position
        current_value = current_getter()
        if not isinstance(current_value, (list, tuple)) or len(current_value) < 3:
            current_value = self._robot.get_current_position()
        current = list(current_value or self._cached_position or [])
        violations = []
        if len(target) < 3 or len(current) < 3:
            violations.append("current and target poses must contain XYZ")
        else:
            if not corridor.contains_xy(current):
                violations.append("current pose is outside corridor XY bounds")
            if not corridor.contains_xy(target):
                violations.append("target pose is outside corridor XY bounds")
            current_z = float(current[2])
            target_z = float(target[2])
            descending = 0.0 <= current_z <= corridor.entry_z_max and corridor.z_min <= target_z < 0.0
            retracting = corridor.z_min <= current_z < 0.0 and 0.0 <= target_z <= corridor.entry_z_max
            planar_transit = (
                corridor.allow_planar_transit
                and corridor.contains_xyz(current)
                and corridor.contains_xyz(target)
            )
            if not (descending or retracting or planar_transit):
                violations.append("move is not permitted by the registered corridor")
            if float(velocity) > corridor.maximum_velocity:
                violations.append("velocity exceeds corridor limit")
            if float(acceleration) > corridor.maximum_acceleration:
                violations.append("acceleration exceeds corridor limit")
        if violations:
            self._logger.error(
                "Corridor LIN rejected corridor_id=%s current_xyz=%s target_xyz=%s: %s",
                corridor_id,
                [round(float(value), 3) for value in current[:3]] if len(current) >= 3 else current,
                [round(float(value), 3) for value in target[:3]] if len(target) >= 3 else target,
                ", ".join(violations),
            )
            return False
        passage_setter = getattr(self._robot, "set_motion_passage_closed", None)
        requires_passage_control = descending or retracting
        if requires_passage_control and not callable(passage_setter):
            self._logger.error("Corridor LIN rejected: ROS passage-lid control is unavailable")
            return False
        if descending and not passage_setter(corridor_id, False):
            self._logger.error("Corridor LIN rejected: failed to open passage lid corridor_id=%s", corridor_id)
            return False
        try:
            ret = self._robot.move_linear(
                target,
                tool,
                user,
                velocity,
                acceleration,
                max(0.0, float(blendR)),
                blocking=wait_to_reach,
            )
            success = ret >= 0
            if wait_to_reach and success:
                success = self._wait_for_position(target)
            if descending and not success:
                passage_setter(corridor_id, True)
            if retracting and success and not passage_setter(corridor_id, True):
                self._logger.error("Corridor retract completed but passage lid failed to close corridor_id=%s", corridor_id)
                return False
            return bool(success)
        except Exception:
            self._logger.exception("Corridor LIN failed corridor_id=%s", corridor_id)
            if descending:
                passage_setter(corridor_id, True)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fresh_position(self) -> list[float]:
        getter = getattr(self._robot, "get_current_position_fresh", None)
        if not callable(getter):
            getter = self._robot.get_current_position
        try:
            return list(getter() or self._cached_position or [])
        except Exception:
            self._logger.exception("Fresh robot position unavailable")
            return []

    @staticmethod
    def _is_bounded_subzero_retract(current, target) -> bool:
        """Allow only a pure +Z escape; never lateral, rotational, or downward motion."""
        if len(current) < 6 or len(target) < 6:
            return False
        try:
            current_values = [float(value) for value in current[:6]]
            target_values = [float(value) for value in target[:6]]
        except (TypeError, ValueError):
            return False
        if current_values[2] >= 0.0 or target_values[2] <= current_values[2]:
            return False
        unchanged_indices = (0, 1, 3, 4, 5)
        return all(
            abs(target_values[index] - current_values[index]) <= 0.05
            for index in unchanged_indices
        )

    def _start_servo_floor_supervisor(
            self,
            *,
            allow_subzero_recovery: bool = False,
            initial_z: float | None = None,
            allow_initial_reverse_settle: bool = False,
    ) -> None:
        """Stop unrestricted continuous Servo before it can continue below Z=0."""
        self._servo_floor_stop.set()
        previous = self._servo_floor_thread
        if previous is not None and previous.is_alive():
            previous.join(timeout=self._SERVO_FLOOR_POLL_S * 2.0)
        self._servo_floor_stop = Event()
        stop_event = self._servo_floor_stop
        self._servo_floor_thread = Thread(
            target=self._supervise_servo_floor,
            args=(
                stop_event,
                allow_subzero_recovery,
                initial_z,
                allow_initial_reverse_settle,
            ),
            name="robot-servo-z-floor",
            daemon=True,
        )
        self._servo_floor_thread.start()

    def _supervise_servo_floor(
            self,
            stop_event: Event,
            allow_subzero_recovery: bool = False,
            initial_z: float | None = None,
            allow_initial_reverse_settle: bool = False,
    ) -> None:
        getter = getattr(self._robot, "get_current_position_fresh", None)
        if not callable(getter):
            getter = self._robot.get_current_position
        started = time.monotonic()
        initial_z = float(initial_z) if initial_z is not None else None
        while not stop_event.wait(self._SERVO_FLOOR_POLL_S):
            try:
                position = list(getter() or self._cached_position or [])
                if len(position) >= 3 and float(position[2]) <= 0.0:
                    z = float(position[2])
                    if allow_subzero_recovery and initial_z is not None:
                        if z >= 0.0:
                            return
                        elapsed = time.monotonic() - started
                        reverse_limit_mm = (
                            10.0 if allow_initial_reverse_settle and elapsed <= 0.35 else 2.0
                        )
                        if not (z < initial_z - reverse_limit_mm or (
                            time.monotonic() - started > 1.0 and z <= initial_z + 0.2
                        )):
                            continue
                        self._logger.error(
                            "Servo recovery stopped: Z did not retract safely from z=%.3f (current z=%.3f)",
                            initial_z,
                            z,
                        )
                    self._logger.error(
                        "Servo stopped by platform Z floor at z=%.3f; sub-zero motion requires corridor LIN",
                        float(position[2]),
                    )
                    stopper = getattr(self._robot, "stop_servo_jog", None)
                    if callable(stopper):
                        stopper()
                    return
            except Exception:
                self._logger.exception("Servo Z-floor supervision failed; stopping Servo fail-safe")
                stopper = getattr(self._robot, "stop_servo_jog", None)
                if callable(stopper):
                    try:
                        stopper()
                    except Exception:
                        self._logger.exception("Failed to stop Servo after supervision failure")
                return

    @staticmethod
    def _tool_frame_delta(position: List[float], axis_idx: int,
                          direction_value: float, step: float):
        """Project a single tool-frame jog step into base-frame XYZ displacement.

        R = Rz(rz_degrees) · Ry(ry_degrees) · Rx(rx_degrees), angles in degrees from position[3:6].
        Returns (dx, dy, dz) in base frame.
        """
        cx, sx = math.cos(math.radians(position[3])), math.sin(math.radians(position[3]))
        cy, sy = math.cos(math.radians(position[4])), math.sin(math.radians(position[4]))
        cz, sz = math.cos(math.radians(position[5])), math.sin(math.radians(position[5]))
        cols = (
            (cy * cz, cy * sz, -sy),  # tool X in base
            (cz * sx * sy - cx * sz, cx * cz + sx * sy * sz, cy * sx),  # tool Y in base
            (cx * cz * sy + sx * sz, cx * sy * sz - cz * sx, cx * cy),  # tool Z in base
        )
        col = cols[axis_idx]
        scale = direction_value * step
        return col[0] * scale, col[1] * scale, col[2] * scale

    def _select_jog_base_position(self, current: List[float]) -> List[float]:
        if self._last_jog_target and current and self._positions_close(current, self._last_jog_target):
            return list(self._last_jog_target)
        self._last_jog_target = []
        return list(current) if current else []

    @classmethod
    def _positions_close(cls, a: List[float], b: List[float]) -> bool:
        if len(a) < 6 or len(b) < 6:
            return False
        pos_dist = math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))
        ang_dist = cls._orientation_delta_deg(a, b)
        return pos_dist <= cls._JOG_TARGET_REUSE_POS_MM and ang_dist <= cls._JOG_TARGET_REUSE_ANG_DEG

    def _wait_for_position(
            self,
            target: List[float],
            threshold: float = _WAIT_THRESHOLD_MM,
            orientation_threshold_deg: float = _WAIT_THRESHOLD_DEG,
            delay: float = _WAIT_DELAY_S,
            timeout: float = _WAIT_TIMEOUT_S,
            cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        deadline = time.monotonic() + timeout
        required_stable_samples = 3
        stable_samples = 0
        last_current: List[float] | None = None
        last_dist: float | None = None
        last_orientation_delta: float | None = None
        while time.monotonic() < deadline:
            if cancelled is not None and cancelled():
                self._logger.debug("wait_for_position cancelled while waiting for %s", target)
                return False
            current = self._fresh_position()
            if current and len(current) >= 3:
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(current[:3], target[:3])))
                orientation_delta = 0.0
                if len(target) >= 6 and len(current) >= 6:
                    orientation_delta = self._orientation_delta_deg(current, target)
                last_current = list(current)
                last_dist = dist
                last_orientation_delta = orientation_delta
                if dist <= threshold and orientation_delta <= orientation_threshold_deg:
                    stable_samples += 1
                    if stable_samples >= required_stable_samples:
                        return True
                else:
                    stable_samples = 0
            time.sleep(delay)
        if last_current and len(last_current) >= 6:
            self._logger.warning(
                "Timed out waiting for robot to reach %s within %.3fmm / %.3fdeg; "
                "last_current=%s dist=%.3fmm orientation_delta=%.3fdeg",
                target,
                threshold,
                orientation_threshold_deg,
                last_current,
                last_dist if last_dist is not None else float("nan"),
                last_orientation_delta if last_orientation_delta is not None else float("nan"),
            )
        else:
            self._logger.warning(
                "Timed out waiting for robot to reach %s within %.3fmm / %.3fdeg",
                target,
                threshold,
                orientation_threshold_deg,
            )
        return False

    @staticmethod
    def _wrapped_angle_delta_deg(current: float, target: float) -> float:
        return abs((current - target + 180.0) % 360.0 - 180.0)

    @classmethod
    def _orientation_delta_deg(cls, current_pose: List[float], target_pose: List[float]) -> float:
        if len(current_pose) < 6 or len(target_pose) < 6:
            return 0.0
        current_rot = cls._euler_xyz_deg_to_matrix(
            float(current_pose[3]),
            float(current_pose[4]),
            float(current_pose[5]),
        )
        target_rot = cls._euler_xyz_deg_to_matrix(
            float(target_pose[3]),
            float(target_pose[4]),
            float(target_pose[5]),
        )
        relative = [[0.0] * 3 for _ in range(3)]
        for row in range(3):
            for col in range(3):
                relative[row][col] = sum(
                    target_rot[row][k] * current_rot[col][k]
                    for k in range(3)
                )
        trace = relative[0][0] + relative[1][1] + relative[2][2]
        cos_angle = max(-1.0, min(1.0, (trace - 1.0) * 0.5))
        return math.degrees(math.acos(cos_angle))

    @staticmethod
    def _euler_xyz_deg_to_matrix(rx_deg: float, ry_deg: float, rz_deg: float):
        rx = math.radians(rx_deg)
        ry = math.radians(ry_deg)
        rz = math.radians(rz_deg)
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)
        return (
            (cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
            (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
            (-sy, cy * sx, cy * cx),
        )
    def _motion_violations(
        self,
        position: List[float],
        *,
        current_position: List[float] | None = None,
    ) -> List[str]:
        violations = list(self._safety.get_violations(position))
        current = current_position
        if current is None:
            current_getter = getattr(self._robot, "get_current_position_fresh", None)
            if not callable(current_getter):
                current_getter = self._robot.get_current_position
            current = current_getter()
            if not isinstance(current, (list, tuple)) or len(current) < 3:
                current = self._robot.get_current_position()
        current = current or self._cached_position or []
        if current and len(current) >= 3 and isinstance(current[2], (int, float)) and float(current[2]) < 0.0:
            violations.append(
                "Platform Z floor violation: a sub-zero pose may only retract through its registered corridor LIN"
            )
        if position and len(position) >= 3 and float(position[2]) < 0.0:
            violations.append(
                "Platform Z floor violation: sub-zero motion requires a registered corridor LIN"
            )
        return violations
