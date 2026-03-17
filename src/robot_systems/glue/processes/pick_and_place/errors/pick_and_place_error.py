from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.shared_contracts.events.process_events import ProcessState


class PickAndPlaceStage(str, Enum):
    STARTUP = "startup"
    MATCHING = "matching"
    TRANSFORM = "transform"
    HEIGHT = "height"
    TOOLING = "tooling"
    PICK = "pick"
    PLACE = "place"
    PLANE = "plane"
    SHUTDOWN = "shutdown"
    CANCELLED = "cancelled"


class PickAndPlaceErrorCode(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    MOVE_HOME_FAILED = "MOVE_HOME_FAILED"
    MATCHING_FAILED = "MATCHING_FAILED"
    TRANSFORM_FAILED = "TRANSFORM_FAILED"
    HEIGHT_MEASUREMENT_FAILED = "HEIGHT_MEASUREMENT_FAILED"
    TOOL_CHANGE_FAILED = "TOOL_CHANGE_FAILED"
    PICK_MOTION_FAILED = "PICK_MOTION_FAILED"
    PLACE_MOTION_FAILED = "PLACE_MOTION_FAILED"
    DROP_GRIPPER_FAILED = "DROP_GRIPPER_FAILED"
    PLANE_FULL = "PLANE_FULL"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class PickAndPlaceErrorInfo:
    code: PickAndPlaceErrorCode
    stage: PickAndPlaceStage
    message: str
    detail: Optional[str] = None
    recoverable: bool = False


@dataclass(frozen=True)
class PickAndPlaceWorkflowResult:
    state: ProcessState
    message: str = ""
    error: Optional[PickAndPlaceErrorInfo] = None

    @property
    def success(self) -> bool:
        return self.state == ProcessState.STOPPED and self.error is None

    @classmethod
    def stopped(cls, message: str = "") -> "PickAndPlaceWorkflowResult":
        return cls(state=ProcessState.STOPPED, message=message)

    @classmethod
    def error_result(
        cls,
        code: PickAndPlaceErrorCode,
        stage: PickAndPlaceStage,
        message: str,
        detail: Optional[str] = None,
        recoverable: bool = False,
    ) -> "PickAndPlaceWorkflowResult":
        return cls(
            state=ProcessState.ERROR,
            message=message,
            error=PickAndPlaceErrorInfo(
                code=code,
                stage=stage,
                message=message,
                detail=detail,
                recoverable=recoverable,
            ),
        )


@dataclass(frozen=True)
class WorkpieceProcessResult:
    placed: bool
    plane_full: bool = False
    error: Optional[PickAndPlaceErrorInfo] = None

    @classmethod
    def success(cls) -> "WorkpieceProcessResult":
        return cls(placed=True)

    @classmethod
    def skipped_plane_full(cls) -> "WorkpieceProcessResult":
        return cls(placed=False, plane_full=True)

    @classmethod
    def fail(cls, error: PickAndPlaceErrorInfo) -> "WorkpieceProcessResult":
        return cls(placed=False, plane_full=False, error=error)
