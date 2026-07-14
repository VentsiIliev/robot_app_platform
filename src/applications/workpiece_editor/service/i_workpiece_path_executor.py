from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.engine.robot.path_preparation import WorkpieceExecutionPlan


@dataclass(frozen=True)
class WorkpieceProcessAction:
    """One executor-owned process action that the editor can present generically."""
    action_id: str
    label: str
    requires_projected_path_plot: bool = False


class IWorkpiecePathExecutor(ABC):
    """Robot-system-owned execution adapter for prepared workpiece paths."""

    def prepare_workpiece_execution_plan(self, workpiece: dict, skip_debug_plot: bool = False) -> "WorkpieceExecutionPlan":
        """Optionally let the robot-system executor own workpiece-to-execution-plan preparation."""
        raise NotImplementedError

    def prepare_workpiece_preview(self, workpiece: dict, skip_debug_plot: bool = False) -> "WorkpieceExecutionPlan":
        """Backward-compatible alias for editor preview callers."""
        return self.prepare_workpiece_execution_plan(workpiece, skip_debug_plot=skip_debug_plot)

    def get_last_execution_plan(self) -> "WorkpieceExecutionPlan | None":
        """Optionally expose the executor-owned execution plan cache."""
        raise NotImplementedError

    def get_process_actions(self) -> tuple[WorkpieceProcessAction, ...]:
        """Expose executor-owned process actions for the editor UI."""
        return tuple(
            WorkpieceProcessAction(
                action_id=mode,
                label=f"Run {str(mode).replace('_', ' ').title()}",
            )
            for mode in self.get_supported_execution_modes()
        )

    def execute_process_action(
        self,
        execution_plan: "WorkpieceExecutionPlan",
        action_id: str,
    ) -> tuple[bool, str]:
        """Execute one executor-owned process action."""
        return self.execute_process_paths(execution_plan, mode=action_id)

    @abstractmethod
    def get_supported_execution_modes(self) -> tuple[str, ...]:
        ...

    @abstractmethod
    def get_projected_pivot_paths(
        self,
        execution_plan: "WorkpieceExecutionPlan",
    ) -> tuple[list[list[list[float]]], list[float] | None]:
        ...

    def get_pivot_preview_paths(
        self,
        execution_plan: "WorkpieceExecutionPlan",
    ) -> tuple[list[list[list[float]]], list[float] | None]:
        """Backward-compatible alias for editor preview callers."""
        return self.get_projected_pivot_paths(execution_plan)

    @abstractmethod
    def get_pivot_motion_snapshots(
        self,
        execution_plan: "WorkpieceExecutionPlan",
    ) -> tuple[list[list[np.ndarray]], list[float] | None]:
        ...

    def get_pivot_motion_preview(
        self,
        execution_plan: "WorkpieceExecutionPlan",
    ) -> tuple[list[list[np.ndarray]], list[float] | None]:
        """Backward-compatible alias for editor preview callers."""
        return self.get_pivot_motion_snapshots(execution_plan)

    @abstractmethod
    def execute_process_paths(
        self,
        execution_plan: "WorkpieceExecutionPlan",
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        ...

    def execute_preview_paths(
        self,
        execution_plan: "WorkpieceExecutionPlan",
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        """Backward-compatible alias for older executor callers."""
        return self.execute_process_paths(execution_plan, mode=mode)

    def execute_paint_process(
        self,
        execution_plan: "WorkpieceExecutionPlan",
    ) -> tuple[bool, str]:
        """Paint-specific full-process entry point when supported by the robot system."""
        return False, "Paint process is not supported by this executor"
