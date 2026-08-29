from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from src.robot_systems.paint.processes.paint.config import (
    SERVO_APPROACH_STRATEGY_FULL_SERVO,
    SERVO_APPROACH_STRATEGY_LEARNED_HEIGHT,
)


@dataclass(frozen=True)
class ServoSpeedTransition:
    initial_linear_mm_s: float | None = None
    slowdown_z_mm: float | None = None


class ServoPickupApproachStrategy(Protocol):
    def resolve(
        self,
        *,
        source: str,
        approach_z_mm: float,
        minimum_z_mm: float,
        contact_linear_mm_s: float,
        fast_linear_mm_s: float,
        clearance_mm: float,
    ) -> ServoSpeedTransition: ...

    def record_success(self, source: str, contact_pose: tuple[float, ...] | None) -> None: ...

    def reset(self) -> None: ...


class FullServoApproachStrategy:
    def resolve(self, **_kwargs) -> ServoSpeedTransition:
        return ServoSpeedTransition()

    def record_success(self, _source: str, _contact_pose: tuple[float, ...] | None) -> None:
        return None

    def reset(self) -> None:
        return None


class LearnedHeightServoApproachStrategy:
    def __init__(self) -> None:
        self._contact_z_by_source: dict[str, float] = {}

    def resolve(
        self,
        *,
        source: str,
        approach_z_mm: float,
        minimum_z_mm: float,
        contact_linear_mm_s: float,
        fast_linear_mm_s: float,
        clearance_mm: float,
    ) -> ServoSpeedTransition:
        contact_z = self._contact_z_by_source.get(source)
        if contact_z is None:
            return ServoSpeedTransition()
        slowdown_z = contact_z + clearance_mm
        if (
            not all(math.isfinite(value) for value in (
                approach_z_mm,
                minimum_z_mm,
                contact_linear_mm_s,
                fast_linear_mm_s,
                clearance_mm,
                slowdown_z,
            ))
            or clearance_mm <= 0.0
            or fast_linear_mm_s <= contact_linear_mm_s
            or slowdown_z <= minimum_z_mm
            or slowdown_z >= approach_z_mm
        ):
            return ServoSpeedTransition()
        return ServoSpeedTransition(
            initial_linear_mm_s=fast_linear_mm_s,
            slowdown_z_mm=slowdown_z,
        )

    def record_success(self, source: str, contact_pose: tuple[float, ...] | None) -> None:
        if contact_pose is None or len(contact_pose) < 3:
            return
        contact_z = float(contact_pose[2])
        if math.isfinite(contact_z):
            self._contact_z_by_source[source] = contact_z

    def reset(self) -> None:
        self._contact_z_by_source.clear()


class ServoPickupApproachSelector:
    """Select the configured policy while keeping learned heights process-local."""

    def __init__(self) -> None:
        self._full_servo = FullServoApproachStrategy()
        self._learned_height = LearnedHeightServoApproachStrategy()
        self._active_name: str | None = None

    def select(self, name: object) -> ServoPickupApproachStrategy:
        normalized = str(name or SERVO_APPROACH_STRATEGY_FULL_SERVO).strip().lower()
        if normalized not in {
            SERVO_APPROACH_STRATEGY_FULL_SERVO,
            SERVO_APPROACH_STRATEGY_LEARNED_HEIGHT,
        }:
            normalized = SERVO_APPROACH_STRATEGY_FULL_SERVO
        if self._active_name is not None and normalized != self._active_name:
            self._learned_height.reset()
        self._active_name = normalized
        if normalized == SERVO_APPROACH_STRATEGY_LEARNED_HEIGHT:
            return self._learned_height
        return self._full_servo

    def reset(self) -> None:
        self._learned_height.reset()


def selector_for(owner) -> ServoPickupApproachSelector:
    selector = getattr(owner, "_servo_pickup_approach_selector", None)
    if selector is None:
        selector = ServoPickupApproachSelector()
        owner._servo_pickup_approach_selector = selector
    return selector


def resolve_transition(owner, *, source: str, approach_z_mm: float):
    pickup = owner._paint_process_config().pickup_motion
    strategy = selector_for(owner).select(
        getattr(pickup, "servo_contact_approach_strategy", SERVO_APPROACH_STRATEGY_FULL_SERVO)
    )
    return strategy, strategy.resolve(
        source=source,
        approach_z_mm=float(approach_z_mm),
        minimum_z_mm=float(getattr(pickup, "servo_contact_min_z_mm", 0.0)),
        contact_linear_mm_s=float(pickup.servo_contact_linear_mm_s),
        fast_linear_mm_s=float(getattr(pickup, "servo_contact_fast_linear_mm_s", 100.0)),
        clearance_mm=float(getattr(pickup, "servo_contact_slowdown_clearance_mm", 10.0)),
    )
