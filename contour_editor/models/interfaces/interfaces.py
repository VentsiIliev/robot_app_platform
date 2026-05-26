from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Protocol, Callable, Tuple
import numpy as np
from PyQt6.QtCore import QPointF


class ISegment(ABC):
    @abstractmethod
    def add_point(self, point: QPointF) -> None:
        pass

    @abstractmethod
    def remove_point(self, index: int) -> None:
        pass

    @abstractmethod
    def add_control_point(self, index: int, point: QPointF) -> None:
        pass

    @abstractmethod
    def set_layer(self, layer: 'ILayer') -> None:
        pass

    @abstractmethod
    def set_settings(self, settings: Dict[str, Any]) -> None:
        pass

    @property
    @abstractmethod
    def points(self) -> List[QPointF]:
        pass

    @property
    @abstractmethod
    def controls(self) -> List[Optional[QPointF]]:
        pass

    @property
    @abstractmethod
    def visible(self) -> bool:
        pass

    @property
    @abstractmethod
    def layer(self) -> Optional['ILayer']:
        pass

    @property
    @abstractmethod
    def settings(self) -> Dict[str, Any]:
        pass


class ILayer(ABC):
    @abstractmethod
    def add_segment(self, segment: ISegment) -> None:
        pass

    @abstractmethod
    def remove_segment(self, index: int) -> None:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def locked(self) -> bool:
        pass

    @locked.setter
    @abstractmethod
    def locked(self, value: bool) -> None:
        pass

    @property
    @abstractmethod
    def visible(self) -> bool:
        pass

    @visible.setter
    @abstractmethod
    def visible(self, value: bool) -> None:
        pass

    @property
    @abstractmethod
    def segments(self) -> List[ISegment]:
        pass


class ISegmentManager(ABC):
    @abstractmethod
    def create_segment(self, points: List[QPointF], layer_name: str = "Contour") -> ISegment:
        pass

    @abstractmethod
    def get_segments(self) -> List[ISegment]:
        pass

    @abstractmethod
    def get_layer(self, name: str) -> Optional[ILayer]:
        pass

    @abstractmethod
    def undo(self) -> None:
        pass

    @abstractmethod
    def redo(self) -> None:
        pass

    @property
    @abstractmethod
    def segments(self) -> List[ISegment]:
        pass


class ISettingsProvider(ABC):
    @abstractmethod
    def get_all_setting_keys(self) -> List[str]:
        pass

    @abstractmethod
    def get_default_values(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_material_type_key(self) -> str:
        pass

    @abstractmethod
    def get_available_material_types(self) -> List[str]:
        pass

    @abstractmethod
    def get_default_material_type(self) -> str:
        pass

    @abstractmethod
    def get_setting_label(self, key: str) -> str:
        pass

    @abstractmethod
    def get_settings_tabs_config(self) -> List[tuple[str, List[str]]]:
        pass

    def validate_setting_value(self, key: str, value: Any) -> tuple[bool, Optional[str]]:
        return (True, None)


class AdditionalDataFormBase(ABC):
    """
    Abstract Base Class for forms that collect additional data when saving.

    This enforces implementation of required methods at runtime.
    Forms MUST inherit from this class to be used with the contour editor.

    Required Methods (must implement):
        - get_data() -> dict: Return form data as dictionary
        - onSubmit() -> bool: Handle form submission, return success
        - validate() -> tuple[bool, str]: Validate form data
        - clear(): Clear all form fields

    Optional Methods (can override):
        - prefill_form(data): Prefill form with existing data

    Optional Attributes:
        - onSubmitCallBack: Callable that receives form data

    Example:
        class MyForm(AdditionalDataFormBase, QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)

            def get_data(self) -> Dict[str, Any]:
                return {"name": self.name_input.text()}

            def validate(self) -> Tuple[bool, str]:
                if not self.get_data()["name"]:
                    return False, "Name required"
                return True, ""

            def onSubmit(self) -> bool:
                is_valid, error = self.validate()
                if not is_valid:
                    return False
                if hasattr(self, 'onSubmitCallBack'):
                    return self.onSubmitCallBack(self.get_data())[0]
                return True

            def clear(self) -> None:
                self.name_input.clear()
    """

    @abstractmethod
    def get_data(self) -> Dict[str, Any]:
        """
        Get current form data as a dictionary.

        Returns:
            dict: Form data with field names as keys

        Example:
            {"name": "Part123", "thickness": "10.5"}
        """
        pass

    @abstractmethod
    def onSubmit(self) -> bool:
        """
        Handle form submission.

        Should:
        1. Validate the form data
        2. Call onSubmitCallBack if it exists
        3. Return success status

        Returns:
            bool: True if submission succeeded, False otherwise
        """
        pass

    @abstractmethod
    def validate(self) -> Tuple[bool, str]:
        """
        Validate form data.

        Returns:
            tuple: (is_valid: bool, error_message: str)

        Example:
            (True, "") if valid
            (False, "Name is required") if invalid
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all form fields."""
        pass

    def prefill_form(self, data: Any) -> None:
        """
        Prefill form with existing data (optional - can override).

        Args:
            data: Existing data (dict or object) to load into form
        """
        pass  # Default implementation does nothing


class IAdditionalDataForm(Protocol):
    """
    Protocol (duck-typing interface) for additional data forms.

    Use this for type hints when you DON'T want to enforce inheritance.
    Use AdditionalDataFormBase when you DO want to enforce inheritance.

    This protocol matches AdditionalDataFormBase's interface.
    """

    def get_data(self) -> Dict[str, Any]: ...
    def onSubmit(self) -> bool: ...
    def validate(self) -> Tuple[bool, str]: ...
    def clear(self) -> None: ...
    def prefill_form(self, data: Any) -> None: ...
    onSubmitCallBack: Optional[Callable[[Dict[str, Any]], Tuple[bool, str]]]


# WorkpieceBase has been moved to workpiece_editor package
# Import it from: from workpiece_editor.models import BaseWorkpiece
#
# Domain-specific base interfaces and doesn't belong in the
# domain-agnostic contour_editor package. Use BaseWorkpiece from workpiece_editor instead.
