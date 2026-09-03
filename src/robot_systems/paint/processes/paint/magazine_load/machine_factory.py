from __future__ import annotations

from src.engine.process.executable_state_machine import (
    ExecutableStateMachine,
    ExecutableStateMachineBuilder,
    State,
    StateRegistry,
)
from src.robot_systems.paint.processes.paint.magazine_load.context import MagazineLoadContext
from src.robot_systems.paint.processes.paint.magazine_load.handlers import (
    guard_control,
    handle_capture_magazine,
    handle_completed,
    handle_error,
    handle_execute_pickup_and_release,
    handle_idle,
    handle_move_to_calibration,
    handle_move_to_magazine,
    handle_paused,
    handle_resolve_pickup,
    handle_starting,
    handle_stopped,
    handle_wait_camera_settle,
    handle_wait_release_settle,
)
from src.robot_systems.paint.processes.paint.magazine_load.state import (
    MagazineLoadState,
    MagazineLoadTransitions,
)


class MagazineLoadMachineFactory:
    def build(self, context: MagazineLoadContext) -> ExecutableStateMachine:
        S = MagazineLoadState

        def _with_guards(state, handler):
            def _wrapped(ctx):
                guarded = guard_control(ctx, state)
                if guarded is not None:
                    return guarded
                return handler(ctx)

            return _wrapped

        handlers = {
            S.STARTING: handle_starting,
            S.MOVE_TO_MAGAZINE: _with_guards(S.MOVE_TO_MAGAZINE, handle_move_to_magazine),
            S.WAIT_CAMERA_SETTLE: _with_guards(S.WAIT_CAMERA_SETTLE, handle_wait_camera_settle),
            S.CAPTURE_MAGAZINE: _with_guards(S.CAPTURE_MAGAZINE, handle_capture_magazine),
            S.RESOLVE_PICKUP: _with_guards(S.RESOLVE_PICKUP, handle_resolve_pickup),
            S.EXECUTE_PICKUP_AND_RELEASE: _with_guards(
                S.EXECUTE_PICKUP_AND_RELEASE,
                handle_execute_pickup_and_release,
            ),
            S.MOVE_TO_CALIBRATION: _with_guards(S.MOVE_TO_CALIBRATION, handle_move_to_calibration),
            S.WAIT_RELEASE_SETTLE: _with_guards(S.WAIT_RELEASE_SETTLE, handle_wait_release_settle),
            S.PAUSED: handle_paused,
            S.STOPPED: handle_stopped,
            S.COMPLETED: handle_completed,
            S.ERROR: handle_error,
            S.IDLE: handle_idle,
        }

        registry = StateRegistry()
        for state_enum, handler in handlers.items():
            registry.register_state(
                State(
                    state=state_enum,
                    handler=handler,
                    on_enter=_record_current_state,
                )
            )

        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(S.STARTING)
            .with_transition_rules(MagazineLoadTransitions.get_rules())
            .with_state_registry(registry)
            .with_context(context)
            .build()
        )
        context.state_machine = machine
        return machine


def _record_current_state(context: MagazineLoadContext, state: MagazineLoadState) -> None:
    context.current_state = state
