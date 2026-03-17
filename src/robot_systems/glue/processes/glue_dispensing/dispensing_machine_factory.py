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
from src.robot_systems.glue.processes.glue_dispensing.handler_guards import guard_pause, guard_stop
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.terminal.terminal_handlers import (
    handle_completed,
    handle_error,
    handle_idle,
    handle_paused,
    handle_stopped,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.startup.handle_loading_path import (
    handle_loading_path,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.startup.handle_loading_current_path import (
    handle_loading_current_path,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.startup.handle_issuing_move_to_first_point import (
    handle_issuing_move_to_first_point,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.startup.handle_resuming import (
    handle_resuming,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.startup.handle_starting import handle_starting
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.motion.handle_moving_to_first_point import (
    handle_moving_to_first_point,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.hardware.generator_handlers import (
    handle_turning_off_generator,
    handle_turning_on_generator,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.hardware.pump_handlers import (
    handle_turning_off_pump,
    handle_turning_on_pump,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.hardware.handle_starting_pump_adjustment_thread import (
    handle_starting_pump_adjustment_thread,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.hardware.handle_waiting_for_pump_thread_ready import (
    handle_waiting_for_pump_thread_ready,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.motion.handle_sending_path_points import (
    handle_sending_path_points,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.waiting.handle_routing_path_completion_wait import (
    handle_routing_path_completion_wait,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.waiting.handle_waiting_for_pump_thread import (
    handle_waiting_for_pump_thread,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.waiting.handle_waiting_for_final_position import (
    handle_waiting_for_final_position,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.motion.handle_advancing_path import (
    handle_advancing_path,
)

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

        def _with_default_guards(state, handler):
            def _wrapped(ctx):
                next_state = guard_stop(ctx)
                if next_state is not None:
                    return next_state

                next_state = guard_pause(ctx, state)
                if next_state is not None:
                    return next_state

                return handler(ctx)

            return _wrapped

        def _pump_adj_handler(ctx):
            return handle_starting_pump_adjustment_thread(ctx, adjust)

        def _pump_off_handler(ctx):
            return handle_turning_off_pump(ctx, turn_off_between)

        handlers = {
            S.IDLE:                            handle_idle,
            S.STARTING:                        _with_default_guards(S.STARTING, handle_starting),
            S.LOADING_PATH:                    _with_default_guards(S.LOADING_PATH, handle_loading_path),
            S.LOADING_CURRENT_PATH:            _with_default_guards(S.LOADING_CURRENT_PATH, handle_loading_current_path),
            S.ISSUING_MOVE_TO_FIRST_POINT:     _with_default_guards(S.ISSUING_MOVE_TO_FIRST_POINT, handle_issuing_move_to_first_point),
            S.MOVING_TO_FIRST_POINT:           handle_moving_to_first_point,
            S.TURNING_ON_GENERATOR:            _with_default_guards(S.TURNING_ON_GENERATOR, handle_turning_on_generator),
            S.TURNING_ON_PUMP:                 _with_default_guards(S.TURNING_ON_PUMP, handle_turning_on_pump),
            S.STARTING_PUMP_ADJUSTMENT_THREAD: _with_default_guards(S.STARTING_PUMP_ADJUSTMENT_THREAD, _pump_adj_handler),
            S.WAITING_FOR_PUMP_THREAD_READY:   _with_default_guards(S.WAITING_FOR_PUMP_THREAD_READY, handle_waiting_for_pump_thread_ready),
            S.SENDING_PATH_POINTS:             handle_sending_path_points,
            S.ROUTING_PATH_COMPLETION_WAIT:    _with_default_guards(S.ROUTING_PATH_COMPLETION_WAIT, handle_routing_path_completion_wait),
            S.WAITING_FOR_PUMP_THREAD:         handle_waiting_for_pump_thread,
            S.WAITING_FOR_FINAL_POSITION:      handle_waiting_for_final_position,
            S.TURNING_OFF_PUMP:                _with_default_guards(S.TURNING_OFF_PUMP, _pump_off_handler),
            S.ADVANCING_PATH:                  _with_default_guards(S.ADVANCING_PATH, handle_advancing_path),
            S.TURNING_OFF_GENERATOR:           handle_turning_off_generator,
            S.RESUMING:                        _with_default_guards(S.RESUMING, handle_resuming),
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
