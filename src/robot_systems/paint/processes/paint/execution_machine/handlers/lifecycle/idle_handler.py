from __future__ import annotations

from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState


def handle_idle(ctx: PaintExecutionContext) -> PaintExecutionState:
    return PaintExecutionState.IDLE
