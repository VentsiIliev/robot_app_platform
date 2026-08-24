from enum import IntFlag
from typing import Mapping


class DryerCommand(IntFlag):
    NEXT_POSITION = 0
    EJECT = 1
    CLOSE_PLATE = 2

    # Compatibility aliases for callers that still expose the former UI names.
    MOVE_SERVOS = EJECT
    OPEN_PLATE = CLOSE_PLATE


DEFAULT_DRYER_COMMANDS: dict[str, int] = {
    "next_position": int(DryerCommand.NEXT_POSITION),
    "eject": int(DryerCommand.EJECT),
    "close_plate": int(DryerCommand.CLOSE_PLATE),
}

def dryer_commands(overrides: Mapping[str, int] | None = None) -> dict[str, int]:
    """Return firmware command defaults with robot-system overrides applied."""
    return {**DEFAULT_DRYER_COMMANDS, **dict(overrides or {})}
