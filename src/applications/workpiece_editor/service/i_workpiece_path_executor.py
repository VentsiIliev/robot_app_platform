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
    """Robot-system-owned execution adapter for editor preview paths."""

    def prepare_workpiece_preview(self, workpiece: dict) -> "WorkpieceExecutionPlan":
        """Optionally let the robot-system executor own workpiece-to-preview-plan preparation."""
        raise NotImplementedError

    def get_last_execution_plan(self) -> "WorkpieceExecutionPlan | None":
        """Optionally expose the executor-owned preview plan cache."""
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
        return self.execute_preview_paths(execution_plan, mode=action_id)

    @abstractmethod
    def get_supported_execution_modes(self) -> tuple[str, ...]:
        ...

    @abstractmethod
    def supports_pickup_to_pivot(self) -> bool:
        ...

    @abstractmethod
    def get_pivot_preview_paths(
        self,
        execution_plan: "WorkpieceExecutionPlan",
    ) -> tuple[list[list[list[float]]], list[float] | None]:
        ...

    @abstractmethod
    def get_pivot_motion_preview(
        self,
        execution_plan: "WorkpieceExecutionPlan",
    ) -> tuple[list[list[np.ndarray]], list[float] | None]:
        ...

    @abstractmethod
    def execute_preview_paths(
        self,
        execution_plan: "WorkpieceExecutionPlan",
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        ...

    @abstractmethod
    def execute_pickup_to_pivot(
        self,
        execution_plan: "WorkpieceExecutionPlan",
    ) -> tuple[bool, str]:
        ...

    @abstractmethod
    def execute_pickup_and_paint(
        self,
        execution_plan: "WorkpieceExecutionPlan",
    ) -> tuple[bool, str]:
        ...
