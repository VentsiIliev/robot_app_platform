from enum import IntFlag
from typing import Mapping


class DryerStatus(IntFlag):
    READY = 0x01
    EJECT = 0x08
    EJECT_DONE = 0x10
    NEXT_POS_MOVING = 0x20
    NEXT_POS_DONE = 0x40


DEFAULT_DRYER_STATUSES: dict[str, int] = {
    "ready": int(DryerStatus.READY),
    "eject": int(DryerStatus.EJECT),
    "eject_done": int(DryerStatus.EJECT_DONE),
    "next_pos_moving": int(DryerStatus.NEXT_POS_MOVING),
    "next_pos_done": int(DryerStatus.NEXT_POS_DONE),
}


def dryer_statuses(overrides: Mapping[str, int] | None = None) -> dict[str, int]:
    """Return firmware status defaults with robot-system overrides applied."""
    return {**DEFAULT_DRYER_STATUSES, **dict(overrides or {})}
