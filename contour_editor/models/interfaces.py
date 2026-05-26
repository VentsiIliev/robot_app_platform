from abc import ABC, abstractmethod
from typing import Protocol, Optional, Tuple, Dict, Any, Callable


class IAdditionalDataForm(ABC):
    """
    ABC for forms that collect additional data when saving.

    The contour editor can optionally show a form to collect additional
    metadata before saving. This ABC defines the required interface.

    Required Methods:
        - get_data() -> dict: Return form data as dictionary
        - onSubmit() -> bool: Handle form submission, return success
        - validate() -> tuple[bool, str]: Validate form data
        - clear(): Clear all form fields

    Optional Methods:
        - prefill_form(data): Prefill form with existing data

    Optional Attributes:
        - onSubmitCallBack: Callable that receives form data
    """

    @abstractmethod
    def get_data(self) -> Dict[str, Any]:
        """
        Get current form data as a dictionary.

        Returns:
            dict: Form data with field names as keys

        Example:
            {"name": "Part123", "thickness": "10.5", "material": "Steel"}
        """
        ...

    @abstractmethod
    def onSubmit(self) -> bool:
        """
        Handle form submission.

        This should:
        1. Validate the form data
        2. Call onSubmitCallBack if it exists
        3. Return success status

        Returns:
            bool: True if submission succeeded, False otherwise
        """
        ...

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
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear all form fields."""
        ...

    # Optional methods
    @abstractmethod
    def prefill_form(self, data: Any) -> None:
        """
        Prefill form with existing data (optional).

        Args:
            data: Existing data (dict or object) to load into form
        """
        ...

    # Optional attributes
    onSubmitCallBack: Optional[Callable[[Dict[str, Any]], Tuple[bool, str]]]



