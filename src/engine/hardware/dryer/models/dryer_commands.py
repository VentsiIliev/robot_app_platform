from enum import IntFlag


class DryerStatus(IntFlag):
    READY = 0x01
    SERVOS_MOVING = 0x02
    PLATE_ON_POSITION = 0x04


class DryerCommand(IntFlag):
    MOVE_SERVOS = 0x01
    OPEN_PLATE = 2
    CLOSE_PLATE= 0
    NEXT_POSITION = 0x04
