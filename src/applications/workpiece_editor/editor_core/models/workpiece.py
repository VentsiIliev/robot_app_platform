from __future__ import annotations
from typing import Optional, Dict, Any
from .base_workpiece import BaseWorkpiece


class GenericWorkpiece(BaseWorkpiece):
    def __init__(self, workpiece_id: str, name: str = "", **kwargs):
        super().__init__(workpiece_id, name)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        return {key: value for key, value in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenericWorkpiece':
        workpiece_id = data.get('workpieceId', '')
        name = data.get('name', '')
        kwargs = {k: v for k, v in data.items() if k not in ['workpieceId', 'name']}
        return cls(workpiece_id, name, **kwargs)


class WorkpieceFactory:
    _workpiece_class = GenericWorkpiece

    @classmethod
    def set_workpiece_class(cls, workpiece_class: type):
        if not issubclass(workpiece_class, BaseWorkpiece):
            raise ValueError(f"{workpiece_class} must inherit from BaseWorkpiece")
        cls._workpiece_class = workpiece_class

    @classmethod
    def create_workpiece(cls, data: Dict[str, Any]) -> BaseWorkpiece:
        return cls._workpiece_class.from_dict(data)

    @classmethod
    def get_workpiece_class(cls) -> type:
        return cls._workpiece_class
