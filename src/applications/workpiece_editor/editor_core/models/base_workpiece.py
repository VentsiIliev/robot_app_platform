from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseWorkpiece(ABC):
    """
    Abstract base class for workpiece objects.
    Application-agnostic interface for contour editor.
    """

    def __init__(self, workpiece_id: str, name: str = ""):
        self.workpieceId = workpiece_id
        self.name = name

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert workpiece to dictionary representation"""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseWorkpiece':
        """Create workpiece from dictionary data"""
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(ID: {self.workpieceId}, Name: {self.name})"


class GenericWorkpiece(BaseWorkpiece):
    """
    Generic workpiece implementation for contour editor.
    Can be extended by application-specific workpiece classes.
    """

    def __init__(self, workpiece_id: str, name: str = "", **kwargs):
        super().__init__(workpiece_id, name)
        # Store any additional fields as attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {key: value for key, value in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenericWorkpiece':
        """Create from dictionary"""
        workpiece_id = data.get('workpieceId', '')
        name = data.get('name', '')
        # Pass remaining fields as kwargs
        kwargs = {k: v for k, v in data.items() if k not in ['workpieceId', 'name']}
        return cls(workpiece_id, name, **kwargs)


class WorkpieceFactory:
    """
    Factory for creating application-specific workpiece instances.
    Allows contour editor to remain decoupled from specific implementations.
    """

    _workpiece_class = GenericWorkpiece

    @classmethod
    def set_workpiece_class(cls, workpiece_class: type):
        """
        Set the workpiece class to use for creating instances.

        Args:
            workpiece_class: Class that implements BaseWorkpiece interface
        """
        if not issubclass(workpiece_class, BaseWorkpiece):
            raise ValueError(f"{workpiece_class} must inherit from BaseWorkpiece")
        cls._workpiece_class = workpiece_class

    @classmethod
    def create_workpiece(cls, data: Dict[str, Any]) -> BaseWorkpiece:
        """
        Create a workpiece instance from data dictionary.

        Args:
            data: Dictionary with workpiece data

        Returns:
            Instance of configured workpiece class
        """
        return cls._workpiece_class.from_dict(data)

    @classmethod
    def get_workpiece_class(cls) -> type:
        """Get the currently configured workpiece class"""
        return cls._workpiece_class

