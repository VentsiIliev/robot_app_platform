from abc import ABC, abstractmethod


class IHeightCorrectionService(ABC):
    @abstractmethod
    def predict_z(self, x: float, y: float) -> float | None:
        """Interpolated surface height in mm at robot position (x, y).
        Returns None when no model is loaded or the point cannot be covered."""

    @abstractmethod
    def reload(self) -> None:
        """Discard cached model — next predict_z call rebuilds from storage."""
