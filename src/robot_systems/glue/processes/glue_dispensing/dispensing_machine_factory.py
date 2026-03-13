from __future__ import annotations
import logging
from src.engine.process.executable_state_machine import (
    ExecutableStateMachine,
    ExecutableStateMachineBuilder,
    StateRegistry,
    State,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_config import GlueDispensingConfig
from src.robot_systems.glue.processes.glue_dispensing.dispensing_context import DispensingContext
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import (
    GlueDispensingState,
    GlueDispensingTransitions,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_idle import handle_idle
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_starting import handle_starting
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_moving_to_first_point import (
    handle_moving_to_first_point,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_executing_path import handle_executing_path
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_pump_initial_boost import (
    handle_pump_initial_boost,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_starting_pump_adjustment_thread import (
    handle_starting_pump_adjustment_thread,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_sending_path_points import (
    handle_sending_path_points,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_wait_for_path_completion import (
    handle_wait_for_path_completion,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_transition_between_paths import (
    handle_transition_between_paths,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_paused import handle_paused
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_stopped import handle_stopped
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_completed import handle_completed
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.handle_error import handle_error

_logger = logging.getLogger(__name__)


class DispensingMachineFactory:
    def build(
        self,
        context: DispensingContext,
        config: GlueDispensingConfig,
    ) -> ExecutableStateMachine:
        S = GlueDispensingState

        adjust = config.adjust_pump_speed_while_spray
        turn_off_between = config.turn_off_pump_between_paths

        def _pump_adj_handler(ctx):
            return handle_starting_pump_adjustment_thread(ctx, adjust)

        def _transition_handler(ctx):
            return handle_transition_between_paths(ctx, turn_off_between)

        handlers = {
            S.IDLE:                            handle_idle,
            S.STARTING:                        handle_starting,
            S.MOVING_TO_FIRST_POINT:           handle_moving_to_first_point,
            S.EXECUTING_PATH:                  handle_executing_path,
            S.PUMP_INITIAL_BOOST:              handle_pump_initial_boost,
            S.STARTING_PUMP_ADJUSTMENT_THREAD: _pump_adj_handler,
            S.SENDING_PATH_POINTS:             handle_sending_path_points,
            S.WAIT_FOR_PATH_COMPLETION:        handle_wait_for_path_completion,
            S.TRANSITION_BETWEEN_PATHS:        _transition_handler,
            S.PAUSED:                          handle_paused,
            S.STOPPED:                         handle_stopped,
            S.COMPLETED:                       handle_completed,
            S.ERROR:                           handle_error,
        }

        registry = StateRegistry()
        for state_enum, handler in handlers.items():
            registry.register_state(State(state=state_enum, handler=handler))

        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.STARTING)
            .with_transition_rules(GlueDispensingTransitions.get_rules())
            .with_state_registry(registry)
            .with_context(context)
            .build()
        )

        context.state_machine = machine
        _logger.debug("DispensingMachine built (adjust=%s, turn_off_between=%s)", adjust, turn_off_between)
        return machine

