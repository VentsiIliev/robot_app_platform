from __future__ import annotations

from enum import Enum, auto


class MagazineLoadState(Enum):
    STARTING = auto()
    MOVE_TO_MAGAZINE = auto()
    WAIT_CAMERA_SETTLE = auto()
    CAPTURE_MAGAZINE = auto()
    RESOLVE_PICKUP = auto()
    EXECUTE_PICKUP_AND_RELEASE = auto()
    MOVE_TO_CALIBRATION = auto()
    WAIT_RELEASE_SETTLE = auto()
    COMPLETED = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()
    IDLE = auto()


class MagazineLoadTransitions:
    @staticmethod
    def get_rules() -> dict[MagazineLoadState, set[MagazineLoadState]]:
        S = MagazineLoadState
        active = {S.PAUSED, S.STOPPED, S.ERROR}
        resumable = {
            S.MOVE_TO_MAGAZINE,
            S.WAIT_CAMERA_SETTLE,
            S.CAPTURE_MAGAZINE,
            S.RESOLVE_PICKUP,
            S.EXECUTE_PICKUP_AND_RELEASE,
            S.MOVE_TO_CALIBRATION,
            S.WAIT_RELEASE_SETTLE,
        }
        return {
            S.STARTING: {*resumable, *active},
            S.MOVE_TO_MAGAZINE: {S.WAIT_CAMERA_SETTLE, *active},
            S.WAIT_CAMERA_SETTLE: {S.CAPTURE_MAGAZINE, *active},
            S.CAPTURE_MAGAZINE: {S.RESOLVE_PICKUP, S.COMPLETED, *active},
            S.RESOLVE_PICKUP: {S.EXECUTE_PICKUP_AND_RELEASE, *active},
            S.EXECUTE_PICKUP_AND_RELEASE: {S.MOVE_TO_CALIBRATION, *active},
            S.MOVE_TO_CALIBRATION: {S.WAIT_RELEASE_SETTLE, *active},
            S.WAIT_RELEASE_SETTLE: {S.COMPLETED, *active},
            S.COMPLETED: {S.IDLE},
            S.STOPPED: {S.IDLE},
            S.ERROR: {S.IDLE},
            S.PAUSED: {S.STARTING, S.STOPPED, S.ERROR},
            S.IDLE: {S.IDLE},
        }
