from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from src.engine.geometry.planar import unwrap_degrees
from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff_handlers import (
    _resolve_dropoff_align_pose,
    _should_release_at_current_dropoff_pose,
)
from src.robot_systems.paint.timing import timed_step

_logger = logging.getLogger(__name__)


def _poses_close(left: list[float] | None, right: list[float] | None, tolerance: float = 1e-3) -> bool:
    if left is None or right is None or len(left) < 6 or len(right) < 6:
        return False
    if not all(abs(float(a) - float(b)) <= tolerance for a, b in zip(left[:5], right[:5])):
        return False
    equivalent_rz = unwrap_degrees(float(right[5]), float(left[5]))
    return abs(equivalent_rz - float(right[5])) <= tolerance


@dataclass(frozen=True)
class DropoffWaypoint:
    """One dropoff move or release action."""

    label: str
    pose: list[float] | None
    vel_percent: float
    acc_percent: float
    motion_type: str = "ptp"
    blendR: float = 0.0
    release_here: bool = False


@dataclass(frozen=True)
class DropoffPlan:
    """Resolved dropoff sequence for the current held workpiece."""

    strategy_name: str
    waypoints: tuple[DropoffWaypoint, ...]


class PaintDropoffStrategy(Protocol):
    """Build a dropoff plan without exposing strategy specifics to the main executor."""

    name: str

    def build_plan(self, owner, execution_plan: WorkpieceExecutionPlan) -> DropoffPlan:
        """Return the ordered dropoff actions for the active workpiece."""


class PickupOriginDropoffStrategy:
    """Default strategy: return to the pickup align pose and release there."""

    name = "pickup_origin"

    def build_plan(self, owner, execution_plan: WorkpieceExecutionPlan) -> DropoffPlan:
        dropoff = owner._paint_process_config().dropoff
        if _should_release_at_current_dropoff_pose(owner):
            return DropoffPlan(
                strategy_name=self.name,
                waypoints=(
                    DropoffWaypoint(
                        label="Release at current dropoff pose",
                        pose=None,
                        vel_percent=dropoff.release_align_vel_percent,
                        acc_percent=dropoff.release_align_acc_percent,
                        motion_type=dropoff.release_align_motion_type,
                        blendR=dropoff.release_align_blendR,
                        release_here=True,
                    ),
                ),
            )
        plan = owner._last_pickup_plan
        if plan is None:
            _logger.info("[DROPOFF] pickup_origin has no pickup plan; releasing at current pose")
            waypoints = (
                DropoffWaypoint(
                    label="Release at current pose",
                    pose=None,
                    vel_percent=dropoff.release_align_vel_percent,
                    acc_percent=dropoff.release_align_acc_percent,
                    motion_type=dropoff.release_align_motion_type,
                    blendR=dropoff.release_align_blendR,
                    release_here=True,
                ),
            )
        else:
            waypoints = (
                DropoffWaypoint(
                    label="Returning to align pose for release",
                    pose=list(plan.align_pose),
                    vel_percent=dropoff.release_align_vel_percent,
                    acc_percent=dropoff.release_align_acc_percent,
                    motion_type=dropoff.release_align_motion_type,
                    blendR=dropoff.release_align_blendR,
                    release_here=True,
                ),
            )
        return DropoffPlan(strategy_name=self.name, waypoints=waypoints)


class MovementGroupDropoffStrategy:
    """Release the held workpiece at the configured dropoff movement group."""

    name = "movement_group"

    def build_plan(self, owner, execution_plan: WorkpieceExecutionPlan) -> DropoffPlan:
        dropoff = owner._paint_process_config().dropoff
        group_id = "Dropoff"
        pose = _resolve_dropoff_align_pose(owner)
        if pose is None:
            _logger.info("[DROPOFF] movement_group has no configured pose for group '%s'", group_id)
            return DropoffPlan(strategy_name=self.name, waypoints=())
        return DropoffPlan(
            strategy_name=self.name,
            waypoints=(
                DropoffWaypoint(
                    label=f"Moving to dropoff group '{group_id}' for release",
                    pose=pose,
                    vel_percent=dropoff.release_align_vel_percent,
                    acc_percent=dropoff.release_align_acc_percent,
                    motion_type=dropoff.release_align_motion_type,
                    blendR=dropoff.release_align_blendR,
                    release_here=True,
                ),
            ),
        )


