from abc import ABC, abstractmethod

import numpy as np


class IWorkpiecePathExecutor(ABC):
    """Robot-system-owned execution adapter for editor preview paths."""

    @abstractmethod
    def get_supported_execution_modes(self) -> tuple[str, ...]:
        ...

    @abstractmethod
    def supports_pickup_to_pivot(self) -> bool:
        ...

    @abstractmethod
    def get_pivot_preview_paths(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[list[list[list[float]]], list[float] | None]:
        ...

    @abstractmethod
    def get_pivot_motion_preview(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[list[list[np.ndarray]], list[float] | None]:
        ...

    @abstractmethod
    def execute_preview_paths(
        self,
        execution_preview_jobs: list[dict],
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        ...

    @abstractmethod
    def execute_pickup_to_pivot(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[bool, str]:
        ...

    @abstractmethod
    def execute_pickup_and_pivot_paint(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[bool, str]:
        ...
