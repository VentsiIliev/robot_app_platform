from typing import Optional, Protocol
from PyQt6.QtWidgets import QWidget


class IAdditionalFormBehavior(Protocol):
    """Protocol for attaching non-destructive behaviors to additional data forms."""

    def apply(self, form: QWidget, editor_frame: QWidget) -> None:
        """
        Attach behavior to a live form instance.

        Args:
            form: Additional data form widget
            editor_frame: MainApplicationFrame instance hosting the form
        """
        ...


class AdditionalFormBehaviorProvider:
    """Singleton registry for optional form behaviors."""

    _instance = None

    def __init__(self):
        self._behaviors: list[IAdditionalFormBehavior] = []

    @classmethod
    def get(cls) -> "AdditionalFormBehaviorProvider":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_behavior(self, behavior: IAdditionalFormBehavior) -> None:
        self._behaviors.append(behavior)

    def set_behaviors(self, behaviors: list[IAdditionalFormBehavior]) -> None:
        self._behaviors = list(behaviors or [])

    def apply_behaviors(self, form: Optional[QWidget], editor_frame: QWidget) -> None:
        if form is None:
            return
        for behavior in self._behaviors:
            behavior.apply(form, editor_frame)

    def has_behaviors(self) -> bool:
        return bool(self._behaviors)

    def reset(self) -> None:
        self._behaviors = []
