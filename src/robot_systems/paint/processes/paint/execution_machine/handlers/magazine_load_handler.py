from __future__ import annotations

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.guards import guard_control
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.magazine_load_service import PaintMagazineLoadService


def interrupted_or_error(
    ctx: PaintExecutionContext,
    state: PaintExecutionState,
    message: str,
) -> PaintExecutionState:
    interrupted = guard_control(ctx, state)
    if interrupted is not None:
        return interrupted
    ctx.set_result(False, message)
    return PaintExecutionState.ERROR


def supports_fine_magazine_states(load_service: object) -> bool:
    return isinstance(load_service, PaintMagazineLoadService)
