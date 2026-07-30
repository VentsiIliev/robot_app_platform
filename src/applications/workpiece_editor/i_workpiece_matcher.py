from abc import ABC, abstractmethod


class IWorkpieceMatcher(ABC):
    """Matching capability consumed by the reusable workpiece editor."""

    @abstractmethod
    def can_match_saved_workpieces(self) -> bool:
        ...

    @abstractmethod
    def match_saved_workpieces(
        self,
        contour,
    ) -> tuple[bool, dict | None, str]:
        ...
