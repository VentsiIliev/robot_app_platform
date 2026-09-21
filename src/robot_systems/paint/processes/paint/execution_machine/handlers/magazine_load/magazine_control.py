from __future__ import annotations

from src.robot_systems.paint.processes.paint.execution_machine.context import (
    PaintExecutionContext,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.guards import (
    guard_control,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import (
    PaintExecutionState,
)


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
