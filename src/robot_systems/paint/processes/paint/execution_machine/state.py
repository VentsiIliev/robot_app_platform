from __future__ import annotations

from enum import Enum, auto


class PaintExecutionState(Enum):
    """Business-level states for one paint production cycle."""

    STARTING = auto()
    MAGAZINE_LOAD = auto()
    MAGAZINE_MOVE_TO_MAGAZINE = auto()
    MAGAZINE_WAIT_CAMERA_SETTLE = auto()
    MAGAZINE_CAPTURE = auto()
    MAGAZINE_PREPARE_PICKUP_RELEASE = auto()
    MAGAZINE_EXECUTE_PICKUP_RELEASE = auto()
    MAGAZINE_MOVE_TO_CALIBRATION = auto()
    CALIBRATION_WAIT_CAMERA_SETTLE = auto()
    CAPTURE_WORKPIECE = auto()
    PREPARE_WORKPIECE = auto()
    BUILD_EXECUTION_PLAN = auto()
    EXECUTE_PAINT = auto()
    PICKUP = auto()
    PAINT_CONTACT = auto()
    EDGE_CLEANUP = auto()
    PREPARE_DROPOFF = auto()
    DROPOFF = auto()
    POST_RETURN = auto()
    COMPLETED = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()
    IDLE = auto()


class PaintExecutionTransitions:
    """Allowed transitions for the paint production execution machine."""

    @staticmethod
    def get_rules() -> dict[PaintExecutionState, set[PaintExecutionState]]:
        S = PaintExecutionState
        active = {S.PAUSED, S.STOPPED, S.ERROR}
        magazine_states = {
            S.MAGAZINE_MOVE_TO_MAGAZINE,
            S.MAGAZINE_WAIT_CAMERA_SETTLE,
            S.MAGAZINE_CAPTURE,
            S.MAGAZINE_PREPARE_PICKUP_RELEASE,
            S.MAGAZINE_EXECUTE_PICKUP_RELEASE,
            S.MAGAZINE_MOVE_TO_CALIBRATION,
            S.CALIBRATION_WAIT_CAMERA_SETTLE,
        }
        paint_states = {
            S.CAPTURE_WORKPIECE,
            S.PREPARE_WORKPIECE,
            S.BUILD_EXECUTION_PLAN,
            S.EXECUTE_PAINT,
            S.PICKUP,
            S.PAINT_CONTACT,
            S.EDGE_CLEANUP,
            S.PREPARE_DROPOFF,
            S.DROPOFF,
            S.POST_RETURN,
        }
        return {
            S.STARTING: {S.MAGAZINE_LOAD, *magazine_states, *paint_states, S.STOPPED, S.ERROR},
            S.MAGAZINE_LOAD: {S.MAGAZINE_MOVE_TO_MAGAZINE, S.CAPTURE_WORKPIECE, S.COMPLETED, *active},
            S.MAGAZINE_MOVE_TO_MAGAZINE: {S.MAGAZINE_WAIT_CAMERA_SETTLE, *active},
            S.MAGAZINE_WAIT_CAMERA_SETTLE: {S.MAGAZINE_CAPTURE, *active},
            S.MAGAZINE_CAPTURE: {S.MAGAZINE_PREPARE_PICKUP_RELEASE, S.COMPLETED, *active},
            S.MAGAZINE_PREPARE_PICKUP_RELEASE: {S.MAGAZINE_EXECUTE_PICKUP_RELEASE, *active},
            S.MAGAZINE_EXECUTE_PICKUP_RELEASE: {S.MAGAZINE_MOVE_TO_CALIBRATION, *active},
            S.MAGAZINE_MOVE_TO_CALIBRATION: {S.CALIBRATION_WAIT_CAMERA_SETTLE, *active},
            S.CALIBRATION_WAIT_CAMERA_SETTLE: {S.CAPTURE_WORKPIECE, *active},
            S.CAPTURE_WORKPIECE: {S.PREPARE_WORKPIECE, S.COMPLETED, *active},
            S.PREPARE_WORKPIECE: {S.BUILD_EXECUTION_PLAN, S.STOPPED, S.ERROR},
            S.BUILD_EXECUTION_PLAN: {S.EXECUTE_PAINT, S.PICKUP, S.STOPPED, S.ERROR},
            S.EXECUTE_PAINT: {S.COMPLETED, *active},
            S.PICKUP: {S.PAINT_CONTACT, *active},
            S.PAINT_CONTACT: {S.EDGE_CLEANUP, *active},
            S.EDGE_CLEANUP: {S.PREPARE_DROPOFF, *active},
            S.PREPARE_DROPOFF: {S.DROPOFF, *active},
            S.DROPOFF: {S.POST_RETURN, *active},
            S.POST_RETURN: {S.COMPLETED, S.ERROR, S.STOPPED},
            S.COMPLETED: {S.IDLE},
            S.STOPPED: {S.IDLE},
            S.ERROR: {S.IDLE},
            S.PAUSED: {S.STARTING, *magazine_states, *paint_states, S.STOPPED, S.ERROR},
            S.IDLE: {S.IDLE},
        }
