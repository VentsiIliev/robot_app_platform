from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _float_list(values, expected: int) -> List[float]:
    result = [float(v) for v in (values or [])]
    if result and len(result) != expected:
        raise ValueError(f"Expected {expected} values, got {len(result)}")
    return result


@dataclass
class RobotChoreographyPose:
    pose: List[float] = field(default_factory=list)
    joints: List[float] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "RobotChoreographyPose":
        data = data or {}
        return cls(
            pose=_float_list(data.get("pose"), 6),
            joints=_float_list(data.get("joints"), 6),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pose": list(self.pose),
            "joints": list(self.joints),
        }

    @property
    def captured(self) -> bool:
        return len(self.pose) == 6


@dataclass
class RobotMotionProfile:
    """Motion limits for the segment ending at the owning choreography step."""

    velocity: float = 30.0
    acceleration: float = 30.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "RobotMotionProfile":
        data = data or {}
        return cls(
            velocity=float(data.get("velocity", 30.0)),
            acceleration=float(data.get("acceleration", 30.0)),
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "velocity": float(self.velocity),
            "acceleration": float(self.acceleration),
        }


@dataclass
class ChoreographyStep:
    name: str
    robot1: RobotChoreographyPose = field(default_factory=RobotChoreographyPose)
    robot2: RobotChoreographyPose = field(default_factory=RobotChoreographyPose)
    robot1_motion: RobotMotionProfile = field(default_factory=RobotMotionProfile)
    robot2_motion: RobotMotionProfile = field(default_factory=RobotMotionProfile)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChoreographyStep":
        return cls(
            name=str(data.get("name", "Step")),
            robot1=RobotChoreographyPose.from_dict(data.get("robot1")),
            robot2=RobotChoreographyPose.from_dict(data.get("robot2")),
            robot1_motion=RobotMotionProfile.from_dict(data.get("robot1_motion")),
            robot2_motion=RobotMotionProfile.from_dict(data.get("robot2_motion")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "robot1": self.robot1.to_dict(),
            "robot2": self.robot2.to_dict(),
            "robot1_motion": self.robot1_motion.to_dict(),
            "robot2_motion": self.robot2_motion.to_dict(),
        }

    @property
    def complete(self) -> bool:
        return self.robot1.captured and self.robot2.captured


@dataclass
class ChoreographyDefinition:
    choreography_id: str
    name: str
    steps: List[ChoreographyStep] = field(default_factory=list)
    loop_count: int = 1

    VERSION = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChoreographyDefinition":
        return cls(
            choreography_id=str(data.get("id", "")).strip(),
            name=str(data.get("name", "")).strip(),
            steps=[ChoreographyStep.from_dict(item) for item in data.get("steps", [])],
            loop_count=max(1, int(data.get("loop_count", 1))),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.VERSION,
            "id": self.choreography_id,
            "name": self.name,
            "loop_count": int(self.loop_count),
            "steps": [step.to_dict() for step in self.steps],
        }

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.choreography_id:
            errors.append("Choreography ID is required")
        if not self.name:
            errors.append("Choreography name is required")
        if len(self.steps) < 2:
            errors.append("At least two choreography steps are required")

        for index, step in enumerate(self.steps, start=1):
            if not step.robot1.captured:
                errors.append(f"Step {index} has no Robot 1 pose")
            if not step.robot2.captured:
                errors.append(f"Step {index} has no Robot 2 pose")
            self._validate_motion_profile(errors, index, "Robot 1", step.robot1_motion)
            self._validate_motion_profile(errors, index, "Robot 2", step.robot2_motion)

        if self.steps:
            start = self.steps[0]
            if len(start.robot1.joints) != 6:
                errors.append("Start step must contain exact Robot 1 joint anchor")
            if len(start.robot2.joints) != 6:
                errors.append("Start step must contain exact Robot 2 joint anchor")
        return errors

    @staticmethod
    def _validate_motion_profile(
        errors: List[str],
        step_index: int,
        robot_label: str,
        profile: RobotMotionProfile,
    ) -> None:
        if not 0.0 < float(profile.velocity) <= 100.0:
            errors.append(
                f"Step {step_index} {robot_label} velocity must be in (0, 100]"
            )
        if not 0.0 < float(profile.acceleration) <= 100.0:
            errors.append(
                f"Step {step_index} {robot_label} acceleration must be in (0, 100]"
            )

    @property
    def start_step(self) -> Optional[ChoreographyStep]:
        return self.steps[0] if self.steps else None
