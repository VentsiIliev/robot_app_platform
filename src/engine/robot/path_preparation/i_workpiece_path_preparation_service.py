from __future__ import annotations

from abc import ABC, abstractmethod


class IWorkpiecePathPreparationService(ABC):
    @abstractmethod
    def build_execution_plan(self, workpiece: dict):
        ...

