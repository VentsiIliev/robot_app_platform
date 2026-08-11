from __future__ import annotations

from time import perf_counter
from typing import Callable

from src.engine.process.executable_state_machine import (
    ExecutableStateMachine,
    ExecutableStateMachineBuilder,
    State,
    StateRegistry,
)
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.calibration_wait_camera_settle_handler import (
    handle_calibration_wait_camera_settle,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.capture_handler import (
    handle_capture_workpiece,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.completed_handler import (
    handle_completed,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handler import (
    handle_dropoff,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.edge_cleanup_handler import (
    handle_edge_cleanup,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.error_handler import (
    handle_error,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.execution_handler import (
    handle_execute_paint,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.idle_handler import (
    handle_idle,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_capture_handler import (
    handle_magazine_capture,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_execute_pickup_release_handler import (
    handle_magazine_execute_pickup_release,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_load_compat_handler import (
    handle_magazine_load,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_move_to_calibration_handler import (
    handle_magazine_move_to_calibration,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_move_to_magazine_handler import (
    handle_magazine_move_to_magazine,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_prepare_pickup_release_handler import (
    handle_magazine_prepare_pickup_release,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_wait_camera_settle_handler import (
    handle_magazine_wait_camera_settle,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.paint_contact_handler import (
    handle_paint_contact,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.pickup_handler import (
    handle_pickup,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.pause_handler import (
    handle_paused,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.plan_handler import (
    handle_build_execution_plan,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.preparation_handler import (
    handle_prepare_workpiece,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.prepare_dropoff_handler import (
    handle_prepare_dropoff,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.post_return_handler import (
    handle_post_return,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.startup_handler import (
    handle_starting,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.lifecycle.stopped_handler import (
    handle_stopped,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import (
    PaintExecutionState,
    PaintExecutionTransitions,
)
from src.robot_systems.paint.timing import TimingRecorder


class PaintExecutionMachineFactory:
    """Build the internal state machine for one paint production cycle."""

    def build(
        self,
        context: PaintExecutionContext,
        *,
        initial_state: PaintExecutionState = PaintExecutionState.STARTING,
    ) -> ExecutableStateMachine:
        S = PaintExecutionState

        registry = StateRegistry()
        if _state_timing_enabled(context):
            context.state_timing_recorder = TimingRecorder(f"paint_execution_cycle_{context.cycle_index}")

        _register(registry, context, S.STARTING, handle_starting)
        _register(registry, context, S.MAGAZINE_LOAD, handle_magazine_load)
        _register(registry, context, S.MAGAZINE_MOVE_TO_MAGAZINE, handle_magazine_move_to_magazine)
        _register(registry, context, S.MAGAZINE_WAIT_CAMERA_SETTLE, handle_magazine_wait_camera_settle)
        _register(registry, context, S.MAGAZINE_CAPTURE, handle_magazine_capture)
        _register(registry, context, S.MAGAZINE_PREPARE_PICKUP_RELEASE, handle_magazine_prepare_pickup_release)
        _register(registry, context, S.MAGAZINE_EXECUTE_PICKUP_RELEASE, handle_magazine_execute_pickup_release)
        _register(registry, context, S.MAGAZINE_MOVE_TO_CALIBRATION, handle_magazine_move_to_calibration)
        _register(registry, context, S.CALIBRATION_WAIT_CAMERA_SETTLE, handle_calibration_wait_camera_settle)
        _register(registry, context, S.CAPTURE_WORKPIECE, handle_capture_workpiece)
        _register(registry, context, S.PREPARE_WORKPIECE, handle_prepare_workpiece)
        _register(registry, context, S.BUILD_EXECUTION_PLAN, handle_build_execution_plan)
        _register(registry, context, S.EXECUTE_PAINT, handle_execute_paint)
        _register(registry, context, S.PICKUP, handle_pickup)
        _register(registry, context, S.PAINT_CONTACT, handle_paint_contact)
        _register(registry, context, S.EDGE_CLEANUP, handle_edge_cleanup)
        _register(registry, context, S.PREPARE_DROPOFF, handle_prepare_dropoff)
        _register(registry, context, S.DROPOFF, handle_dropoff)
        _register(registry, context, S.POST_RETURN, handle_post_return)
        _register(registry, context, S.COMPLETED, handle_completed)
        _register(registry, context, S.PAUSED, handle_paused)
        _register(registry, context, S.STOPPED, handle_stopped)
        _register(registry, context, S.ERROR, handle_error)
        _register(registry, context, S.IDLE, handle_idle)

        machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(initial_state)
            .with_transition_rules(PaintExecutionTransitions.get_rules())
            .with_state_registry(registry)
            .with_context(context)
            .build()
        )
        context.state_machine = machine
        return machine


def _record_current_state(context: PaintExecutionContext, state: PaintExecutionState) -> None:
    context.current_state = state


def _register(
    registry: StateRegistry,
    context: PaintExecutionContext,
    state: PaintExecutionState,
    handler: Callable[[PaintExecutionContext], PaintExecutionState],
) -> None:
    registry.register_state(
        State(
            state=state,
            handler=_timed_handler(context, state, handler),
            on_enter=_record_current_state,
        )
    )


def _timed_handler(
    context: PaintExecutionContext,
    state: PaintExecutionState,
    handler: Callable[[PaintExecutionContext], PaintExecutionState],
) -> Callable[[PaintExecutionContext], PaintExecutionState]:
    if context.state_timing_recorder is None:
        return handler

    def wrapped(ctx: PaintExecutionContext) -> PaintExecutionState:
        started = perf_counter()
        try:
            next_state = handler(ctx)
        except Exception as exc:
            ended = perf_counter()
            _record_state_timing(
                ctx,
                state=state,
                next_state=None,
                success=False,
                exception=True,
                started=started,
                ended=ended,
                message=str(exc),
            )
            raise

        ended = perf_counter()
        _record_state_timing(
            ctx,
            state=state,
            next_state=next_state,
            success=_state_success(ctx, next_state),
            exception=False,
            started=started,
            ended=ended,
            message=_state_message(ctx, next_state),
        )
        return next_state

    return wrapped


def _record_state_timing(
    context: PaintExecutionContext,
    *,
    state: PaintExecutionState,
    next_state: PaintExecutionState | None,
    success: bool,
    exception: bool,
    started: float,
    ended: float,
    message: str,
) -> None:
    recorder = context.state_timing_recorder
    if recorder is None:
        return
    recorder.record_state(
        state=state,
        next_state=next_state,
        success=success,
        exception=exception,
        elapsed_s=ended - started,
        started_at=started,
        ended_at=ended,
        message=message,
    )


def _state_success(context: PaintExecutionContext, next_state: PaintExecutionState) -> bool:
    if next_state in {PaintExecutionState.ERROR, PaintExecutionState.STOPPED}:
        return False
    if next_state == PaintExecutionState.IDLE and not context.result_ok:
        return False
    return True


def _state_message(context: PaintExecutionContext, next_state: PaintExecutionState) -> str:
    if next_state in {
        PaintExecutionState.ERROR,
        PaintExecutionState.STOPPED,
        PaintExecutionState.COMPLETED,
        PaintExecutionState.IDLE,
    }:
        return context.result_message
    return ""


def _state_timing_enabled(context: PaintExecutionContext) -> bool:
    config = context.process_config
    if config is None:
        return True
    return bool(getattr(config, "enable_execution_state_timing", True))
