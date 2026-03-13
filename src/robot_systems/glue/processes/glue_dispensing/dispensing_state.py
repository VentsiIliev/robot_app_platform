from enum import Enum, auto
from typing import Dict, Set


class GlueDispensingState(Enum):
    IDLE                            = auto()
    STARTING                        = auto()
    MOVING_TO_FIRST_POINT           = auto()
    EXECUTING_PATH                  = auto()
    PUMP_INITIAL_BOOST              = auto()
    STARTING_PUMP_ADJUSTMENT_THREAD = auto()
    SENDING_PATH_POINTS             = auto()
    WAIT_FOR_PATH_COMPLETION        = auto()
    TRANSITION_BETWEEN_PATHS        = auto()
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
                S.STARTING, S.MOVING_TO_FIRST_POINT, S.EXECUTING_PATH,
                S.COMPLETED, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.MOVING_TO_FIRST_POINT: {
                S.EXECUTING_PATH, S.PAUSED, S.STOPPED, S.COMPLETED, S.ERROR,
            },
            S.EXECUTING_PATH: {
                S.PUMP_INITIAL_BOOST, S.PAUSED, S.STOPPED, S.COMPLETED, S.ERROR,
            },
            S.PUMP_INITIAL_BOOST: {
                S.STARTING_PUMP_ADJUSTMENT_THREAD, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.STARTING_PUMP_ADJUSTMENT_THREAD: {
                S.SENDING_PATH_POINTS, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.SENDING_PATH_POINTS: {
                S.WAIT_FOR_PATH_COMPLETION, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.WAIT_FOR_PATH_COMPLETION: {
                S.TRANSITION_BETWEEN_PATHS, S.COMPLETED, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.TRANSITION_BETWEEN_PATHS: {
                S.STARTING, S.COMPLETED, S.PAUSED, S.STOPPED, S.ERROR,
            },
            S.PAUSED:    {S.PAUSED, S.STARTING, S.STOPPED, S.COMPLETED, S.IDLE, S.ERROR},
            S.STOPPED:   {S.COMPLETED, S.IDLE, S.ERROR},
            S.COMPLETED: {S.IDLE, S.ERROR},
            S.ERROR:     {S.ERROR, S.IDLE},
        }

