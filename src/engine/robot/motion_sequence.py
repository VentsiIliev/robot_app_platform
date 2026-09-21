from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, TypeAlias


MotionType = Literal["linear", "ptp"]


class OrderedMotionType(StrEnum):
    """Supported motion algorithms for a single-position ordered command."""

    PTP = "ptp"
    LINEAR = "linear"
    FAST_LINEAR = "fast_lin"

    @classmethod
    def parse(cls, value: object, *, field_name: str = "motion_type") -> "OrderedMotionType":
        """Validate an external motion-type value at a configuration boundary."""
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:
            raise ValueError(
                f"{field_name} has unsupported motion type {value!r}"
            ) from exc


class OrderedExecutionPolicy(StrEnum):
    """How adjacent ordered commands are combined by the motion backend."""

    CONCATENATE = "concatenate"


class OrderedMotionLimitProfile(StrEnum):
    """Named backend limit profiles supported by ordered motion."""

    PAINT_CONTACT = "paint_contact"


@dataclass(frozen=True)
class OrderedMotionProfile:
    """Velocity, acceleration, and blending for an ordered motion command."""

    velocity_percent: float
    acceleration_percent: float
    blend_radius: float | None = None

    def __post_init__(self) -> None:
        _require_finite("velocity_percent", self.velocity_percent)
        _require_finite("acceleration_percent", self.acceleration_percent)
        if self.blend_radius is not None:
            _require_finite("blend_radius", self.blend_radius)


@dataclass(frozen=True)
class OrderedMotionMetadata:
    """Optional scheduling and interruption metadata for an ordered command."""

    protected: bool = False
    readiness_group: str | None = None
    execution_group: str | None = None
    execution_policy: OrderedExecutionPolicy | None = None

    def __post_init__(self) -> None:
        if self.execution_policy is not None and not isinstance(
            self.execution_policy,
            OrderedExecutionPolicy,
        ):
            raise TypeError("execution_policy must be an OrderedExecutionPolicy")


@dataclass(frozen=True)
class OrderedPositionCommand:
    """One typed ordered move to a six-axis robot pose."""

    label: str
    motion_type: OrderedMotionType
    position: tuple[float, ...]
    profile: OrderedMotionProfile
    metadata: OrderedMotionMetadata = OrderedMotionMetadata()

    def __post_init__(self) -> None:
        if not isinstance(self.motion_type, OrderedMotionType):
            raise TypeError("motion_type must be an OrderedMotionType")
        _require_pose("position", self.position)

    def to_payload(self) -> dict[str, object]:
        payload = _base_payload(self.label, self.profile, self.metadata)
        payload.update({"type": self.motion_type.value, "position": list(self.position)})
        return payload


@dataclass(frozen=True)
class OrderedPathCommand:
    """One typed ordered Cartesian path containing one or more six-axis poses."""

    label: str
    path: tuple[tuple[float, ...], ...]
    profile: OrderedMotionProfile
    metadata: OrderedMotionMetadata = OrderedMotionMetadata()
    limit_profile: OrderedMotionLimitProfile | None = None

    def __post_init__(self) -> None:
        if self.limit_profile is not None and not isinstance(
            self.limit_profile,
            OrderedMotionLimitProfile,
        ):
            raise TypeError("limit_profile must be an OrderedMotionLimitProfile")
        if not self.path:
            raise ValueError("path must contain at least one pose")
        for index, pose in enumerate(self.path):
            _require_pose(f"path[{index}]", pose)

    def to_payload(self) -> dict[str, object]:
        payload = _base_payload(self.label, self.profile, self.metadata)
        payload.update({"type": "path", "path": [list(pose) for pose in self.path]})
        if self.limit_profile is not None:
            payload["limit_profile"] = self.limit_profile.value
        return payload


@dataclass(frozen=True)
class OrderedUnwindJoint6Command:
    """One typed request to unwind robot Joint 6 inside an ordered chain."""

    label: str
    velocity_percent: float
    acceleration_percent: float
    protected: bool = False

    def __post_init__(self) -> None:
        _require_finite("velocity_percent", self.velocity_percent)
        _require_finite("acceleration_percent", self.acceleration_percent)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": "unwind_joint6",
            "label": self.label,
            "vel": float(self.velocity_percent),
            "acc": float(self.acceleration_percent),
        }
        if self.protected:
            payload["protected"] = True
        return payload


OrderedMotionCommand: TypeAlias = (
    OrderedPositionCommand | OrderedPathCommand | OrderedUnwindJoint6Command
)
OrderedMotionInput: TypeAlias = OrderedMotionCommand


def serialize_ordered_motion_commands(
    commands: list[OrderedMotionCommand] | tuple[OrderedMotionCommand, ...],
) -> list[dict[str, object]]:
    """Serialize typed commands at the ordered-motion transport boundary."""
    supported_types = (
        OrderedPositionCommand,
        OrderedPathCommand,
        OrderedUnwindJoint6Command,
    )
    payloads: list[dict[str, object]] = []
    for index, command in enumerate(commands):
        if not isinstance(command, supported_types):
            raise TypeError(
                f"commands[{index}] must be an OrderedMotionCommand, "
                f"got {type(command).__name__}"
            )
        payloads.append(command.to_payload())
    return payloads


def serialize_ordered_motion_inputs(
    commands: list[OrderedMotionInput] | tuple[OrderedMotionInput, ...],
) -> list[dict[str, object]]:
    """Serialize typed commands at the robot-client boundary."""
    return serialize_ordered_motion_commands(commands)


def _base_payload(
    label: str,
    profile: OrderedMotionProfile,
    metadata: OrderedMotionMetadata,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "label": str(label),
        "vel": float(profile.velocity_percent),
        "acc": float(profile.acceleration_percent),
    }
    if profile.blend_radius is not None:
        payload["blendR"] = float(profile.blend_radius)
    if metadata.protected:
        payload["protected"] = True
    if metadata.readiness_group is not None:
        payload["readiness_group"] = metadata.readiness_group
    if metadata.execution_group is not None:
        payload["execution_group"] = metadata.execution_group
    if metadata.execution_policy is not None:
        payload["execution_policy"] = metadata.execution_policy.value
    return payload


def _require_pose(name: str, pose: tuple[float, ...]) -> None:
    if len(pose) != 6:
        raise ValueError(f"{name} must contain exactly six axis values")
    if not all(math.isfinite(float(value)) for value in pose):
        raise ValueError(f"{name} must contain only finite axis values")


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class MotionSequenceSegment:
    """One explicitly parameterized robot motion segment."""

    position: list[float]
    velocity: float
    acceleration: float
    motion_type: MotionType = "linear"
    blend_radius: float = 0.0
