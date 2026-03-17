"""
Dynamic pump speed adjustment — clean port of the old dynamicPumpSpeedAdjustment.py.

Key changes from original:
- IMotorService.set_speed() replaces adjustMotorSpeed()
- IRobotService.get_current_position/velocity/acceleration() used directly
- context.stop_event / context.run_allowed replace state-machine enum checks
- stdlib logging replaces files.write_to_debug_file
- inline math replaces robot_utils.calculate_distance_between_points
"""
from __future__ import annotations
import logging
import math
import threading
import time
from typing import Optional, Tuple

from src.engine.hardware.motor.interfaces.i_motor_service import IMotorService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.robot_systems.glue.processes.glue_dispensing.dispensing_settings import (
    DispensingSegmentSettings,
)

_logger      = logging.getLogger(__name__)
_CHECKPOINT_THRESHOLD_MM = 1.0


def _dist(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])))


def _should_exit(context) -> Tuple[bool, int]:
    """Return (exit, progress). progress=-1 means caller should fill in."""
    if context is None:
        return False, 0
    if context.stop_event.is_set():
        return True, context.current_point_index
    if not context.run_allowed.is_set():
        return True, -1   # sentinel — caller fills real value
    return False, 0


def _update_checkpoints(pos, remaining, furthest, start_idx) -> int:
    for i in range(furthest, len(remaining)):
        if _dist(pos, remaining[i]) < _CHECKPOINT_THRESHOLD_MM:
            furthest = i + 1
    return furthest


def _final_reached(pos, final, remaining, furthest, threshold) -> bool:
    if _dist(pos, final) < threshold:
        if len(remaining) < 2:
            return True
        if furthest > len(remaining) - 2:
            return True
    return False


def _calc_speed(velocity, acceleration, speed_coeff, accel_coeff) -> float:
    vel_comp = float(velocity) * float(speed_coeff)
    if acceleration <= 0:
        acc_comp = float(accel_coeff) * float(acceleration)
    else:
        acc_comp = (float(accel_coeff) / 2.0) * float(acceleration)
    return vel_comp + acc_comp


def adjust_pump_speed_dynamically(
    motor_service:     IMotorService,
    robot_service:     IRobotService,
    speed_coeff,
    accel_coeff,
    motor_address:     int,
    path:              list,
    threshold:         float,
    start_point_index: int = 0,
    ready_event        = None,
    context            = None,
) -> Tuple[bool, int]:
    if ready_event is not None:
        ready_event.set()

    poll_s = (
        float(getattr(context, "pump_adjuster_poll_s", 0.01))
        if context is not None else 0.01
    )

    remaining = path[start_point_index:]
    if not remaining:
        return True, start_point_index

    first_point   = remaining[0]
    final_point   = remaining[-1]
    furthest      = 0
    first_reached = False

    while True:
        should_exit, progress = _should_exit(context)
        if should_exit:
            real_progress = start_point_index + max(furthest - 1, 0) if progress == -1 else progress
            return False, real_progress

        pos = robot_service.get_current_position()
        if not pos:
            time.sleep(poll_s)
            continue

        if not first_reached:
            if _dist(pos, first_point) < threshold:
                first_reached = True
                _logger.debug("First point %s reached", start_point_index)
            else:
                time.sleep(poll_s)
                continue

        if _final_reached(pos, final_point, remaining, furthest, threshold):
            break

        furthest = _update_checkpoints(pos, remaining, furthest, start_point_index)

        vel  = robot_service.get_current_velocity()
        acc  = robot_service.get_current_acceleration()
        spd  = _calc_speed(vel, acc, speed_coeff, accel_coeff)
        motor_service.set_speed(motor_address=motor_address, speed=int(spd))
        _logger.debug("vel=%.3f acc=%.3f adj=%.3f chk=%s", vel, acc, spd, furthest)

    final_progress = start_point_index + len(remaining) - 1
    _logger.debug("Path complete, final_progress=%s", final_progress)
    return True, final_progress


class PumpThreadWithResult(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = None

    def run(self) -> None:
        try:
            self.result = self._target(*self._args, **self._kwargs)
        except Exception as exc:
            _logger.exception("Pump adjustment thread raised an exception")
            self.result = (False, 0, exc)


def start_pump_speed_adjustment_thread(
    motor_service:       IMotorService,
    robot_service:       IRobotService,
    settings:            DispensingSegmentSettings | None,
    motor_address:       int,
    path:                list,
    reach_end_threshold: float,
    pump_ready_event,
    start_point_index:   int = 0,
    context              = None,
) -> PumpThreadWithResult:
    thread = PumpThreadWithResult(
        target=adjust_pump_speed_dynamically,
        args=(
            motor_service,
            robot_service,
            settings.glue_speed_coefficient if settings is not None else 5.0,
            settings.glue_acceleration_coefficient if settings is not None else 0.0,
            motor_address,
            path,
            reach_end_threshold,
            start_point_index,
            pump_ready_event,
            context,
        ),
        daemon=True,
        name="PumpSpeedAdjuster",
    )
    thread.start()
    _logger.debug("Pump speed adjuster started (start_idx=%s)", start_point_index)
    return thread