class PaintDropoffExecutor:
    """Execute the configured paint dropoff strategy."""

    def __init__(self, owner, strategy: PaintDropoffStrategy | None = None) -> None:
        self._owner = owner
        self._strategy_override = strategy
        self._strategies: dict[str, PaintDropoffStrategy] = {
            PickupOriginDropoffStrategy.name: PickupOriginDropoffStrategy(),
            MovementGroupDropoffStrategy.name: MovementGroupDropoffStrategy(),
        }

    def _resolve_strategy(self) -> PaintDropoffStrategy | None:
        if self._strategy_override is not None:
            return self._strategy_override
        strategy_name = str(self._owner._paint_process_config().dropoff.strategy or "pickup_origin").strip().lower()
        return self._strategies.get(strategy_name)

    @timed_step(_logger, "pre_release_dropoff")
    def execute(self, execution_plan: WorkpieceExecutionPlan) -> tuple[bool, str]:
        """Execute the dropoff plan and release the workpiece at its release waypoint."""
        started = perf_counter()
        strategy = self._resolve_strategy()
        if strategy is None:
            strategy_name = str(self._owner._paint_process_config().dropoff.strategy or "").strip()
            return False, f"Unknown paint dropoff strategy '{strategy_name}'"
        plan = strategy.build_plan(self._owner, execution_plan)
        release_count = sum(1 for waypoint in plan.waypoints if waypoint.release_here)
        if release_count != 1:
            if plan.strategy_name == MovementGroupDropoffStrategy.name:
                return False, "Dropoff movement group 'Dropoff' is not configured"
            return False, f"Dropoff strategy '{plan.strategy_name}' must define exactly one release waypoint"

        _logger.info(
            "[DROPOFF] executing strategy=%s waypoints=%d",
            plan.strategy_name,
            len(plan.waypoints),
        )
        for index, waypoint in enumerate(plan.waypoints, start=1):
            waypoint_started = perf_counter()
            if waypoint.pose is not None:
                already_at_release_pose = (
                    bool(getattr(self._owner, "_dropoff_unwind_prepared", False))
                    and waypoint.release_here
                    and _poses_close(waypoint.pose, getattr(self._owner, "_last_process_end_pose", None))
                )
                if already_at_release_pose:
                    _logger.info(
                        "[DROPOFF] waypoint '%s' already completed by ordered cleanup chain; releasing in place",
                        waypoint.label,
                    )
                elif not self._owner._motion.move_pickup_phase(
                    waypoint.label,
                    list(waypoint.pose),
                    velocity=waypoint.vel_percent,
                    acceleration=waypoint.acc_percent,
                    motion_type=waypoint.motion_type,
                    blendR=waypoint.blendR,
                ):
                    _logger.info(
                        "[TIMING] pre_release_dropoff success=false strategy=%s waypoint=%d label=%s elapsed_s=%.3f total_elapsed_s=%.3f",
                        plan.strategy_name,
                        index,
                        waypoint.label,
                        elapsed_s(waypoint_started),
                        elapsed_s(started),
                    )
                    return False, f"Pivot paint finished, but dropoff waypoint '{waypoint.label}' failed before release"

            if waypoint.release_here:
                ok, msg = self._owner._motion.turn_vacuum_off()
                if not ok:
                    _logger.info(
                        "[TIMING] pre_release_dropoff success=false strategy=%s waypoint=%d stage=release elapsed_s=%.3f total_elapsed_s=%.3f",
                        plan.strategy_name,
                        index,
                        elapsed_s(waypoint_started),
                        elapsed_s(started),
                    )
                    return False, msg

        _logger.info(
            "[DROPOFF] strategy=%s completed elapsed_s=%.3f",
            plan.strategy_name,
            elapsed_s(started),
        )
        return True, ""
