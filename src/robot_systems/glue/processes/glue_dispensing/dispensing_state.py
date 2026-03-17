from enum import Enum, auto
from typing import Dict, Set


class GlueDispensingState(Enum):
    IDLE                            = auto()
    STARTING                        = auto()
    LOADING_PATH                    = auto()
    LOADING_CURRENT_PATH            = auto()
    ISSUING_MOVE_TO_FIRST_POINT     = auto()
    MOVING_TO_FIRST_POINT           = auto()
    TURNING_ON_GENERATOR            = auto()
    TURNING_ON_PUMP                 = auto()
    STARTING_PUMP_ADJUSTMENT_THREAD = auto()
    WAITING_FOR_PUMP_THREAD_READY   = auto()
    SENDING_PATH_POINTS             = auto()
    ROUTING_PATH_COMPLETION_WAIT    = auto()
    WAITING_FOR_PUMP_THREAD         = auto()
    WAITING_FOR_FINAL_POSITION      = auto()
    TURNING_OFF_PUMP                = auto()
    ADVANCING_PATH                  = auto()
    TURNING_OFF_GENERATOR           = auto()
    RESUMING                        = auto()
    PAUSED                          = auto()
    STOPPED                         = auto()
    COMPLETED                       = auto()
    ERROR                           = auto()


class GlueDispensingTransitions:
    @staticmethod
    def get_rules() -> Dict[GlueDispensingState, Set[GlueDispensingState]]:
        S = GlueDispensingState
        return {
            S.IDLE: {S.IDLE, S.STARTING, S.ERROR},
            S.STARTING: {
                S.LOADING_PATH, S.RESUMING, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.LOADING_PATH: {
                S.LOADING_PATH, S.LOADING_CURRENT_PATH,
                S.COMPLETED, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.LOADING_CURRENT_PATH: {
                S.ISSUING_MOVE_TO_FIRST_POINT, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.ISSUING_MOVE_TO_FIRST_POINT: {
                S.MOVING_TO_FIRST_POINT, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.MOVING_TO_FIRST_POINT: {
                S.TURNING_ON_GENERATOR, S.PAUSED, S.STOPPED, S.COMPLETED, S.ERROR,
            },
            S.TURNING_ON_GENERATOR: {
                S.TURNING_ON_PUMP, S.PAUSED, S.STOPPED, S.COMPLETED, S.ERROR,
            },
            S.TURNING_ON_PUMP: {
                S.STARTING_PUMP_ADJUSTMENT_THREAD, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.STARTING_PUMP_ADJUSTMENT_THREAD: {
                S.WAITING_FOR_PUMP_THREAD_READY, S.SENDING_PATH_POINTS, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.WAITING_FOR_PUMP_THREAD_READY: {
                S.SENDING_PATH_POINTS, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.SENDING_PATH_POINTS: {
                S.ROUTING_PATH_COMPLETION_WAIT, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.ROUTING_PATH_COMPLETION_WAIT: {
                S.WAITING_FOR_PUMP_THREAD, S.WAITING_FOR_FINAL_POSITION,
                S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.WAITING_FOR_PUMP_THREAD: {
                S.TURNING_OFF_PUMP, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.WAITING_FOR_FINAL_POSITION: {
                S.TURNING_OFF_PUMP, S.COMPLETED, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.TURNING_OFF_PUMP: {
                S.ADVANCING_PATH, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.ADVANCING_PATH: {
                S.STARTING, S.COMPLETED, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.TURNING_OFF_GENERATOR: {
                S.IDLE, S.ERROR,
            },
            S.RESUMING: {
                S.ISSUING_MOVE_TO_FIRST_POINT, S.MOVING_TO_FIRST_POINT,
                S.TURNING_ON_GENERATOR, S.TURNING_OFF_PUMP, S.STARTING,
                S.COMPLETED, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.PAUSED:    {S.PAUSED, S.STARTING, S.STOPPED, S.COMPLETED, S.IDLE, S.ERROR},
            S.STOPPED:   {S.COMPLETED, S.IDLE, S.ERROR},
            S.COMPLETED: {S.TURNING_OFF_GENERATOR, S.ERROR},
            S.ERROR:     {S.ERROR, S.IDLE},
        }
